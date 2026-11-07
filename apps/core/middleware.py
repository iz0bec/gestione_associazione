# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Rende disponibili utente e IP della richiesta al registro attività.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from axes.helpers import get_client_ip_address

from .audit import contesto_richiesta


class ContestoRichiestaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = contesto_richiesta.set((getattr(request, "user", None), ip_richiesta(request)))
        try:
            return self.get_response(request)
        finally:
            contesto_richiesta.reset(token)


def ip_richiesta(request):
    """IP del client, considerando i proxy fidati configurati (PROXY_COUNT)."""
    try:
        return get_client_ip_address(request)
    except Exception:  # noqa: BLE001 - l'IP è informativo, non deve bloccare la richiesta
        return request.META.get("REMOTE_ADDR")
