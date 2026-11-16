# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test delle domande di iscrizione arrivate per email (recupero dei dati,
# *              protocollazione, documento di iscrizione fino alla scheda del socio)
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
import io
from datetime import date
from email.message import EmailMessage

import pytest
from PIL import Image

from apps.protocollo import posta
from apps.protocollo.models import CasellaPosta, MessaggioRicevuto
from apps.soci import estrazione, servizi
from apps.soci.models import DomandaIscrizione, Sezione, TipologiaSocio

pytestmark = pytest.mark.django_db

CF = "RSSMRA50C15A519V"  # Rossi Mario, 15/03/1950, Avigliano (PZ)
TESTO = """Buongiorno,
vorrei chiedere l'iscrizione all'associazione.

Cognome: Rossi
Nome: Mario
Codice fiscale: rssmra50c15a519v
Residente in via: Via Roma 1
CAP: 85021
Comune: Avigliano
Provincia: PZ
Cell. 333 1234567

Allego il modulo di adesione firmato.
"""


@pytest.fixture(autouse=True)
def cartella_media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def _jpeg():
    uscita = io.BytesIO()
    Image.new("RGB", (60, 80), "white").save(uscita, "JPEG")
    return uscita.getvalue()


def _pdf_con_testo(testo):
    from weasyprint import HTML

    return HTML(string=f"<pre>{testo}</pre>").write_pdf()


def _messaggio(testo=TESTO, mittente="Mario Rossi <mario@example.org>", allegati=()):
    casella = CasellaPosta.objects.create(nome="Segreteria", server="imap.example.org", utente="u")
    m = EmailMessage()
    m["From"] = mittente
    m["To"] = "segreteria@example.org"
    m["Subject"] = "Richiesta di adesione"
    m["Date"] = "Mon, 02 Nov 2026 10:00:00 +0100"
    m["Message-ID"] = "<adesione@example.org>"
    m.set_content(testo)
    for nome, dati, tipo in allegati:
        principale, secondario = tipo.split("/")
        m.add_attachment(dati, maintype=principale, subtype=secondario, filename=nome)
    return posta.salva_messaggio(casella, m.as_bytes())


class TestEstrazione:
    def test_riconoscimento(self):
        assert estrazione.probabile_iscrizione(_messaggio())

    def test_dati_dal_testo(self):
        valori, provenienza = estrazione.estrai(_messaggio())
        assert valori["cognome"] == "Rossi" and valori["nome"] == "Mario"
        assert valori["codice_fiscale"] == CF
        # dal codice fiscale, se il testo non li dice
        assert valori["data_nascita"] == date(1950, 3, 15)
        assert valori["luogo_nascita"] == "Avigliano (PZ)"
        assert provenienza["data_nascita"] == "codice fiscale"
        assert valori["indirizzo"] == "Via Roma 1" and valori["cap"] == "85021"
        assert valori["comune"] == "Avigliano" and valori["provincia"] == "PZ"
        assert valori["cellulare"] == "3331234567"
        assert valori["email"] == "mario@example.org"

    def test_nome_dal_mittente_solo_con_il_codice_fiscale(self):
        testo = f"Chiedo l'iscrizione. Il mio codice fiscale è {CF}."
        valori, _ = estrazione.estrai(_messaggio(testo, mittente="ROSSI MARIO <m@example.org>"))
        assert valori["cognome"] == "Rossi" and valori["nome"] == "Mario"
        senza_cf, _ = estrazione.estrai(
            _messaggio("Chiedo l'iscrizione.", mittente="Rossi Mario <x@example.org>")
        )
        assert "cognome" not in senza_cf and "nome" not in senza_cf  # non si indovina

    def test_dati_dal_pdf_allegato(self):
        pdf = _pdf_con_testo("Cognome: Bianchi\nNome: Laura\nComune: Potenza")
        m = _messaggio(
            "Vedi allegato.", mittente="x@example.org",
            allegati=[("adesione.pdf", pdf, "application/pdf")],
        )  # fmt: skip
        valori, provenienza = estrazione.estrai(m)
        assert valori["cognome"] == "Bianchi" and valori["comune"] == "Potenza"
        assert provenienza["cognome"] == "allegato «adesione.pdf»"

    def test_niente_dati_inventati(self):
        valori, _ = estrazione.estrai(_messaggio("Vorrei informazioni.", mittente="x@example.org"))
        assert valori == {"email": "x@example.org"}


class TestPercorso:
    def _post(self, m, **extra):
        return {
            "cognome": "Rossi", "nome": "Mario", "codice_fiscale": CF,
            "data_nascita": "1950-03-15", "luogo_nascita": "Avigliano (PZ)",
            "email": "mario@example.org", "indirizzo": "Via Roma 1", "cap": "85021",
            "comune": "Avigliano", "provincia": "PZ", "sezione": Sezione.objects.first().pk,
            "accetta_statuto": "on", "consenso_trattamento": "on",
            "oggetto_protocollo": "Domanda di iscrizione di Rossi Mario", **extra,
        }  # fmt: skip

    def test_dal_messaggio_al_socio(self, client_ruolo):
        m = _messaggio(allegati=[("modulo firmato.jpg", _jpeg(), "image/jpeg")])
        c = client_ruolo("Segretario")
        pagina = c.get(f"/soci/domande/da-messaggio/{m.pk}/")
        assert pagina.status_code == 200
        html = pagina.content.decode()
        assert CF in html and "Avigliano (PZ)" in html and "modulo firmato.jpg" in html

        r = c.post(f"/soci/domande/da-messaggio/{m.pk}/", self._post(m, modulo=["0"]))
        assert r.status_code == 302
        domanda = DomandaIscrizione.objects.get()
        m.refresh_from_db()
        assert domanda.origine == "email" and domanda.protocollo == m.protocollo
        assert m.stato == MessaggioRicevuto.Stato.PROTOCOLLATO
        assert domanda.protocollo.oggetto == "Domanda di iscrizione di Rossi Mario"
        assert domanda.modulo_firmato.read(5) == b"%PDF-"  # la foto unita in un PDF

        utente = domanda.protocollo.creato_da
        socio = servizi.accogli_domanda(
            domanda, utente, tipologia=TipologiaSocio.objects.first(),
            data_ammissione=date(2026, 11, 9),
        )  # fmt: skip
        socio.refresh_from_db()
        assert socio.modulo_adesione and socio.modulo_adesione.read(5) == b"%PDF-"

    def test_errore_lascia_tutto_com_era(self, client_ruolo):
        m = _messaggio()
        c = client_ruolo("Segretario")
        r = c.post(f"/soci/domande/da-messaggio/{m.pk}/", self._post(m, oggetto_protocollo=""))
        assert r.status_code == 200 and "oggetto" in r.content.decode()
        m.refresh_from_db()
        assert m.stato == MessaggioRicevuto.Stato.NUOVO and not DomandaIscrizione.objects.exists()

    def test_messaggio_gia_gestito(self, client_ruolo):
        m = _messaggio()
        MessaggioRicevuto.objects.filter(pk=m.pk).update(stato="scartato", motivo_scarto="prova")
        r = client_ruolo("Segretario").get(f"/soci/domande/da-messaggio/{m.pk}/")
        assert r.status_code == 302

    def test_senza_permessi_del_protocollo(self, client_ruolo):
        m = _messaggio()
        assert (
            client_ruolo("Consigliere").get(f"/soci/domande/da-messaggio/{m.pk}/").status_code
            == 403
        )

    def test_modulo_su_domanda_inserita_a_mano(self, client_ruolo):
        from django.core.files.uploadedfile import SimpleUploadedFile

        c = client_ruolo("Segretario")
        dati = self._post(None)
        dati.pop("oggetto_protocollo")
        c.post("/soci/domande/nuova/", dati)
        domanda = DomandaIscrizione.objects.get()
        file = SimpleUploadedFile("scansione.jpg", _jpeg(), content_type="image/jpeg")
        c.post(f"/soci/domande/{domanda.pk}/modulo-firmato.pdf", {"modulo": file})
        domanda.refresh_from_db()
        assert domanda.modulo_firmato
        assert c.get(f"/soci/domande/{domanda.pk}/modulo-firmato.pdf").status_code == 200


class TestConfermaRicezione:
    _post = TestPercorso._post

    def _registra(self, client_ruolo, mittente="Mario Rossi <mario@example.org>", **extra):
        m = _messaggio(mittente=mittente)
        c = client_ruolo("Segretario")
        assert (
            'name="conferma_ricezione" checked'
            in c.get(f"/soci/domande/da-messaggio/{m.pk}/").content.decode()
        )
        r = c.post(f"/soci/domande/da-messaggio/{m.pk}/", self._post(m, **extra), follow=True)
        return r, DomandaIscrizione.objects.get()

    def test_in_coda_con_il_protocollo(self, client_ruolo):
        from apps.comunicazioni import servizi as com
        from apps.comunicazioni.models import Invio

        r, domanda = self._registra(client_ruolo, conferma_ricezione="on")
        invio = Invio.objects.get(origine=com.ORIGINE_RICEZIONE, origine_id=domanda.pk)
        assert invio.stato == Invio.Stato.IN_CODA and invio.finalita == "istituzionale"
        d = invio.destinatari.get()
        assert d.email == "mario@example.org" and d.nome == "Mario"
        oggetto, testo = com.messaggio(invio, d).subject, com.messaggio(invio, d).body
        assert domanda.protocollo.segnatura in testo and "Mario Rossi" in testo
        assert "{{" not in testo + oggetto
        assert "Conferma di ricezione" in r.content.decode()
        # rieseguibile: non ne prepara una seconda
        utente = domanda.protocollo.creato_da
        m = MessaggioRicevuto.objects.get(protocollo=domanda.protocollo)
        assert servizi.conferma_ricezione(domanda, m, utente) == invio

    def test_mittente_diverso_dal_richiedente(self, client_ruolo):
        from apps.comunicazioni.models import Invio

        self._registra(
            client_ruolo, mittente="Sezione di Montebello <sezione@example.org>",
            conferma_ricezione="on",
        )  # fmt: skip
        d = Invio.objects.get().destinatari.get()
        assert d.email == "sezione@example.org" and d.nome == "Sezione di Montebello"

    def test_senza_spunta_nessuna_conferma(self, client_ruolo):
        from apps.comunicazioni.models import Invio

        self._registra(client_ruolo)
        assert not Invio.objects.exists()

    def test_senza_modello_la_domanda_resta(self, client_ruolo):
        from apps.comunicazioni.models import Invio, Modello

        Modello.objects.filter(uso=Modello.Uso.RICEZIONE).update(attivo=False)
        m = _messaggio()
        c = client_ruolo("Segretario")
        r = c.post(
            f"/soci/domande/da-messaggio/{m.pk}/",
            self._post(m, conferma_ricezione="on"), follow=True,
        )  # fmt: skip
        assert DomandaIscrizione.objects.exists() and not Invio.objects.exists()
        assert "Conferma di ricezione non inviata" in r.content.decode()
