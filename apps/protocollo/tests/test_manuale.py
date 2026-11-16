# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test del manuale di gestione documentale: composizione dalla configurazione,
# *              dati organizzativi, adozione protocollata, permessi.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
import pytest
from django.template.loader import render_to_string
from django.urls import reverse

from apps.anagrafica.models import Soggetto
from apps.protocollo import manuale
from apps.protocollo.models import CasellaPosta, ManualeGestione, Protocollo
from apps.protocollo.servizi import OperazioneNonValida

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def cartella_media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def responsabile():
    return Soggetto.objects.create(cognome="Bianchi", nome="Laura")


def _html(**opzioni):
    return render_to_string(manuale.TEMPLATE, manuale.contesto(**opzioni))


def test_composto_dalla_configurazione(crea_utente):
    crea_utente("addetto", ruoli=["Addetto protocollo"], first_name="Anna", last_name="Neri")
    crea_utente("tesoriere", ruoli=["Tesoriere"])
    CasellaPosta.objects.create(
        nome="PEC dell'ente", pec=True, server="imap.example.org", utente="ente@pec.example.org"
    )
    html = _html()
    assert "BOZZA" in html and "[da indicare]" in html
    assert "Anna Neri" in html and "ente@pec.example.org" in html
    assert "Organizzazione e statuto" in html  # titolario di base
    assert "Addetto protocollo" in html and "segnatura di protocollo in formato XML" in html
    ruoli = {r["nome"]: r for r in manuale.contesto()["ruoli"]}
    assert ruoli["Addetto protocollo"]["valori"][1] and not ruoli["Addetto protocollo"]["valori"][3]


def test_testo_dell_utente_neutralizzato(responsabile):
    m = ManualeGestione.corrente()
    m.responsabile = responsabile
    m.atto_adozione = "delibera <b>n. 5</b>"
    m.integrazioni = "**Orari**: la segreteria protocolla il martedì. <script>x</script>"
    m.save()
    html = _html()
    assert "Laura Bianchi" in html and "delibera &lt;b&gt;n. 5&lt;/b&gt;" in html
    assert "<strong>Orari</strong>" in html and "<script>" not in html
    assert "Disposizioni organizzative" in html


def test_adozione_protocollata(crea_utente, responsabile):
    utente = crea_utente("segr", ruoli=["Segretario"])
    with pytest.raises(OperazioneNonValida, match="responsabile"):
        manuale.adotta(utente)
    m = ManualeGestione.corrente()
    m.responsabile, m.atto_adozione = responsabile, "delibera n. 5 del 20/11/2026"
    m.save()
    m = manuale.adotta(utente)
    assert m.versione == 1 and m.adottato_il is not None
    p = m.protocollo
    assert p.direzione == Protocollo.Direzione.INTERNO and "versione 1" in p.oggetto
    assert p.testo == "delibera n. 5 del 20/11/2026"
    allegato = p.allegati.get(principale=True)
    assert allegato.nome == "manuale_gestione_v1.pdf"
    assert p.allegati.filter(nome="manuale_gestione_v1_pubblico.pdf").exists()
    assert manuale.adotta(utente).versione == 2


def test_pagina_e_permessi(client, crea_utente, responsabile):
    addetto = crea_utente("addetto", ruoli=["Addetto protocollo"])
    client.force_login(addetto)
    r = client.get(reverse("protocollo:manuale"))
    assert r.status_code == 200 and "manuale_adotta" not in r.text and 'id="adotta"' not in r.text
    r = client.get(reverse("protocollo:manuale_pdf"))
    assert r.status_code == 200 and r.content[:4] == b"%PDF"
    assert client.post(reverse("protocollo:manuale"), {}).status_code == 403
    assert client.post(reverse("protocollo:manuale_adotta")).status_code == 403
    client.force_login(crea_utente("segr", ruoli=["Segretario"]))
    r = client.post(
        reverse("protocollo:manuale"),
        {"responsabile": responsabile.pk, "atto_adozione": "delibera n. 1"},
    )
    assert r.status_code == 302 and ManualeGestione.corrente().atto_adozione == "delibera n. 1"
    r = client.post(reverse("protocollo:manuale_adotta"))
    assert r.status_code == 302 and ManualeGestione.corrente().versione == 1
    # consultazione: chiunque abbia un ruolo vede le versioni adottate, non la bozza né i dati
    client.force_login(crea_utente("sezione", ruoli=["Presidente di sezione"]))
    r = client.get(reverse("protocollo:manuale"))
    assert r.status_code == 200 and "Versione in vigore (1)" in r.text and "Bozza" not in r.text
    assert client.get(reverse("protocollo:manuale_pdf")).status_code == 403
    r = client.get(reverse("protocollo:manuale_versione", args=[1]))
    assert r.status_code == 200 and r["Content-Type"] == "application/pdf"
    assert "Manuale di gestione documentale" in client.get(reverse("core:aiuto")).text
    assert client.get(reverse("protocollo:manuale_versione", args=[9])).status_code == 404


def test_storico_e_pubblicazione(client, crea_utente, responsabile):
    from apps.core.models import DocumentoPubblico
    from apps.protocollo.models import VersioneManuale

    utente = crea_utente("segr", ruoli=["Segretario"], first_name="Sara", last_name="Gialli")
    CasellaPosta.objects.create(
        nome="PEC", pec=True, server="imap.example.org", utente="login@x.it"
    )
    m = ManualeGestione.corrente()
    m.responsabile = responsabile
    m.save()
    with pytest.raises(OperazioneNonValida):
        manuale.pubblica_in_vigore(utente)  # niente da pubblicare
    manuale.adotta(utente)
    v1 = VersioneManuale.objects.get()
    assert not DocumentoPubblico.objects.exists() and v1.allegato_pubblico is not None
    assert v1.protocollo.allegati.count() == 2
    # pubblicata dopo l'adozione: la variante prodotta allora, non la configurazione di oggi
    CasellaPosta.objects.create(nome="Nuova", server="imap.example.org", utente="altra@x.it")
    client.force_login(utente)
    client.post(reverse("protocollo:manuale_pubblica"), {"azione": "pubblica"})
    doc = DocumentoPubblico.objects.get()
    with doc.file.open("rb") as a, v1.allegato_pubblico.file.open("rb") as b:
        assert a.read() == b.read()
    assert doc.pubblicato and "versione 1" in doc.descrizione and manuale.pubblicato()
    # una nuova versione sostituisce quella pubblicata
    manuale.adotta(utente)
    assert DocumentoPubblico.objects.get().descrizione.startswith("versione 2")
    assert list(VersioneManuale.objects.values_list("versione", "pubblicata")) == [
        (2, True), (1, False),
    ]  # fmt: skip
    client.post(reverse("protocollo:manuale_pubblica"), {"azione": "ritira"})
    assert not manuale.pubblicato() and not DocumentoPubblico.objects.get().pubblicato
    assert not VersioneManuale.objects.filter(pubblicata=True).exists()
    client.force_login(crea_utente("addetto", ruoli=["Addetto protocollo"]))
    r = client.post(reverse("protocollo:manuale_pubblica"), {"azione": "pubblica"})
    assert r.status_code == 403
    pubblico = _html(bozza=False, pubblico=True)
    interno = _html(bozza=False)
    assert "Sara Gialli" in interno and "login@x.it" in interno
    assert "Sara Gialli" not in pubblico and "login@x.it" not in pubblico
    assert "non è pubblicato" in pubblico and "Organizzazione e statuto" in pubblico
