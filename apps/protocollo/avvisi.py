# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Avvisi della posta da protocollare per messaggistica istantanea (Telegram, SMS,
# *              WhatsApp), scelti da ciascun utente che gestisce la posta: un riepilogo per
# *              ogni scaricamento che porta messaggi nuovi.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.core.models import CanaleTelegram, Organizzazione, ServizioMessaggi

from .models import MessaggioRicevuto

log = logging.getLogger(__name__)

PERMESSO = "protocollo.gestisci_posta"
MAX_ELENCATI = 5


class AvvisoNonInviato(Exception):
    pass


def canali_disponibili():
    """Canali attivi nell'organizzazione: [(valore, etichetta)]."""
    canali = []
    if CanaleTelegram.corrente().pronto:
        canali.append(("telegram", "Telegram"))
    if ServizioMessaggi.attivo_per("sms"):
        canali.append(("sms", "SMS"))
    if ServizioMessaggi.attivo_per("whatsapp"):
        canali.append(("whatsapp", "WhatsApp"))
    return canali


def numero_di(utente):
    from apps.comunicazioni.messaggi import numero_e164

    soggetto = utente.soggetto
    return numero_e164((soggetto.cellulare if soggetto else "") or utente.telefono)


def problema(utente, canale=None):
    """Perché l'utente non può ricevere gli avvisi sul canale scelto ("" se può)."""
    canale = canale if canale is not None else utente.avvisi_posta
    if not canale:
        return ""
    if canale not in dict(canali_disponibili()):
        return "il canale non è attivo nell'organizzazione"
    if canale == "telegram":
        if utente.soggetto is None:
            return "l'utente non è collegato a una scheda anagrafica (serve per Telegram)"
        if not utente.soggetto.telegram_chat_id:
            return "Telegram non ancora collegato"
    elif not numero_di(utente):
        return "manca il numero di cellulare (scheda anagrafica o profilo utente)"
    return ""


def destinatari():
    """Utenti attivi che gestiscono la posta e hanno scelto un canale utilizzabile."""
    utenti = get_user_model().objects.filter(is_active=True).exclude(avvisi_posta="")
    return [
        u for u in utenti.select_related("soggetto") if u.has_perm(PERMESSO) and not problema(u)
    ]


def testo(messaggi):
    org = Organizzazione.corrente()
    n = len(messaggi)
    righe = [f"{org.denominazione}: {n} nuov{'o messaggio' if n == 1 else 'i messaggi'} "
             "da protocollare"]  # fmt: skip
    for m in messaggi[:MAX_ELENCATI]:
        pec = "PEC " if m.casella.pec else ""
        mittente = m.mittente_email or m.mittente
        righe.append(f"- {pec}{(m.oggetto or '(senza oggetto)')[:80]} ({mittente[:60]})")
    if n > MAX_ELENCATI:
        righe.append(f"- e altri {n - MAX_ELENCATI}")
    if settings.URL_PUBBLICO:
        righe.append(f"{settings.URL_PUBBLICO}{reverse('protocollo:posta')}")
    return "\n".join(righe)


def invia(utente, contenuto):
    """Manda l'avviso sul canale scelto dall'utente; solleva AvvisoNonInviato."""
    from apps.comunicazioni import messaggi, telegram

    canale = utente.avvisi_posta
    if motivo := problema(utente):
        raise AvvisoNonInviato(motivo)
    try:
        if canale == "telegram":
            canale_tg = CanaleTelegram.corrente()
            telegram._chiama(canale_tg.token(), "sendMessage", {
                "chat_id": utente.soggetto.telegram_chat_id, "text": contenuto,
                "disable_web_page_preview": True,
            })  # fmt: skip
        else:
            servizio = ServizioMessaggi.attivo_per(canale)
            breve = " ".join(contenuto.split())  # SMS e WhatsApp: una riga
            messaggi.fornitore(servizio).invia(numero_di(utente), breve)
    except (telegram.ErroreTelegram, messaggi.ErroreMessaggi) as e:
        raise AvvisoNonInviato(str(e)) from e


def avvisa_nuova_posta(dal):
    """Dopo lo scaricamento: un riepilogo dei messaggi da esaminare arrivati da `dal` a chi ha
    scelto gli avvisi. Rispetta l'interruttore dell'invio dei messaggi. Restituisce quanti."""
    if not Organizzazione.corrente().invio_email:
        return 0
    nuovi = list(
        MessaggioRicevuto.objects.da_esaminare()
        .filter(scaricato_il__gte=dal)
        .select_related("casella")
        .order_by("-data", "-pk")
    )
    if not nuovi:
        return 0
    contenuto = testo(nuovi)
    inviati = 0
    for utente in destinatari():
        try:
            invia(utente, contenuto)
            inviati += 1
        except AvvisoNonInviato as e:
            log.warning("Avviso della posta a %s non inviato: %s", utente, e)
    return inviati
