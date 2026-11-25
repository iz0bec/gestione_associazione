# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test della progettazione (P4a): quadro, indicatori, cronoprogramma con le
# *              dipendenze, partner, piano economico con i controlli dei limiti del bando.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.anagrafica.models import Soggetto
from apps.progetti import piano, servizi
from apps.progetti.forms import AttivitaForm, BandoForm, ProgettoForm
from apps.progetti.models import Attivita, FonteFinanziamento, Partner, VoceCosto
from apps.progetti.views import gantt

pytestmark = pytest.mark.django_db
OGGI = date.today()


@pytest.fixture
def utente(crea_utente):
    return crea_utente("presidente", ruoli=["Presidente"])


@pytest.fixture
def progetto(utente):
    form = ProgettoForm(data={"titolo": "Memoria a scuola", "sintesi": "Incontri",
                              "responsabile": utente.pk})  # fmt: skip
    assert form.is_valid()
    return servizi.crea_progetto(form, utente)


def _bando(utente, **extra):
    dati = {"titolo": "Bando cultura", "scadenza": OGGI + timedelta(30)} | extra
    form = BandoForm(data=dati)
    assert form.is_valid(), form.errors
    return servizi.crea_bando(form, utente)


def _voce(progetto, categoria, importo, quantita=1):
    return VoceCosto.objects.create(progetto=progetto, categoria=categoria, descrizione=categoria,
                                    quantita=quantita, costo_unitario=Decimal(importo))  # fmt: skip


def _fonte(progetto, tipo, importo):
    FonteFinanziamento.objects.create(progetto=progetto, tipo=tipo, importo=Decimal(importo))


class TestPiano:
    def test_totali_e_bilanciamento(self, progetto):
        _voce(progetto, "servizi", "100.00", 10)  # 1000
        _voce(progetto, "volontariato", "15.00", 20)  # 300 in natura
        progetto.spese_generali = Decimal("10")
        progetto.save()
        p = piano.calcola(progetto)
        assert (p.diretti, p.spese_generali, p.natura, p.totale_costi) == (
            Decimal("1000.00"), Decimal("100.00"), Decimal("300.00"), Decimal("1400.00"),
        )  # fmt: skip
        assert p.controlli[0].esito == "errore" and "Mancano coperture" in p.controlli[0].testo
        _fonte(progetto, "contributo", "1000")
        Partner.objects.create(progetto=progetto, cofinanziamento=Decimal("100"),
                               soggetto=Soggetto.objects.create(tipo="ente", denominazione="Comune"))  # fmt: skip
        p = piano.calcola(progetto)
        assert p.totale_fonti == Decimal("1400.00") and p.controlli[0].esito == "ok"
        assert p.cofinanziamento == Decimal("400.00")

    def test_limiti_del_bando(self, utente, progetto):
        b = _bando(utente, importo_massimo="800", cofinanziamento="30",
                   spese_generali_massime="7", natura_massima="50")  # fmt: skip
        servizi.imposta_limite(b, utente, categoria="beni", percentuale_massima=Decimal("20"))
        servizi.candida(progetto, b, utente)
        progetto.refresh_from_db()
        _voce(progetto, "beni", "500")
        _voce(progetto, "servizi", "500")
        _voce(progetto, "volontariato", "300")
        progetto.spese_generali = Decimal("10")
        progetto.save()
        _fonte(progetto, "contributo", "900")
        _fonte(progetto, "proprio", "200")
        p = piano.calcola(progetto)
        testi = {c.testo.split(" ")[0]: c.esito for c in p.controlli}
        assert p.totale_costi == Decimal("1400.00") and p.differenza == 0
        assert testi["Il"] == "errore"  # contributo 900 > 800
        assert testi["Cofinanziamento"] == "ok"  # 500/1400 = 35,71% ≥ 30%
        assert testi["Spese"] == "errore"  # 10% > 7%
        assert testi["Beni"] == "errore"  # 500/1400 = 35,71% > 20%
        assert testi["In"] == "errore"  # 300/500 = 60% > 50%

    def test_senza_bando(self, progetto):
        _voce(progetto, "servizi", "10")
        assert piano.calcola(progetto).controlli[-1].esito == "avviso"


class TestCronoprogramma:
    def test_dipendenze_e_date(self, progetto):
        a = Attivita.objects.create(progetto=progetto, titolo="Preparazione",
                                    inizio=OGGI, fine=OGGI + timedelta(10))  # fmt: skip
        form = AttivitaForm(data={"titolo": "Incontri", "inizio": OGGI + timedelta(5),
                                  "fine": OGGI + timedelta(20), "dopo": a.pk}, progetto=progetto)  # fmt: skip
        assert not form.is_valid() and "inizio" in form.errors
        form = AttivitaForm(data={"titolo": "Incontri", "inizio": OGGI + timedelta(3),
                                  "fine": OGGI + timedelta(1)}, progetto=progetto)  # fmt: skip
        assert not form.is_valid() and "fine" in form.errors

    def test_gantt(self, progetto):
        a = Attivita.objects.create(progetto=progetto, titolo="A", inizio=OGGI,
                                    fine=OGGI + timedelta(9))  # fmt: skip
        Attivita.objects.create(progetto=progetto, titolo="B", inizio=OGGI + timedelta(10),
                                fine=OGGI + timedelta(19), dopo=a)  # fmt: skip
        g = gantt(progetto.attivita.all())
        assert [r["x"] for r in g["righe"]] == [0, 500.0] and g["righe"][0]["w"] == 500.0
        assert len(g["collegamenti"]) == 1

    def test_calendario(self, utente, progetto):
        from apps.calendario import servizi as calendario

        Attivita.objects.create(progetto=progetto, titolo="Mostra", inizio=OGGI,
                                fine=OGGI + timedelta(3))  # fmt: skip
        titoli = [e.titolo for e in calendario.eventi(utente, dal=OGGI, al=OGGI + timedelta(5))]
        assert f"Mostra ({progetto.codice})" in titoli


class TestPagine:
    def test_sezioni_e_blocco_dopo_candidatura(self, client_ruolo, utente):
        c = client_ruolo("Segretario")
        form = ProgettoForm(data={"titolo": "Viaggio", "sintesi": "Redipuglia",
                                  "responsabile": c.utente.pk})  # fmt: skip
        assert form.is_valid()
        p = servizi.crea_progetto(form, c.utente)
        url = reverse("progetti:progettazione", args=[p.pk, "piano"])
        r = c.post(url, {"azione": "salva_voce", "voce-categoria": "viaggi",
                         "voce-descrizione": "Pullman", "voce-quantita": "1",
                         "voce-costo_unitario": "1200"}, follow=True)  # fmt: skip
        assert "Pullman" in r.content.decode() and "Mancano coperture" in r.content.decode()
        r = c.post(reverse("progetti:progettazione", args=[p.pk, "quadro"]),
                   {"azione": "salva_quadro", "quadro-obiettivo_generale": "Trasmettere la memoria",
                    "quadro-destinatari": "Studenti", "quadro-territorio": "Potenza"})  # fmt: skip
        p.refresh_from_db()
        assert p.obiettivo_generale == "Trasmettere la memoria"
        ente = Soggetto.objects.create(tipo="ente", denominazione="Istituto")
        dati = {"azione": "salva_partner", "partner-soggetto": ente.pk, "partner-ruolo": "partner"}
        c.post(reverse("progetti:progettazione", args=[p.pk, "partner"]), dati)
        r = c.post(reverse("progetti:progettazione", args=[p.pk, "partner"]), dati, follow=True)
        assert "Già presente" in r.content.decode() or p.partner.count() == 1
        for sezione in ("quadro", "cronoprogramma", "partner", "piano"):
            assert c.get(reverse("progetti:progettazione", args=[p.pk, sezione])).status_code == 200
        servizi.candida(p, _bando(utente), utente)
        r = c.post(url, {"azione": "salva_voce", "voce-categoria": "viaggi",
                         "voce-descrizione": "Pranzo", "voce-quantita": "1",
                         "voce-costo_unitario": "300"}, follow=True)  # fmt: skip
        assert "Si modifica solo in progettazione" in r.content.decode()
        assert p.voci.count() == 1

    def test_consigliere_solo_lettura(self, client_ruolo, progetto):
        c = client_ruolo("Consigliere")
        url = reverse("progetti:progettazione", args=[progetto.pk, "piano"])
        assert c.get(url).status_code == 200
        assert (
            c.post(url, {"azione": "salva_spese", "spese-spese_generali": "5"}).status_code == 404
        )
