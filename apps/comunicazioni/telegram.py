# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Comunicazioni anche su Telegram: bot dell'organizzazione, invito personale
# *              (/start con il codice), lettura dei comandi senza webhook (getUpdates dal
# *              pianificatore) e invio di testo e allegati a chi si è collegato.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import http.client
import json
import logging
import re
import secrets
import urllib.error
import urllib.request
import uuid

from django.db import transaction
from django.utils import timezone

from apps.anagrafica.models import Soggetto
from apps.core.audit import Azione, registra
from apps.core.models import CanaleTelegram, Organizzazione

log = logging.getLogger(__name__)

API = "https://api.telegram.org/bot{token}/{metodo}"
TIMEOUT = 20
LUNGHEZZA_MASSIMA = 4000  # Telegram accetta 4096 caratteri per messaggio
MAX_TENTATIVI = 3
# Formato dei token di BotFather: «<id numerico>:<chiave>», senza spazi né altro testo
FORMATO_TOKEN = re.compile(r"\d+:[A-Za-z0-9_-]+")


class ErroreTelegram(Exception):
    pass


def _chiama(token, metodo, dati=None, documento=None):
    """Chiamata all'API dei bot. `documento`: (nome, byte) per sendDocument (multipart)."""
    url = API.format(token=token, metodo=metodo)
    if documento is None:
        corpo = json.dumps(dati or {}).encode()
        intestazioni = {"Content-Type": "application/json"}
    else:
        confine = uuid.uuid4().hex
        parti = []
        for chiave, valore in (dati or {}).items():
            parti.append(f'--{confine}\r\nContent-Disposition: form-data; name="{chiave}"\r\n\r\n'
                         f"{valore}\r\n".encode())  # fmt: skip
        nome, contenuto = documento
        nome = nome.replace('"', "'").replace("\r", " ").replace("\n", " ")
        parti.append(f'--{confine}\r\nContent-Disposition: form-data; name="document"; '
                     f'filename="{nome}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode()
                     + contenuto + b"\r\n")  # fmt: skip
        parti.append(f"--{confine}--\r\n".encode())
        corpo = b"".join(parti)
        intestazioni = {"Content-Type": f"multipart/form-data; boundary={confine}"}
    # URL fisso https://api.telegram.org: nessuno schema scelto dall'utente
    richiesta = urllib.request.Request(url, data=corpo, headers=intestazioni, method="POST")  # noqa: S310
    try:
        with urllib.request.urlopen(richiesta, timeout=TIMEOUT) as risposta:  # noqa: S310
            esito = json.loads(risposta.read().decode())
    except urllib.error.HTTPError as e:
        try:
            esito = json.loads(e.read().decode())
        except ValueError:
            raise ErroreTelegram(f"errore HTTP {e.code}") from e
    except (urllib.error.URLError, http.client.HTTPException, OSError, ValueError) as e:
        raise ErroreTelegram(f"Telegram non raggiungibile: {e}") from e
    if not esito.get("ok"):
        raise ErroreTelegram(esito.get("description") or "risposta non valida")
    return esito.get("result")


# --- configurazione ----------------------------------------------------------------------------


def verifica(token):
    """Nome del bot (getMe): controlla il token senza mandare messaggi."""
    if not FORMATO_TOKEN.fullmatch(token or ""):
        raise ErroreTelegram("il token deve essere solo «numero:chiave» come lo dà BotFather, "
                             "senza spazi né altro testo")  # fmt: skip
    risultato = _chiama(token, "getMe")
    if not risultato.get("is_bot") or not risultato.get("username"):
        raise ErroreTelegram("il token non è di un bot")
    return risultato["username"]


def link_invito(soggetto):
    """Link personale per collegarsi al bot (il codice si genera alla prima richiesta)."""
    canale = CanaleTelegram.corrente()
    if not canale.nome_bot:
        return ""
    if not soggetto.telegram_codice:
        soggetto.telegram_codice = secrets.token_urlsafe(18)[:24]
        soggetto.save(update_fields=["telegram_codice"])
    return f"https://t.me/{canale.nome_bot}?start={soggetto.telegram_codice}"


@transaction.atomic
def scollega(soggetto, utente=None):
    soggetto.telegram_chat_id = soggetto.telegram_collegato_il = None
    soggetto.telegram_codice = ""
    soggetto.save(update_fields=["telegram_chat_id", "telegram_collegato_il", "telegram_codice"])
    registra(Azione.MODIFICA, soggetto, utente=utente, telegram="scollegato")


# --- comandi ricevuti dal bot (getUpdates) -----------------------------------------------------


def _rispondi(token, chat_id, testo):
    try:
        _chiama(token, "sendMessage", {"chat_id": chat_id, "text": testo})
    except ErroreTelegram as e:
        log.warning("Telegram: risposta a %s non riuscita: %s", chat_id, e)


def _gestisci(token, messaggio, org):
    chat_id = (messaggio.get("chat") or {}).get("id")
    testo = (messaggio.get("text") or "").strip()
    if not chat_id or (messaggio.get("chat") or {}).get("type") != "private":
        return
    if testo.startswith("/start"):
        codice = testo.removeprefix("/start").strip()
        soggetto = Soggetto.objects.filter(telegram_codice=codice).first() if codice else None
        if soggetto is None:
            _rispondi(token, chat_id, f"Questo è il canale di {org.denominazione}. Per ricevere "
                                      "le comunicazioni serve il link personale che vi ha inviato "
                                      "l'associazione.")  # fmt: skip
            return
        with transaction.atomic():
            Soggetto.objects.filter(telegram_chat_id=chat_id).exclude(pk=soggetto.pk).update(
                telegram_chat_id=None, telegram_collegato_il=None
            )  # un account Telegram, una persona
            soggetto.telegram_chat_id = chat_id
            soggetto.telegram_collegato_il = timezone.now()
            soggetto.telegram_codice = ""
            soggetto.save(
                update_fields=["telegram_chat_id", "telegram_collegato_il", "telegram_codice"]
            )
            registra(Azione.MODIFICA, soggetto, utente=None, telegram="collegato")
        _rispondi(token, chat_id, f"Ciao {soggetto.nome or soggetto.nome_completo}, da ora "
                                  f"riceverai qui le comunicazioni di {org.denominazione}. "
                                  "Scrivi /stop per non riceverle più.")  # fmt: skip
    elif testo.startswith("/stop"):
        soggetto = Soggetto.objects.filter(telegram_chat_id=chat_id).first()
        if soggetto is not None:
            scollega(soggetto)
        _rispondi(token, chat_id, "Non riceverai più comunicazioni su Telegram. Per riattivarle "
                                  "serve un nuovo link dall'associazione.")  # fmt: skip
    else:
        contatto = org.email or org.denominazione
        _rispondi(token, chat_id, "Questo canale serve solo a ricevere le comunicazioni: per "
                                  f"rispondere scrivete a {contatto}.")  # fmt: skip


def leggi_comandi():
    """Per il pianificatore: legge /start e /stop arrivati al bot. Restituisce quanti."""
    canale = CanaleTelegram.corrente()
    if not canale.pronto:
        return 0
    token = canale.token()
    try:
        aggiornamenti = _chiama(token, "getUpdates", {
            "offset": canale.ultimo_update + 1, "timeout": 0, "allowed_updates": ["message"],
        })  # fmt: skip
        canale.ultimo_errore = ""
    except ErroreTelegram as e:
        canale.ultimo_errore = str(e)[:300]
        aggiornamenti = []
    org = Organizzazione.corrente()
    for a in aggiornamenti:
        canale.ultimo_update = max(canale.ultimo_update, a.get("update_id", 0))
        if a.get("message"):
            _gestisci(token, a["message"], org)
    canale.ultimo_controllo = timezone.now()
    canale.save(update_fields=["ultimo_update", "ultimo_errore", "ultimo_controllo"])
    return len(aggiornamenti)


# --- invio delle comunicazioni -----------------------------------------------------------------


def _pezzi(testo):
    """Il testo diviso in messaggi entro il limite di Telegram, possibilmente fra i paragrafi."""
    pezzi = []
    while len(testo) > LUNGHEZZA_MASSIMA:
        taglio = testo.rfind("\n", 0, LUNGHEZZA_MASSIMA)
        taglio = taglio if taglio > LUNGHEZZA_MASSIMA // 2 else LUNGHEZZA_MASSIMA
        pezzi.append(testo[:taglio])
        testo = testo[taglio:].lstrip("\n")
    return [*pezzi, testo] if testo else pezzi


def testo_per(invio, destinatario, org):
    from .servizi import componi, contesto_destinatario

    contesto = contesto_destinatario(invio, destinatario)
    oggetto = " ".join(componi(invio.oggetto, contesto).split())
    return f"{oggetto}\n\n{componi(invio.corpo, contesto)}\n\n— {org.denominazione}"


def invia_coda(invio, limite):
    """Manda su Telegram i messaggi in attesa dell'invio. Restituisce (inviati, errori)."""
    canale = CanaleTelegram.corrente()
    inviati = errori = 0
    attesa = invio.destinatari.filter(telegram_stato="in_attesa").select_related("soggetto")
    if not canale.pronto:
        return 0, 0  # restano in attesa finché il canale non torna attivo
    token = canale.token()
    org = Organizzazione.corrente()
    allegati = [(a.nome, a.file) for a in invio.allegati.all()]
    for d in attesa:
        if inviati + errori >= limite:
            break
        chat_id = d.soggetto.telegram_chat_id if d.soggetto_id else None
        try:
            if not chat_id:
                raise ErroreTelegram("la persona ha scollegato Telegram")
            for pezzo in _pezzi(testo_per(invio, d, org)):
                _chiama(token, "sendMessage", {"chat_id": chat_id, "text": pezzo})
            for nome, file in allegati:
                with file.open("rb") as f:
                    _chiama(token, "sendDocument", {"chat_id": chat_id}, documento=(nome, f.read()))
        except ErroreTelegram as e:
            d.telegram_errore = str(e)[:255]
            d.tentativi += 1
            definitivo = d.tentativi >= MAX_TENTATIVI or not chat_id
            d.telegram_stato = "errore" if definitivo else "in_attesa"
            d.save(update_fields=["telegram_errore", "telegram_stato", "tentativi"])
            errori += 1
            log.warning("Telegram: invio %s a %s non riuscito: %s", invio.pk, d.nome, e)
            continue
        d.telegram_stato, d.telegram_errore = "inviato", ""
        d.save(update_fields=["telegram_stato", "telegram_errore"])
        inviati += 1
    return inviati, errori


def collegati():
    return Soggetto.objects.filter(telegram_chat_id__isnull=False, attivo=True).count()
