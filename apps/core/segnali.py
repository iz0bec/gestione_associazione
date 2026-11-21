# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Registro attività per accessi, uscite e tentativi falliti
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import logging

from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from . import sicurezza
from .audit import Azione, registra
from .middleware import ip_richiesta

log = logging.getLogger(__name__)


@receiver(user_logged_in)
def accesso(sender, request, user, **kwargs):
    ip = ip_richiesta(request)
    _protetto(sicurezza.accesso, user, ip)  # prima: l'indirizzo è nuovo se non è già registrato
    registra(Azione.ACCESSO, utente=user, ip=ip, descrizione=user.get_username())


@receiver(user_logged_out)
def uscita(sender, request, user, **kwargs):
    if user is not None:
        registra(
            Azione.USCITA, utente=user, ip=ip_richiesta(request), descrizione=user.get_username()
        )


@receiver(user_login_failed)
def accesso_fallito(sender, credentials, request=None, **kwargs):
    nome = str(
        credentials.get("username") or credentials.get("email") or credentials.get("login") or ""
    )
    ip = ip_richiesta(request) if request else None
    registra(Azione.ACCESSO_FALLITO, ip=ip, descrizione=f"Tentativo come '{nome[:100]}'")
    _protetto(sicurezza.accesso_fallito, ip, nome[:100])


def _protetto(funzione, *argomenti):
    """Gli avvisi di sicurezza non devono mai impedire l'accesso o la sua registrazione."""
    try:
        funzione(*argomenti)
    except Exception:  # noqa: BLE001
        log.warning("Avviso di sicurezza non elaborato", exc_info=True)
