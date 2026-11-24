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
    assert invio.corpo.startswith("Cara {{ sezione }}, quota {{ quota_tessera }}.")
    assert invio.corpo.endswith("{{ istruzioni_risposta }}")  # come rispondere, sempre in fondo
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

    Sezione.objects.exclude(pk=sezione.pk).update(attiva=False)  # gestionale di una sezione

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


def test_avviso_protocollato_con_i_valori_e_non_i_segnaposto(admin, sezione, settings):
    """Il protocollo (oggetto e comunicazione.txt) riporta il testo spedito, non il modello."""
    from apps.comunicazioni import servizi as comunicazioni
    from apps.comunicazioni.models import Invio

    settings.MAILERS = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}
    admin.post(f"/soci/tessere/campagna/{ANNO}/avvisi/tesseramento/",
               {"sezioni": [sezione.pk], "protocolla": "on"})  # fmt: skip
    invio = Invio.objects.get()
    comunicazioni.conferma(invio, admin.utente)
    comunicazioni.elabora_coda()
    invio.refresh_from_db()
    protocollo = invio.protocollo
    assert protocollo is not None
    assert (
        protocollo.oggetto
        == f"Tesseramento {ANNO}: quota e richiesta delle tessere – Sezione di Avigliano"
    )
    allegato = protocollo.allegati.get(nome="comunicazione.txt")
    with allegato.file.open("rb") as f:
        testo = f.read().decode()
    assert "{{" not in testo and "Sezione di Avigliano" in testo and "5,00" in testo


def test_richiesta_registrata_a_mano_si_corregge_e_si_annulla(admin, sezione):
    from apps.core.models import EventoAudit
    from apps.soci.models import RichiestaTessere

    richiesta = ciclo.registra_richiesta(admin.utente, anno=ANNO, sezione=sezione, quantita=20)
    pagina = admin.get(f"/soci/tessere/campagna/{ANNO}/").content.decode()
    assert f"/soci/tessere/richieste/{richiesta.pk}/annulla/" in pagina
    r = admin.post(f"/soci/tessere/richieste/{richiesta.pk}/modifica/",
                   {"quantita": 25, "data": date.today(), "note": "integrazione"})  # fmt: skip
    assert r.status_code == 302
    richiesta.refresh_from_db()
    assert (richiesta.quantita, richiesta.note) == (25, "integrazione")
    assert ciclo.da_ordinare(ANNO)[0]["quantita"] == 25
    r = admin.post(f"/soci/tessere/richieste/{richiesta.pk}/annulla/", {"motivo": "doppione"})
    assert r.status_code == 302
    assert not RichiestaTessere.objects.exists()
    assert ciclo.da_ordinare(ANNO) == []
    assert EventoAudit.objects.filter(dettagli__motivo="doppione").exists()


def test_richiesta_arrivata_via_api_non_si_corregge(admin, sezione):
    from apps.api.models import ClienteApi
    from apps.soci.models import RichiestaTessere
    from apps.soci.servizi import OperazioneNonValida

    cliente = ClienteApi.objects.create(nome="Matera", tipo="installazione",
                                        origine="invito_nostro", ruolo="sezione", sezione=sezione)  # fmt: skip
    api = ciclo.registra_richiesta(admin.utente, anno=ANNO, sezione=sezione, quantita=20,
                                   cliente_api=cliente)  # fmt: skip
    pagina = admin.get(f"/soci/tessere/campagna/{ANNO}/").content.decode()
    assert f"/soci/tessere/richieste/{api.pk}/annulla/" not in pagina
    r = admin.post(f"/soci/tessere/richieste/{api.pk}/annulla/")
    assert r.status_code == 302 and RichiestaTessere.objects.filter(pk=api.pk).exists()
    assert admin.get(f"/soci/tessere/richieste/{api.pk}/modifica/").status_code == 302
    with pytest.raises(OperazioneNonValida):
        ciclo.modifica_richiesta(admin.utente, api, quantita=5)


def test_conferma_della_federazione_alla_sezione(admin, sezione):
    """Nella federazione (più sezioni) il pulsante della richiesta prepara la conferma per la
    sezione, non l'email «alla federazione» (che partirebbe verso la federazione stessa)."""
    from apps.comunicazioni.models import Invio
    from apps.core.models import Organizzazione

    Sezione.objects.create(codice="ZZ", nome="Altra")  # più sezioni: siamo la federazione
    Organizzazione.objects.filter(pk=1).update(federazione_email="fed@example.org")
    sezione.email = "sezione@example.org"
    sezione.save()
    presidente = _presidente("Vito", "Masiello", sezione)
    presidente.email = "vito@example.org"
    presidente.save()
    richiesta = ciclo.registra_richiesta(admin.utente, anno=ANNO, sezione=sezione, quantita=90)
    pagina = admin.get(f"/soci/tessere/campagna/{ANNO}/").content.decode()
    assert f"/soci/tessere/richieste/{richiesta.pk}/conferma/" in pagina
    assert f"/soci/tessere/richieste/{richiesta.pk}/rispondi/" not in pagina
    r = admin.post(f"/soci/tessere/richieste/{richiesta.pk}/rispondi/", follow=True)
    assert "alla sezione si manda la conferma" in r.content.decode() and not Invio.objects.exists()
    r = admin.post(f"/soci/tessere/richieste/{richiesta.pk}/conferma/")
    invio = Invio.objects.get()
    assert r.status_code == 302 and invio.origine == "tessere_conferma" and invio.stato == "bozza"
    assert set(invio.destinatari.values_list("email", flat=True)) == {
        "sezione@example.org",
        "vito@example.org",
    }
    from apps.comunicazioni import servizi as comunicazioni

    email = comunicazioni.messaggio(invio, invio.destinatari.first())
    assert "90 tessere" in email.body and sezione.nome in email.subject
    assert "{{" not in email.body + email.subject
    assert "(1 in bozza)" in ciclo.fasi_verso_sezioni(ANNO)[1].sintesi
    assert "conferma in bozza" in admin.get(f"/soci/tessere/campagna/{ANNO}/").content.decode()
    comunicazioni.conferma(invio, admin.utente)  # nessun segnaposto sconosciuto
    invio.refresh_from_db()
    assert invio.stato == "in_coda"
    assert "confermate 1 su 1" in ciclo.fasi_verso_sezioni(ANNO)[1].sintesi


def _protocollo_entrata(utente, oggetto):
    from apps.protocollo import servizi as protocollo
    from apps.protocollo.models import Corrispondente, Protocollo

    return protocollo.registra_protocollo(
        {"direzione": Protocollo.Direzione.ENTRATA, "mezzo": Protocollo.Mezzo.EMAIL,
         "oggetto": oggetto},
        [{"ruolo": Corrispondente.Ruolo.MITTENTE, "descrizione": "Federazione"}], utente,
    )  # fmt: skip


def test_campagna_federazione_due_direzioni_e_fasi(admin, sezione):
    from apps.comunicazioni.models import Invio

    Invio.objects.create(oggetto="Avviso", corpo="x", finalita="istituzionale",
                         origine="tessere_avviso", origine_id=sezione.pk, stato="inviato",
                         contesto={"anno": ANNO})  # fmt: skip
    ciclo.registra_richiesta(admin.utente, anno=ANNO, sezione=sezione, quantita=10)
    pagina = admin.get(f"/soci/tessere/campagna/{ANNO}/").content.decode()
    assert "Verso le sezioni" in pagina and "Verso la sede nazionale" in pagina
    assert "Invito alla richiesta" in pagina and "Ordine alla sede nazionale" in pagina
    assert "Richiesta alla Federazione" not in pagina and "Importa consegna" not in pagina
    fasi = ciclo.fasi_verso_sezioni(ANNO)
    attive = Sezione.objects.filter(attiva=True).count()
    assert fasi[0].sintesi == f"avvisate 1 sezioni su {attive}" and fasi[1].stato == "in_corso"
    assert "confermate 0 su 1" in fasi[1].sintesi
    stato = {s["sezione"].pk: s for s in ciclo.stato_inviti(ANNO)}
    assert stato[sezione.pk]["avviso"] and stato[sezione.pk]["richiesta"]


def test_invito_ricevuto_collegato_al_protocollo(admin, sezione):
    Sezione.objects.exclude(pk=sezione.pk).update(attiva=False)  # gestionale di una sezione
    prot = _protocollo_entrata(
        admin.utente, f"Tesseramento {ANNO}: quota e richiesta delle tessere"
    )
    _protocollo_entrata(admin.utente, f"Tesseramento {ANNO}: sollecito della richiesta")
    assert ciclo.invito_suggerito(ANNO) == prot
    pagina = admin.get(f"/soci/tessere/campagna/{ANNO}/").content.decode()
    assert "Verso la Federazione" in pagina and "Verso le sezioni" not in pagina
    assert prot.segnatura in pagina and "collegalo" in pagina
    assert ciclo.fasi_verso_superiore(ANNO)[0].stato == "da_fare"
    admin.post(f"/soci/tessere/campagna/{ANNO}/invito/", {"segnatura": prot.segnatura})
    voce = ciclo.invito(ANNO)
    assert voce.protocollo == prot and ciclo.fasi_verso_superiore(ANNO)[0].stato == "fatto"
    r = admin.post(f"/soci/tessere/campagna/{ANNO}/invito/", {"segnatura": "1999-00001"},
                   follow=True)  # fmt: skip
    assert "non trovato" in r.content.decode()


def test_richiesta_dal_collegamento_si_registra_nella_fase_2(admin, sezione):
    """Nella federazione la richiesta arrivata dal collegamento compare nella fase 2 (e la
    sezione risulta «arrivata, da registrare»), non solo fra i documenti in arrivo."""
    import uuid as uuid_mod

    from apps.api.models import ClienteApi, DocumentoRicevuto

    cliente = ClienteApi.objects.create(nome="Pisticci", tipo="installazione",
                                        origine="invito_nostro", ruolo="sezione", sezione=sezione,
                                        stato="attiva")  # fmt: skip
    DocumentoRicevuto.objects.create(
        cliente=cliente,
        tipo="richiesta",
        uuid_origine=uuid_mod.uuid4(),
        dati={
            "anno": ANNO,
            "quantita": 90,
            "data": "2026-11-24",
            "uuid": str(uuid_mod.uuid4()),
            "note": "telefono",
        },
    )
    pagina = admin.get(f"/soci/tessere/campagna/{ANNO}/").content.decode()
    fase2 = pagina[pagina.index('id="richieste-sezioni"') : pagina.index('id="consegne-sezioni"')]
    assert "1 da registrare" in fase2 and "Registra la richiesta" in fase2 and "90 tessere" in fase2
    assert "arrivata, da registrare" in pagina
    fase = ciclo.fasi_verso_sezioni(ANNO)[1]
    assert fase.stato == "in_corso" and "da registrare 1" in fase.sintesi
