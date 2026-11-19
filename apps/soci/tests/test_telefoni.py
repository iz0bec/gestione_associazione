# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test di telefono e cellulare negli scambi: niente doppioni né pezzi troncati,
# *              confronto per cifre, pulizia dei dati già raddoppiati (migrazione).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import importlib

import pytest
from django.apps import apps as django_apps

from apps.anagrafica.models import Soggetto
from apps.soci import allineamento, importazione

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(("valori", "atteso"), [
    (("3282713339", "3282713339"), ("", "3282713339")),
    (("", "3282713339, 3282713339, 328271"), ("", "3282713339")),
    (("0971 123456", "+39 333 1234567, 3331234567"), ("0971 123456", "+39 333 1234567")),
    (("348 2917525", "348-2917525"), ("", "348 2917525")),
])  # fmt: skip
def test_separazione_senza_doppioni(valori, atteso):
    assert importazione._telefoni(*valori) == atteso


def test_confronto_per_cifre():
    p = Soggetto(cognome="Rossi", telefono="3331234567", cellulare="348 2917525")
    d = {"cellulare": "3482917525", "telefono": ""}
    assert not importazione._diverso(p, "cellulare", d)
    d = {"cellulare": "3331234567, 3482917525", "telefono": ""}
    assert not importazione._diverso(p, "cellulare", d)
    assert importazione._diverso(p, "cellulare", {"cellulare": "3209999999"})


def test_verifica_non_propone_numeri_gia_presenti(crea_utente):
    from apps.soci import servizi
    from apps.soci.models import Sezione, TipologiaSocio

    utente = crea_utente("capo", ruoli=["Amministratore di sistema"])
    p = Soggetto.objects.create(cognome="Rossi", nome="Mario", telefono="3331234567")
    servizi.ammetti_socio(p, TipologiaSocio.objects.get(nome="Ordinario"), utente)
    remota = {"codice_fiscale": "", "cognome": "Rossi", "nome": "Mario", "telefono": "",
              "cellulare": "333 123 4567", "tipologia": "Ordinario", "data_iscrizione": "",
              "stato_socio": "attivo", "tessere": [], "modificato_il": ""}  # fmt: skip
    proposta = allineamento.confronta([remota], Sezione.predefinita(), da_sezione=False)
    assert proposta["voci"][0]["stato"] == "invariato", proposta["voci"]


def test_migrazione_ripulisce_solo_i_doppioni():
    migrazione = importlib.import_module("apps.anagrafica.migrations.0010_telefoni_senza_doppioni")
    doppio = Soggetto.objects.create(cognome="A", cellulare="3282713339, 3282713339, 328271")
    incrociato = Soggetto.objects.create(cognome="B", telefono="3331234567",
                                         cellulare="333 1234567")  # fmt: skip
    pulito = Soggetto.objects.create(cognome="C", telefono="0971 123456 / 3331112222")
    migrazione.ripulisci(django_apps, None)
    for s in (doppio, incrociato, pulito):
        s.refresh_from_db()
    assert (doppio.telefono, doppio.cellulare) == ("", "3282713339")
    assert (incrociato.telefono, incrociato.cellulare) == ("", "333 1234567")
    assert pulito.telefono == "0971 123456 / 3331112222"  # nulla da togliere: invariato


@pytest.mark.parametrize(("qui", "file", "diverso"), [
    ("San Severo (FG)", "San Severo", False),
    ("San Severo", "SAN SEVERO (FG)", False),
    ("Ruoti (PZ)", "Potenza", True),
])  # fmt: skip
def test_luogo_di_nascita_senza_provincia(qui, file, diverso):
    p = Soggetto(cognome="Bulso", luogo_nascita=qui)
    assert importazione._diverso(p, "luogo_nascita", {"luogo_nascita": file}) is diverso
