# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test della candidatura (P4b): sezioni (predefinite o del bando), testi composti dai
# *              dati del progetto e riusati, verifica, PDF ed Excel, lettere dai modelli di
# *              stampa, protocollo in uscita della candidatura.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO

import pytest
from django.urls import reverse

from apps.anagrafica.models import Soggetto
from apps.progetti import proposta, servizi
from apps.progetti.forms import BandoForm, ProgettoForm
from apps.progetti.models import (
    Attivita,
    FonteFinanziamento,
    Obiettivo,
    Partner,
    TestoSezione,
    VoceCosto,
)

pytestmark = pytest.mark.django_db
OGGI = date.today()


@pytest.fixture(autouse=True)
def _media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def utente(crea_utente):
    return crea_utente("presidente", ruoli=["Presidente", "Addetto protocollo"])


def _progetto(utente, titolo="Memoria a scuola"):
    form = ProgettoForm(data={"titolo": titolo, "sintesi": "Incontri", "responsabile": utente.pk})
    assert form.is_valid()
    return servizi.crea_progetto(form, utente)


def _bando(utente, **extra):
    form = BandoForm(data={"titolo": "Bando cultura", "scadenza": OGGI + timedelta(30)} | extra)
    assert form.is_valid(), form.errors
    return servizi.crea_bando(form, utente)


def _completo(utente):
    """Un progetto con quadro, attività, partner, piano in pari e tutte le sezioni scritte."""
    p = _progetto(utente)
    p.obiettivo_generale, p.destinatari, p.territorio = "Memoria", "300 studenti", "Potenza"
    p.save()
    Obiettivo.objects.create(progetto=p, testo="Far conoscere la Grande Guerra")
    p.indicatori.create(descrizione="Studenti coinvolti", valore_atteso=300, unita="studenti")
    Attivita.objects.create(progetto=p, titolo="Incontri", inizio=OGGI, fine=OGGI + timedelta(30))
    ente = Soggetto.objects.create(tipo="ente", denominazione="Istituto", pec="ic@pec.example.it")
    Partner.objects.create(progetto=p, soggetto=ente, lettera_ricevuta=True)
    VoceCosto.objects.create(progetto=p, categoria="servizi", descrizione="Guide",
                             costo_unitario=Decimal("1000"))  # fmt: skip
    FonteFinanziamento.objects.create(progetto=p, tipo="contributo", importo=Decimal("1000"))
    for s in proposta.prepara_sezioni(p):
        proposta.salva_testo(s, f"Testo di {s.titolo}", utente)
    return p


class TestSezioni:
    def test_schema_predefinito_e_del_bando(self, utente):
        p = _progetto(utente)
        assert len(proposta.prepara_sezioni(p)) == len(proposta.SCHEMA)
        assert len(proposta.prepara_sezioni(p)) == len(proposta.SCHEMA)  # rieseguibile
        b = _bando(utente)
        servizi.aggiungi_sezione_bando(b, utente, titolo="Partenariato", massimo="500")
        servizi.aggiungi_sezione_bando(b, utente, titolo="Piano di comunicazione")
        q = _progetto(utente, "Altro")
        q.bando = b
        q.save()
        sezioni = proposta.prepara_sezioni(q)
        assert [s.titolo for s in sezioni] == ["Partenariato", "Piano di comunicazione"]
        assert sezioni[0].chiave == "partenariato" and sezioni[0].massimo_caratteri == 500

    def test_componi_dai_dati(self, utente):
        p = _completo(utente)
        p.finalita.create(codice="g", titolo="Cultura sul combattente",
                          testo="La cultura sul combattente italiano")  # fmt: skip
        assert "g) La cultura sul combattente italiano" in proposta.componi(p, "finalita")
        assert "Obiettivo generale: Memoria" in proposta.componi(p, "obiettivi")
        assert "Incontri (" in proposta.componi(p, "attivita")
        assert "valore atteso 300 studenti" in proposta.componi(p, "monitoraggio")
        with pytest.raises(proposta.ErroreProposta):
            proposta.componi(_progetto(utente, "Vuoto"), "attivita")

    def test_riuso_e_lunghezza(self, utente):
        a = _completo(utente)
        b = _progetto(utente, "Nuovo")
        s = next(x for x in proposta.prepara_sezioni(b) if x.chiave == "contesto")
        simili = list(proposta.testi_simili(s))
        assert len(simili) == 1 and simili[0].progetto == a
        s.massimo_caratteri = 5
        s.testo = "troppo lungo"
        assert s.troppo_lungo


class TestVerificaEDocumenti:
    def test_verifica(self, utente):
        p = _progetto(utente)
        esiti = {v.esito for v in proposta.verifica(p)}
        assert "errore" in esiti
        c = _completo(utente)
        assert not [v for v in proposta.verifica(c) if v.esito == "errore"]

    def test_pdf_ed_excel(self, utente):
        from openpyxl import load_workbook

        p = _completo(utente)
        assert proposta.proposta_pdf(p).startswith(b"%PDF")
        ws = load_workbook(BytesIO(proposta.piano_excel(p))).active
        valori = [c.value for riga in ws.iter_rows() for c in riga]
        assert "TOTALE COSTI" in valori and 1000.0 in valori

    def test_protocolla(self, utente):
        p = _completo(utente)
        ente = Soggetto.objects.create(tipo="ente", denominazione="Fondazione",
                                       pec="bandi@pec.fondazione.it")  # fmt: skip
        b = _bando(utente, finanziatore=ente.pk)
        with pytest.raises(proposta.ErroreProposta, match="candidato"):
            proposta.protocolla(p, utente, mezzo="pec")
        servizi.candida(p, b, utente)
        p.refresh_from_db()
        prot = proposta.protocolla(p, utente, mezzo="pec")
        assert prot.direzione == "uscita" and prot.allegati.count() == 2
        assert prot.corrispondenti.get().indirizzo == "bandi@pec.fondazione.it"
        with pytest.raises(proposta.ErroreProposta, match="già"):
            proposta.protocolla(p, utente, mezzo="pec")


class TestPagine:
    def test_proposta_e_candidatura(self, client, utente):
        client.force_login(utente)
        p = _completo(utente)
        s = p.sezioni.get(chiave="obiettivi")
        r = client.post(reverse("progetti:proposta", args=[p.pk]),
                        {"sezione": s.pk, "azione": "componi"}, follow=True)  # fmt: skip
        assert "Obiettivo generale: Memoria" in r.content.decode()
        r = client.get(reverse("progetti:candidatura", args=[p.pk]))
        assert r.status_code == 200 and "Verifica prima dell" in r.content.decode()
        r = client.get(reverse("progetti:documento_candidatura", args=[p.pk, "piano.xlsx"]))
        assert r.status_code == 200 and "sandbox" in r["Content-Security-Policy"]
        assert (
            client.get(reverse("progetti:documento_candidatura", args=[p.pk, "x"])).status_code
            == 404
        )
        ente = Soggetto.objects.create(tipo="ente", denominazione="Ente", pec="e@pec.example.it")
        servizi.candida(p, _bando(utente, finanziatore=ente.pk), utente)
        r = client.post(reverse("progetti:azione_candidatura", args=[p.pk, "protocolla"]),
                        {"mezzo": "pec", "proposta": "1", "excel": "1"})  # fmt: skip
        p.refresh_from_db()
        assert p.protocollo_candidatura and r["Location"] == reverse(
            "protocollo:spedisci", args=[p.protocollo_candidatura.pk]
        )
        s.refresh_from_db()
        r = client.post(reverse("progetti:proposta", args=[p.pk]),
                        {"sezione": s.pk, "testo": "cambiato"})  # fmt: skip
        assert r.status_code == 404  # dopo la candidatura la proposta non si modifica

    def test_lettera_di_partenariato(self, client, utente):
        from apps.documenti.models import ModelloStampa

        client.force_login(utente)
        p = _completo(utente)
        m = ModelloStampa.objects.create(nome="Partenariato", titolo="Lettera",
                                         corpo="Aderiamo a {{ progetto }} come {{ ruolo_partner }}.")  # fmt: skip
        r = client.post(reverse("progetti:azione_candidatura", args=[p.pk, "lettera"]),
                        {"modello": m.pk, "partner": p.partner.get().pk})  # fmt: skip
        assert r.status_code == 200 and r["Content-Type"] == "application/pdf"

    def test_consigliere_legge_soltanto(self, client_ruolo, utente):
        p = _completo(utente)
        c = client_ruolo("Consigliere")
        assert c.get(reverse("progetti:proposta", args=[p.pk])).status_code == 200
        assert c.get(reverse("progetti:candidatura", args=[p.pk])).status_code == 200
        s = TestoSezione.objects.filter(progetto=p).first()
        r = c.post(reverse("progetti:proposta", args=[p.pk]), {"sezione": s.pk, "testo": "x"})
        assert r.status_code == 404
        r = c.post(reverse("progetti:azione_candidatura", args=[p.pk, "protocolla"]), {})
        assert r.status_code == 403
