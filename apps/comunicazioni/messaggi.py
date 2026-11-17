# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Comunicazioni anche per SMS (Skebby, Aruba, Twilio) e su WhatsApp Business
# *              (API Cloud di Meta, modelli approvati): numeri, testo breve, fornitori, coda.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import base64
import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request

from django.utils import timezone

from apps.core.models import Organizzazione, ServizioMessaggi

from .models import ConsegnaMessaggio

log = logging.getLogger(__name__)

TIMEOUT = 20
MAX_TENTATIVI = 3
LUNGHEZZA_SMS = 459  # tre SMS concatenati
LUNGHEZZA_WHATSAPP = 1000  # parametro di un modello (Meta: 1024)


class ErroreMessaggi(Exception):
    pass


# --- numeri e testo ----------------------------------------------------------------------------


def numero_e164(numero, prefisso="39"):
    """Numero di cellulare in formato internazionale (+393331234567), o "" se non valido.

    Accetta spazi, trattini, punti e parentesi; «00» diventa «+»; senza prefisso vale l'Italia.
    """
    cifre = re.sub(r"[\s\-./()]", "", numero or "")
    if cifre.startswith("00"):
        cifre = "+" + cifre[2:]
    if not cifre.startswith("+"):
        cifre = f"+{prefisso}{cifre}"
    return cifre if re.fullmatch(r"\+[1-9]\d{7,14}", cifre) else ""


def testo_breve(invio, destinatario, org=None):
    """Testo breve con i segnaposto (o l'oggetto) e la firma dell'organizzazione, su una riga."""
    from .servizi import componi, contesto_destinatario

    org = org or Organizzazione.corrente()
    contesto = contesto_destinatario(invio, destinatario)
    testo = componi(invio.testo_breve or invio.oggetto, contesto)
    return " ".join(f"{testo} - {org.denominazione}".split())


# --- chiamate HTTP -----------------------------------------------------------------------------


def _http(metodo, url, *, json_dati=None, form=None, intestazioni=None, utente=None):
    """Richiesta HTTPS verso il fornitore: (codice, corpo decodificato da JSON o testo)."""
    intestazioni = dict(intestazioni or {})
    corpo = None
    if json_dati is not None:
        corpo = json.dumps(json_dati).encode()
        intestazioni["Content-Type"] = "application/json"
    elif form is not None:
        corpo = urllib.parse.urlencode(form).encode()
        intestazioni["Content-Type"] = "application/x-www-form-urlencoded"
    if utente is not None:
        credenziali = base64.b64encode(f"{utente[0]}:{utente[1]}".encode()).decode()
        intestazioni["Authorization"] = f"Basic {credenziali}"
    if not url.startswith("https://"):
        raise ErroreMessaggi("l'indirizzo dell'API deve essere https")
    richiesta = urllib.request.Request(url, data=corpo, headers=intestazioni, method=metodo)  # noqa: S310
    try:
        with urllib.request.urlopen(richiesta, timeout=TIMEOUT) as risposta:  # noqa: S310
            codice, grezzo = risposta.status, risposta.read()
    except urllib.error.HTTPError as e:
        codice, grezzo = e.code, e.read()
    except (urllib.error.URLError, OSError) as e:
        raise ErroreMessaggi(f"fornitore non raggiungibile: {e}") from e
    testo = grezzo.decode(errors="replace")
    try:
        return codice, json.loads(testo)
    except ValueError:
        return codice, testo


def _errore(codice, corpo):
    if isinstance(corpo, dict):
        dettaglio = corpo.get("error") or corpo.get("message") or corpo.get("detail") or corpo
        if isinstance(dettaglio, dict):
            dettaglio = dettaglio.get("message") or dettaglio
        return ErroreMessaggi(f"errore {codice}: {dettaglio}"[:250])
    return ErroreMessaggi(f"errore {codice}: {str(corpo)[:200]}")


# --- fornitori ---------------------------------------------------------------------------------


class _SmsPiattaforma:
    """Skebby e Aruba SMS: stessa API REST v1.0 (login con utente e password, poi le chiavi)."""

    def __init__(self, servizio):
        self.s = servizio

    def _chiavi(self):
        url = f"{self.s.url}/login?" + urllib.parse.urlencode(
            {"username": self.s.account, "password": self.s.segreto()}
        )
        codice, corpo = _http("GET", url)
        if codice != 200 or not isinstance(corpo, str) or ";" not in corpo:
            raise _errore(codice, corpo)
        utente, sessione = corpo.strip().split(";", 1)
        return {"user_key": utente, "Session_key": sessione}

    def verifica(self):
        chiavi = self._chiavi()
        codice, corpo = _http("GET", f"{self.s.url}/status", intestazioni=chiavi)
        if codice != 200 or not isinstance(corpo, dict):
            raise _errore(codice, corpo)
        credito = ", ".join(f"{c.get('type')}: {c.get('quantity')}" for c in corpo.get("sms", []))
        return f"accesso riuscito{f', credito SMS {credito}' if credito else ''}"

    def invia(self, numero, testo):
        dati = {
            "message_type": self.s.tipo_messaggio or "GP",
            "message": testo[:LUNGHEZZA_SMS],
            "recipient": [numero],
            "returnCredits": False,
        }
        if self.s.mittente:
            dati["sender"] = self.s.mittente
        codice, corpo = _http("POST", f"{self.s.url}/sms", json_dati=dati,
                              intestazioni=self._chiavi())  # fmt: skip
        if codice not in (200, 201) or not isinstance(corpo, dict) or corpo.get("result") != "OK":
            raise _errore(codice, corpo)
        return str(corpo.get("order_id", ""))


class _Twilio:
    def __init__(self, servizio):
        self.s = servizio

    def _conto(self):
        return f"{self.s.url}/Accounts/{urllib.parse.quote(self.s.account)}"

    def verifica(self):
        codice, corpo = _http("GET", f"{self._conto()}.json",
                              utente=(self.s.account, self.s.segreto()))  # fmt: skip
        if codice != 200 or not isinstance(corpo, dict):
            raise _errore(codice, corpo)
        return f"accesso riuscito ({corpo.get('friendly_name', 'account')}, {corpo.get('status')})"

    def invia(self, numero, testo):
        dati = {"To": numero, "Body": testo[:LUNGHEZZA_SMS]}
        if self.s.mittente.startswith("MG"):
            dati["MessagingServiceSid"] = self.s.mittente
        else:
            dati["From"] = self.s.mittente
        codice, corpo = _http("POST", f"{self._conto()}/Messages.json", form=dati,
                              utente=(self.s.account, self.s.segreto()))  # fmt: skip
        if codice not in (200, 201) or not isinstance(corpo, dict):
            raise _errore(codice, corpo)
        return str(corpo.get("sid", ""))


class _WhatsApp:
    """API Cloud di Meta: fuori dalla finestra di 24 ore si possono mandare solo modelli
    approvati; il testo breve va nell'unico parametro {{1}} del corpo del modello."""

    def __init__(self, servizio):
        self.s = servizio

    def _intestazioni(self):
        return {"Authorization": f"Bearer {self.s.segreto()}"}

    def verifica(self):
        campi = "fields=display_phone_number,verified_name"
        url = f"{self.s.url}/{urllib.parse.quote(self.s.account)}?{campi}"
        codice, corpo = _http("GET", url, intestazioni=self._intestazioni())
        if codice != 200 or not isinstance(corpo, dict):
            raise _errore(codice, corpo)
        if not self.s.modello:
            raise ErroreMessaggi("indicare il nome del modello di messaggio approvato")
        nome, numero = corpo.get("verified_name"), corpo.get("display_phone_number")
        return f"accesso riuscito ({nome}, {numero})"

    def invia(self, numero, testo):
        # Meta non accetta a capo, tabulazioni né più di quattro spazi nei parametri
        parametro = " ".join(testo.split())[:LUNGHEZZA_WHATSAPP]
        dati = {
            "messaging_product": "whatsapp",
            "to": numero.lstrip("+"),
            "type": "template",
            "template": {
                "name": self.s.modello,
                "language": {"code": self.s.lingua or "it"},
                "components": [
                    {"type": "body", "parameters": [{"type": "text", "text": parametro}]}
                ],
            },
        }
        codice, corpo = _http("POST", f"{self.s.url}/{urllib.parse.quote(self.s.account)}/messages",
                              json_dati=dati, intestazioni=self._intestazioni())  # fmt: skip
        if codice not in (200, 201) or not isinstance(corpo, dict) or not corpo.get("messages"):
            raise _errore(codice, corpo)
        return str(corpo["messages"][0].get("id", ""))


FORNITORI = {"skebby": _SmsPiattaforma, "aruba": _SmsPiattaforma, "twilio": _Twilio,
             "whatsapp": _WhatsApp}  # fmt: skip


def fornitore(servizio):
    return FORNITORI[servizio.tipo](servizio)


def verifica(servizio):
    """Prova di accesso al fornitore (nessun messaggio inviato)."""
    return fornitore(servizio).verifica()


# --- coda ---------------------------------------------------------------------------------------


def invia_coda(invio, limite):
    """Manda SMS e WhatsApp in attesa per l'invio. Restituisce (inviati, errori)."""
    inviati = errori = 0
    org = Organizzazione.corrente()
    servizi = {c: ServizioMessaggi.attivo_per(c) for c in ("sms", "whatsapp")}
    attesa = ConsegnaMessaggio.objects.filter(
        destinatario__invio=invio, stato=ConsegnaMessaggio.Stato.IN_ATTESA
    ).select_related("destinatario__soggetto")
    for c in attesa:
        if inviati + errori >= limite:
            break
        servizio = servizi[c.canale]
        if servizio is None:
            continue  # restano in attesa finché un servizio non torna attivo
        try:
            testo = testo_breve(invio, c.destinatario, org)
            c.riferimento = fornitore(servizio).invia(c.numero, testo)[:100]
        except ErroreMessaggi as e:
            c.tentativi += 1
            c.errore = str(e)[:255]
            if c.tentativi >= MAX_TENTATIVI:
                c.stato = ConsegnaMessaggio.Stato.ERRORE
            c.save(update_fields=["tentativi", "errore", "stato"])
            errori += 1
            log.warning("%s a %s non riuscito: %s", c.get_canale_display(), c.numero, e)
            continue
        c.stato, c.errore, c.inviato_il = ConsegnaMessaggio.Stato.INVIATO, "", timezone.now()
        c.save(update_fields=["stato", "errore", "inviato_il", "riferimento"])
        inviati += 1
    return inviati, errori
