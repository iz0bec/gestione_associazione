# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Obblighi di accesso: cambio della password temporanea e secondo fattore
# *              richiesto dal ruolo. Fino a quando non sono soddisfatti l'utente può usare
# *              solo le pagine del proprio account.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse

from . import servizi

# Percorsi sempre consentiti (account, risorse statiche, pagine tecniche)
CONSENTITI = ("/account/", "/salute/", "/aspetto.css", "/logo.png", "/ripristino/")


class ObblighiAccessoMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        utente = getattr(request, "user", None)
        if utente is not None and utente.is_authenticated and not self._consentito(request.path):
            destinazione = self._obbligo(request, utente)
            if destinazione:
                if request.headers.get("HX-Request"):
                    risposta = HttpResponse(status=204)
                    risposta["HX-Redirect"] = destinazione
                    return risposta
                return redirect(destinazione)
        return self.get_response(request)

    @staticmethod
    def _consentito(percorso):
        statici = settings.STATIC_URL or "/static/"
        return percorso.startswith((*CONSENTITI, statici))

    @staticmethod
    def _obbligo(request, utente):
        if utente.deve_cambiare_password:
            messages.warning(
                request, "Stai usando una password temporanea: scegline una nuova per continuare."
            )
            return reverse("account_change_password")
        if servizi.mfa_richiesta(utente) and not servizi.ha_secondo_fattore(utente):
            messages.warning(
                request,
                "Il tuo ruolo richiede il secondo fattore: configura un'app di autenticazione "
                "o una passkey per continuare.",
            )
            return reverse("mfa_index")
        return None
