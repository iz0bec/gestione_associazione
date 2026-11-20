# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test della veste grafica delle email: testo in HTML, logo incorporato,
# *              impostazioni in Sistema -> Aspetto, anteprima e messaggio di prova.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import io

import pytest
from django.core import mail
from django.core.files.base import ContentFile
from django.core.mail import EmailMessage
from django.urls import reverse
from PIL import Image

from apps.core import veste_email
from apps.core.models import Organizzazione

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def cartella_media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def org():
    org = Organizzazione.corrente()
    org.denominazione = "ANCR Sezione di Prova"
    org.colore_primario = "#1d4e89"
    org.save()
    return org


@pytest.fixture
def admin_client(client, crea_utente):
    client.force_login(crea_utente("capo", ruoli=["Amministratore di sistema"]))
    return client


def con_logo(org):
    buf = io.BytesIO()
    Image.new("RGBA", (512, 512), (200, 30, 30, 255)).save(buf, "PNG")
    org.logo.save("logo.png", ContentFile(buf.getvalue()), save=True)
    return org


class TestTestoHtml:
    def test_righe_spezzate_si_ricompongono(self, org):
        testo = "Siamo lieti di presentare\nil gestionale.\nIl Direttivo\n\nSecondo paragrafo"
        html = veste_email.testo_html(testo, org=org)
        assert "presentare\nil gestionale." in html  # stessa riga logica: nessun <br>
        assert "il gestionale.<br />" in html  # a fine frase si va a capo
        assert html.count("<p ") == 2

    def test_indirizzi_cliccabili_e_url_spezzato(self, org):
        testo = "Vedi https://example.org/docs/\nmanuale.pdf oppure scrivi a info@example.org."
        html = veste_email.testo_html(testo, org=org)
        assert '<a style="color:' in html
        assert 'href="https://example.org/docs/manuale.pdf"' in html
        assert 'href="mailto:info@example.org"' in html

    def test_html_neutralizzato_e_markdown(self, org):
        html = veste_email.testo_html("<script>x</script> **forte**\n\n- uno\n- due", org=org)
        assert "<script>" not in html and "&lt;script&gt;" in html
        assert "<strong>forte</strong>" in html and "<li style=" in html

    def test_link_markdown_non_raddoppiato(self, org):
        html = veste_email.testo_html("[il sito](https://example.org/a_b)", org=org)
        assert html.count("<a ") == 1 and ">il sito</a>" in html

    def test_senza_markdown_conserva_gli_a_capo(self, org):
        html = veste_email.testo_html("riga uno\nriga due", org=org, markdown=False)
        assert "riga uno<br>riga due" in html


class TestVeste:
    def test_logo_incorporato_come_related(self, org):
        con_logo(org)
        email = veste_email.veste(EmailMessage("Oggetto", "Testo", to=["a@example.org"]), org)
        parti = [p.get_content_type() for p in email.message().walk()]
        assert parti == [
            "multipart/alternative", "text/plain", "multipart/related", "text/html", "image/png",
        ]  # fmt: skip
        assert f"cid:{veste_email.CID_LOGO}" in email.alternatives[0][0]
        immagine = Image.open(io.BytesIO(email.logo_png))
        assert max(immagine.size) == veste_email.LATO_LOGO

    def test_senza_logo_e_allegati_conservati(self, org):
        org.email_logo = False
        con_logo(org)
        msg = EmailMessage("Oggetto", "Testo", to=["a@example.org"], headers={"X-Prova": "1"})
        msg.attach("doc.pdf", b"%PDF", "application/pdf")
        email = veste_email.veste(msg, org)
        assert email.logo_png is None and "cid:" not in email.alternatives[0][0]
        assert email.attachments[0][0] == "doc.pdf" and email.extra_headers["X-Prova"] == "1"

    def test_impostazioni_nella_pagina(self, org):
        org.email_titolo = "Associazione Nazionale"
        org.email_sottotitolo = "Federazione di Prova"
        org.email_fascia = Organizzazione.FasciaEmail.TRICOLORE
        org.email_colore_testata = "#0e2525"
        org.email_informativa = "Titolare: l'associazione. Scrivere a privacy@example.org."
        org.email_firma = "Via Roma 1\nhttps://example.org"
        html = veste_email.html(org, titolo="Titolo", corpo_html="<p>x</p>", avviso="Perché")
        for atteso in ("Associazione Nazionale", "Federazione di Prova", "#1a8a3c", "#0e2525",
                       "mailto:privacy@example.org", "Via Roma 1", ">example.org</a>", "Perché"):  # fmt: skip
            assert atteso in html
        assert "ANCR Sezione di Prova" not in html  # il titolo sostituisce la denominazione
        sobria = veste_email.html(org, titolo="T", corpo_html="", sobrio=True)
        assert "#1a8a3c" not in sobria and "privacy@example.org" not in sobria

    def test_firma_predefinita_dai_dati_dell_ente(self, org):
        org.indirizzo, org.cap, org.comune, org.provincia = "Via Roma 1", "85100", "Potenza", "PZ"
        org.email, org.sito_web = "info@example.org", "https://example.org"
        assert veste_email.righe_firma(org) == [
            "Via Roma 1, 85100 Potenza (PZ)", "info@example.org", "https://example.org",
        ]  # fmt: skip

    def test_accento_chiaro_scurito_per_i_collegamenti(self, org):
        org.email_colore_accento = "#ffe066"
        c = veste_email.colori(org)
        assert c["accento"] == "#ffe066" and c["collegamenti"] != "#ffe066"


class TestPaginaAspetto:
    def test_salva_e_colori_legati_al_principale(self, admin_client, org):
        dati = {
            "email_titolo": "Associazione", "email_sottotitolo": "Sezione", "email_logo": "on",
            "email_fascia": "colore", "email_colore_testata": "#1D4E89",
            "email_colore_accento": "#a0876e", "email_colore_sfondo": "#F1EDE6",
            "email_carattere": "bastone", "email_firma": "", "email_informativa": "Breve",
        }  # fmt: skip
        r = admin_client.post(reverse("core:aspetto_email"), dati)
        assert r.status_code == 302
        org.refresh_from_db()
        assert org.email_colore_testata == ""  # uguale al principale: lo segue
        assert org.email_colore_accento == "#a0876e" and org.email_colore_sfondo == "#f1ede6"
        assert org.email_sottotitolo == "Sezione" and org.email_carattere == "bastone"
        r = admin_client.get(reverse("core:aspetto"))
        assert r.status_code == 200 and b"Veste delle email" in r.content

    def test_errore_ripresenta_la_pagina(self, admin_client, org):
        r = admin_client.post(reverse("core:aspetto_email"), {"email_colore_sfondo": "rosso"})
        assert r.status_code == 200 and b"Veste delle email" in r.content

    def test_anteprima_isolata(self, admin_client, org):
        r = admin_client.get(reverse("core:anteprima_email"))
        assert r.status_code == 200 and b"Convocazione" in r.content
        assert "sandbox" in r["Content-Security-Policy"]
        assert r["X-Frame-Options"] == "SAMEORIGIN"

    def test_prova_inviata_all_utente(self, admin_client, org):
        r = admin_client.post(reverse("core:prova_email"))
        assert r.status_code == 302
        assert mail.outbox[0].to == ["capo@example.org"]
        assert "text/html" in mail.outbox[0].alternatives[0][1]

    def test_prova_con_invio_spento(self, admin_client, org):
        Organizzazione.objects.update(invio_email=False)
        admin_client.post(reverse("core:prova_email"))
        assert mail.outbox == []

    def test_permessi(self, client_ruolo, org):
        c = client_ruolo("Consigliere", username="c")
        assert c.get(reverse("core:anteprima_email")).status_code == 403
        assert c.post(reverse("core:prova_email")).status_code == 403
