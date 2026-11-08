# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test della ricerca globale (risultati secondo permessi e sezioni)
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import pytest

from apps.anagrafica.models import Soggetto
from apps.core import ricerca
from apps.protocollo import servizi as protocollo
from apps.soci import servizi as soci
from apps.soci.models import Sezione, TipologiaSocio

pytestmark = pytest.mark.django_db


@pytest.fixture
def dati(crea_utente):
    segr = crea_utente("segr", ruoli=["Segretario"])
    nord = Sezione.objects.create(codice="N", nome="Nord", comune="Nordville")
    sud = Sezione.objects.create(codice="S", nome="Sud", comune="Sudville")
    ordinario = TipologiaSocio.objects.get(nome="Ordinario")
    a = soci.ammetti_socio(Soggetto.objects.create(cognome="Garibaldi", nome="Anita"), ordinario,
                           segr, sezione=nord)  # fmt: skip
    soci.ammetti_socio(Soggetto.objects.create(cognome="Garibaldi", nome="Menotti"), ordinario,
                       segr, sezione=sud)  # fmt: skip
    p = protocollo.registra_protocollo(
        {"direzione": "entrata", "oggetto": "Lettera della famiglia Garibaldi"},
        [{"ruolo": "mittente", "descrizione": "Famiglia Garibaldi"}], segr)  # fmt: skip
    riservato = protocollo.registra_protocollo(
        {"direzione": "entrata", "oggetto": "Garibaldi: questione riservata", "riservato": True},
        [{"ruolo": "mittente", "descrizione": "Avvocato"}], segr)  # fmt: skip
    return {"nord": nord, "socio": a, "protocollo": p, "riservato": riservato}


def _titoli(gruppi, nome):
    g = next((g for g in gruppi if g.titolo == nome), None)
    return [v.titolo for v in g.voci] if g else None


def test_segretario_trova_tutto(dati, crea_utente):
    gruppi = ricerca.cerca(crea_utente("s2", ruoli=["Segretario"]), "garibaldi")
    assert {g.titolo for g in gruppi} >= {"Anagrafica", "Soci", "Protocollo"}
    assert len(_titoli(gruppi, "Soci")) == 2
    assert len(_titoli(gruppi, "Protocollo")) == 2  # anche il riservato
    numero = ricerca.cerca(crea_utente("s3", ruoli=["Segretario"]), str(dati["socio"].numero))
    assert "Garibaldi Anita" in (_titoli(numero, "Soci") or [])


def test_limiti_dei_permessi(dati, crea_utente):
    consigliere = ricerca.cerca(crea_utente("c", ruoli=["Consigliere"]), "garibaldi")
    assert len(_titoli(consigliere, "Protocollo")) == 1  # niente riservati
    presidente_sezione = crea_utente("ps", ruoli=["Presidente di sezione"])
    presidente_sezione.sezioni.add(dati["nord"])
    gruppi = ricerca.cerca(presidente_sezione, "garibaldi")
    assert _titoli(gruppi, "Soci") == ["Garibaldi Anita"]  # solo la sua sezione
    assert _titoli(gruppi, "Protocollo") is None
    assert ricerca.cerca(crea_utente("x"), "garibaldi") == []


def test_pagina(dati, client_ruolo):
    c = client_ruolo("Segretario")
    assert 'action="/cerca/"' in c.get("/").content.decode()
    testo = c.get("/cerca/?q=garibaldi+anita").content.decode()
    assert "Garibaldi Anita" in testo and "Menotti" not in testo
    assert "almeno due caratteri" in c.get("/cerca/?q=g").content.decode()
    assert "Nessun risultato" in c.get("/cerca/?q=inesistente").content.decode()
