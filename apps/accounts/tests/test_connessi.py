# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test degli utenti connessi (ultima attività, uscita, elenco).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import Utente

pytestmark = pytest.mark.django_db


def test_attivita_e_uscita(client_ruolo):
    c = client_ruolo("Segretario")
    c.get("/")
    u = Utente.objects.get(pk=c.utente.pk)
    assert u.connesso
    prima = u.ultima_attivita
    c.get("/")  # entro il minuto: nessuna nuova scrittura
    assert Utente.objects.get(pk=u.pk).ultima_attivita == prima
    c.post("/account/logout/")
    assert Utente.objects.get(pk=u.pk).ultima_attivita is None


def test_elenco_dei_connessi(client_ruolo, crea_utente):
    from django.test import Client

    altro = Client()
    altro.force_login(crea_utente("mario", ruoli=["Segretario"]))
    altro.get("/")
    admin = client_ruolo("Amministratore di sistema")
    Utente.objects.create(username="vecchio", email="v@example.org",
                          ultima_attivita=timezone.now() - timedelta(hours=1))  # fmt: skip
    pagina = admin.get("/sistema/utenti/").content.decode()
    assert "Connessi ora: 1" in pagina and "connesso ora" in pagina  # mario
    assert "Connessi ora: 2" in admin.get("/sistema/utenti/").content.decode()  # e ora l'admin
    pagina = admin.get("/sistema/utenti/?stato=connessi").content.decode()
    assert "mario" in pagina and "vecchio" not in pagina
