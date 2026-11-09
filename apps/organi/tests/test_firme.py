# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test delle firme in calce alle stampe (cariche alla data del documento)
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
from datetime import date

import pytest
from django.template import Context, Template

from apps.anagrafica.models import Soggetto
from apps.organi.firme import Firma, firme, in_carica_al
from apps.organi.models import Carica, Organo

pytestmark = pytest.mark.django_db


@pytest.fixture
def consiglio():
    return Organo.objects.get(sigla="CD")


def _carica(organo, cognome, ruolo, dal, al=None):
    persona = Soggetto.objects.create(cognome=cognome, nome="Mario", titolo="Cav.")
    return Carica.objects.create(organo=organo, soggetto=persona, ruolo=ruolo, dal=dal, al=al)


class TestServizio:
    def test_carica_alla_data_del_documento(self, consiglio):
        _carica(consiglio, "Vecchi", "presidente", date(2021, 1, 1), al=date(2025, 4, 13))
        _carica(consiglio, "Nuovi", "presidente", date(2025, 4, 13))
        assert in_carica_al("presidente", date(2024, 6, 1)).cognome == "Vecchi"
        assert in_carica_al("presidente", date(2025, 4, 13)).cognome == "Nuovi"
        assert in_carica_al("presidente", date(2020, 1, 1)) is None

    def test_organo_di_sezione_escluso(self, consiglio):
        from apps.soci.models import Sezione

        sezione = Sezione.objects.create(codice="S1", nome="Sezione di prova")
        locale = Organo.objects.create(
            nome="Direttivo di sezione", sigla="DS", tipo="consiglio", sezione=sezione
        )
        _carica(locale, "Locale", "presidente", date(2025, 1, 1))
        assert in_carica_al("presidente", date(2025, 6, 1)) is None
        assert in_carica_al("presidente", date(2025, 6, 1), sezione=sezione).cognome == "Locale"

    def test_vacante_senza_nome(self):
        assert firme("presidente") == [Firma("Il Presidente", "")]

    def test_alternativa_e_facoltativa(self, consiglio):
        _carica(consiglio, "Rossi", "presidente", date(2025, 1, 1))
        # ricevuta: firma il tesoriere, che manca -> il presidente
        assert firme("tesoriere|presidente") == [Firma("Il Presidente", "Cav. Mario Rossi")]
        # rendiconto: il tesoriere solo se c'è
        assert firme("tesoriere?", "presidente") == [Firma("Il Presidente", "Cav. Mario Rossi")]
        _carica(consiglio, "Bianchi", "tesoriere", date(2025, 1, 1))
        assert [f.qualifica for f in firme("tesoriere?", "presidente")] == [
            "Il Tesoriere",
            "Il Presidente",
        ]


class TestTag:
    def test_blocco_firme(self, consiglio):
        _carica(consiglio, "Rossi", "presidente", date(2025, 1, 1))
        html = Template('{% load firme %}{% firme "presidente" giorno=quando %}').render(
            Context({"quando": date(2025, 6, 1)})
        )
        assert "Il Presidente" in html and "Cav. Mario Rossi" in html and "spazio-firma" in html

    def test_prima_della_nomina_resta_vuota(self, consiglio):
        _carica(consiglio, "Rossi", "presidente", date(2025, 1, 1))
        html = Template('{% load firme %}{% firme "presidente" giorno=quando %}').render(
            Context({"quando": date(2024, 6, 1)})
        )
        assert "Il Presidente" in html and "Rossi" not in html
