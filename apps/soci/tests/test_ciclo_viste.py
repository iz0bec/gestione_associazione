# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test delle pagine del ciclo delle tessere: campagna, richieste, magazzino,
# *              consegne con PDF e file, ordine, avvisi alle sezioni (bozze con i segnaposto),
# *              importazione della consegna con anteprima e permessi.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from datetime import date
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.soci import ciclo
from apps.soci.models import ConsegnaTessere, ListinoTessere, LottoTessere, Sezione

pytestmark = pytest.mark.django_db
ANNO = date.today().year


@pytest.fixture(autouse=True)
def cartella_media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def admin(client_ruolo):
    client = client_ruolo("Amministratore di sistema")
    ListinoTessere.objects.update_or_create(anno=ANNO, defaults={
        "costo_acquisto": Decimal("3.50"), "quota_federale": Decimal("1.50"),
        "scadenza_richieste": date(ANNO, 2, 28), "istruzioni_pagamento": "IBAN IT00 X000",
    })  # fmt: skip
    return client


@pytest.fixture
def sezione():
    return Sezione.objects.create(codice="PZ01", nome="Sezione di Avigliano",
                                  email="avigliano@example.org")  # fmt: skip


def test_solo_con_il_permesso(client_ruolo):
    assert client_ruolo("Consigliere").get(f"/soci/tessere/campagna/{ANNO}/").status_code == 403


def test_percorso_completo(admin, sezione):
    base = f"/soci/tessere/campagna/{ANNO}/"
    assert admin.get(base).status_code == 200
    r = admin.post(
        base + "richiesta/", {"sezione": sezione.pk, "quantita": 30, "data": date.today()}
    )
    assert r.status_code == 302
    r = admin.post(base + "blocco/", {"numero_da": 1, "numero_a": 100, "data_arrivo": date.today(),
                                      "fornitore": "Sede nazionale", "serie": ""})  # fmt: skip
    assert r.status_code == 302
    pagina = admin.get(base + "consegna/").content.decode()
    assert 'value="1"' in pagina and 'value="100"' in pagina  # primo intervallo libero proposto
    blocco = ciclo.riepilogo_magazzino(ANNO)["blocchi"][0]
    r = admin.post(base + "consegna/", {
        "blocco": blocco.pk, "sezione": sezione.pk, "numero_da": 1, "numero_a": 30,
        "data": date.today(), "modalita": "ritiro", "note_distribuzione": "In sede, sabato",
    })  # fmt: skip
    assert r.status_code == 302
    consegna = ConsegnaTessere.objects.get()
    assert consegna.importo == Decimal("150.00")
    r = admin.get(f"/soci/tessere/consegne/{consegna.pk}/pdf/")
    assert r.status_code == 200 and r["Content-Type"] == "application/pdf"
    r = admin.get(f"/soci/tessere/consegne/{consegna.pk}/numeri.csv")
    assert r.status_code == 200 and b"numero_da" in r.content
    admin.post(f"/soci/tessere/consegne/{consegna.pk}/presa-in-carico/")
    consegna.refresh_from_db()
    assert consegna.presa_in_carico_il == date.today()
    r = admin.post(base + "ordine/", {"data": date.today()})
    assert r.status_code == 302
    ordine = sezione.richieste_tessere.first()
    assert ordine is not None
    from apps.soci.models import OrdineTessere

    o = OrdineTessere.objects.get()
    assert admin.get(f"/soci/tessere/ordini/{o.pk}/pdf/").status_code == 200
    assert admin.get(f"/soci/tessere/richieste/{ordine.pk}/pdf/").status_code == 200
    pagina = admin.get(base).content.decode()
    assert "Sezione di Avigliano" in pagina and "150,00" in pagina


def test_avvisi_in_bozza_con_i_dati_della_sezione(admin, sezione):
    from apps.comunicazioni.models import Invio

    r = admin.post(f"/soci/tessere/campagna/{ANNO}/avvisi/tesseramento/",
                   {"sezioni": [sezione.pk], "protocolla": ""})  # fmt: skip
    assert r.status_code == 302 and r["Location"] == "/comunicazioni/"
    invio = Invio.objects.get()
    assert invio.stato == "bozza" and invio.origine == "tessere_avviso"
    assert invio.contesto["sezione"] == "Sezione di Avigliano"
    assert invio.contesto["quota_tessera"] == "5,00"
    assert invio.contesto["delibera"] == "la delibera [da indicare]"  # mai valori inventati
    assert invio.contesto["scadenza_richiesta"] == f"28/02/{ANNO}"
    assert list(invio.destinatari.values_list("email", flat=True)) == ["avigliano@example.org"]
    # il sollecito propone solo le sezioni senza richiesta
    form = admin.get(f"/soci/tessere/campagna/{ANNO}/avvisi/sollecito/").context["form"]
    assert sezione in form.initial["sezioni"]
    ciclo.registra_richiesta(admin.utente, anno=ANNO, sezione=sezione, quantita=5)
    form = admin.get(f"/soci/tessere/campagna/{ANNO}/avvisi/sollecito/").context["form"]
    assert sezione not in form.initial["sezioni"]


def test_avviso_di_attribuzione_per_consegna(admin, sezione):
    from apps.comunicazioni.models import Invio

    blocco = ciclo.carica_blocco(admin.utente, anno=ANNO, numero_da=10, numero_a=19, serie="B")
    consegna = ciclo.consegna(admin.utente, blocco=blocco, sezione=sezione, numero_da=10,
                              numero_a=19, modalita="spedizione")  # fmt: skip
    admin.post(f"/soci/tessere/campagna/{ANNO}/avvisi/attribuzione/",
               {"consegne": [consegna.pk]})  # fmt: skip
    contesto = Invio.objects.get().contesto
    assert contesto["tessere"] == "serie B, dal n. 10 al n. 19"
    assert (contesto["quantita"], contesto["importo_dovuto"], contesto["saldo"]) == (
        10,
        "50,00",
        "50,00",
    )
    assert contesto["modalita_distribuzione"] == "spedizione"


def test_importa_consegna_con_anteprima(admin, sezione):
    contenuto = (
        "anno;serie;numero_da;numero_a;cifre;prezzo_unitario;consegna;data;fornitore\n"
        f"{ANNO};C;1;5;3;5.00;{ANNO}/7;{ANNO}-01-15;Federazione Potenza Matera\n"
    ).encode()
    r = admin.post("/soci/tessere/importa-consegna/",
                   {"file": SimpleUploadedFile("consegna.csv", contenuto), "sezione": sezione.pk})  # fmt: skip
    assert r.status_code == 200 and r.context["righe"] and not LottoTessere.objects.exists()
    r = admin.post("/soci/tessere/importa-consegna/", {
        "temporaneo": r.context["temporaneo"], "conferma": "1", "sezione": sezione.pk,
    })  # fmt: skip
    assert r.status_code == 302
    lotto = LottoTessere.objects.get()
    assert (lotto.sezione, lotto.fornitore, lotto.quantita) == (
        sezione,
        "Federazione Potenza Matera",
        5,
    )
    assert lotto.riferimento == f"Consegna n. {ANNO}/7 del {ANNO}-01-15"


def test_voce_nel_menu(client_ruolo):
    tesoriere = client_ruolo("Tesoriere", username="tesoriere").get("/").content.decode()
    assert "Campagna delle tessere" in tesoriere
    consigliere = client_ruolo("Consigliere", username="consigliere").get("/").content.decode()
    assert "Campagna delle tessere" not in consigliere


def test_denominazione_della_sezione_negli_avvisi(admin):
    from apps.comunicazioni.models import Invio

    ruoti = Sezione.objects.create(codice="007", nome="Ruoti", email="ruoti@example.org")
    assert ruoti.denominazione == "Sezione di Ruoti"
    assert Sezione(nome="Sezione di Avigliano").denominazione == "Sezione di Avigliano"
    admin.post(f"/soci/tessere/campagna/{ANNO}/avvisi/tesseramento/", {"sezioni": [ruoti.pk]})
    invio = Invio.objects.get()
    assert invio.contesto["sezione"] == "Sezione di Ruoti"
    assert invio.destinatari.get().nome == "Direzione della Sezione di Ruoti"
    assert "Alla Direzione della {{ sezione }}" in invio.corpo


def test_testo_dell_avviso_modificabile(admin, sezione, client_ruolo):
    from apps.comunicazioni.models import Invio, Modello

    url = f"/soci/tessere/campagna/{ANNO}/avvisi/tesseramento/"
    modello = Modello.objects.get(uso="tesseramento")
    form = admin.get(url).context["form"]
    assert form.initial["corpo"] == modello.corpo and "salva_modello" in form.fields
    # solo per questo invio
    admin.post(url, {"sezioni": [sezione.pk], "oggetto": "Tesseramento {{ anno }}",
                     "corpo": "Cara {{ sezione }}, quota {{ quota_tessera }}."})  # fmt: skip
    invio = Invio.objects.get()
    assert invio.corpo == "Cara {{ sezione }}, quota {{ quota_tessera }}."
    modello.refresh_from_db()
    assert "Alla Direzione" in modello.corpo  # il modello non cambia
    # anche nel modello
    admin.post(url, {"sezioni": [sezione.pk], "oggetto": "Nuovo oggetto {{ anno }}",
                     "corpo": "Testo predefinito {{ sezione }}", "salva_modello": "on"})  # fmt: skip
    modello.refresh_from_db()
    assert (modello.oggetto, modello.corpo) == (
        "Nuovo oggetto {{ anno }}",
        "Testo predefinito {{ sezione }}",
    )
    r = admin.post(url, {"sezioni": [sezione.pk], "corpo": "{{ inventato }}"})
    assert "Segnaposto sconosciuti" in r.content.decode()
    # il tesoriere corregge il testo dell'invio ma non salva nel modello
    tesoriere = client_ruolo("Tesoriere", username="tesoriere2")
    assert "salva_modello" not in tesoriere.get(url).context["form"].fields


def test_la_campagna_e_quella_dell_anno_successivo(admin):
    r = admin.get("/soci/tessere/campagna/")
    assert r.context["anno"] == ANNO + 1 == r.context["anno_campagna"]
    r = admin.get(f"/soci/tessere/campagna/{ANNO}/")
    assert (
        f'href="/soci/tessere/campagna/{ANNO + 1}/"' in r.content.decode()
    )  # rimando alla corrente
    pagina = admin.get("/soci/tessere/fisiche/").content.decode()
    assert 'href="/soci/tessere/campagna/"' in pagina


def test_risposta_della_sezione_alla_federazione(admin, sezione):
    from apps.comunicazioni.models import Invio
    from apps.core.models import Organizzazione

    richiesta = ciclo.registra_richiesta(admin.utente, anno=ANNO, sezione=sezione, quantita=40,
                                         note="Servono entro marzo.")  # fmt: skip
    url = f"/soci/tessere/richieste/{richiesta.pk}/rispondi/"
    r = admin.post(url, follow=True)
    assert "email della federazione: indicarla" in r.content.decode()
    Organizzazione.objects.filter(pk=1).update(federazione="Potenza Matera",
                                               federazione_email="fed@example.org")  # fmt: skip
    r = admin.post(url, {"riferimento_avviso": "prot. n. 12 del 10/01"})
    invio = Invio.objects.get()
    assert r.status_code == 302 and r["Location"] == invio.get_absolute_url()
    assert invio.stato == "bozza" and invio.origine == "tessere_richiesta"
    assert list(invio.destinatari.values_list("email", flat=True)) == ["fed@example.org"]
    assert invio.contesto["quantita"] == 40 and invio.contesto["federazione"] == "Potenza Matera"
    assert invio.contesto["riferimento_avviso"] == " (prot. n. 12 del 10/01)"
    assert invio.allegati.get().nome == f"richiesta-tessere-{ANNO}.pdf"


def _presidente(nome, cognome, sezione=None):
    from apps.anagrafica.models import Soggetto
    from apps.organi.models import Carica, Organo

    organo = Organo.objects.create(nome=f"Consiglio {cognome}", sigla="CD", tipo="consiglio",
                                   sezione=sezione)  # fmt: skip
    persona = Soggetto.objects.create(tipo="persona", nome=nome, cognome=cognome)
    Carica.objects.create(organo=organo, soggetto=persona, ruolo="presidente", dal=date(2024, 1, 1))
    return persona


def _testo_pdf(contenuto):
    import io

    from pypdf import PdfReader

    return "".join(p.extract_text() for p in PdfReader(io.BytesIO(contenuto)).pages)


def test_richiesta_firmata_dal_presidente_della_sezione(admin, sezione):
    """Sulla federazione (più sezioni) la richiesta la firma il presidente della sezione che
    chiede, non quello della federazione."""
    Sezione.objects.create(codice="PZ02", nome="Potenza", email="p@example.org")
    _presidente("Federico", "Federale")  # presidente della federazione
    _presidente("Silvia", "Sezionale", sezione=sezione)
    richiesta = ciclo.registra_richiesta(admin.utente, anno=ANNO, sezione=sezione, quantita=10)
    testo = _testo_pdf(admin.get(f"/soci/tessere/richieste/{richiesta.pk}/pdf/").content)
    assert "Sezionale" in testo and "Federale" not in testo


def test_richiesta_ricevuta_mostra_il_pdf_originale(admin, sezione):
    import uuid as uuid_mod

    from django.core.files.base import ContentFile

    from apps.api.models import ClienteApi, DocumentoRicevuto

    cliente = ClienteApi.objects.create(nome="Avigliano", tipo="installazione",
                                        origine="invito_nostro", ruolo="sezione", sezione=sezione)  # fmt: skip
    origine = uuid_mod.uuid4()
    documento = DocumentoRicevuto.objects.create(cliente=cliente, tipo="richiesta",
                                                 uuid_origine=origine, dati={})  # fmt: skip
    documento.pdf.save("r.pdf", ContentFile(b"%PDF-1.4 originale della sezione"), save=True)
    richiesta = ciclo.registra_richiesta(admin.utente, anno=ANNO, sezione=sezione, quantita=10,
                                         uuid_origine=origine, cliente_api=cliente)  # fmt: skip
    r = admin.get(f"/soci/tessere/richieste/{richiesta.pk}/pdf/")
    assert b"".join(r.streaming_content) == b"%PDF-1.4 originale della sezione"
