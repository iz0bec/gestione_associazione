# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test della scadenza dei mandati: calcolo, cruscotto e calendario.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from datetime import date, timedelta

import pytest

from apps.anagrafica.models import Soggetto
from apps.calendario import servizi as calendario
from apps.organi import servizi
from apps.organi.models import Organo

pytestmark = pytest.mark.django_db


@pytest.fixture
def consiglio():
    return Organo.objects.get(sigla="CD")


def _nomina(organo, cognome, ruolo, dal, utente):
    persona = Soggetto.objects.create(cognome=cognome, nome="Prova")
    return servizi.nomina(organo, persona, ruolo, dal, utente)


def test_scadenza_e_preavviso(consiglio, crea_utente):
    u = crea_utente("segr", ruoli=["Segretario"])
    oggi = date(2026, 11, 17)
    presidente = _nomina(consiglio, "Rossi", "presidente", date(2022, 12, 1), u)
    _nomina(consiglio, "Verdi", "tesoriere", date(2024, 3, 1), u)
    assert presidente.scadenza_mandato is None  # durata non indicata
    assert servizi.mandati_in_scadenza(oggi) == []
    consiglio.durata_mandato, consiglio.preavviso_mandato = 4, 30
    consiglio.save()
    presidente.refresh_from_db()
    assert presidente.scadenza_mandato == date(2026, 12, 1)
    ((carica, scadenza, giorni),) = servizi.mandati_in_scadenza(oggi)  # il tesoriere scade nel 2028
    assert (carica, scadenza, giorni) == (presidente, date(2026, 12, 1), 14)
    assert servizi.mandati_in_scadenza(oggi + timedelta(days=30))[0][2] == -16  # scaduto, resta


def test_cruscotto_e_calendario(client_ruolo, consiglio):
    c = client_ruolo("Segretario")
    consiglio.durata_mandato = 4
    consiglio.save()
    dal = date.today().replace(year=date.today().year - 4) + timedelta(days=10)
    _nomina(consiglio, "Neri", "presidente", dal, c.utente)
    pagina = c.get("/").content.decode()
    assert "Mandati in scadenza" in pagina and "presidente Neri Prova" in pagina
    eventi = calendario.eventi(c.utente, dal=date.today(), al=date.today() + timedelta(days=30))
    assert any(e.categoria == "Mandati" and "Neri Prova" in e.titolo for e in eventi)
    assert "mandato fino al" in c.get(f"/organi/{consiglio.pk}/").content.decode()
