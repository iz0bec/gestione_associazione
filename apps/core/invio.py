# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Servizi di invio (SMTP) di Sistema → Servizi di posta: backend generale di
# *              Django (servizio generale, altrimenti il server del file .env), connessione a
# *              un servizio scelto e prova di accesso.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from email.utils import formataddr, parseaddr

from django.conf import settings
from django.core.mail import mailers
from django.core.mail.backends.smtp import EmailBackend as BackendSmtp

BACKEND = "apps.core.invio.Backend"
TIMEOUT = 30


def servizio_generale():
    from .models import ServizioInvio

    return ServizioInvio.objects.filter(generale=True, attivo=True).first()


def servizi_attivi():
    from .models import ServizioInvio

    return ServizioInvio.objects.filter(attivo=True).order_by("-generale", "tipo", "nome")


def invio_reale():
    """False in sviluppo e nei test (backend console o in memoria): non si apre alcun SMTP."""
    backend = settings.MAILERS["default"]["BACKEND"]
    return backend == BACKEND or backend.endswith("smtp.EmailBackend")


def mittente_env():
    """(nome, indirizzo) di DEFAULT_FROM_EMAIL."""
    return parseaddr(settings.DEFAULT_FROM_EMAIL)


def mittente(servizio, org=None):
    """Intestazione From del servizio (nome del mittente o denominazione dell'organizzazione)."""
    from .models import Organizzazione

    nome = servizio.nome_mittente or (org or Organizzazione.corrente()).denominazione
    return formataddr((nome, servizio.indirizzo))


def _parametri(servizio):
    return {
        "host": servizio.server,
        "port": servizio.porta,
        "username": servizio.nome_utente,
        "password": servizio.password(),
        "use_ssl": servizio.ssl,
        "use_tls": not servizio.ssl,
        "timeout": TIMEOUT,
    }


def _smtp(servizio, alias):
    return BackendSmtp(alias=alias, **_parametri(servizio))


def _applica(backend, servizio):
    backend.host, backend.port = servizio.server, servizio.porta
    backend.username, backend.password = servizio.nome_utente, servizio.password()
    backend.use_ssl, backend.use_tls = servizio.ssl, not servizio.ssl
    backend.timeout = backend.timeout or TIMEOUT


class Backend(BackendSmtp):
    """Backend predefinito: il servizio generale se c'è, altrimenti il server del .env.

    Con il servizio generale il mittente predefinito (DEFAULT_FROM_EMAIL) diventa il suo: i
    server (es. Aruba) rifiutano un mittente diverso dall'account.
    """

    servizio = None
    _CAMPI = ("host", "port", "username", "password", "use_ssl", "use_tls", "timeout")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._env = {campo: getattr(self, campo) for campo in self._CAMPI}

    def open(self):
        if self.connection is None:  # a ogni nuova connessione: il servizio può essere cambiato
            for campo, valore in self._env.items():
                setattr(self, campo, valore)
            self.servizio = servizio_generale()
            if self.servizio is not None:
                _applica(self, self.servizio)
        return super().open()

    def _send(self, email_message):
        if self.servizio is not None and email_message.from_email in (
            None,
            "",
            settings.DEFAULT_FROM_EMAIL,
        ):
            email_message.from_email = mittente(self.servizio)
        return super()._send(email_message)


def connessione(servizio=None):
    """Connessione per spedire: quella del servizio indicato o la generale."""
    if servizio is None or not invio_reale():
        return mailers.default
    return _smtp(servizio, f"servizio-{servizio.pk}")


def verifica(servizio):
    """Prova di accesso al server SMTP (nessun messaggio spedito)."""
    backend = _smtp(servizio, f"verifica-{servizio.pk}")
    backend.timeout = 20
    backend.open()
    backend.close()
    return f"accesso a {servizio.server}:{servizio.porta} riuscito (nessun messaggio spedito)"


def stato_env():
    """Server del file .env (mai la password): vale se non c'è un servizio generale."""
    mailer = settings.MAILERS.get("default", {})
    backend = mailer.get("BACKEND", "")
    opzioni = mailer.get("OPTIONS", {})
    smtp = invio_reale()
    host = opzioni.get("host", "")
    return {
        "smtp": smtp,
        "backend": backend.rsplit(".", 2)[-2] if "." in backend else backend,
        "host": host,
        "porta": opzioni.get("port", ""),
        "utente": opzioni.get("username", ""),
        "configurato": smtp and host not in ("", "localhost", "127.0.0.1"),
        "mittente": settings.DEFAULT_FROM_EMAIL,
    }


def configurato():
    """C'è un server reale per le email (servizio generale o .env)."""
    return invio_reale() and (servizio_generale() is not None or stato_env()["configurato"])
