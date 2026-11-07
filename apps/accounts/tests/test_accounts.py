# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test di autenticazione e ruoli
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import pytest
from django.contrib.auth.models import Group

from apps.accounts.ruoli import RUOLI


@pytest.mark.django_db
class TestRuoli:
    def test_tutti_i_ruoli_esistono_con_i_permessi(self):
        for nome, permessi in RUOLI.items():
            gruppo = Group.objects.get(name=nome)
            assert gruppo.permissions.count() == len(set(permessi))

    def test_permessi_effettivi(self, crea_utente):
        consigliere = crea_utente("c", ruoli=["Consigliere"])
        segretario = crea_utente("s", ruoli=["Segretario"])
        assert consigliere.has_perm("anagrafica.view_soggetto")
        assert not consigliere.has_perm("anagrafica.change_soggetto")
        assert segretario.has_perm("anagrafica.esporta_soggetti")


@pytest.mark.django_db
class TestAccesso:
    def test_registrazione_libera_chiusa(self, client):
        r = client.post(
            "/account/signup/",
            {
                "username": "x",
                "email": "x@x.it",
                "password1": "Abcdef-12345!",
                "password2": "Abcdef-12345!",
            },
        )
        from django.contrib.auth import get_user_model

        assert not get_user_model().objects.filter(username="x").exists()
        assert r.status_code in (200, 403, 404)

    def test_login_con_email(self, client, crea_utente):
        crea_utente("luigi")
        r = client.post(
            "/account/login/", {"login": "luigi@example.org", "password": "Password-di-prova-123"}
        )
        assert r.status_code == 302

    def test_blocco_dopo_tentativi_falliti(self, client, crea_utente):
        crea_utente("bersaglio")
        risposte = [
            client.post("/account/login/", {"login": "bersaglio", "password": "sbagliata"})
            for _ in range(5)
        ]
        # il quinto errore fa scattare il blocco di django-axes
        assert [r.status_code for r in risposte] == [200, 200, 200, 200, 429]
        assert "bloccato" in risposte[-1].content.decode().lower()
        # durante il blocco anche la password giusta non fa entrare
        # (risponde prima il limite di tentativi di allauth, poi axes)
        r = client.post(
            "/account/login/", {"login": "bersaglio", "password": "Password-di-prova-123"}
        )
        assert r.status_code != 302
        assert "_auth_user_id" not in client.session
        assert "troppi tentativi" in r.content.decode().lower()

    def test_password_corta_rifiutata(self):
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError

        with pytest.raises(ValidationError):
            validate_password("Corta-1")
