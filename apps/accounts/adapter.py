# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Adattatore allauth: la registrazione libera è disattivata
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import logging

from allauth.account.adapter import DefaultAccountAdapter

log = logging.getLogger(__name__)


class AdapterAccount(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        return False

    def send_mail(self, template_prefix, email, context):
        """Con l'invio delle email disattivato (Sistema -> Servizi di posta) non si spedisce."""
        from apps.core.models import Organizzazione

        if not Organizzazione.corrente().invio_email:
            log.warning("Email %s a %s non inviata: invio disattivato", template_prefix, email)
            return
        utente = context.get("user")
        if (
            "password_reset" in template_prefix
            and utente is not None
            and not getattr(utente, "puo_cambiare_password", True)
        ):
            log.warning("Recupero password non inviato a %s: la imposta l'amministratore", email)
            return
        super().send_mail(template_prefix, email, context)
