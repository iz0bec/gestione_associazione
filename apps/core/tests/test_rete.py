# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test dell'IP reale del client dietro reverse proxy
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import pytest
from django.test import RequestFactory

from apps.core.middleware import ip_richiesta
from apps.core.rete import ip_client


def _r(remoto, xff=None):
    extra = {"HTTP_X_FORWARDED_FOR": xff} if xff is not None else {}
    return RequestFactory().get("/", REMOTE_ADDR=remoto, **extra)


@pytest.mark.parametrize(("count", "fidati", "remoto", "xff", "atteso"), [
    (0, [], "192.168.0.26", "203.0.113.7", "192.168.0.26"),  # nessun proxy configurato
    (1, ["192.168.0.26"], "192.168.0.26", "203.0.113.7", "203.0.113.7"),
    (1, ["192.168.0.26"], "192.168.0.26", "1.2.3.4, 203.0.113.7", "203.0.113.7"),  # falsificato
    (1, ["192.168.0.26"], "192.168.0.50", "203.0.113.7", "192.168.0.50"),  # non dal proxy
    (1, ["192.168.0.0/24"], "192.168.0.34", "203.0.113.7", "203.0.113.7"),
    (1, [], "10.0.0.1", "203.0.113.7", "203.0.113.7"),  # nessun elenco: fiducia a tutti
    (2, [], "10.0.0.1", "203.0.113.7, 10.0.0.2", "203.0.113.7"),  # due proxy in catena
    (1, ["192.168.0.26"], "192.168.0.26", None, "192.168.0.26"),  # intestazione assente
    (1, ["192.168.0.26"], "192.168.0.26", "spazzatura", "192.168.0.26"),
])  # fmt: skip
def test_ip_client(settings, count, fidati, remoto, xff, atteso):
    settings.PROXY_COUNT, settings.PROXY_FIDATI = count, fidati
    assert ip_client(_r(remoto, xff)) == atteso


def test_usato_da_axes_e_registro(settings):
    settings.PROXY_COUNT, settings.PROXY_FIDATI = 1, ["192.168.0.26"]
    assert ip_richiesta(_r("192.168.0.26", "203.0.113.7")) == "203.0.113.7"
