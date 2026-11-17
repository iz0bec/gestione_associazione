# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Obblighi di accesso: cambio della password temporanea e secondo fattore
# *              richiesto dal ruolo. Fino a quando non sono soddisfatti l'utente può usare
# *              solo le pagine del proprio account. Ultima attività (utenti connessi).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse

from . import servizi

# Pagine con cui l'utente cambia la propria password (vietate a chi non può farlo)
PAGINE_PASSWORD = ("/account/password/change/", "/account/password/set/")

# Percorsi sempre consentiti (account, risorse statiche, pagine tecniche)
# (il contatore della chat è richiesto da ogni pagina ogni 30 secondi: rediretto, ricaricherebbe la
# pagina del cambio password mentre si scrive)
CONSENTITI = (
    "/account/",
    "/salute/",
    "/aspetto.css",
    "/logo.png",
    "/ripristino/",
    "/chat/non-letti/",
)


class ObblighiAccessoMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        utente = getattr(request, "user", None)
        if (
            utente is not None
            and utente.is_authenticated
            and not utente.puo_cambiare_password
            and request.path.startswith(PAGINE_PASSWORD)
        ):
            messages.warning(
                request, "La tua password la imposta l'amministratore: rivolgiti a lui."
            )
            return redirect("core:cruscotto")
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


class AttivitaMiddleware:
    """Annota l'ultima attività dell'utente (al massimo una scrittura al minuto)."""

    INTERVALLO = 60  # secondi

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        risposta = self.get_response(request)
        utente = getattr(request, "user", None)
        if (
            utente is not None
            and utente.is_authenticated
            and not request.path.startswith((settings.STATIC_URL or "/static/", "/salute/"))
        ):
            from django.utils import timezone

            from .models import Utente

            adesso = timezone.now()
            ultima = utente.ultima_attivita
            if ultima is None or (adesso - ultima).total_seconds() >= self.INTERVALLO:
                Utente.objects.filter(pk=utente.pk).update(ultima_attivita=adesso)
        return risposta
