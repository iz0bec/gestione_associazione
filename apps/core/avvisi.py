# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Avvisi personali agli utenti per messaggistica istantanea (Telegram, SMS,
# *              WhatsApp): posta da protocollare, domande di iscrizione, bandi, sicurezza.
# *              Ognuno sceglie il canale per tipo nella pagina Avvisi; posta, domande e bandi
# *              arrivano su Telegram da sole a chi l'ha collegato, la sicurezza solo a chi la
# *              sceglie.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import logging
from dataclasses import dataclass

from django.contrib.auth import get_user_model

from .models import CanaleTelegram, Organizzazione, ServizioMessaggi

log = logging.getLogger(__name__)

CANALI_NOMI = [("telegram", "Telegram"), ("sms", "SMS"), ("whatsapp", "WhatsApp")]
NESSUNO = "no"  # scelta esplicita di non ricevere (il vuoto vale «automatico» dove previsto)


@dataclass(frozen=True)
class Tipo:
    chiave: str
    nome: str
    permesso: str
    campo: str
    automatico: bool  # vuoto = Telegram, se collegato
    descrizione: str


TIPI = {
    t.chiave: t
    for t in (
        Tipo("posta", "Posta da protocollare", "protocollo.gestisci_posta", "avvisi_posta", True,
             "Messaggi nuovi da protocollare (email e PEC): un riepilogo per ogni scaricamento."),
        Tipo("domande", "Domande di iscrizione", "soci.valuta_domanda", "avvisi_domande", True,
             "Ogni nuova domanda di iscrizione da valutare (modulo, email, collegamenti)."),
        Tipo("bandi", "Scadenze dei bandi", "progetti.gestisci_bandi", "avvisi_bandi", True,
             "Bandi nuovi da vagliare dalle fonti e domande in scadenza (7 e 2 giorni prima)."),
        Tipo("sicurezza", "Sicurezza", "accounts.change_utente", "avvisi_sicurezza", False,
             "Accessi falliti ripetuti, accessi degli amministratori da indirizzi nuovi, "
             "modifiche agli utenti, lavori periodici e backup non riusciti."),
    )
}  # fmt: skip


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


def telegram_collegato(utente):
    return bool(utente.soggetto_id and utente.soggetto.telegram_chat_id)


def scelta(utente, tipo):
    return getattr(utente, TIPI[tipo].campo)


def canale_di(utente, tipo):
    """Canale su cui l'utente riceve gli avvisi del tipo ("" = nessuno)."""
    valore = scelta(utente, tipo)
    if valore == NESSUNO:
        return ""
    if valore:
        return valore
    if TIPI[tipo].automatico and telegram_collegato(utente) and CanaleTelegram.corrente().pronto:
        return "telegram"
    return ""


def problema(utente, canale):
    """Perché l'utente non può ricevere avvisi sul canale ("" se può)."""
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


def destinatari(tipo, filtro=None):
    """[(utente, canale)]: attivi, con il permesso del tipo e un canale utilizzabile.
    `filtro(utente)` restringe ulteriormente (es. le sezioni visibili)."""
    risultato = []
    utenti = get_user_model().objects.filter(is_active=True).select_related("soggetto")
    for u in utenti:
        canale = canale_di(u, tipo)
        if not canale or problema(u, canale) or not u.has_perm(TIPI[tipo].permesso):
            continue
        if filtro is None or filtro(u):
            risultato.append((u, canale))
    return risultato


def invia(utente, canale, contenuto):
    """Manda il testo sul canale; solleva AvvisoNonInviato."""
    from apps.comunicazioni import messaggi, telegram

    if motivo := problema(utente, canale):
        raise AvvisoNonInviato(motivo)
    try:
        if canale == "telegram":
            telegram._chiama(CanaleTelegram.corrente().token(), "sendMessage", {
                "chat_id": utente.soggetto.telegram_chat_id, "text": contenuto,
                "disable_web_page_preview": True,
            })  # fmt: skip
        else:
            servizio = ServizioMessaggi.attivo_per(canale)
            breve = " ".join(contenuto.split())  # SMS e WhatsApp: una riga
            messaggi.fornitore(servizio).invia(numero_di(utente), breve)
    except (telegram.ErroreTelegram, messaggi.ErroreMessaggi) as e:
        raise AvvisoNonInviato(str(e)) from e


def avvisa(tipo, contenuto, filtro=None):
    """Manda l'avviso a tutti i destinatari del tipo. Rispetta l'interruttore dell'invio dei
    messaggi; un errore non ferma gli altri né chi chiama. Restituisce quanti sono partiti."""
    try:
        if not Organizzazione.corrente().invio_email:
            return 0
        lista = destinatari(tipo, filtro)
    except Exception:  # noqa: BLE001 - un avviso non deve mai bloccare l'operazione
        log.warning("Avvisi %s non calcolati", tipo, exc_info=True)
        return 0
    inviati = 0
    for utente, canale in lista:
        try:
            invia(utente, canale, contenuto)
            inviati += 1
            log.info("Avviso %s inviato a %s su %s", tipo, utente, canale)
        except AvvisoNonInviato as e:
            log.warning("Avviso %s a %s non inviato: %s", tipo, utente, e)
    return inviati
