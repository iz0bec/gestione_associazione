# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Scaricamento dei messaggi dalle caselle IMAP (email e PEC) per la
# *              protocollazione. La casella è aperta in sola lettura: nulla viene
# *              cancellato o segnato come letto sul server.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import contextlib
import email
import hashlib
import imaplib
import logging
import ssl
from datetime import timedelta
from email import policy
from email.utils import getaddresses, parseaddr, parsedate_to_datetime

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.html import strip_tags

from .models import CasellaPosta, MessaggioRicevuto
from .servizi import nome_file_sicuro

log = logging.getLogger(__name__)

DIMENSIONE_MASSIMA = 50 * 1024 * 1024  # messaggi più grandi non vengono scaricati
TIMEOUT = 30


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
    """Nelle PEC il messaggio originale è nell'allegato postacert.eml."""
    for parte in msg.iter_attachments():
        if (parte.get_filename() or "").lower() == "postacert.eml":
            if parte.get_content_type() == "message/rfc822":
                return parte.get_content()
            dati = parte.get_payload(decode=True)
            if dati:
                return email.message_from_bytes(dati, policy=policy.default)
    return None


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
    messaggio.file_eml.save(f"{impronta[:20]}.eml", ContentFile(grezzo), save=False)
    try:
        with transaction.atomic():
            messaggio.save()
    except IntegrityError:
        return None  # scaricato in parallelo da un altro processo
    return messaggio


def scarica_casella(casella):
    """Scarica i messaggi degli ultimi `casella.giorni` giorni non ancora presenti."""
    conn = _connetti(casella)
    nuovi = 0
    try:
        stato, _ = conn.select(f'"{casella.cartella}"', readonly=True)
        if stato != "OK":
            raise ErroreCasella(f"Cartella «{casella.cartella}» non trovata.")
        dal = (timezone.localdate() - timedelta(days=casella.giorni)).strftime("%d-%b-%Y")
        stato, dati = conn.uid("SEARCH", None, f"SINCE {dal}")
        if stato != "OK":
            raise ErroreCasella("Ricerca dei messaggi non riuscita.")
        for uid in dati[0].split():
            stato, dimensione = conn.uid("FETCH", uid, "(RFC822.SIZE)")
            try:
                byte = int(dimensione[0].decode().rsplit("RFC822.SIZE", 1)[1].strip(" )"))
            except (IndexError, ValueError, AttributeError):
                byte = 0
            if byte > DIMENSIONE_MASSIMA:
                log.warning("Casella %s: messaggio UID %s troppo grande, ignorato", casella, uid)
                continue
            stato, parti = conn.uid("FETCH", uid, "(BODY.PEEK[])")
            if stato != "OK" or not parti or not isinstance(parti[0], tuple):
                continue
            if salva_messaggio(casella, parti[0][1]) is not None:
                nuovi += 1
    finally:
        with contextlib.suppress(OSError, imaplib.IMAP4.error):
            conn.logout()
    return nuovi


def scarica_tutte():
    """Per il comando pianificato: scarica da ogni casella attiva, registrando gli errori."""
    risultati = {}
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
