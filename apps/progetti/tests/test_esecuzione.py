# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test dell'esecuzione (P5): imputazione dei movimenti di prima nota, consuntivo
# *              per voce, contributo incassato, ore di volontariato valorizzate, avanzamento,
# *              varianti al piano con la delibera, pagina.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.anagrafica.models import Soggetto
from apps.progetti import esecuzione, servizi
from apps.progetti.forms import ProgettoForm
from apps.progetti.models import Attivita, FonteFinanziamento, Progetto, VoceCosto

pytestmark = pytest.mark.django_db
OGGI = date.today()


@pytest.fixture
def utente(crea_utente):
    return crea_utente("tesoriere", ruoli=["Presidente", "Tesoriere"])


@pytest.fixture
def progetto(utente):
    form = ProgettoForm(data={"titolo": "Memoria a scuola", "sintesi": "Incontri",
                              "responsabile": utente.pk})  # fmt: skip
    assert form.is_valid()
    p = servizi.crea_progetto(form, utente)
    VoceCosto.objects.create(progetto=p, categoria="servizi", descrizione="Guide",
                             costo_unitario=Decimal("1000"))  # fmt: skip
    VoceCosto.objects.create(progetto=p, categoria="volontariato", descrizione="Volontari",
                             quantita=20, costo_unitario=Decimal("15"))  # fmt: skip
    FonteFinanziamento.objects.create(progetto=p, tipo="contributo", importo=Decimal("800"))
    servizi.cambia_stato(p, Progetto.Stato.IN_CORSO, utente)
    p.refresh_from_db()
    return p


def _movimento(utente, tipo, importo, descrizione="Fattura guide"):
    from apps.tesoreria import servizi as tesoreria
    from apps.tesoreria.models import Conto, Esercizio, Voce

    Esercizio.objects.get_or_create(anno=OGGI.year)
    conto = Conto.objects.first() or Conto.objects.create(nome="Cassa")
    voce = Voce.objects.filter(tipo=tipo, sottovoci__isnull=True).order_by("codice").first()
    return tesoreria.registra_movimento(
        {"data": OGGI, "tipo": tipo, "conto": conto, "importo": Decimal(importo),
         "descrizione": descrizione, "voce": voce}, utente,
    )  # fmt: skip


class TestCentroDiCosto:
    def test_imputa_e_consuntivo(self, utente, progetto):
        guide = progetto.voci.get(categoria="servizi")
        uscita = _movimento(utente, "uscita", "600")
        entrata = _movimento(utente, "entrata", "400", "Anticipo contributo")
        assert set(esecuzione.movimenti_imputabili(progetto)) == {uscita, entrata}
        esecuzione.imputa(progetto, uscita, utente, voce=guide)
        esecuzione.imputa(progetto, entrata, utente, contributo=True)
        assert not esecuzione.movimenti_imputabili(progetto)
        c = esecuzione.consuntivo(progetto)
        riga = c.righe[0]
        assert (riga.preventivo, riga.consuntivo, riga.scostamento, riga.percentuale) == (
            Decimal("1000.00"), Decimal("600.00"), Decimal("-400.00"), 60,
        )  # fmt: skip
        assert c.contributo_incassato == Decimal("400") and c.contributo_da_incassare == 400
        with pytest.raises(esecuzione.ErroreEsecuzione, match="già imputato"):
            esecuzione.imputa(progetto, uscita, utente)

    def test_controlli(self, utente, progetto):
        uscita = _movimento(utente, "uscita", "100")
        with pytest.raises(esecuzione.ErroreEsecuzione, match="non oltre|non superare"):
            esecuzione.imputa(progetto, uscita, utente, importo="150")
        volontari = progetto.voci.get(categoria="volontariato")
        with pytest.raises(esecuzione.ErroreEsecuzione, match="voce in denaro"):
            esecuzione.imputa(progetto, uscita, utente, voce=volontari)
        imp = esecuzione.imputa(progetto, uscita, utente, importo="40")
        assert imp.importo == Decimal("40") and imp.voce is None
        assert esecuzione.consuntivo(progetto).non_attribuiti == Decimal("40")

    def test_solo_in_esecuzione(self, utente):
        form = ProgettoForm(data={"titolo": "Idea", "sintesi": "x", "responsabile": utente.pk})
        assert form.is_valid()
        p = servizi.crea_progetto(form, utente)
        with pytest.raises(esecuzione.ErroreEsecuzione, match="non è in esecuzione"):
            esecuzione.imputa(p, _movimento(utente, "uscita", "10"), utente)


class TestVolontariato:
    def test_ore_valorizzate(self, utente, progetto):
        anna = Soggetto.objects.create(tipo="persona", cognome="Verdi", nome="Anna")
        esecuzione.registra_ore(progetto, utente, soggetto=anna, data=OGGI, ore=Decimal("3.5"))
        esecuzione.registra_ore(progetto, utente, soggetto=anna, data=OGGI, ore=Decimal("2"))
        c = esecuzione.consuntivo(progetto)
        assert c.ore == Decimal("5.5") and c.natura_consuntivo == 0  # senza tariffa
        progetto.tariffa_volontariato = Decimal("16")
        progetto.save()
        c = esecuzione.consuntivo(progetto)
        assert c.natura_consuntivo == Decimal("88.00") and c.natura_preventivo == Decimal("300.00")
        ente = Soggetto.objects.create(tipo="ente", denominazione="Comune")
        with pytest.raises(esecuzione.ErroreEsecuzione, match="persona"):
            esecuzione.registra_ore(progetto, utente, soggetto=ente, data=OGGI, ore=1)
        with pytest.raises(esecuzione.ErroreEsecuzione, match="future"):
            esecuzione.registra_ore(progetto, utente, soggetto=anna, data=OGGI + timedelta(1),
                                    ore=1)  # fmt: skip


class TestAvanzamentoEVarianti:
    def test_avanzamento(self, utente, progetto):
        a = Attivita.objects.create(progetto=progetto, titolo="Incontri", inizio=OGGI, fine=OGGI)
        x = progetto.indicatori.create(descrizione="Studenti", valore_atteso=200)
        esecuzione.segna_attivita(a, utente, completata=True)
        esecuzione.aggiorna_indicatore(x, utente, valore="150")
        av = esecuzione.avanzamento(progetto)
        assert (av["completate"], av["attivita"], av["media_indicatori"]) == (1, 1, 75)

    def test_variante_sblocca_il_piano(self, utente, progetto):
        assert not servizi.modificabile(progetto, "piano")
        v = esecuzione.apri_variante(progetto, utente, descrizione="Più guide")
        assert servizi.modificabile(progetto, "piano")
        assert not servizi.modificabile(progetto, "quadro")
        VoceCosto.objects.create(progetto=progetto, categoria="servizi", descrizione="Pullman",
                                 costo_unitario=Decimal("500"))  # fmt: skip
        with pytest.raises(esecuzione.ErroreEsecuzione, match="già una variante"):
            esecuzione.apri_variante(progetto, utente, descrizione="Altra")
        esecuzione.chiudi_variante(progetto, utente)
        v.refresh_from_db()
        assert v.piano_prima["totale_costi"] == "1300.00"
        assert v.piano_dopo["totale_costi"] == "1800.00"
        assert not servizi.modificabile(progetto, "piano")


class TestPagina:
    def test_pagina_e_azioni(self, client, utente, progetto):
        client.force_login(utente)
        url = reverse("progetti:esecuzione", args=[progetto.pk])
        uscita = _movimento(utente, "uscita", "250", "Stampa locandine")
        r = client.get(url)
        assert r.status_code == 200 and "Stampa locandine" in r.content.decode()
        r = client.post(url, {"azione": "imputa", "movimento": uscita.pk,
                              "voce": progetto.voci.get(categoria="servizi").pk}, follow=True)  # fmt: skip
        assert "Movimento imputato" in r.content.decode()
        r = client.post(url, {"azione": "apri_variante", "variante-descrizione": "Ritocco"})
        assert r["Location"].endswith("/progettazione/piano/")

    def test_consigliere_legge(self, client_ruolo, progetto):
        c = client_ruolo("Consigliere")
        url = reverse("progetti:esecuzione", args=[progetto.pk])
        assert c.get(url).status_code == 200
        assert c.post(url, {"azione": "chiudi_variante"}).status_code == 404
