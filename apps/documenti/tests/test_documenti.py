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
        assert {"Attestato di iscrizione", "Lettera di auguri", "Lettera"} <= nomi

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
        assert servizi.firmatario(_modello()) == "Rossi Mario"
        m = _modello()
        m.firma_nome = "Altro Nome"
        assert servizi.firmatario(m) == "Altro Nome"


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
