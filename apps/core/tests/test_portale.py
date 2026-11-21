# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test del generatore del portale dei servizi (scripts/portale/genera_portale.py):
# *              servizi e recapiti dalle schede dei gestionali, esclusioni, dati di riserva.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import importlib.util
import json
from pathlib import Path

import pytest

PERCORSO = Path(__file__).resolve().parents[3] / "scripts" / "portale" / "genera_portale.py"


@pytest.fixture
def portale():
    spec = importlib.util.spec_from_file_location("genera_portale", PERCORSO)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


SCHEDA = {
    "nome": "ANCR Sezione di Ruoti",
    "servizi": {"gestionale": "https://ruoti.example.org/", "iscrizione": None,
                "area_soci": "https://ruoti.example.org/area/accesso/", "presentazione": None},
    "recapiti": {"indirizzo": "Via Roma 1", "cap": "85056", "comune": "Ruoti", "provincia": "PZ",
                 "telefono": "0971 123456", "email": "ruoti@example.org", "pec": "",
                 "sito_web": "https://ruoti.example.org/sito/"},
}  # fmt: skip
CONFIG = {
    "titolo": "Servizi", "ente": "ASSOCIAZIONE", "intestazione": "Federazione",
    "senza_recapiti": "Recapiti tramite la Federazione",
    "livelli": [{"titolo": "Sezioni", "gruppi": [{"titolo": "Provincia", "voci": [
        {"nome": "Sezione di Ruoti", "gestionale": "https://ruoti.example.org"},
        {"nome": "Sezione di Genzano", "gestionale": "https://genzano.example.org",
         "escludi": ["email"]},
        {"nome": "Sede nazionale", "collegamenti": [{"testo": "Sito", "url": "https://n.example"}]},
    ]}]}],
}  # fmt: skip


def test_pagina_dai_dati_dei_gestionali(portale):
    genzano = {"servizi": {"gestionale": "https://genzano.example.org/"},
               "recapiti": {"email": "privato@gmail.com", "comune": "Genzano"}}  # fmt: skip
    html = portale.pagina(CONFIG, {"https://ruoti.example.org": SCHEDA,
                                   "https://genzano.example.org": genzano})  # fmt: skip
    assert "Via Roma 1 — 85056 Ruoti (PZ)" in html and 'href="tel:+390971123456"' in html
    assert 'href="https://ruoti.example.org/area/accesso/"' in html and "Area soci" in html
    assert "Iscrizione online" not in html.split("Guida ai servizi")[0]  # spenta a Ruoti
    assert ">ruoti.example.org/sito</a>" in html
    assert "privato@gmail.com" not in html  # escluso dalla configurazione
    assert html.count("Recapiti tramite la Federazione") == 1  # Genzano, senza altri recapiti
    assert 'href="https://n.example"' in html


def test_testi_dei_gestionali_neutralizzati(portale):
    cattiva = {"recapiti": {"indirizzo": "<script>x</script>", "comune": "A"}}
    html = portale.pagina(CONFIG, {"https://ruoti.example.org": cattiva})
    assert "<script>x" not in html and "&lt;script&gt;" in html


def test_dati_di_riserva_se_non_risponde(portale, tmp_path, monkeypatch):
    cache = tmp_path / "cache.json"
    cache.write_text(json.dumps({"https://ruoti.example.org": SCHEDA}))

    def giu(url):
        raise OSError("connessione rifiutata")

    monkeypatch.setattr(portale, "leggi_scheda", giu)
    lette, problemi = portale.schede(["https://ruoti.example.org"], cache)
    assert lette["https://ruoti.example.org"]["nome"] == "ANCR Sezione di Ruoti"
    assert "connessione rifiutata" in problemi[0]


def test_solo_indirizzi_web(portale):
    with pytest.raises(ValueError):
        portale.leggi_scheda("file:///etc/passwd")


def test_colori_in_un_file_senza_stili_in_linea(portale):
    html = portale.pagina(CONFIG, {})
    assert "<style" not in html and 'href="colori.css"' in html
    css = portale.colori_css({"colori": {"testata": "#112233"}, "sfondo": "foto.jpg"})
    assert "--testata: #112233" in css and 'url("foto.jpg")' in css
    with pytest.raises(ValueError):
        portale.colori_css({"colori": {"accento": "red;}body{display:none"}})
