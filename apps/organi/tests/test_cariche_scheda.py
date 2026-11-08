# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Cariche sociali mostrate nella scheda del socio e in anagrafica
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from datetime import date

import pytest

from apps.anagrafica.models import Soggetto
from apps.organi.models import Carica, Organo, cariche_di
from apps.soci import servizi
from apps.soci.models import TipologiaSocio


@pytest.fixture
def socio_presidente(crea_utente):
    utente = crea_utente("seg", ruoli=["Segretario"])
    s = Soggetto.objects.create(tipo="persona", cognome="Rossi", nome="Mario")
    socio = servizi.ammetti_socio(s, TipologiaSocio.objects.get(nome="Ordinario"), utente)
    organo, _ = Organo.objects.get_or_create(nome="Consiglio di prova", defaults={"sigla": "CP"})
    Carica.objects.create(organo=organo, soggetto=s, ruolo="consigliere",
                          dal=date(2018, 1, 1), al=date(2021, 12, 31))  # fmt: skip
    Carica.objects.create(organo=organo, soggetto=s, ruolo="presidente", dal=date(2022, 1, 1))
    return socio


@pytest.mark.django_db
class TestCaricheNellaScheda:
    def test_ordine_in_corso_prima(self, socio_presidente):
        cariche = cariche_di(socio_presidente.soggetto)
        assert [c.ruolo for c in cariche] == ["presidente", "consigliere"]

    def test_scheda_socio(self, client_ruolo, socio_presidente):
        testo = client_ruolo("Consigliere").get(f"/soci/{socio_presidente.pk}/").content.decode()
        assert "Presidente · CP" in testo  # etichetta in testa
        assert "Cariche sociali" in testo and "conclusa" in testo and "dal 01/01/2018" in testo

    def test_scheda_anagrafica(self, client_ruolo, socio_presidente):
        r = client_ruolo("Consigliere").get(f"/anagrafica/{socio_presidente.soggetto.pk}/")
        assert "Cariche sociali" in r.content.decode()

    def test_senza_cariche_nessuna_sezione(self, client_ruolo, crea_utente):
        s = Soggetto.objects.create(tipo="persona", cognome="Bianchi")
        socio = servizi.ammetti_socio(s, TipologiaSocio.objects.get(nome="Ordinario"),
                                      crea_utente("x"))  # fmt: skip
        assert (
            "Cariche sociali"
            not in client_ruolo("Consigliere").get(f"/soci/{socio.pk}/").content.decode()
        )
