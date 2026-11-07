# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Registro attività per accessi, uscite e tentativi falliti
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from .audit import Azione, registra
from .middleware import ip_richiesta


@receiver(user_logged_in)
def accesso(sender, request, user, **kwargs):
    registra(Azione.ACCESSO, utente=user, ip=ip_richiesta(request), descrizione=user.get_username())


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
    registra(
        Azione.ACCESSO_FALLITO,
        ip=ip_richiesta(request) if request else None,
        descrizione=f"Tentativo come '{nome[:100]}'",
    )
