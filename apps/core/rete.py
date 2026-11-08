# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: IP reale del client dietro uno o più reverse proxy (X-Forwarded-For), usato dal
# *              blocco dei tentativi di accesso e dal registro attività. L'intestazione è
# *              considerata solo se la richiesta arriva da un proxy fidato (PROXY_FIDATI).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import ipaddress

from django.conf import settings


def _ip(valore):
    try:
        return ipaddress.ip_address(valore.strip().strip("[]"))
    except ValueError:
        return None


def _fidato(ip):
    reti = getattr(settings, "PROXY_FIDATI", [])
    if not reti:  # nessun elenco: ci si fida di chiunque (sconsigliato se la porta è esposta)
        return True
    for rete in reti:
        try:
            if ip in ipaddress.ip_network(rete, strict=False):
                return True
        except ValueError:
            continue
    return False


def ip_client(request):
    """Con PROXY_COUNT=N l'IP del client è l'N-esimo indirizzo di X-Forwarded-For contando da
    destra (quelli più a sinistra li può scrivere chiunque); altrimenti REMOTE_ADDR."""
    remoto = request.META.get("REMOTE_ADDR", "")
    n = getattr(settings, "PROXY_COUNT", 0)
    ip_remoto = _ip(remoto)
    if n <= 0 or ip_remoto is None or not _fidato(ip_remoto):
        return remoto
    catena = [x for x in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",") if x.strip()]
    if len(catena) < n:
        return remoto
    client = _ip(catena[-n])
    return str(client) if client else remoto
