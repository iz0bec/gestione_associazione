# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Scaricamento dei messaggi dalle caselle IMAP (email e PEC) per la
# *              protocollazione. Nulla viene cancellato né segnato come letto: i
# *              messaggi scaricati si spostano nella cartella «processata» della
# *              casella (creata se manca). Le ricevute PEC dei protocolli spediti
# *              si agganciano da sole alla spedizione.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import contextlib
import email
import hashlib
import imaplib
import logging
import re
import ssl
from datetime import timedelta
from email import policy
from email.utils import getaddresses, parseaddr, parsedate_to_datetime

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.html import strip_tags

from . import spedizioni
from .models import CasellaPosta, MessaggioRicevuto
from .servizi import nome_file_sicuro

log = logging.getLogger(__name__)

DIMENSIONE_MASSIMA = 50 * 1024 * 1024  # messaggi più grandi non vengono scaricati
TIMEOUT = 30
LOTTO_SPOSTAMENTO = 200  # UID per comando di spostamento


class ErroreCasella(Exception):
    pass


def _connetti(casella):
    try:
        if casella.ssl:
            conn = imaplib.IMAP4_SSL(
                casella.server,
                casella.porta,
                ssl_context=ssl.create_default_context(),
                timeout=TIMEOUT,
            )
        else:
            conn = imaplib.IMAP4(casella.server, casella.porta, timeout=TIMEOUT)
            conn.starttls(ssl_context=ssl.create_default_context())
        conn.login(casella.utente, casella.password())
    except (OSError, imaplib.IMAP4.error, ssl.SSLError) as e:
        raise ErroreCasella(f"Connessione a {casella.server} non riuscita: {e}") from e
    return conn


def _testo(msg):
    """Corpo in solo testo: se c'è solo HTML lo si riduce a testo (mai mostrato come HTML)."""
    parte = msg.get_body(preferencelist=("plain", "html"))
    if parte is None:
        return ""
    try:
        contenuto = parte.get_content()
    except (LookupError, UnicodeDecodeError):
        contenuto = parte.get_payload(decode=True).decode("utf-8", "replace")
    if parte.get_content_type() == "text/html":
        contenuto = strip_tags(contenuto)
    return contenuto.strip()[:100_000]


def _originale_pec(msg):
    """Nelle PEC il messaggio originale è nell'allegato postacert.eml.

    La busta di trasporto è firmata (multipart/signed → multipart/mixed → postacert.eml): si
    cerca a ogni livello, non solo tra gli allegati diretti.
    """
    for parte in msg.walk():
        if (parte.get_filename() or "").lower() == "postacert.eml":
            if parte.get_content_type() == "message/rfc822":
                return parte.get_content()
            dati = parte.get_payload(decode=True)
            if dati:
                return email.message_from_bytes(dati, policy=policy.default)
    return None


def _mittente_busta_pec(msg, nome, indirizzo):
    """Dalla busta «Per conto di: x@y» <posta-certificata@...> ricava x@y (o il Reply-To)."""
    _, risposta = parseaddr(str(msg.get("Reply-To", "")))
    trovato = re.search(r"per conto di:\s*(\S+@\S+)", nome, re.IGNORECASE)
    vero = trovato.group(1).strip("<>\"'") if trovato else risposta
    return ("", vero) if "@" in vero else (nome, indirizzo)


def _allegati(msg, cartella):
    elenco = []
    for parte in msg.iter_attachments():
        nome = nome_file_sicuro(parte.get_filename() or "allegato")
        if nome.lower() in ("daticert.xml", "smime.p7s", "postacert.eml"):
            # ricevute tecniche della PEC: restano nel file .eml completo
            continue
        dati = parte.get_payload(decode=True)
        if not dati:
            continue
        impronta = hashlib.sha256(dati).hexdigest()
        percorso = default_storage.save(f"{cartella}/{impronta[:20]}", ContentFile(dati))
        elenco.append(
            {"nome": nome, "percorso": percorso, "dimensione": len(dati), "impronta": impronta}
        )
    return elenco


def salva_messaggio(casella, grezzo: bytes):
    """Crea il MessaggioRicevuto da un messaggio RFC 822; None se già presente."""
    impronta = hashlib.sha256(grezzo).hexdigest()
    msg = email.message_from_bytes(grezzo, policy=policy.default)
    message_id = (msg.get("Message-ID") or "").strip()[:500] or f"senza-id-{impronta}"
    if MessaggioRicevuto.objects.filter(casella=casella, message_id=message_id).exists():
        return None
    contenuto = msg
    if casella.pec and (originale := _originale_pec(msg)) is not None:
        contenuto = originale
    nome_mitt, email_mitt = parseaddr(str(contenuto.get("From", "")))
    if contenuto is msg and casella.pec and msg.get("X-Trasporto"):
        # busta PEC senza originale leggibile: il mittente vero non è posta-certificata@...
        nome_mitt, email_mitt = _mittente_busta_pec(msg, nome_mitt, email_mitt)
    try:
        data = parsedate_to_datetime(str(contenuto.get("Date") or msg.get("Date")))
        if timezone.is_naive(data):
            data = timezone.make_aware(data, timezone.get_current_timezone())
    except (TypeError, ValueError, IndexError):
        data = None
    cartella = f"protocollo/posta/{casella.pk}/{impronta[:20]}"
    destinatari = ", ".join(
        a
        for _, a in getaddresses([str(contenuto.get("To", "")), str(contenuto.get("Cc", ""))])
        if a
    )
    messaggio = MessaggioRicevuto(
        casella=casella,
        message_id=message_id,
        mittente=(f"{nome_mitt} <{email_mitt}>" if nome_mitt else email_mitt)[:500]
        or "(sconosciuto)",
        mittente_email=email_mitt[:254] if "@" in email_mitt else "",
        destinatari=destinatari[:5000],
        oggetto=str(contenuto.get("Subject", ""))[:500],
        data=data,
        testo=_testo(contenuto),
        impronta=impronta,
        allegati=_allegati(contenuto, cartella),
    )
    # ricevuta PEC di un nostro protocollo spedito: si aggancia da sola, senza protocollarla
    destinatario = ricevuta = None
    if casella.pec and (ricevuta := spedizioni.ricevuta_pec(msg)):
        destinatario = spedizioni.destinatario_della_ricevuta(ricevuta[1])
    if destinatario is not None:
        messaggio.stato = MessaggioRicevuto.Stato.PROTOCOLLATO
        messaggio.protocollo = destinatario.spedizione.protocollo
        messaggio.gestito_il = timezone.now()
    messaggio.file_eml.save(f"{impronta[:20]}.eml", ContentFile(grezzo), save=False)
    try:
        with transaction.atomic():
            messaggio.save()
            if destinatario is not None:
                spedizioni.applica_ricevuta(destinatario, ricevuta[0], grezzo, data)
    except IntegrityError:
        return None  # scaricato in parallelo da un altro processo
    return messaggio


def _quota(nome):
    """Nome di cartella IMAP fra virgolette (imaplib non quota gli argomenti di UID MOVE)."""
    return '"' + nome.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _capacita(conn):
    stato, dati = conn.capability()
    if stato != "OK" or not dati or not dati[0]:
        return set()
    return {c.upper() for c in dati[0].decode(errors="replace").split()}


def nome_sul_server(conn, cartella):
    """Nome completo della cartella nel namespace personale del server (es. Aruba e Courier
    vogliono «INBOX.PROCESSATA»): si chiede al server con NAMESPACE, se lo supporta."""
    if cartella.upper().startswith("INBOX"):
        return cartella
    try:
        stato, dati = conn.namespace()
    except (imaplib.IMAP4.error, AttributeError):
        return cartella
    if stato != "OK" or not dati or not dati[0]:
        return cartella
    trovato = re.match(rb'\s*\(\("([^"]*)"', dati[0])
    prefisso = trovato.group(1).decode(errors="replace") if trovato else ""
    if prefisso and not cartella.startswith(prefisso):
        return prefisso + cartella
    return cartella


def _assicura_cartella(conn, cartella):
    """Crea la cartella se non esiste (e la sottoscrive, per vederla nel client di posta)."""
    stato, _ = conn.status(_quota(cartella), "(MESSAGES)")
    if stato == "OK":
        return False
    stato, dati = conn.create(_quota(cartella))
    if stato != "OK":
        raise ErroreCasella(f"Impossibile creare la cartella «{cartella}»: {dati}")
    with contextlib.suppress(imaplib.IMAP4.error):
        conn.subscribe(_quota(cartella))
    log.info("Creata la cartella %s", cartella)
    return True


def _sposta(conn, uids, cartella):
    """Sposta i messaggi (per UID) nella cartella: MOVE, oppure COPY con cancellazione dei soli
    messaggi copiati (UID EXPUNGE). Senza nessuna delle due non si tocca nulla."""
    cartella = nome_sul_server(conn, cartella)
    _assicura_cartella(conn, cartella)
    capacita = _capacita(conn)
    if "MOVE" not in capacita and "UIDPLUS" not in capacita:
        raise ErroreCasella(
            "Il server non permette di spostare i messaggi (mancano MOVE e UIDPLUS): "
            "lasciare vuota la cartella dei messaggi scaricati."
        )
    for i in range(0, len(uids), LOTTO_SPOSTAMENTO):
        insieme = b",".join(uids[i : i + LOTTO_SPOSTAMENTO]).decode()
        if "MOVE" in capacita:
            stato, dati = conn.uid("MOVE", insieme, _quota(cartella))
        else:
            stato, dati = conn.uid("COPY", insieme, _quota(cartella))
            if stato == "OK":
                stato, dati = conn.uid("STORE", insieme, "+FLAGS.SILENT", r"(\Deleted)")
            if stato == "OK":
                stato, dati = conn.uid("EXPUNGE", insieme)
        if stato != "OK":
            raise ErroreCasella(f"Spostamento nella cartella «{cartella}» non riuscito: {dati}")


# cestini più comuni se il server non indica \Trash (RFC 6154) nell'elenco delle cartelle
CESTINI = ("Trash", "Cestino", "Deleted Messages", "Deleted Items", "Posta eliminata")
_RIGA_LIST = re.compile(rb'^\((?P<attributi>[^)]*)\) (?:"[^"]*"|NIL) (?P<nome>.+)$')


def cestino_del_server(conn):
    """Nome del cestino della casella, o None: mai creato, per non inventarne uno."""
    with contextlib.suppress(imaplib.IMAP4.error):
        stato, righe = conn.list()
        if stato == "OK":
            for riga in righe or []:
                trovato = _RIGA_LIST.match(riga) if isinstance(riga, bytes) else None
                if trovato and b"\\trash" in trovato["attributi"].lower():
                    return trovato["nome"].decode(errors="replace").strip().strip('"')
    for nome in CESTINI:
        completo = nome_sul_server(conn, nome)
        if conn.status(_quota(completo), "(MESSAGES)")[0] == "OK":
            return completo
    return None


def _dove(casella, posizione):
    """Cartella del server per una posizione logica del messaggio."""
    if posizione == "scartata":
        return casella.cartella_scartata.strip()
    return casella.cartella_processata.strip() or casella.cartella  # "" o "processata"


def _cerca_per_message_id(conn, message_id):
    if message_id.startswith("senza-id-"):  # Message-ID assente: non si ritrova
        return []
    stato, dati = conn.uid("SEARCH", None, "HEADER", "Message-ID", _quota(message_id))
    return dati[0].split() if stato == "OK" and dati and dati[0] else []


def applica_spostamenti(conn, casella):
    """Sposta sul server i messaggi scartati, ripristinati o ripuliti nel frattempo (cercati per
    Message-ID nella cartella in cui si trovano). Gli errori restano sul messaggio."""
    attesa = list(
        MessaggioRicevuto.objects.filter(casella=casella).exclude(spostare_in="").order_by("pk")
    )
    gruppi = {}
    for m in attesa:
        gruppi.setdefault((m.cartella_server, m.spostare_in), []).append(m)
    spostati = 0
    for (da, verso), messaggi in gruppi.items():
        try:
            origine = nome_sul_server(conn, _dove(casella, da))
            if verso == "cestino":
                destinazione = cestino_del_server(conn)
                if destinazione is None:
                    raise ErroreCasella("cestino della casella non trovato")
            else:
                destinazione = _dove(casella, verso)
                if not destinazione:
                    raise ErroreCasella("cartella di destinazione non indicata nella casella")
            # dove dovrebbe essere, poi nella cartella letta: i messaggi scaricati prima della
            # cartella PROCESSATA (o fuori dalla finestra dei giorni) sono ancora lì
            arrivo = destinazione if verso == "cestino" else nome_sul_server(conn, destinazione)
            cartelle = [origine]
            if casella.cartella not in (origine, arrivo):
                cartelle.append(casella.cartella)
            restanti = list(messaggi)
            for cartella in cartelle:
                if not restanti or conn.select(_quota(cartella))[0] != "OK":
                    continue
                trovati, mancanti = [], []
                for m in restanti:
                    uids = _cerca_per_message_id(conn, m.message_id)
                    (trovati if uids else mancanti).append((m, uids[-1] if uids else None))
                if trovati:
                    _sposta(conn, [u for _, u in trovati], destinazione)
                for m, _ in trovati:
                    m.cartella_server = "" if verso == "processata" else verso
                    m.spostare_in = m.errore_server = ""
                    m.save(update_fields=["cartella_server", "spostare_in", "errore_server"])
                    spostati += 1
                restanti = [m for m, _ in mancanti]
            for m in restanti:  # cancellato a mano o mai arrivato: non si riprova
                m.spostare_in = ""
                m.errore_server = f"non trovato in «{'» né in «'.join(cartelle)}»"[:300]
                m.save(update_fields=["spostare_in", "errore_server"])
        except (ErroreCasella, imaplib.IMAP4.error, OSError) as e:
            log.warning("Casella %s: spostamento verso %s non riuscito: %s", casella, verso, e)
            for m in messaggi:  # si riprova al prossimo scaricamento
                m.errore_server = f"spostamento non riuscito: {e}"[:300]
                m.save(update_fields=["errore_server"])
    return spostati


def scarica_casella(casella):
    """Scarica i messaggi degli ultimi `casella.giorni` giorni non ancora presenti e sposta
    quelli conservati (nuovi o già scaricati) nella cartella dei messaggi scaricati."""
    conn = _connetti(casella)
    archivio = casella.cartella_processata.strip()
    nuovi = 0
    conservati = []
    try:
        stato, _ = conn.select(_quota(casella.cartella), readonly=not archivio)
        if stato != "OK":
            raise ErroreCasella(f"Cartella «{casella.cartella}» non trovata.")
        dal = (timezone.localdate() - timedelta(days=casella.giorni)).strftime("%d-%b-%Y")
        stato, dati = conn.uid("SEARCH", None, f"SINCE {dal}")
        if stato != "OK":
            raise ErroreCasella("Ricerca dei messaggi non riuscita.")
        try:
            for uid in dati[0].split():
                stato, dimensione = conn.uid("FETCH", uid, "(RFC822.SIZE)")
                try:
                    byte = int(dimensione[0].decode().rsplit("RFC822.SIZE", 1)[1].strip(" )"))
                except (IndexError, ValueError, AttributeError):
                    byte = 0
                if byte > DIMENSIONE_MASSIMA:
                    log.warning(
                        "Casella %s: messaggio UID %s troppo grande, ignorato", casella, uid
                    )
                    continue
                stato, parti = conn.uid("FETCH", uid, "(BODY.PEEK[])")
                if stato != "OK" or not parti or not isinstance(parti[0], tuple):
                    continue
                if salva_messaggio(casella, parti[0][1]) is not None:
                    nuovi += 1
                conservati.append(uid)  # salvato ora o già presente: si può spostare
        finally:
            # anche dopo un errore: si spostano quelli già conservati nel programma
            if archivio and conservati:
                _sposta(conn, conservati, archivio)
        applica_spostamenti(conn, casella)  # scartati, ripristinati, ripuliti nel frattempo
    finally:
        with contextlib.suppress(OSError, imaplib.IMAP4.error):
            conn.logout()
    return nuovi


def verifica_casella(casella):
    """Prova di accesso (sola lettura, nulla viene scaricato): solleva ErroreCasella o
    restituisce un messaggio con i messaggi presenti e quelli nel periodo da scaricare."""
    conn = _connetti(casella)
    try:
        stato, dati = conn.select(_quota(casella.cartella), readonly=True)
        if stato != "OK":
            raise ErroreCasella(
                f"Accesso riuscito, ma la cartella «{casella.cartella}» non esiste."
            )
        try:
            totale = int(dati[0])
        except (TypeError, ValueError, IndexError):
            totale = None
        dal = (timezone.localdate() - timedelta(days=casella.giorni)).strftime("%d-%b-%Y")
        stato, trovati = conn.uid("SEARCH", None, f"SINCE {dal}")
        recenti = len(trovati[0].split()) if stato == "OK" and trovati and trovati[0] else 0
        gia = MessaggioRicevuto.objects.filter(casella=casella).count()
        archivio = casella.cartella_processata.strip()
        if archivio:
            archivio = nome_sul_server(conn, archivio)
            esiste = conn.status(_quota(archivio), "(MESSAGES)")[0] == "OK"
            capacita = _capacita(conn)
        scartata = casella.cartella_scartata.strip()
        if scartata:
            scartata = nome_sul_server(conn, scartata)
        cestino = None if casella.pec else cestino_del_server(conn)
    finally:
        with contextlib.suppress(OSError, imaplib.IMAP4.error):
            conn.logout()
    parti = [f"accesso a {casella.server} riuscito, cartella «{casella.cartella}»"]
    if totale is not None:
        parti.append(f"{totale} messaggi in tutto")
    parti.append(f"{recenti} negli ultimi {casella.giorni} giorni")
    parti.append(f"{gia} già scaricati nel programma")
    if archivio:
        parti.append(
            f"i messaggi scaricati vanno nella cartella «{archivio}»"
            + ("" if esiste else " (sarà creata al primo scaricamento)")
        )
        if "MOVE" not in capacita and "UIDPLUS" not in capacita:
            parti.append("ATTENZIONE: il server non permette di spostarli (mancano MOVE e UIDPLUS)")
    if scartata:
        parti.append(f"gli scartati vanno nella cartella «{scartata}»")
    if not casella.pec and cestino:
        parti.append(f"cestino della casella: «{cestino}»")
    elif not casella.pec:
        parti.append("cestino non trovato (i messaggi ripuliti restano sul server)")
    return "; ".join(parti) + "."


def scarica_tutte():
    """Per il comando pianificato: scarica da ogni casella attiva, registrando gli errori."""
    from apps.core.models import Organizzazione

    risultati = {}
    if not Organizzazione.corrente().ricezione_posta:
        return risultati  # lettura della posta disattivata (Sistema -> Servizi di posta)
    for casella in CasellaPosta.objects.filter(attiva=True):
        try:
            risultati[casella.nome] = scarica_casella(casella)
            casella.ultimo_errore = ""
        except Exception as e:  # noqa: BLE001 - una casella in errore non blocca le altre
            log.exception("Casella %s: errore", casella)
            risultati[casella.nome] = str(e)
            casella.ultimo_errore = str(e)[:500]
        casella.ultimo_controllo = timezone.now()
        casella.save(update_fields=["ultimo_controllo", "ultimo_errore"])
    return risultati
