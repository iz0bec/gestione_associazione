# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Inoltro dei messaggi scaricati da una casella (es. la casella istituzionale della
# *              sezione) alle persone scelte, al posto dell'inoltro del fornitore: reindirizzo
# *              trasparente, con l'originale allegato se il server lo rifiuta; i messaggi
# *              riservati («per conto») solo all'incaricato della trattazione.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import email
import logging
import re
import smtplib
from email import policy
from email.utils import formatdate, make_msgid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import InoltroMessaggio, MessaggioRicevuto

log = logging.getLogger(__name__)
TENTATIVI_MASSIMI = 5
PER_CONTO = re.compile(r"\bper conto di\b", re.IGNORECASE)
# rifiuti del server che giustificano il ripiego sull'inoltro con l'originale allegato
RIFIUTI = (smtplib.SMTPSenderRefused, smtplib.SMTPDataError, smtplib.SMTPRecipientsRefused)


def indirizzi_extra(testo):
    """Indirizzi validi scritti a mano (uno per riga, anche separati da virgole)."""
    validi = []
    for parte in re.split(r"[\s,;]+", testo or ""):
        try:
            validate_email(parte)
        except ValidationError:
            continue  # riga vuota o indirizzo non valido: ignorato (il modulo lo segnala)
        if parte.lower() not in {v.lower() for v in validi}:
            validi.append(parte)
    return validi


def destinatari(casella):
    """Indirizzi a cui inoltrare i messaggi non riservati."""
    indirizzi = [s.email for s in casella.inoltro_destinatari.exclude(email="")]
    indirizzi += indirizzi_extra(casella.inoltro_indirizzi)
    proprio = (casella.indirizzo or "").lower()
    visti, unici = set(), []
    for i in indirizzi:
        if i.lower() not in visti and i.lower() != proprio:  # mai a sé stessa (giro infinito)
            visti.add(i.lower())
            unici.append(i)
    return unici


def e_riservato(messaggio):
    """Messaggio riservato: intestazione del programma o oggetto «… per conto di …»."""
    if PER_CONTO.search(messaggio.oggetto or ""):
        return True
    try:
        with messaggio.file_eml.open("rb") as f:
            intestazioni = email.message_from_bytes(f.read(65536), policy=policy.default)
    except (OSError, ValueError):
        return False
    return bool(intestazioni.get("X-Gestione-Riservato"))


def prepara(casella):
    """Mette in coda gli inoltri dei messaggi scaricati dopo l'attivazione dell'inoltro. I
    messaggi riservati vanno solo all'incaricato; le ricevute PEC agganciate non si inoltrano."""
    if not casella.inoltro_attivo or casella.inoltro_dal is None:
        return 0
    da_esaminare = MessaggioRicevuto.objects.filter(
        casella=casella, inoltro_esaminato=False, scaricato_il__gte=casella.inoltro_dal
    )
    tutti = destinatari(casella)
    incaricato = casella.inoltro_incaricato
    creati = 0
    for messaggio in da_esaminare:
        gestito = messaggio.stato != MessaggioRicevuto.Stato.NUOVO
        ricevuta = gestito and messaggio.gestito_da_id is None
        riservato = e_riservato(messaggio)
        if ricevuta:  # ricevuta PEC agganciata da sola a un protocollo o a una comunicazione
            indirizzi = []
        elif riservato:
            indirizzi = [incaricato.email] if incaricato is not None and incaricato.email else []
            if not indirizzi:
                log.warning("Casella %s: messaggio riservato %s non inoltrato (manca "
                            "l'incaricato con un'email)", casella, messaggio.pk)  # fmt: skip
        else:
            indirizzi = tutti
        with transaction.atomic():
            for indirizzo in indirizzi:
                try:
                    with transaction.atomic():
                        InoltroMessaggio.objects.create(
                            messaggio=messaggio, email=indirizzo, riservato=riservato
                        )
                    creati += 1
                except IntegrityError:
                    pass  # già in coda
            messaggio.inoltro_esaminato = True
            messaggio.save(update_fields=["inoltro_esaminato"])
    return creati


def _connessione(casella):
    """(backend Django, servizio usato): quello scelto per l'inoltro se attivo, altrimenti il
    generale (None se vale il server del .env)."""
    from apps.core import invio

    scelto = casella.inoltro_servizio
    if scelto is not None and scelto.attivo:
        return invio.connessione(scelto), scelto
    return invio.connessione(None), invio.servizio_generale()


def _mittente_busta(servizio):
    from apps.core import invio

    if servizio is not None:
        return servizio.indirizzo
    return invio.mittente_env()[1] or settings.SERVER_EMAIL


def _reindirizza(backend, busta, inoltro, grezzo):
    """Reindirizzo trasparente: il messaggio originale con le intestazioni Resent-* (RFC 5322)."""
    from apps.core import invio

    intestazioni = (
        f"Resent-From: {busta}\r\nResent-To: {inoltro.email}\r\n"
        f"Resent-Date: {formatdate(localtime=True)}\r\n"
        f"Resent-Message-ID: {make_msgid(domain=busta.rsplit('@', 1)[-1])}\r\n"
    ).encode()
    if not invio.invio_reale():  # sviluppo e test: nella posta del backend in memoria
        originale = email.message_from_bytes(grezzo, policy=policy.default)
        copia = EmailMessage(
            subject=str(originale.get("Subject", "")),
            body=_testo(originale),
            from_email=str(originale.get("From", "")) or busta,
            to=[inoltro.email],
            headers={"Resent-From": busta, "Resent-To": inoltro.email},
        )
        backend.send_messages([copia])
        return
    backend.open()
    try:
        backend.connection.sendmail(busta, [inoltro.email], intestazioni + grezzo)
    finally:
        backend.close()


def _testo(msg):
    parte = msg.get_body(preferencelist=("plain",))
    try:
        return parte.get_content() if parte is not None else ""
    except (LookupError, KeyError):
        return ""


def _con_allegato(backend, servizio, messaggio, inoltro, grezzo):
    """Inoltro classico: «Inoltro: …» con il testo e il messaggio originale allegato (.eml)."""
    from apps.core import invio

    originale = email.message_from_bytes(grezzo, policy=policy.default)
    casella = messaggio.casella
    nota = ("Messaggio arrivato alla casella "
            f"{casella.indirizzo or casella.nome} e inoltrato dal gestionale.\n"
            f"Da: {messaggio.mittente}\nOggetto: {messaggio.oggetto}\n\n"
            "Il messaggio originale è allegato; per rispondere si usa «Rispondi».\n\n")  # fmt: skip
    copia = EmailMessage(
        subject=f"Inoltro: {messaggio.oggetto}"[:250],
        body=nota + _testo(originale),
        from_email=invio.mittente(servizio) if servizio is not None else None,
        to=[inoltro.email],
        reply_to=[messaggio.mittente_email] if messaggio.mittente_email else None,
    )
    copia.attach("messaggio-originale.eml", grezzo, "message/rfc822")
    if backend.send_messages([copia]) != 1:
        raise smtplib.SMTPException("messaggio non accettato dal server")


def inoltra(inoltro):
    """Spedisce un inoltro: prima trasparente, poi con l'originale allegato se il server rifiuta."""
    messaggio = inoltro.messaggio
    backend, servizio = _connessione(messaggio.casella)
    busta = _mittente_busta(servizio)
    with messaggio.file_eml.open("rb") as f:
        grezzo = f.read()
    inoltro.tentativi += 1
    try:
        try:
            _reindirizza(backend, busta, inoltro, grezzo)
            inoltro.modo = InoltroMessaggio.Modo.TRASPARENTE
        except RIFIUTI as e:
            log.info("Inoltro %s rifiutato come reindirizzo (%s): con l'originale allegato",
                     inoltro.pk, e)  # fmt: skip
            _con_allegato(backend, servizio, messaggio, inoltro, grezzo)
            inoltro.modo = InoltroMessaggio.Modo.ALLEGATO
    except Exception as e:  # noqa: BLE001 - resta in coda fino ai tentativi massimi
        inoltro.errore = f"{type(e).__name__}: {e}"[:300]
        if inoltro.tentativi >= TENTATIVI_MASSIMI:
            inoltro.stato = InoltroMessaggio.Stato.ERRORE
        inoltro.save(update_fields=["tentativi", "errore", "stato"])
        return False
    inoltro.stato, inoltro.errore = InoltroMessaggio.Stato.INOLTRATO, ""
    inoltro.inoltrato_il = timezone.now()
    inoltro.save(update_fields=["tentativi", "errore", "stato", "modo", "inoltrato_il"])
    return True


def invia_coda(limite=200):
    """Spedisce gli inoltri in attesa (se l'invio dei messaggi è attivo). Rieseguibile."""
    from apps.core.models import Organizzazione

    if not Organizzazione.corrente().invio_email:
        return 0
    fatti = 0
    coda = InoltroMessaggio.objects.filter(stato=InoltroMessaggio.Stato.IN_ATTESA).select_related(
        "messaggio__casella"
    )[:limite]
    for inoltro in coda:
        fatti += inoltra(inoltro)
    return fatti


def attiva(casella, attiva_ora):
    """Accende o spegne l'inoltro: si inoltrano solo i messaggi scaricati da quel momento."""
    if attiva_ora and not casella.inoltro_attivo:
        casella.inoltro_dal = timezone.now()
    casella.inoltro_attivo = attiva_ora


def descrizione(casella):
    """Riepilogo per l'elenco delle caselle."""
    if not casella.inoltro_attivo:
        return ""
    n = len(destinatari(casella))
    testo = f"inoltra a {n} {'indirizzo' if n == 1 else 'indirizzi'}"
    if casella.inoltro_incaricato_id:
        testo += f"; riservati a {casella.inoltro_incaricato}"
    return testo
