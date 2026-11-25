# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test di rendicontazione e chiusura (P6) e della relazione al consiglio: relazioni
# *              guidate, rendiconto con i giustificativi numerati (PDF, Excel, ZIP), verifica
# *              prima della chiusura, riuso come modello, stampa e invio ai partecipanti.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import zipfile
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from apps.anagrafica.models import Soggetto
from apps.progetti import consiglio, esecuzione, proposta, rendiconto, servizi
from apps.progetti.forms import ProgettoForm
from apps.progetti.models import Attivita, FonteFinanziamento, Progetto, VoceCosto

pytestmark = pytest.mark.django_db
OGGI = date.today()


@pytest.fixture(autouse=True)
def _media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def utente(crea_utente):
    return crea_utente("pres", ruoli=["Presidente", "Tesoriere"])


def _progetto(utente, titolo="Memoria a scuola", in_corso=True):
    form = ProgettoForm(data={"titolo": titolo, "sintesi": "Incontri con le classi",
                              "responsabile": utente.pk})  # fmt: skip
    assert form.is_valid()
    p = servizi.crea_progetto(form, utente)
    p.obiettivo_generale = "Memoria"
    p.save()
    VoceCosto.objects.create(progetto=p, categoria="servizi", descrizione="Guide",
                             costo_unitario=Decimal("1000"))  # fmt: skip
    FonteFinanziamento.objects.create(progetto=p, tipo="contributo", importo=Decimal("1000"))
    Attivita.objects.create(progetto=p, titolo="Incontri", inizio=OGGI - timedelta(30),
                            fine=OGGI - timedelta(10))  # fmt: skip
    p.indicatori.create(descrizione="Studenti", valore_atteso=100, unita="studenti")
    p.sezioni.create(documento="proposta", titolo="Contesto e bisogni", testo="Testo riusabile")
    if in_corso:
        servizi.cambia_stato(p, Progetto.Stato.IN_CORSO, utente)
        p.refresh_from_db()
    return p


def _spesa(utente, progetto, importo, giustificativo=True):
    from apps.tesoreria import servizi as tesoreria
    from apps.tesoreria.models import Conto, Esercizio, Voce

    Esercizio.objects.get_or_create(anno=OGGI.year)
    conto = Conto.objects.first() or Conto.objects.create(nome="Cassa")
    voce = Voce.objects.filter(tipo="uscita", sottovoci__isnull=True).order_by("codice").first()
    file = SimpleUploadedFile("fattura.pdf", b"%PDF-1.4 fattura") if giustificativo else None
    m = tesoreria.registra_movimento(
        {"data": OGGI, "tipo": "uscita", "conto": conto, "importo": Decimal(importo),
         "descrizione": "Fattura guide", "voce": voce}, utente, giustificativo=file,
    )  # fmt: skip
    return esecuzione.imputa(progetto, m, utente, voce=progetto.voci.get())


class TestRelazioneFinale:
    def test_sezioni_e_testi_proposti(self, utente):
        p = _progetto(utente)
        sezioni = rendiconto.prepara_relazione(p)
        assert len(sezioni) == len(rendiconto.SCHEMA_RELAZIONE)
        assert not p.sezioni_proposta.filter(titolo="Attività svolte").exists()
        assert "Incontri (" in rendiconto.componi(p, "svolte")
        assert "raggiunto da indicare" in rendiconto.componi(p, "risultati")
        anna = Soggetto.objects.create(tipo="persona", cognome="Verdi", nome="Anna")
        esecuzione.registra_ore(p, utente, soggetto=anna, data=OGGI, ore=Decimal("4"))
        assert "1 volontari per 4 ore" in rendiconto.componi(p, "volontariato")
        s = sezioni[0]
        proposta.salva_testo(s, "Svolti 10 incontri", utente)
        servizi.cambia_stato(p, Progetto.Stato.CHIUSO, utente)
        p.refresh_from_db()
        with pytest.raises(proposta.ErroreProposta):
            proposta.salva_testo(s, "dopo la chiusura", utente)


class TestRendiconto:
    def test_giustificativi_numerati_e_archivio(self, utente):
        from openpyxl import load_workbook

        p = _progetto(utente)
        _spesa(utente, p, "300")
        _spesa(utente, p, "200", giustificativo=False)
        _spesa(utente, p, "100")
        r = rendiconto.calcola(p)
        assert [s.numero for s in r.spese] == [1, 0, 2]
        assert len(r.senza_giustificativo) == 1
        assert rendiconto.rendiconto_pdf(p).startswith(b"%PDF")
        ws = load_workbook(BytesIO(rendiconto.rendiconto_excel(p)))["Spese"]
        assert 600.0 in [c.value for riga in ws.iter_rows() for c in riga]
        rendiconto.prepara_relazione(p)
        with zipfile.ZipFile(BytesIO(rendiconto.archivio_zip(p, utente))) as z:
            nomi = z.namelist()
        base = f"{p.codice}-rendiconto/"
        assert base + "rendiconto.pdf" in nomi and base + "relazione-finale.pdf" in nomi
        assert sorted(n for n in nomi if "giustificativi/" in n) == [
            f"{base}giustificativi/001-{OGGI:%Y%m%d}.pdf",
            f"{base}giustificativi/002-{OGGI:%Y%m%d}.pdf",
        ]

    def test_verifica_chiusura(self, utente):
        p = _progetto(utente)
        _spesa(utente, p, "100", giustificativo=False)
        testi = " ".join(v.testo for v in rendiconto.verifica_chiusura(p))
        assert "non completate" in testi and "senza giustificativo" in testi
        assert "relazione finale non è stata scritta" in testi
        assert "da incassare" in testi


class TestRiuso:
    def test_copia_come_modello(self, utente):
        p = _progetto(utente)
        a, b = (
            p.attivita.get(),
            Attivita.objects.create(
                progetto=p, titolo="Mostra", inizio=OGGI - timedelta(5), fine=OGGI - timedelta(1)
            ),
        )
        b.dopo = a
        b.save()
        nuovo = rendiconto.riusa(p, utente, titolo="Memoria a scuola 2027")
        assert nuovo.stato == Progetto.Stato.PROGETTAZIONE and nuovo.pk != p.pk
        assert nuovo.voci.count() == 1 and nuovo.indicatori.count() == 1
        assert nuovo.sezioni_proposta.get().testo == "Testo riusabile"
        attivita = list(nuovo.attivita.order_by("inizio"))
        assert attivita[0].inizio == OGGI and attivita[1].dopo == attivita[0]
        assert not nuovo.imputazioni.exists() and nuovo.bando is None


class TestConsiglio:
    def _riunione(self, utente, stato="bozza"):
        from apps.organi.models import Carica, Organo, Riunione

        organo = Organo.objects.get(sigla="CD")
        socio = Soggetto.objects.create(tipo="persona", cognome="Bianchi", nome="Luca",
                                        email="luca@example.org")  # fmt: skip
        Carica.objects.create(organo=organo, soggetto=socio, ruolo="consigliere",
                              dal=OGGI - timedelta(365))  # fmt: skip
        return Riunione.objects.create(organo=organo, prima_convocazione=timezone.now()
                                       + timedelta(days=7), luogo="Sede", stato=stato,
                                       anno=OGGI.year)  # fmt: skip

    def test_relazione_pdf_e_invio(self, utente):
        p = _progetto(utente, in_corso=False)
        sezioni = consiglio.prepara(p)
        assert [s.chiave for s in sezioni][0] == "decisione"
        assert "Costo complessivo: € 1.000,00." in consiglio.componi(p, "impegno")
        assert "verifiche" in consiglio.componi(p, "rischi")
        riunione = self._riunione(utente)
        with pytest.raises(consiglio.ErroreConsiglio, match="vuota"):
            consiglio.invia(p, riunione, utente)
        proposta.salva_testo(sezioni[0], "Avviare la candidatura al bando", utente)
        assert consiglio.pdf(p).startswith(b"%PDF")
        invio = consiglio.invia(p, riunione, utente, punto=True)
        assert invio.stato == "bozza" and p.codice in invio.oggetto
        assert riunione.punti.filter(titolo__contains=p.codice).count() == 1
        consiglio.invia(p, riunione, utente, punto=True)  # il punto non si duplica
        assert riunione.punti.filter(titolo__contains=p.codice).count() == 1


class TestPagine:
    def test_schede(self, client, utente):
        client.force_login(utente)
        p = _progetto(utente)
        _spesa(utente, p, "50")
        for url in (reverse("progetti:rendiconto", args=[p.pk]),
                    reverse("progetti:relazione", args=[p.pk, "consiglio"]),
                    reverse("progetti:relazione", args=[p.pk, "relazione"])):  # fmt: skip
            assert client.get(url).status_code == 200, url
        r = client.get(reverse("progetti:documento_relazioni", args=[p.pk, "consiglio.pdf"]))
        assert r.status_code == 200 and r["Content-Disposition"].startswith("inline")
        r = client.get(reverse("progetti:documento_relazioni", args=[p.pk, "archivio.zip"]))
        assert r.status_code == 200 and r["Content-Type"] == "application/zip"
        s = p.sezioni_consiglio.get(chiave="impegno")
        r = client.post(reverse("progetti:relazione", args=[p.pk, "consiglio"]),
                        {"sezione": s.pk, "azione": "componi"}, follow=True)  # fmt: skip
        assert "Costo complessivo" in r.content.decode()
        r = client.post(reverse("progetti:rendiconto", args=[p.pk]), {"titolo": "Copia"})
        assert Progetto.objects.filter(titolo="Copia").exists() and r.status_code == 302

    def test_consigliere(self, client_ruolo, utente):
        p = _progetto(utente)
        c = client_ruolo("Consigliere")
        assert c.get(reverse("progetti:rendiconto", args=[p.pk])).status_code == 200
        assert c.get(reverse("progetti:documento_relazioni",
                             args=[p.pk, "consiglio.pdf"])).status_code == 200  # fmt: skip
        assert c.get(reverse("progetti:documento_relazioni",
                             args=[p.pk, "archivio.zip"])).status_code == 404  # fmt: skip
        s = consiglio.prepara(p)[0]
        r = c.post(reverse("progetti:relazione", args=[p.pk, "consiglio"]),
                   {"sezione": s.pk, "testo": "x"})  # fmt: skip
        assert r.status_code == 404
