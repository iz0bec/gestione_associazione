# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test del modulo di richiesta di adesione (Allegato A): domanda con gli stessi
# *              campi e consensi, PDF compilati e in bianco, richiesta firmata nella scheda.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import io
from datetime import date

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image

from apps.anagrafica.models import Soggetto
from apps.core.models import EventoAudit, Organizzazione
from apps.soci import modulo, servizi
from apps.soci.forms import DomandaForm
from apps.soci.models import DomandaIscrizione, Sezione, TipologiaSocio

pytestmark = pytest.mark.django_db
CF = "BNCLRA80A41F205G"


@pytest.fixture(autouse=True)
def cartella_media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture(autouse=True)
def testi_modulo():
    org = Organizzazione.corrente()
    org.federazione = "Potenza Matera"
    org.modulo_intestazione = (
        "ASSOCIAZIONE NAZIONALE COMBATTENTI E REDUCI\n(Eretta in ente morale)\nPRESIDENZA NAZIONALE"
    )
    org.modulo_articoli_statuto = "all'art. 2 ed agli articoli 5, 6, 7, 8, 9 e 58"
    org.modulo_dichiarazione = "iscritto all'Associazione Decorati di Medaglia d'Oro"
    org.informativa_privacy = "Gentile aspirante socio, ..."
    org.save()


@pytest.fixture
def capo(crea_utente):
    return crea_utente("capo", ruoli=["Amministratore di sistema"])


@pytest.fixture
def socio(capo):
    p = Soggetto.objects.create(cognome="Bianchi", nome="Laura", codice_fiscale=CF)
    return servizi.ammetti_socio(p, TipologiaSocio.objects.get(nome="Ordinario"), capo)


DATI = {
    "cognome": "Bianchi", "nome": "Laura", "luogo_nascita": "Milano", "data_nascita": "1980-01-01",
    "codice_fiscale": CF, "indirizzo": "Via Roma 1", "cap": "20100", "comune": "Milano",
    "provincia": "MI", "cellulare": "3331234567", "accetta_statuto": "on",
    "consenso_trattamento": "on", "consenso_particolari": "on", "dichiarazione": "False",
}  # fmt: skip


class TestDomanda:
    def test_campi_come_il_modulo(self):
        form = DomandaForm({**DATI, "sezione": Sezione.predefinita().pk})
        assert form.is_valid(), form.errors
        assert "articoli 5, 6, 7, 8, 9 e 58" in form.fields["accetta_statuto"].label
        assert "Medaglia d'Oro" in form.fields["dichiarazione"].label
        d = form.save()
        assert d.dichiarazione is False and d.consenso_comunicazioni and not d.email
        senza = DomandaForm({**DATI, "consenso_trattamento": ""})
        assert not senza.is_valid() and "consenso_trattamento" in senza.errors
        Organizzazione.objects.update(modulo_dichiarazione="")
        assert "dichiarazione" not in DomandaForm().fields

    def test_accoglimento(self, capo):
        form = DomandaForm({**DATI, "sezione": Sezione.predefinita().pk, "dichiarazione": "True"})
        assert form.is_valid()
        d = form.save()
        s = servizi.accogli_domanda(d, capo, tipologia=TipologiaSocio.objects.first(),
                                    data_ammissione=date.today())  # fmt: skip
        assert s.dichiarazione is True and s.soggetto.cellulare == "3331234567"
        dati = modulo.dati_socio(s)
        assert dati["consensi"] == {"trattamento": True, "particolari": True, "immagini": False}


class TestPdf:
    def test_modulo_compilato_e_in_bianco(self, client, capo, socio):
        d = DomandaIscrizione.objects.create(
            cognome="Verdi", nome="Anna", codice_fiscale=CF, data_nascita=date(1980, 1, 1),
            luogo_nascita="Milano", indirizzo="Via Roma 1", cap="20100", comune="Milano",
            provincia="MI", sezione=Sezione.predefinita(), consenso_trattamento=True,
        )  # fmt: skip
        client.force_login(capo)
        for url in [reverse("soci:modulo_vuoto"), reverse("soci:domanda_pdf", args=[d.pk]),
                    reverse("soci:modulo_socio", args=[socio.pk])]:  # fmt: skip
            r = client.get(url)
            assert r.status_code == 200 and r.content.startswith(b"%PDF"), url
        html = client.get(reverse("soci:domanda", args=[d.pk])).content.decode()
        assert reverse("soci:domanda_pdf", args=[d.pk]) in html

    def test_pagina_pubblica(self, client):
        Organizzazione.objects.update(iscrizioni_online=True)
        html = client.get(reverse("iscrizione")).content.decode()
        for testo in ["C H I E D E", "Federazione di Potenza Matera", "dati «particolari»",
                      "Medaglia d&#x27;Oro", "Gentile aspirante socio"]:  # fmt: skip
            assert testo in html, testo
        assert 'name="tipologia"' not in html


class TestRichiestaFirmata:
    def test_pdf_caricato_e_mostrato(self, client, capo, socio):
        client.force_login(capo)
        assert client.get(reverse("soci:modulo_firmato", args=[socio.pk])).status_code == 404
        pdf = SimpleUploadedFile("firmato.pdf", b"%PDF-1.4\n% prova\n", "application/pdf")
        r = client.post(reverse("soci:carica_modulo", args=[socio.pk]), {"modulo": pdf})
        assert r.status_code == 302
        socio.refresh_from_db()
        assert socio.modulo_adesione and socio.modulo_adesione_il
        r = client.get(reverse("soci:modulo_firmato", args=[socio.pk]))
        assert r["Content-Type"] == "application/pdf" and r["X-Frame-Options"] == "SAMEORIGIN"
        assert b"".join(r.streaming_content).startswith(b"%PDF")
        html = client.get(reverse("soci:dettaglio", args=[socio.pk])).content.decode()
        assert "<iframe" in html and reverse("soci:modulo_firmato", args=[socio.pk]) in html
        assert EventoAudit.objects.filter(azione="consultazione", oggetto_id=str(socio.pk)).exists()

    def test_foto_unite_in_pdf_e_file_rifiutati(self, capo, socio):
        pagine = []
        for colore in ("white", "gray"):
            buf = io.BytesIO()
            Image.new("RGB", (1200, 1700), colore).save(buf, "JPEG")
            pagine.append(SimpleUploadedFile(f"{colore}.jpg", buf.getvalue(), "image/jpeg"))
        s = servizi.carica_modulo(socio, pagine, capo)
        contenuto = s.modulo_adesione.open("rb").read()
        assert (
            contenuto.startswith(b"%PDF")
            and contenuto.count(b"/Type /Page\n")
            + contenuto.count(b"/Type /Page\r")
            + contenuto.count(b"/Type /Page ")
            >= 2
        )
        with pytest.raises(servizi.OperazioneNonValida):
            servizi.carica_modulo(socio, [SimpleUploadedFile("x.exe", b"MZ...")], capo)

    def test_permessi(self, client_ruolo, socio):
        c = client_ruolo("Consigliere")
        pdf = SimpleUploadedFile("firmato.pdf", b"%PDF-1.4\n", "application/pdf")
        assert (
            c.post(reverse("soci:carica_modulo", args=[socio.pk]), {"modulo": pdf}).status_code
            == 403
        )
