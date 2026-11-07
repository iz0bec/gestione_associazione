# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Fixture comuni dei test
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import pytest
from django.contrib.auth.models import Group


@pytest.fixture
def crea_utente(db, django_user_model):
    def _crea(username="mario", ruoli=(), **extra):
        utente = django_user_model.objects.create_user(
            username=username,
            email=f"{username}@example.org",
            password="Password-di-prova-123",
            **extra,
        )
        for ruolo in ruoli:
            utente.groups.add(Group.objects.get(name=ruolo))
        return utente

    return _crea


@pytest.fixture
def client_ruolo(client, crea_utente):
    """Client autenticato con i ruoli indicati: client_ruolo("Segretario")."""

    def _client(*ruoli, username="operatore"):
        utente = crea_utente(username=username, ruoli=ruoli)
        client.force_login(utente)
        client.utente = utente
        return client

    return _client
