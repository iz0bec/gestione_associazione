# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Adattatore allauth: la registrazione libera è disattivata
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from allauth.account.adapter import DefaultAccountAdapter


class AdapterAccount(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        return False
