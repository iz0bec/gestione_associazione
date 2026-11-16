# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test delle firme e dei timbri nelle stampe: immagini caricate (ripulite, con
# *              sfondo trasparente), firma e timbro generici, pagina di gestione e permessi.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
import io
from datetime import date

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template import Context, Template
from django.urls import reverse
from PIL import Image, ImageDraw

from apps.anagrafica.models import Soggetto
from apps.core.models import EventoAudit, Organizzazione
from apps.organi import servizi, timbro_generico
from apps.organi.firme import timbro
from apps.organi.models import Carica, FirmaGrafica, Organo, Timbro
from apps.organi.servizi import OperazioneNonValida

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def cartella_media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def presidente():
    persona = Soggetto.objects.create(cognome="Rossi", nome="Mario", titolo="Cav.")
    Carica.objects.create(
        organo=Organo.objects.get(sigla="CD"), soggetto=persona, ruolo="presidente",
        dal=date(2025, 1, 1),
    )  # fmt: skip
    return persona


@pytest.fixture
def amministratore(crea_utente):
    return crea_utente("admin", ruoli=["Amministratore di sistema"])


def _scansione(formato="JPEG", sfondo=(246, 244, 238)):
    """Firma scura su carta chiara, come da scanner o fotografia."""
    img = Image.new("RGB", (900, 400), sfondo)
    ImageDraw.Draw(img).line([(100, 250), (300, 120), (500, 260), (800, 140)], (20, 30, 90), 12)
    buffer = io.BytesIO()
    img.save(buffer, formato)
    return SimpleUploadedFile(f"firma.{formato.lower()}", buffer.getvalue())


def _blocco(**opzioni):
    argomenti = " ".join(f"{k}={v}" for k, v in opzioni.items())
    return Template(f'{{% load firme %}}{{% firme "presidente" {argomenti} %}}').render(Context())


class TestImmagine:
    def test_sfondo_trasparente_e_ritaglio(self, presidente, amministratore):
        firma = servizi.carica_firma(presidente, _scansione(), amministratore)
        img = Image.open(firma.immagine.path)
        assert img.format == "PNG" and img.mode == "RGBA"
        assert img.getpixel((0, 0))[3] == 0  # carta → trasparente
        assert img.width < 900 and img.height < 400  # ritagliata sul tratto
        assert img.getchannel("A").getextrema()[1] == 255  # inchiostro pieno
        assert len(firma.impronta) == 64
        assert EventoAudit.objects.filter(azione="creazione").exists()

    def test_senza_togliere_lo_sfondo(self, presidente, amministratore):
        firma = servizi.carica_firma(
            presidente, _scansione(), amministratore, sfondo_trasparente=False
        )
        assert Image.open(firma.immagine.path).getpixel((0, 0))[3] == 255

    def test_immagine_vuota_o_non_valida(self, presidente, amministratore):
        bianca = _scansione()
        img = Image.new("RGB", (300, 200), (255, 255, 255))
        buffer = io.BytesIO()
        img.save(buffer, "PNG")
        with pytest.raises(OperazioneNonValida, match="né una firma né un timbro"):
            servizi.carica_firma(
                presidente, SimpleUploadedFile("b.png", buffer.getvalue()), amministratore
            )
        with pytest.raises(OperazioneNonValida, match="non è un'immagine"):
            servizi.carica_firma(presidente, SimpleUploadedFile("x.png", b"testo"), amministratore)
        assert bianca and not FirmaGrafica.objects.exists()

    def test_risoluzione_troppo_bassa(self, presidente, amministratore):
        img = Image.new("RGB", (240, 100), (255, 255, 255))
        ImageDraw.Draw(img).line([(20, 70), (220, 30)], (0, 0, 0), 4)
        buffer = io.BytesIO()
        img.save(buffer, "PNG")
        with pytest.raises(OperazioneNonValida, match="300 dpi"):
            servizi.carica_firma(
                presidente, SimpleUploadedFile("p.png", buffer.getvalue()), amministratore
            )

    def test_solo_per_le_persone(self, amministratore):
        ente = Soggetto.objects.create(tipo="ente", denominazione="Comune")
        with pytest.raises(OperazioneNonValida):
            servizi.carica_firma(ente, _scansione(), amministratore)

    def test_sostituzione_cancella_il_file_precedente(
        self, presidente, amministratore, django_capture_on_commit_callbacks
    ):
        with django_capture_on_commit_callbacks(execute=True):
            prima = servizi.carica_firma(presidente, _scansione(), amministratore)
        percorso = prima.immagine.path
        with django_capture_on_commit_callbacks(execute=True):
            dopo = servizi.carica_firma(presidente, _scansione("PNG"), amministratore)
        assert dopo.pk == prima.pk and dopo.immagine.path != percorso
        import os

        assert not os.path.exists(percorso)


class TestStampa:
    def test_firma_caricata_nel_blocco(self, presidente, amministratore):
        firma = servizi.carica_firma(presidente, _scansione(), amministratore)
        html = _blocco()
        assert f'src="risorsa:media/{firma.immagine.name}"' in html
        servizi.imposta_uso(firma, False, amministratore)
        assert "risorsa:media" not in _blocco()

    def test_firma_generica(self, presidente):
        # accesa in partenza
        assert '<span class="firma-generica">Cav. Mario Rossi</span>' in _blocco()
        servizi.imposta_generici(None, firma_generica=False, timbro_generico=True)
        assert "firma-generica" not in _blocco()

    def test_vacante_niente_firma_generica(self):
        assert Organizzazione.corrente().firma_generica
        assert "firma-generica" not in _blocco()

    def test_immagini_escluse_su_richiesta(self, presidente, amministratore):
        servizi.carica_firma(presidente, _scansione(), amministratore)
        servizi.carica_timbro(None, _scansione(), amministratore)
        html = _blocco(immagini="False")
        assert "risorsa:media" not in html and "timbro-calce" not in html

    def test_timbro_caricato_o_generico(self, presidente, amministratore):
        servizi.imposta_generici(None, firma_generica=True, timbro_generico=False)
        assert timbro() is None and "timbro-calce" not in _blocco()
        org = Organizzazione.corrente()
        org.denominazione, org.comune, org.timbro_generico = "Amici <del> Paese", "Avigliano", True
        org.save()
        generico = timbro()
        assert (
            generico.svg and "AVIGLIANO" in generico.svg and ">&lt;<" in generico.svg
        )  # lettera per lettera, con escape
        assert "<svg" in _blocco() and "<del>" not in _blocco()
        assert "timbro-calce" not in _blocco(timbro="False")
        caricato = servizi.carica_timbro(None, _scansione(), amministratore)
        assert timbro().immagine == caricato.immagine.name

    def test_timbro_della_sezione(self, amministratore):
        from apps.soci.models import Sezione

        sezione = Sezione.objects.create(codice="S1", nome="Montebello")
        servizi.carica_timbro(None, _scansione(), amministratore)
        assert timbro(sezione).svg  # non prende quello dell'associazione: vale il generico
        assert "SEZIONE" in timbro_generico.svg(Organizzazione.corrente(), sezione)
        servizi.carica_timbro(sezione, _scansione(), amministratore)
        assert Timbro.objects.count() == 2 and timbro(sezione).immagine

    def test_firme_nei_modelli_di_stampa(self, presidente, amministratore):
        from apps.documenti.models import ModelloStampa
        from apps.documenti.servizi import anteprima

        firma = servizi.carica_firma(presidente, _scansione(), amministratore)
        modello = ModelloStampa.objects.filter(tipo="lettera").first()
        assert modello is not None
        import apps.documenti.servizi as doc

        contesto = doc._contesto_pdf(modello, [])
        assert contesto["firma_grafica"].immagine == firma.immagine.name
        assert anteprima(modello)[:4] == b"%PDF"


class TestPagina:
    def test_gestione(self, client, presidente, amministratore):
        client.force_login(amministratore)
        r = client.get(reverse("organi:firme"))
        assert r.status_code == 200 and "Cav. Mario Rossi" in r.text
        r = client.post(
            reverse("organi:carica_firma", args=[presidente.pk]),
            {"immagine": _scansione("PNG"), "sfondo_trasparente": "on",
             "autorizzazione": "scritta del 12/11/2026"},
        )  # fmt: skip
        firma = FirmaGrafica.objects.get()
        assert firma.autorizzazione == "scritta del 12/11/2026"
        r = client.get(reverse("organi:immagine_firma", args=["firma", firma.pk]))
        assert r.status_code == 200 and r["Content-Type"] == "image/png"
        client.post(reverse("organi:uso_firma", args=["firma", firma.pk]), {"azione": "disattiva"})
        firma.refresh_from_db()
        assert not firma.attiva
        r = client.post(reverse("organi:carica_timbro", args=[0]), {"immagine": _scansione()})
        assert Timbro.objects.filter(sezione=None).exists()
        assert r.url == reverse("core:organizzazione") + "#timbri"
        r = client.get(reverse("organi:foglio_firme", args=["firma"]), {"soggetto": presidente.pk})
        assert r.status_code == 200 and r.content[:4] == b"%PDF"
        r = client.get(reverse("organi:foglio_firme", args=["timbro"]))
        assert r.status_code == 200
        assert client.get(reverse("organi:foglio_firme", args=["altro"])).status_code == 404
        client.post(reverse("organi:firme_generiche"), {})  # solo la firma generica
        client.post(reverse("organi:timbro_generico"), {"timbro_generico": "on"})
        org = Organizzazione.corrente()
        assert org.timbro_generico and not org.firma_generica
        r = client.get(reverse("organi:prova_firme"))
        assert r.status_code == 200 and r.content[:4] == b"%PDF"
        client.post(reverse("organi:uso_firma", args=["firma", firma.pk]), {"azione": "togli"})
        assert not FirmaGrafica.objects.exists()

    def test_permessi(self, client_ruolo, presidente):
        client = client_ruolo("Consigliere")
        assert client.get(reverse("organi:firme")).status_code == 403
        firma = FirmaGrafica.objects.create(soggetto=presidente, immagine="x.png", impronta="0")
        r = client.get(reverse("organi:immagine_firma", args=["firma", firma.pk]))
        assert r.status_code == 403
        r = client.get(reverse("organi:immagine_firma", args=["altro", firma.pk]))
        assert r.status_code == 403

    def test_timbri_solo_amministratore(self, client, crea_utente, amministratore):
        segretario = crea_utente("segr", ruoli=["Segretario"])
        assert not segretario.has_perm("organi.gestisci_timbri")
        assert amministratore.has_perm("organi.gestisci_timbri")
        timbro_ente = servizi.carica_timbro(None, _scansione(), amministratore)
        client.force_login(segretario)
        pagina = client.get(reverse("organi:firme")).text
        assert "Si impostano in" in pagina and "carica_timbro" not in pagina
        assert reverse("organi:carica_timbro", args=[0]) not in pagina
        r = client.get(reverse("organi:immagine_firma", args=["timbro", timbro_ente.pk]))
        assert r.status_code == 200  # anteprima in sola lettura
        assert client.post(reverse("organi:carica_timbro", args=[0]),
                           {"immagine": _scansione()}).status_code == 403  # fmt: skip
        uso = reverse("organi:uso_firma", args=["timbro", timbro_ente.pk])
        assert client.post(uso, {"azione": "togli"}).status_code == 403
        assert client.post(reverse("organi:timbro_generico"), {}).status_code == 403
        assert client.get(reverse("organi:foglio_firme", args=["timbro"])).status_code == 403
        organizzazione = client.get(reverse("core:organizzazione"))
        assert organizzazione.status_code == 200 and 'id="timbri"' not in organizzazione.text
        client.force_login(amministratore)
        pagina = client.get(reverse("core:organizzazione")).text
        assert 'id="timbri"' in pagina and reverse("organi:carica_timbro", args=[0]) in pagina
        r = client.post(uso, {"azione": "disattiva"})
        assert r.url.endswith("#timbri")
        timbro_ente.refresh_from_db()
        assert not timbro_ente.attiva

    def test_ruoli_con_il_permesso(self, crea_utente):
        ruoli = ("Amministratore di sistema", "Presidente", "Segretario", "Presidente di sezione")
        for n, ruolo in enumerate(ruoli):
            assert crea_utente(f"utente{n}", ruoli=[ruolo]).has_perm("organi.gestisci_firme")


class TestPresidenteDiSezione:
    @pytest.fixture
    def sezioni(self):
        from apps.soci.models import Sezione

        return Sezione.objects.create(codice="S1", nome="Montebello"), Sezione.objects.create(
            codice="S2", nome="Collina"
        )

    @pytest.fixture
    def client_sezione(self, client, crea_utente, sezioni):
        utente = crea_utente("pres_sez", ruoli=["Presidente di sezione"])
        utente.sezioni.set([sezioni[0]])
        client.force_login(utente)
        return client

    def _presidente(self, sezione, cognome):
        organo = Organo.objects.create(
            nome=f"Direttivo {cognome}", sigla=cognome[:3].upper(), tipo="consiglio",
            sezione=sezione,
        )  # fmt: skip
        persona = Soggetto.objects.create(cognome=cognome, nome="Anna")
        Carica.objects.create(
            organo=organo, soggetto=persona, ruolo="presidente", dal=date(2025, 1, 1)
        )
        return persona

    def test_solo_la_propria_sezione(self, client_sezione, sezioni, presidente, amministratore):
        mia = self._presidente(sezioni[0], "Verdi")
        altra = self._presidente(sezioni[1], "Neri")
        r = client_sezione.get(reverse("organi:firme"))
        assert r.status_code == 200
        assert "Anna Verdi" in r.text and "Neri" not in r.text and "Cav. Mario Rossi" not in r.text
        assert "Montebello" in r.text and "Collina" not in r.text
        assert "Se manca l'immagine" not in r.text  # interruttori dell'intera associazione
        r = client_sezione.post(
            reverse("organi:carica_firma", args=[mia.pk]), {"immagine": _scansione()}
        )
        assert FirmaGrafica.objects.filter(soggetto=mia).exists()
        r = client_sezione.post(
            reverse("organi:carica_firma", args=[altra.pk]), {"immagine": _scansione()}
        )
        assert r.status_code == 403
        for sezione in (0, sezioni[0].pk, sezioni[1].pk):  # i timbri: solo l'amministratore
            r = client_sezione.post(
                reverse("organi:carica_timbro", args=[sezione]), {"immagine": _scansione()}
            )
            assert r.status_code == 403
        assert Timbro.objects.count() == 0
        firma_altrui = servizi.carica_firma(altra, _scansione(), amministratore)
        r = client_sezione.get(reverse("organi:immagine_firma", args=["firma", firma_altrui.pk]))
        assert r.status_code == 403
        r = client_sezione.post(reverse("organi:firme_generiche"), {})
        assert r.status_code == 403 and Organizzazione.corrente().firma_generica
        r = client_sezione.get(reverse("organi:prova_firme"))
        assert r.status_code == 200
        r = client_sezione.get(reverse("organi:prova_firme"), {"sezione": sezioni[1].pk})
        assert r.status_code == 403
        r = client_sezione.get(reverse("organi:foglio_firme", args=["timbro"]))
        assert r.status_code == 403  # timbro dell'associazione
