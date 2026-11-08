# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test dei documenti pubblici (statuto, regolamento) e del ruolo di sezione
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.core.models import DocumentoPubblico

pytestmark = pytest.mark.django_db
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


@pytest.fixture(autouse=True)
def cartella_media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def _carica(client, titolo="Statuto sociale", contenuto=PDF, **extra):
    f = SimpleUploadedFile("statuto.pdf", contenuto, content_type="application/pdf")
    return client.post("/sistema/documenti-pubblici/nuovo/", {
        "titolo": titolo, "descrizione": "in vigore dal 21/06/2021", "ordine": 1,
        "pubblicato": "on", "nuovo_file": f, **extra,
    })  # fmt: skip


def test_caricamento_e_consultazione_pubblica(client_ruolo, client):
    gestore = client_ruolo("Segretario")
    assert _carica(gestore).status_code == 302
    doc = DocumentoPubblico.objects.get()
    assert doc.nome_file == "statuto.pdf" and doc.file.name.startswith("pubblici/")
    gestore.logout()
    pagina = client.get("/documenti-pubblici/").content.decode()
    assert "Statuto sociale" in pagina and "in vigore dal 21/06/2021" in pagina
    r = client.get(doc.get_absolute_url())
    assert r.status_code == 200 and r["Content-Type"] == "application/pdf"
    assert b"".join(r.streaming_content) == PDF and "inline" in r["Content-Disposition"]
    assert "attachment" in client.get(doc.get_absolute_url() + "?scarica=1")["Content-Disposition"]
    assert "Statuto e regolamento" in client.get("/account/login/").content.decode()
    DocumentoPubblico.objects.update(pubblicato=False)
    assert client.get(doc.get_absolute_url()).status_code == 404
    assert "Statuto sociale" not in client.get("/documenti-pubblici/").content.decode()


def test_solo_pdf_e_sostituzione(client_ruolo):
    gestore = client_ruolo("Segretario")
    r = _carica(gestore, contenuto=b"<html>non un pdf</html>")
    assert r.status_code == 200 and "non è un PDF" in r.content.decode()
    _carica(gestore)
    doc = DocumentoPubblico.objects.get()
    vecchio = doc.file.name
    nuovo = SimpleUploadedFile("statuto-2026.pdf", PDF + b"%nuovo", content_type="application/pdf")
    gestore.post(f"/sistema/documenti-pubblici/{doc.pk}/", {
        "titolo": "Statuto sociale", "ordine": 1, "pubblicato": "on", "nuovo_file": nuovo})  # fmt: skip
    doc.refresh_from_db()
    assert doc.nome_file == "statuto-2026.pdf" and doc.file.name != vecchio
    assert not doc.file.storage.exists(vecchio)


def test_gestione_riservata(client_ruolo):
    assert client_ruolo("Tesoriere").get("/sistema/documenti-pubblici/").status_code == 403


def test_presidente_di_sezione(client_ruolo):
    from apps.anagrafica.models import Soggetto
    from apps.soci import servizi as soci
    from apps.soci.models import Sezione, TipologiaSocio

    mia = Sezione.objects.create(codice="AV", nome="Avigliano", comune="Avigliano")
    altra = Sezione.objects.create(codice="PZ", nome="Potenza", comune="Potenza")
    c = client_ruolo("Presidente di sezione")
    c.utente.sezioni.add(mia)
    ordinario = TipologiaSocio.objects.get(nome="Ordinario")
    for nome, sezione in (("Mio", mia), ("Altro", altra)):
        soci.ammetti_socio(Soggetto.objects.create(cognome=nome, nome="Mario"), ordinario,
                           c.utente, sezione=sezione)  # fmt: skip
    elenco = c.get("/soci/").content.decode()
    assert "Mio Mario" in elenco and "Altro Mario" not in elenco
    for url in ("/protocollo/", "/tesoreria/", "/organi/", "/patrimonio/", "/comunicazioni/",
                "/soci/tipologie/nuova/"):  # fmt: skip
        assert c.get(url).status_code == 403, url
    assert c.get("/calendario/").status_code == 200 and c.get("/anagrafica/").status_code == 200
