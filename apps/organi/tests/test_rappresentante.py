# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test del rappresentante legale (anche esterno, per tutta la struttura)
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
from datetime import date

import pytest
from django.urls import reverse

from apps.anagrafica.models import Soggetto
from apps.organi import servizi
from apps.organi.firme import Firma, firme, legale_rappresentante, situazione_rappresentanza
from apps.organi.models import Carica, Organo, RappresentanteLegale
from apps.organi.servizi import OperazioneNonValida
from apps.soci.models import Sezione

pytestmark = pytest.mark.django_db

GIORNO = date(2026, 6, 1)


@pytest.fixture
def utente(crea_utente):
    return crea_utente("segretario", ruoli=["Segretario"])


@pytest.fixture
def sezione():
    return Sezione.objects.create(codice="S1", nome="Avigliano")


def _persona(cognome, titolo=""):
    return Soggetto.objects.create(cognome=cognome, nome="Mario", titolo=titolo)


def _presidente(organo, cognome, dal=date(2025, 1, 1)):
    return Carica.objects.create(
        organo=organo, soggetto=_persona(cognome), ruolo="presidente", dal=dal
    )


@pytest.fixture
def direttivo_locale(sezione):
    return Organo.objects.create(
        nome="Direttivo di sezione", sigla="DS", tipo="consiglio", sezione=sezione
    )


class TestRisoluzione:
    def test_senza_nomina_firma_il_presidente(self):
        _presidente(Organo.objects.get(sigla="CD"), "Rossi")
        assert legale_rappresentante(GIORNO) == Firma("Il Presidente", "Mario Rossi")

    def test_nomina_esterna_prevale_sul_presidente(self, utente):
        _presidente(Organo.objects.get(sigla="CD"), "Rossi")
        servizi.nomina_rappresentante(
            _persona("Landi", "Prof."), date(2025, 1, 1), utente,
            qualifica="Il Presidente nazionale",
        )  # fmt: skip
        assert legale_rappresentante(GIORNO) == Firma(
            "Il Presidente nazionale", "Prof. Mario Landi"
        )
        # le altre firme restano del presidente
        assert firme("presidente", giorno=GIORNO) == [Firma("Il Presidente", "Mario Rossi")]

    def test_tutta_la_struttura_vale_per_le_sezioni(self, utente, sezione, direttivo_locale):
        _presidente(direttivo_locale, "Locale")
        assert legale_rappresentante(GIORNO, sezione).nome == "Mario Locale"
        servizi.nomina_rappresentante(
            _persona("Landi"), date(2025, 1, 1), utente, tutta_la_struttura=True
        )
        assert legale_rappresentante(GIORNO, sezione).nome == "Mario Landi"
        assert firme("presidente", giorno=GIORNO, sezione=sezione)[0].nome == "Mario Locale"

    def test_nomina_solo_associazione_non_scavalca_il_presidente_locale(
        self, utente, sezione, direttivo_locale
    ):
        _presidente(direttivo_locale, "Locale")
        servizi.nomina_rappresentante(_persona("Landi"), date(2025, 1, 1), utente)
        assert legale_rappresentante(GIORNO, sezione).nome == "Mario Locale"

    def test_nomina_della_sezione_prevale(self, utente, sezione):
        servizi.nomina_rappresentante(
            _persona("Landi"), date(2025, 1, 1), utente, tutta_la_struttura=True
        )
        servizi.nomina_rappresentante(_persona("Proprio"), date(2025, 1, 1), utente,
                                      sezione=sezione)  # fmt: skip
        assert legale_rappresentante(GIORNO, sezione).nome == "Mario Proprio"

    def test_sezione_senza_presidente_ricade_sull_associazione(self, sezione):
        _presidente(Organo.objects.get(sigla="CD"), "Rossi")
        assert legale_rappresentante(GIORNO, sezione).nome == "Mario Rossi"

    def test_vacante(self):
        assert firme("rappresentante_legale", giorno=GIORNO) == [Firma("Il Legale rappresentante")]

    def test_alla_data_del_documento(self, utente):
        servizi.nomina_rappresentante(_persona("Vecchio"), date(2020, 1, 1), utente)
        servizi.nomina_rappresentante(_persona("Nuovo"), date(2026, 1, 1), utente)
        vecchio = RappresentanteLegale.objects.get(soggetto__cognome="Vecchio")
        assert vecchio.al == date(2026, 1, 1)
        assert legale_rappresentante(date(2025, 6, 1)).nome == "Mario Vecchio"
        assert legale_rappresentante(GIORNO).nome == "Mario Nuovo"

    def test_situazione(self, utente, sezione):
        servizi.nomina_rappresentante(
            _persona("Landi"), date(2025, 1, 1), utente, tutta_la_struttura=True
        )
        righe = situazione_rappresentanza(GIORNO)
        assert righe[0]["sezione"] is None and righe[0]["origine"] == "nomina"
        assert {r["origine"] for r in righe[1:]} == {"struttura"}


class TestRegole:
    def test_periodi_sovrapposti(self, utente):
        servizi.nomina_rappresentante(_persona("A"), date(2025, 1, 1), utente)
        with pytest.raises(OperazioneNonValida):
            servizi.nomina_rappresentante(_persona("B"), date(2025, 1, 1), utente)

    def test_struttura_solo_per_associazione(self, utente, sezione):
        with pytest.raises(OperazioneNonValida):
            servizi.nomina_rappresentante(
                _persona("A"), date(2025, 1, 1), utente, sezione=sezione,
                tutta_la_struttura=True,
            )  # fmt: skip

    def test_modifica(self, utente):
        n = servizi.nomina_rappresentante(_persona("A"), date(2025, 1, 1), utente)
        servizi.modifica_rappresentante(
            n, utente, qualifica="Il Presidente nazionale", dal=date(2025, 1, 1),
            al=date(2026, 1, 1),
        )  # fmt: skip
        n.refresh_from_db()
        assert n.qualifica == "Il Presidente nazionale" and n.al == date(2026, 1, 1)
        with pytest.raises(OperazioneNonValida):
            servizi.modifica_rappresentante(n, utente, qualifica="X", dal=date(2025, 1, 1),
                                            al=date(2024, 1, 1))  # fmt: skip


class TestViste:
    def test_pagina_e_nomina(self, client_ruolo):
        client = client_ruolo("Segretario")
        persona = _persona("Landi", "Prof.")
        r = client.post(
            reverse("organi:rappresentante_nuovo"),
            {"soggetto": persona.pk, "qualifica": "Il Presidente nazionale",
             "dal": "2025-01-01", "tutta_la_struttura": "on"},
        )  # fmt: skip
        assert r.status_code == 302
        n = RappresentanteLegale.objects.get()
        assert n.tutta_la_struttura and n.sezione is None
        pagina = client.get(reverse("organi:rappresentanti"))
        assert pagina.status_code == 200 and "Prof. Mario Landi" in pagina.content.decode()

    def test_riepilogo_gdpr_firmato_dal_rappresentante(self, utente):
        from django.template.loader import render_to_string
        from django.utils import timezone

        from apps.core.models import Organizzazione

        servizi.nomina_rappresentante(
            _persona("Landi", "Prof."), date(2025, 1, 1), utente,
            qualifica="Il Presidente nazionale", tutta_la_struttura=True,
        )  # fmt: skip
        html = render_to_string(
            "anagrafica/pdf/dati_personali.html",
            {"soggetto": _persona("Interessato"), "dati": {}, "adesso": timezone.localtime(),
             "organizzazione": Organizzazione.corrente(), "sezione": None},
        )  # fmt: skip
        assert "Il Presidente nazionale" in html and "Prof. Mario Landi" in html
