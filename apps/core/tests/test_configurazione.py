# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test della configurazione iniziale guidata e della personalizzazione
# *              dell'interfaccia (colore, menu, logo).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import io
from datetime import date
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image

from apps.core.models import Organizzazione
from apps.soci import servizi as soci
from apps.soci.models import Sezione, TipologiaSocio
from apps.tesoreria.models import Conto, Esercizio

pytestmark = pytest.mark.django_db
ANNO = date.today().year


@pytest.fixture(autouse=True)
def cartella_media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def admin_client(client, crea_utente):
    client.force_login(crea_utente("capo", ruoli=["Amministratore di sistema"]))
    return client


def png(colore=(200, 30, 30, 128), lato=1200):
    buf = io.BytesIO()
    Image.new("RGBA", (lato, lato), colore).save(buf, "PNG")
    return SimpleUploadedFile("logo.png", buf.getvalue(), content_type="image/png")


def passo(nome):
    return reverse("configurazione", args=[nome])


class TestConfigurazione:
    def test_primo_accesso_porta_al_wizard(self, admin_client, client_ruolo):
        Organizzazione.objects.update(configurata=False)
        r = admin_client.get(reverse("core:cruscotto"))
        assert r.status_code == 302 and r.url == passo("ente")
        # chi non può configurare vede il cruscotto
        assert client_ruolo("Consigliere", username="c").get("/").status_code == 200

    def test_percorso_completo(self, admin_client):
        Organizzazione.objects.update(configurata=False)
        for p in ["ente", "aspetto", "sezioni", "tesseramento", "tesoreria", "riepilogo"]:
            assert admin_client.get(passo(p)).status_code == 200, p
        r = admin_client.post(passo("ente"), {"denominazione": "ANCR Sezione di Prova",
                                               "provincia": "pz", "comune": "Avigliano"})  # fmt: skip
        assert r.url == passo("aspetto")
        r = admin_client.post(passo("aspetto"), {"colore_primario": "#AA3300", "stile_menu": "colorato",
                                                  "nuovo_logo": png()})  # fmt: skip
        assert r.url == passo("sezioni")
        r = admin_client.post(passo("sezioni"), {"struttura": "federazione",
                                                  "elenco": "085; Avigliano; Avigliano; pz\n086; Potenza"})  # fmt: skip
        assert r.url == passo("tesseramento")
        assert list(Sezione.objects.values_list("codice", "nome", "provincia")) == [
            ("085", "Avigliano", "PZ"), ("086", "Potenza", ""),
        ]  # fmt: skip
        dati = {"anno": ANNO, "costo_acquisto": "3.50", "note": ""}
        for t in TipologiaSocio.objects.filter(attiva=True):
            dati[f"quota_{t.pk}"] = "25" if t.nome == "Ordinario" else "0"
        assert admin_client.post(passo("tesseramento"), dati).url == passo("tesoreria")
        assert soci.quota_per(TipologiaSocio.objects.get(nome="Ordinario"), ANNO) == Decimal("25")
        dati = {"anno": ANNO}
        for c in Conto.objects.filter(attivo=True):
            dati[f"saldo_{c.pk}"] = "100" if c.e_cassa else "1500"
            if not c.e_cassa:
                dati[f"iban_{c.pk}"] = "it60 x054 2811 1010 0000 0123 456"
        assert admin_client.post(passo("tesoreria"), dati).url == passo("riepilogo")
        e = Esercizio.objects.get(anno=ANNO)
        assert sorted(s.iniziale for s in e.saldi.all()) == [Decimal("100"), Decimal("1500")]
        html = admin_client.get(passo("riepilogo")).content.decode()
        assert "ANCR Sezione di Prova" in html and "Potenza" in html
        assert admin_client.post(passo("riepilogo")).url == reverse("core:cruscotto")
        org = Organizzazione.corrente()
        assert org.configurata and org.provincia == "PZ" and org.colore_primario == "#aa3300"

    def test_sezione_singola_e_salta(self, admin_client):
        r = admin_client.post(passo("sezioni"), {"struttura": "singola", "codice": "085",
                                                  "nome": "Sezione di Avigliano"})  # fmt: skip
        assert r.status_code == 302
        assert Sezione.objects.get().codice == "085"
        assert admin_client.post(passo("tesseramento"), {"salta": "1"}).url == passo("tesoreria")
        r = admin_client.post(passo("sezioni"), {"struttura": "federazione", "elenco": "solo nome"})
        assert r.status_code == 200 and "codice e nome" in r.content.decode()

    def test_permesso(self, client_ruolo):
        assert client_ruolo("Tesoriere").get(passo("ente")).status_code == 403
        assert client_ruolo("Tesoriere", username="t2").get(passo("inesistente")).status_code == 404


class TestAspetto:
    def test_colore_menu_e_logo(self, admin_client, client):
        r = admin_client.post(reverse("core:aspetto"), {"colore_primario": "#ffdd00",
                                                         "stile_menu": "chiaro", "nuovo_logo": png()})  # fmt: skip
        assert r.status_code == 302
        org = Organizzazione.corrente()
        assert org.colore_testo_primario == "#182433"  # giallo: testo scuro
        img = Image.open(org.logo.open("rb"))
        assert img.format == "PNG" and max(img.size) == 512 and img.mode == "RGBA"
        css = client.get(reverse("aspetto_css") + "?v=1")
        assert "--tblr-primary: #ffdd00" in css.content.decode()
        assert "immutable" in css["Cache-Control"]
        pagina = admin_client.get(reverse("core:aspetto")).content.decode()
        assert 'data-bs-theme="light"' in pagina and reverse("logo") in pagina
        admin_client.logout()
        assert client.get(reverse("logo")).status_code == 200  # pubblico: pagina di accesso
        r = client.post(reverse("account_login"))
        assert reverse("logo") in r.content.decode()

    def test_colore_non_valido(self, admin_client):
        r = admin_client.post(
            reverse("core:aspetto"), {"colore_primario": "red;}", "stile_menu": "scuro"}
        )
        assert r.status_code == 200 and Organizzazione.corrente().colore_primario == "#1d4e89"
        r = admin_client.post(reverse("core:aspetto"), {"colore_primario": "#112233", "stile_menu": "scuro",
                                                         "nuovo_logo": SimpleUploadedFile("x.png", b"no")})  # fmt: skip
        assert r.status_code == 200 and not Organizzazione.corrente().logo
