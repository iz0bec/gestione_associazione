# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test del patrimonio: inventario numerato, foto ripulite, valutazioni,
# *              prestiti e uscite, passaggio di consegne, scheda pubblica del QR.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import hashlib
import io
import re
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image

from apps.patrimonio import servizi
from apps.patrimonio.forms import BeneForm
from apps.patrimonio.models import Bene, CategoriaBene, PassaggioConsegne
from apps.protocollo.models import Protocollo

pytestmark = pytest.mark.django_db
D = Decimal
OGGI = date.today()


@pytest.fixture(autouse=True)
def cartella_media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def utente(crea_utente):
    return crea_utente("segr", ruoli=["Segretario"])


def immagine_con_exif():
    img = Image.new("RGB", (3000, 2000), "red")
    exif = Image.Exif()
    exif[0x8825] = {2: (40, 0, 0)}  # GPSInfo
    exif[0x010F] = "Fotocamera"  # Make
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif)
    return SimpleUploadedFile("foto.jpg", buf.getvalue(), content_type="image/jpeg")


def bene(utente, nome="Labaro della sezione", valore="1500", **extra):
    dati = {"nome": nome, "categoria": CategoriaBene.objects.first().pk, "quantita": 1,
            "conservazione": "buono", "acquisizione": "donazione", "valore_acquisizione": valore, **extra}  # fmt: skip
    form = BeneForm(dati)
    assert form.is_valid(), form.errors
    return servizi.salva_bene(form, utente, foto=extra.get("foto"))


class TestInventario:
    def test_numerazione_e_valore(self, utente):
        a, b = bene(utente), bene(utente, "Medaglia", "200", quantita=3)
        assert (a.numero, b.numero, a.codice) == (1, 2, "INV 00001")
        assert a.valore == D("1500") and b.valore_totale == D("600")
        assert servizi.totali()["valore"] == D("2100")

    def test_foto_ridotta_senza_exif(self, utente):
        b = bene(utente, foto=immagine_con_exif())
        with b.foto.open("rb") as f:
            img = Image.open(f)
            img.load()
        assert max(img.size) == servizi.FOTO_LATO and not img.getexif()
        assert b.token in b.foto.name
        with pytest.raises(ValidationError):
            servizi.foto_ripulita(SimpleUploadedFile("finto.jpg", b"non sono un'immagine"))

    def test_valutazioni(self, utente):
        b = bene(utente)
        servizi.valuta(
            b, utente, data=OGGI - timedelta(days=30), valore=D("1800"), metodo="perizia"
        )
        servizi.valuta(b, utente, data=OGGI - timedelta(days=60), valore=D("1700"), metodo="stima")
        b.refresh_from_db()
        assert b.valore == D("1800")  # vale la valutazione più recente, non l'ultima inserita


class TestUscite:
    def test_prestito_e_restituzione(self, utente):
        b = bene(utente)
        with pytest.raises(ValidationError):  # serve sapere a chi
            servizi.registra_uscita(b, utente, tipo="prestito", data=OGGI, motivo="mostra")
        u = servizi.registra_uscita(
            b, utente, tipo="prestito", data=OGGI - timedelta(days=10), motivo="mostra al Comune",
            controparte_testo="Comune di Avigliano", restituzione_prevista=OGGI - timedelta(days=1),
        )  # fmt: skip
        b.refresh_from_db()
        assert b.stato == "prestito" and list(servizi.prestiti_scaduti()) == [u]
        with pytest.raises(ValidationError):  # in prestito non si dona
            servizi.registra_uscita(
                b, utente, tipo="donazione", data=OGGI, motivo="x", controparte_testo="y"
            )
        servizi.restituzione(u, utente, data=OGGI, rientro="integro")
        b.refresh_from_db()
        assert b.stato == "dotazione" and not servizi.prestiti_scaduti()

    def test_uscita_definitiva(self, utente):
        b = bene(utente)
        servizi.registra_uscita(b, utente, tipo="dismissione", data=OGGI, motivo="irrecuperabile")
        b.refresh_from_db()
        assert b.stato == "uscito" and servizi.totali()["beni"] == 0
        with pytest.raises(ValidationError):
            servizi.registra_uscita(
                b, utente, tipo="prestito", data=OGGI, motivo="x", controparte_testo="y"
            )


class TestPassaggio:
    def test_fotografia_immutabile(self, utente):
        b = bene(utente)
        bene(utente, "Bandiera", "300")
        p = servizi.crea_passaggio(
            utente, data=OGGI, consegnante="Rossi Mario", consegnante_ruolo="Presidente uscente",
            ricevente="Bianchi Anna", ricevente_ruolo="Presidente", protocolla=True,
        )  # fmt: skip
        assert p.numero_beni == 2 and p.valore_totale == D("1800")
        with p.file.open("rb") as f:
            assert hashlib.sha256(f.read()).hexdigest() == p.impronta
        assert Protocollo.objects.get().direzione == "interno"
        servizi.registra_uscita(b, utente, tipo="dismissione", data=OGGI, motivo="rotto")
        p.refresh_from_db()
        assert [x["codice"] for x in p.beni] == [
            "INV 00001",
            "INV 00002",
        ]  # la fotografia non cambia
        with pytest.raises(ValueError):
            p.save()
        Bene.objects.update(stato="uscito")
        with pytest.raises(ValidationError):
            servizi.crea_passaggio(utente, data=OGGI, consegnante="a", consegnante_ruolo="b",
                                   ricevente="c", ricevente_ruolo="d")  # fmt: skip
        assert PassaggioConsegne.objects.count() == 1


class TestViste:
    def test_pagine_e_pdf(self, client, utente):
        client.force_login(utente)
        b = bene(utente, pubblico=True, descrizione_pubblica="Donato dal reduce Mario Rossi.",
                 foto=immagine_con_exif())  # fmt: skip
        for url in [
            reverse("patrimonio:inventario"),
            reverse("patrimonio:inventario") + "?q=labaro",
            reverse("patrimonio:nuovo"),
            reverse("patrimonio:bene", args=[b.pk]),
            reverse("patrimonio:modifica", args=[b.pk]),
            reverse("patrimonio:foto", args=[b.pk]),
            reverse("patrimonio:passaggi"),
            reverse("patrimonio:passaggio_nuovo"),
            reverse("patrimonio:categorie"),
        ]:
            assert client.get(url).status_code == 200, url
        assert "<svg" in client.get(reverse("patrimonio:bene", args=[b.pk])).content.decode()
        for url in [reverse("patrimonio:stampa"), reverse("patrimonio:etichette")]:
            assert client.get(url).content.startswith(b"%PDF"), url
        assert "Labaro" in client.get(reverse("patrimonio:stampa") + "?formato=csv").content.decode(
            "utf-8-sig"
        )
        r = client.get(reverse("patrimonio:inventario"), {"q": "labaro"}, HTTP_HX_REQUEST="true")
        assert 'id="tabella-beni"' in r.content.decode() and "<html" not in r.content.decode()
        client.post(reverse("patrimonio:uscita", args=[b.pk]),
                    {"usc-tipo": "prestito", "usc-data": OGGI.isoformat(), "usc-controparte_testo": "Scuola",
                     "usc-motivo": "mostra", "usc-importo": "0"})  # fmt: skip
        b.refresh_from_db()
        assert b.stato == "prestito"

    def test_scheda_pubblica(self, client, utente):
        b = bene(
            utente,
            pubblico=True,
            descrizione_pubblica="Storia del cimelio",
            foto=immagine_con_exif(),
        )
        client.logout()
        r = client.get(reverse("bene_pubblico", args=[b.token]))
        html = re.sub(r"\?v=\d+", "", r.content.decode())  # versione dei file statici
        assert r.status_code == 200 and "Storia del cimelio" in html
        assert "1500" not in html and "1.500" not in html  # mai il valore
        assert (
            client.get(reverse("bene_pubblico_foto", args=[b.token])).status_code == 404
        )  # foto non pubblica
        Bene.objects.filter(pk=b.pk).update(foto_pubblica=True)
        assert client.get(reverse("bene_pubblico_foto", args=[b.token])).status_code == 200
        Bene.objects.filter(pk=b.pk).update(pubblico=False)
        assert client.get(reverse("bene_pubblico", args=[b.token])).status_code == 404
        assert client.get(reverse("bene_pubblico", args=["indovinato"])).status_code == 404

    def test_permessi(self, client_ruolo, utente):
        b = bene(utente)
        c = client_ruolo("Consigliere")
        assert c.get(reverse("patrimonio:bene", args=[b.pk])).status_code == 200
        assert c.get(reverse("patrimonio:nuovo")).status_code == 403
        assert c.post(reverse("patrimonio:uscita", args=[b.pk]), {}).status_code == 403
        assert c.get(reverse("patrimonio:passaggio_nuovo")).status_code == 403
