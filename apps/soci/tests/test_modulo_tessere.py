# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test del modulo Excel della richiesta di tessere: generato per la sezione,
# *              compilato e riletto, manomissioni rifiutate, allegato agli avvisi con le
# *              istruzioni e le tessere dell'anno precedente, recupero dalla posta e a mano.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import io
from datetime import date
from decimal import Decimal
from email.message import EmailMessage

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import Workbook, load_workbook

from apps.soci import ciclo, modulo_tessere
from apps.soci.models import ListinoTessere, RichiestaTessere, Sezione

pytestmark = pytest.mark.django_db
ANNO = date.today().year + 1


@pytest.fixture(autouse=True)
def cartella_media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def admin(client_ruolo):
    client = client_ruolo("Amministratore di sistema", "Addetto protocollo")
    ListinoTessere.objects.update_or_create(anno=ANNO, defaults={
        "costo_acquisto": Decimal("3.50"), "quota_federale": Decimal("1.50"),
        "scadenza_richieste": date(ANNO, 2, 28),
    })  # fmt: skip
    return client


@pytest.fixture
def sezione():
    Sezione.objects.create(codice="003", nome="Potenza", email="p@example.org")
    return Sezione.objects.create(codice="007", nome="Ruoti", email="ruoti@example.org")


def _compila(
    contenuto, quantita=30, referente="Mario Rossi", telefono="333 111", note="Entro marzo"
):
    wb = load_workbook(io.BytesIO(contenuto))
    ws = wb[modulo_tessere.FOGLIO]
    ws["B12"], ws["B13"], ws["B14"], ws["B15"] = quantita, referente, telefono, note
    uscita = io.BytesIO()
    wb.save(uscita)
    return uscita.getvalue()


def test_modulo_compilato_e_riletto(sezione):
    contenuto = modulo_tessere.genera(ANNO, sezione, quota=Decimal("5.00"),
                                      scadenza=date(ANNO, 2, 28), precedente=42)  # fmt: skip
    ws = load_workbook(io.BytesIO(contenuto))[modulo_tessere.FOGLIO]
    assert "Come rispondere" in ws["A3"].value and "28/02" in ws["A3"].value
    assert ws["B5"].value == "Sezione di Ruoti" and ws["B10"].value == 42
    assert ws.protection.sheet and not ws["B12"].protection.locked and ws["B5"].protection.locked
    dati = modulo_tessere.leggi(_compila(contenuto))
    assert (dati["anno"], dati["sezione"], dati["quantita"]) == (ANNO, sezione, 30)
    assert modulo_tessere.note_richiesta(dati) == "Entro marzo · Referente: Mario Rossi 333 111"


def test_moduli_non_validi(sezione):
    contenuto = modulo_tessere.genera(ANNO, sezione)
    with pytest.raises(modulo_tessere.ModuloNonValido, match="manca il numero"):
        modulo_tessere.leggi(contenuto)
    wb = load_workbook(io.BytesIO(_compila(contenuto)))
    wb[modulo_tessere.FOGLIO_DATI]["A4"] = "003"  # un'altra sezione: la firma non torna
    falso = io.BytesIO()
    wb.save(falso)
    with pytest.raises(modulo_tessere.ModuloNonValido, match="non riconosciuto"):
        modulo_tessere.leggi(falso.getvalue())
    altro = io.BytesIO()
    Workbook().save(altro)
    with pytest.raises(modulo_tessere.ModuloNonValido, match="non è un modulo"):
        modulo_tessere.leggi(altro.getvalue())
    assert not modulo_tessere.sembra_modulo("x.xlsx", altro.getvalue())
    with pytest.raises(modulo_tessere.ModuloNonValido, match="leggibile"):
        modulo_tessere.leggi(b"non excel")


def test_avviso_con_modulo_istruzioni_e_anno_precedente(admin, sezione):
    from apps.comunicazioni.models import Invio

    blocco = ciclo.carica_blocco(admin.utente, anno=ANNO - 1, numero_da=1, numero_a=50)
    ciclo.consegna(admin.utente, blocco=blocco, sezione=sezione, numero_da=1, numero_a=25)
    assert ciclo.tessere_anno_precedente(ANNO, sezione) == 25
    admin.post(f"/soci/tessere/campagna/{ANNO}/avvisi/tesseramento/", {"sezioni": [sezione.pk]})
    invio = Invio.objects.get()
    allegato = invio.allegati.get()
    assert allegato.nome == f"richiesta-tessere-{ANNO}-007.xlsx"
    assert (
        "{{ istruzioni_risposta }}" in invio.corpo
        and "{{ tessere_anno_precedente }}" in invio.corpo
    )
    assert invio.contesto["tessere_anno_precedente"] == 25
    assert "rispondete a questa email allegandolo" in invio.contesto["istruzioni_risposta"]
    with allegato.file.open("rb") as f:
        assert modulo_tessere.leggi(_compila(f.read()))["sezione"] == sezione


def test_registrato_una_volta_sola(admin, sezione):
    compilato = _compila(modulo_tessere.genera(ANNO, sezione))
    richiesta = ciclo.richiesta_da_modulo(admin.utente, compilato)
    assert (richiesta.sezione, richiesta.quantita, richiesta.anno) == (sezione, 30, ANNO)
    with pytest.raises(ciclo.OperazioneNonValida, match="già stato registrato"):
        ciclo.richiesta_da_modulo(admin.utente, compilato)


def test_dalla_posta_da_protocollare(admin, sezione):
    from apps.protocollo import posta
    from apps.protocollo.models import CasellaPosta

    casella = CasellaPosta.objects.create(nome="PEC federazione", server="imap.example.org",
                                          utente="fed@example.org")  # fmt: skip
    messaggio = EmailMessage()
    messaggio["From"] = "Sezione di Ruoti <ruoti@example.org>"
    messaggio["To"] = "fed@example.org"
    messaggio["Subject"] = "Re: Tesseramento"
    messaggio["Message-ID"] = "<modulo-ruoti@example.org>"
    messaggio.set_content("In allegato il modulo.")
    messaggio.add_attachment(_compila(modulo_tessere.genera(ANNO, sezione)), maintype="application",
                             subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             filename=f"richiesta-tessere-{ANNO}-007.xlsx")  # fmt: skip
    ricevuto = posta.salva_messaggio(casella, messaggio.as_bytes())
    pagina = admin.get(f"/protocollo/posta/{ricevuto.pk}/").content.decode()
    assert "Protocolla e registra la richiesta" in pagina and "<strong>30</strong>" in pagina
    r = admin.post(f"/soci/tessere/da-messaggio/{ricevuto.pk}/0/")
    assert r.status_code == 302
    richiesta = RichiestaTessere.objects.get()
    ricevuto.refresh_from_db()
    assert ricevuto.stato == "protocollato" and richiesta.protocollo == ricevuto.protocollo
    assert richiesta.protocollo.oggetto == f"Richiesta di tessere {ANNO} della Sezione di Ruoti"


def test_caricamento_a_mano_con_anteprima(admin, sezione):
    compilato = _compila(modulo_tessere.genera(ANNO, sezione), quantita=12)
    r = admin.post("/soci/tessere/importa-modulo/",
                   {"file": SimpleUploadedFile("modulo.xlsx", compilato)})  # fmt: skip
    assert r.status_code == 200 and r.context["dati"]["quantita"] == 12
    assert not RichiestaTessere.objects.exists()
    r = admin.post("/soci/tessere/importa-modulo/",
                   {"temporaneo": r.context["temporaneo"], "conferma": "1"})  # fmt: skip
    assert r.status_code == 302 and RichiestaTessere.objects.get().quantita == 12


def test_scaricabile_dall_elenco_dei_soci(admin, sezione, client_ruolo):
    pagina = admin.get(f"/soci/?sezione={sezione.pk}").content.decode()
    assert f"/soci/tessere/modulo-richiesta.xlsx?sezione={sezione.pk}" in pagina
    r = admin.get(f"/soci/tessere/modulo-richiesta.xlsx?sezione={sezione.pk}")
    assert r.status_code == 200
    assert f"richiesta-tessere-{ANNO}-007.xlsx" in r["Content-Disposition"]
    dati = modulo_tessere.leggi(_compila(r.content))
    assert (dati["sezione"], dati["anno"]) == (sezione, ANNO)  # la campagna in preparazione
    r = admin.get("/soci/tessere/modulo-richiesta.xlsx")  # più sezioni e nessuna scelta
    assert r.status_code == 302 and r["Location"] == "/soci/"


def test_rispetta_le_sezioni_dell_utente(client_ruolo, sezione):
    potenza = Sezione.objects.get(codice="003")
    segretario = client_ruolo("Segretario", username="segretario")
    segretario.utente.sezioni.add(potenza)
    assert (
        segretario.get(f"/soci/tessere/modulo-richiesta.xlsx?sezione={potenza.pk}").status_code
        == 200
    )
    assert (
        segretario.get(f"/soci/tessere/modulo-richiesta.xlsx?sezione={sezione.pk}").status_code
        == 403
    )


def _come_numbers(contenuto, *, togli_controllo=False, codice_numerico=False):
    """Ciò che fa Numbers esportando in Excel: toglie i fogli nascosti e rinomina il foglio."""
    wb = load_workbook(io.BytesIO(contenuto))
    del wb[modulo_tessere.FOGLIO_DATI]
    ws = wb[modulo_tessere.FOGLIO]
    ws.title = f"{modulo_tessere.FOGLIO}_Tabella 1"
    if togli_controllo:
        ws["A19"], ws["B19"] = None, None
    if codice_numerico:
        ws["B6"] = 7  # «007» diventato numero
    ws["B14"] = 3312876839  # telefono scritto come numero
    uscita = io.BytesIO()
    wb.save(uscita)
    return uscita.getvalue()


def test_modulo_passato_da_numbers_resta_verificato(sezione):
    contenuto = _compila(modulo_tessere.genera(ANNO, sezione))
    dati = modulo_tessere.leggi(_come_numbers(contenuto))  # vale il codice di controllo visibile
    assert dati["verificato"] and dati["avviso"] == "" and dati["sezione"] == sezione
    assert dati["telefono"] == "3312876839"


def test_modulo_senza_firma_riconosciuto_non_verificato(sezione):
    contenuto = _compila(modulo_tessere.genera(ANNO, sezione), quantita=100)
    dati = modulo_tessere.leggi(
        _come_numbers(contenuto, togli_controllo=True, codice_numerico=True)
    )
    assert not dati["verificato"] and "senza codice di controllo" in dati["avviso"]
    assert (dati["sezione"], dati["quantita"], dati["anno"]) == (sezione, 100, ANNO)
    assert "modulo senza codice di controllo" in modulo_tessere.note_richiesta(dati)


def test_controllo_visibile_manomesso_rifiutato(sezione):
    contenuto = _come_numbers(_compila(modulo_tessere.genera(ANNO, sezione)))
    wb = load_workbook(io.BytesIO(contenuto))
    ws = wb.worksheets[0]
    ws["B19"] = ws["B19"].value.replace(" 007 ", " 003 ")
    falso = io.BytesIO()
    wb.save(falso)
    with pytest.raises(modulo_tessere.ModuloNonValido, match="non riconosciuto"):
        modulo_tessere.leggi(falso.getvalue())


def test_allegato_in_formato_numbers_segnalato(sezione):
    class Messaggio:
        allegati = [{"nome": "richiesta-tessere-2027-007 2.numbers", "percorso": "x"}]

    trovato = modulo_tessere.cerca_nel_messaggio(Messaggio())
    assert "formato .numbers" in trovato["errore"] and "Importa modulo" in trovato["errore"]
