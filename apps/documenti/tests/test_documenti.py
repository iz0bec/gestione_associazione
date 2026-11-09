# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test dei modelli di stampa e della stampa dei documenti
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from datetime import date

import pytest

from apps.anagrafica.models import Categoria, Soggetto
from apps.core.models import EventoAudit
from apps.documenti import servizi
from apps.documenti.models import ModelloStampa
from apps.protocollo.models import Protocollo


@pytest.fixture(autouse=True)
def cartella_media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def rossi():
    return Soggetto.objects.create(
        tipo=Soggetto.Tipo.PERSONA, cognome="Rossi", nome="Mario", sesso="M",
        indirizzo="Via Roma 1", cap="85021", comune="Avigliano", provincia="PZ",
    )  # fmt: skip


def _modello(nome="Lettera"):
    return ModelloStampa.objects.get(nome=nome)


@pytest.mark.django_db
class TestComposizione:
    def test_modelli_predefiniti(self):
        nomi = set(ModelloStampa.objects.values_list("nome", flat=True))
        assert {"Attestato di iscrizione", "Lettera di auguri", "Lettera",
                "Attestato di benemerenza"} <= nomi  # fmt: skip

    def test_segnaposto_e_html_neutralizzato(self, rossi):
        rossi.nome = "<script>x</script>"
        html = servizi.testo_html("{{ saluto }} **{{ nome }}**\n\n<b>no</b>",
                                  servizi._contesto(rossi, ""))  # fmt: skip
        assert "<strong>&lt;script&gt;" in html and "<b>" not in html
        assert html.startswith("<p>Caro")

    def test_segnaposto_sconosciuti(self):
        assert servizi.segnaposto_sconosciuti("{{ nome }} {{ boh }}", "{{ luogo }}") == ["boh"]

    def test_firmatario_presidente_in_carica(self, rossi):
        from apps.organi.models import Carica, Organo

        organo = Organo.objects.first() or Organo.objects.create(nome="Consiglio")
        Carica.objects.create(organo=organo, soggetto=rossi, ruolo="presidente",
                              dal=date(2020, 1, 1))  # fmt: skip
        assert servizi.firmatario(_modello()) == "Mario Rossi"
        m = _modello()
        m.firma_nome = "Altro Nome"
        assert servizi.firmatario(m) == "Altro Nome"

    def test_modelli_privacy_firmati_dal_rappresentante_legale(self, rossi):
        from apps.organi.models import RappresentanteLegale

        privacy = ModelloStampa.objects.filter(nome__startswith="Privacy - ")
        assert privacy.count() >= 6 and all(m.firma_legale for m in privacy)
        for m in privacy:  # nessun segnaposto ignoto nei testi pronti
            assert servizi.segnaposto_sconosciuti(m.titolo, m.corpo) == []
        landi = Soggetto.objects.create(cognome="Landi", nome="Antonio", titolo="Prof.")
        RappresentanteLegale.objects.create(
            soggetto=landi, qualifica="Il Presidente nazionale", dal=date(2020, 1, 1),
            tutta_la_struttura=True,
        )  # fmt: skip
        m = privacy.first()
        assert servizi.firmatario(m) == "Prof. Antonio Landi"
        assert servizi.qualifica_firmatario(m) == "Il Presidente nazionale"
        c = servizi._contesto(rossi, "")
        assert c["rappresentante_legale"] == "Prof. Antonio Landi"
        assert servizi.anteprima(m, rossi).startswith(b"%PDF")


@pytest.mark.django_db
class TestStampa:
    def test_permessi(self, client_ruolo):
        assert (
            client_ruolo("Consigliere", username="c").get("/documenti/stampa/").status_code == 403
        )
        client = client_ruolo("Segretario", username="s")
        assert client.get("/documenti/").status_code == 200
        assert client.get("/documenti/nuovo/").status_code == 200

    def test_stampa_da_scheda(self, client_ruolo, rossi):
        client = client_ruolo("Segretario")
        assert "Stampa documento" in client.get(f"/anagrafica/{rossi.pk}/").content.decode()
        r = client.post("/documenti/stampa/", {"modello": _modello().pk,
                        "destinazione": "soggetto", "soggetto": rossi.pk})  # fmt: skip
        assert r.status_code == 200 and r["Content-Type"] == "application/pdf"
        assert r.content.startswith(b"%PDF")
        assert EventoAudit.objects.filter(azione="esportazione").exists()

    def test_lista_per_categoria_esclude_deceduti(self, client_ruolo, rossi):
        cat = Categoria.objects.create(nome="Prova stampa")
        morto = Soggetto.objects.create(tipo=Soggetto.Tipo.PERSONA, cognome="Verdi",
                                        data_decesso=date(2020, 1, 1))  # fmt: skip
        rossi.categorie.add(cat)
        morto.categorie.add(cat)
        r = client_ruolo("Segretario").post("/documenti/stampa/", {
            "modello": _modello().pk, "destinazione": "categoria", "categoria": cat.pk})  # fmt: skip
        assert r.status_code == 200 and r["X-Esclusi"] == "1"

    def test_protocollazione_in_uscita(self, client_ruolo, rossi):
        client = client_ruolo("Segretario")
        r = client.post("/documenti/stampa/", {"modello": _modello().pk,
                        "destinazione": "soggetto", "soggetto": rossi.pk,
                        "protocolla": "on", "mezzo": "raccomandata"})  # fmt: skip
        p = Protocollo.objects.get()
        assert p.direzione == "uscita" and p.mezzo == "raccomandata"
        assert p.destinatari[0].soggetto == rossi
        assert p.allegati.get().principale
        assert p.segnatura in r["Content-Disposition"]

    def test_senza_permesso_di_protocollo_non_protocolla(self, client_ruolo, rossi):
        client = client_ruolo("Tesoriere")  # stampa sì, protocollo no
        r = client.post("/documenti/stampa/", {"modello": _modello().pk,
                        "destinazione": "soggetto", "soggetto": rossi.pk,
                        "protocolla": "on"})  # fmt: skip
        assert r.status_code == 200 and "permesso" in r.content.decode()
        assert not Protocollo.objects.exists()

    def test_modello_con_segnaposto_sconosciuto(self, client_ruolo):
        r = client_ruolo("Segretario").post("/documenti/nuovo/", {
            "nome": "Prova", "tipo": "documento", "corpo": "{{ inesistente }}",
            "firma_ruolo": "", "attivo": "on"})  # fmt: skip
        assert "Segnaposto sconosciuti" in r.content.decode()
        assert not ModelloStampa.objects.filter(nome="Prova").exists()

    def test_anteprima(self, client_ruolo):
        r = client_ruolo("Segretario").get(
            f"/documenti/{_modello('Attestato di iscrizione').pk}/anteprima/"
        )
        assert r.status_code == 200 and r.content.startswith(b"%PDF")


def _png():
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGBA", (40, 40), (180, 140, 60, 255)).save(buf, "PNG")
    buf.name = "stemma.png"
    buf.seek(0)
    return buf


@pytest.mark.django_db
class TestBenemerenza:
    def test_modello_pronto_e_template(self):
        m = _modello("Attestato di benemerenza")
        assert m.tipo == ModelloStampa.Tipo.BENEMERENZA and m.seconda_firma == "segretario"
        assert servizi.template_di(m) == servizi.TEMPLATE_BENEMERENZA
        assert servizi.template_di(_modello()) == servizi.TEMPLATE

    def test_seconda_firma_in_carica(self, rossi):
        from apps.organi.models import Carica, Organo

        organo = Organo.objects.first() or Organo.objects.create(nome="Consiglio")
        rossi.titolo = "Cav."
        rossi.save()
        Carica.objects.create(organo=organo, soggetto=rossi, ruolo="segretario",
                              dal=date(2020, 1, 1))  # fmt: skip
        firma = servizi.seconda_firma(_modello("Attestato di benemerenza"))
        assert firma == {"ruolo": "Il Segretario", "nome": "Cav. Mario Rossi"}
        assert servizi.seconda_firma(_modello()) is None

    def test_pdf_con_font_e_ornamenti(self, rossi, monkeypatch):
        from apps.core import pdf as modulo_pdf

        lette = []
        originale = modulo_pdf._percorso_risorsa
        monkeypatch.setattr(modulo_pdf, "_percorso_risorsa",
                            lambda url: lette.append(url) or originale(url))  # fmt: skip
        pdf = servizi.anteprima(_modello("Attestato di benemerenza"), rossi)
        assert pdf.startswith(b"%PDF")
        nomi = {u.rsplit("/", 1)[-1] for u in lette}
        assert {"Cinzel-VF.ttf", "EBGaramond-VF.ttf", "EBGaramond-Italic-VF.ttf", "angolo.svg",
                "alloro.svg", "sigillo.svg", "fregio.svg"} <= nomi  # fmt: skip

    def test_stemma_caricato_e_tolto(self, client_ruolo):
        client = client_ruolo("Segretario")
        m = _modello("Attestato di benemerenza")
        dati = {"nome": m.nome, "tipo": m.tipo, "titolo": m.titolo, "corpo": m.corpo,
                "firma_ruolo": m.firma_ruolo, "firma_nome": "", "seconda_firma": "segretario",
                "attivo": "on"}  # fmt: skip
        r = client.post(f"/documenti/{m.pk}/", {**dati, "nuovo_stemma": _png()})
        assert r.status_code == 302
        m.refresh_from_db()
        assert m.stemma.name.startswith("stemmi/")
        assert servizi.stemmi(m, _org())[-1] == m.stemma.name
        assert client.get(f"/documenti/{m.pk}/anteprima/").status_code == 200
        client.post(f"/documenti/{m.pk}/", {**dati, "togli_stemma": "on"})
        m.refresh_from_db()
        assert not m.stemma


def _org():
    from apps.core.models import Organizzazione

    return Organizzazione.corrente()
