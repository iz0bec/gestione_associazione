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
