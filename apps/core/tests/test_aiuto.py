# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test dell'help in linea e della pagina delle informazioni
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import re

import pytest
from django.conf import settings

from apps.core import aiuto


def _link_aiuto(risposta):
    m = re.search(r'href="([^"]*)" title="Aiuto su questa pagina"', risposta.content.decode())
    return m.group(1)


@pytest.mark.django_db
class TestAiuto:
    def test_richiede_accesso(self, client):
        assert client.get("/aiuto/").status_code == 302

    def test_tutte_le_pagine_del_manuale(self, client_ruolo):
        client = client_ruolo("Consigliere")
        pagine = aiuto.elenco()
        assert len(pagine) >= 10
        for nome, titolo in pagine:
            testo = client.get(f"/aiuto/{nome}/").content.decode()
            assert titolo in testo
            assert ".md" not in re.sub(r"<code>.*?</code>", "", testo, flags=re.S)

    def test_pagina_inesistente(self, client_ruolo):
        client = client_ruolo("Consigliere")
        assert client.get("/aiuto/non-esiste/").status_code == 404
        with pytest.raises(Exception):  # noqa: B017 - nessun percorso fuori dal manuale
            aiuto.pagina("../sistema/backup")

    def test_aiuto_contestuale(self, client_ruolo):
        client = client_ruolo("Amministratore di sistema")
        assert _link_aiuto(client.get("/")) == "/aiuto/primi-passi/"
        assert _link_aiuto(client.get("/sistema/utenti/")) == "/aiuto/utenti/"
        assert _link_aiuto(client.get("/soci/sezioni/")) == "/aiuto/sistema/#sezioni"
        assert _link_aiuto(client.get("/aiuto/soci/")) == "/aiuto/"

    def test_collegamenti_fra_pagine(self, client_ruolo):
        testo = client_ruolo("Consigliere").get("/aiuto/").content.decode()
        assert 'href="/aiuto/soci/"' in testo

    def test_versione_e_crediti(self, client_ruolo):
        client = client_ruolo("Consigliere")
        barra = client.get("/").content.decode()
        assert f"v{settings.APP_VERSIONE}" in barra and settings.APP_AUTORE in barra
        testo = client.get("/informazioni/").content.decode()
        assert settings.APP_AUTORE in testo and "CC0 1.0" in testo
        assert "WeasyPrint" in testo and "Markdown" in testo


@pytest.mark.django_db
class TestMenuSistema:
    def _menu(self, client, url):
        testo = client.get(url).content.decode()
        return re.search(r'<div class="dropdown-menu( show)?" id="menu-sistema">', testo)

    def test_chiuso_fuori_e_aperto_dentro(self, client_ruolo):
        client = client_ruolo("Amministratore di sistema")
        assert self._menu(client, "/").group(1) is None
        assert self._menu(client, "/anagrafica/").group(1) is None
        for url in ("/sistema/utenti/", "/soci/sezioni/", "/sistema/backup/", "/organizzazione/"):
            assert self._menu(client, url).group(1) == " show", url

    def test_assente_senza_permessi(self, client_ruolo):
        assert self._menu(client_ruolo("Addetto protocollo"), "/") is None
