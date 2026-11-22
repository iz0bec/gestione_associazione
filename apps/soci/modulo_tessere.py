# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Modulo Excel della richiesta di tessere per le sezioni senza gestionale: generato
# *              per ogni sezione (dati bloccati, istruzioni di risposta, celle da compilare) con
# *              un codice firmato in un foglio nascosto; letto e controllato quando torna indietro.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import hashlib
import hmac
import io
import zipfile

from django.conf import settings

from apps.core.models import Organizzazione

FIRMA = "GA-RICHIESTA-TESSERE"
VERSIONE = "1"
FOGLIO = "Richiesta tessere"
FOGLIO_DATI = "dati"
# celle da compilare (colonna B)
CELLA_QUANTITA, CELLA_REFERENTE, CELLA_TELEFONO, CELLA_NOTE = "B12", "B13", "B14", "B15"
CELLA_CONTROLLO = "B19"  # codice di controllo visibile: sopravvive a Numbers e ad altri programmi
ETICHETTE = {"A6": "Codice della sezione", "A7": "Anno di tesseramento",
             "A12": "Tessere richieste (numero)"}  # fmt: skip
ALTRI_FORMATI = (".numbers", ".ods", ".xls", ".xlsm", ".csv", ".pdf")
AVVISO_NON_VERIFICATO = (
    "Modulo senza codice di controllo (passato da Numbers o da un altro programma): controllate "
    "che il mittente sia davvero la sezione indicata prima di registrare la richiesta."
)


class ModuloNonValido(ValueError):
    pass


def _firma(anno, codice):
    chiave = settings.SECRET_KEY.encode()
    return hmac.new(
        chiave, f"{FIRMA}|{VERSIONE}|{anno}|{codice}".encode(), hashlib.sha256
    ).hexdigest()[:24]


def indirizzo_risposta():
    org = Organizzazione.corrente()
    return org.pec or org.email or ""


def istruzioni(anno, sezione, scadenza=None):
    """Come rispondere: lo stesso testo nel modulo e nell'email."""
    indirizzo = indirizzo_risposta()
    entro = f" entro il {scadenza.strftime('%d/%m/%Y')}" if scadenza else ""
    a_chi = f" all'indirizzo {indirizzo}" if indirizzo else ""
    return (
        f"Come rispondere: aprite il modulo Excel allegato «richiesta-tessere-{anno}-"
        f"{sezione.codice}.xlsx», scrivete nelle celle gialle il numero di tessere richieste, "
        f"il referente, il telefono ed eventuali note, salvatelo senza cambiare nome né formato "
        f"e rispondete a questa email allegandolo (oppure speditelo{a_chi}){entro}. "
        "Non modificate le altre celle: il modulo viene letto in automatico. Con Numbers (Mac, "
        "iPad) rispondete con il file Excel: File → Esporta come → Excel."
    )


def genera(anno, sezione, *, quota=None, scadenza=None, precedente=None) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill, Protection
    from openpyxl.worksheet.datavalidation import DataValidation

    org = Organizzazione.corrente()
    wb = Workbook()
    ws = wb.active
    ws.title = FOGLIO
    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 60
    giallo = PatternFill("solid", fgColor="FFF2A8")
    righe = [
        (org.denominazione, None),
        (f"Richiesta di tessere per il tesseramento {anno}", None),
        (istruzioni(anno, sezione, scadenza), None),
        ("", None),
        ("Sezione", sezione.denominazione),
        ("Codice della sezione", sezione.codice),
        ("Anno di tesseramento", anno),
        ("Importo per tessera (€)", float(quota) if quota is not None else "[da indicare]"),
        ("Richieste entro il", scadenza.strftime("%d/%m/%Y") if scadenza else "[da indicare]"),
        (f"Tessere {anno - 1} (per informazione)", precedente if precedente is not None else "—"),
        ("DA COMPILARE", None),
        ("Tessere richieste (numero)", None),
        ("Referente", None),
        ("Telefono", None),
        ("Note", None),
        ("", None),
        ("Totale da versare (€)", f'=IF(ISNUMBER({CELLA_QUANTITA}),{CELLA_QUANTITA}*B8,"")'),
        ("", None),
        (
            "Codice di controllo (non modificare)",
            " ".join((FIRMA, VERSIONE, str(anno), sezione.codice, _firma(anno, sezione.codice))),
        ),
    ]
    for n, (etichetta, valore) in enumerate(righe, start=1):
        ws.cell(n, 1, etichetta)
        if valore is not None:
            ws.cell(n, 2, valore)
    ws["A1"].font = Font(bold=True, size=13)
    ws["A2"].font = Font(bold=True, size=12)
    ws.merge_cells("A3:B3")
    ws["A3"].alignment = Alignment(wrap_text=True, vertical="top")
    ws["A3"].font = Font(bold=True, color="9C2700")
    ws.row_dimensions[3].height = 90
    ws["A11"].font = Font(bold=True)
    for cella in (CELLA_QUANTITA, CELLA_REFERENTE, CELLA_TELEFONO, CELLA_NOTE):
        ws[cella].fill = giallo
        ws[cella].protection = Protection(locked=False)
    ws[CELLA_NOTE].alignment = Alignment(wrap_text=True, vertical="top")
    for cella in ("A19", CELLA_CONTROLLO):
        ws[cella].font = Font(size=8, color="808080")
    ws.row_dimensions[15].height = 45
    validazione = DataValidation(
        type="whole", operator="greaterThan", formula1="0", showErrorMessage=True,
        error="Indicare un numero intero di tessere.",
    )  # fmt: skip
    ws.add_data_validation(validazione)
    validazione.add(CELLA_QUANTITA)
    ws.protection.sheet = True  # solo le celle gialle si possono modificare
    dati = wb.create_sheet(FOGLIO_DATI)
    marcatura = (FIRMA, VERSIONE, anno, sezione.codice, _firma(anno, sezione.codice))
    for n, valore in enumerate(marcatura, start=1):
        dati.cell(n, 1, str(valore))
    dati.sheet_state = "veryHidden"
    uscita = io.BytesIO()
    wb.save(uscita)
    return uscita.getvalue()


def sembra_modulo(nome, contenuto) -> bool:
    """Vero se il file è un modulo di richiesta di tessere (senza segnalare errori)."""
    if not (nome or "").lower().endswith(".xlsx"):
        return False
    try:
        leggi(contenuto)
    except ModuloNonValido:
        return False
    return True


def _foglio(wb):
    """Il foglio del modulo, anche rinominato (Numbers: «Richiesta tessere_Tabella 1»)."""
    if FOGLIO in wb.sheetnames:
        return wb[FOGLIO]
    for nome in wb.sheetnames:
        if nome.startswith(FOGLIO):
            return wb[nome]
    for ws in wb.worksheets:
        if str(ws["A12"].value or "").strip() == ETICHETTE["A12"]:
            return ws
    return None


def _marcatura(wb, ws):
    """(marca, versione, anno, codice, firma) dal foglio nascosto o dal codice di controllo
    visibile; None se il programma usato li ha tolti."""
    if FOGLIO_DATI in wb.sheetnames:
        return tuple(str(wb[FOGLIO_DATI].cell(n, 1).value or "") for n in range(1, 6))
    for riga in ws.iter_rows():
        for cella in riga:
            parti = str(cella.value or "").split()
            if len(parti) == 5 and parti[0] == FIRMA:
                return tuple(parti)
    return None


def _codice(valore):
    """Codice della sezione come scritto o come numero (Numbers trasforma «007» in 7)."""
    from .models import Sezione

    testo = str(valore or "").strip()
    if testo.endswith(".0"):
        testo = testo[:-2]
    sezione = Sezione.objects.filter(codice=testo).first()
    if sezione is None and testo.isdigit():
        cifre = testo.lstrip("0")
        sezione = next((s for s in Sezione.objects.all() if s.codice.lstrip("0") == cifre), None)
    return testo, sezione


def leggi(contenuto: bytes) -> dict:
    """Dati di un modulo compilato, dopo i controlli (firma, sezione, quantità). Un modulo che ha
    perso la firma (aperto e salvato con Numbers o un altro programma) si riconosce dalla struttura
    e torna con `verificato` falso e l'avviso da mostrare."""
    from openpyxl import load_workbook

    try:
        wb = load_workbook(io.BytesIO(contenuto), data_only=True, read_only=False)
    except (zipfile.BadZipFile, OSError, KeyError, ValueError) as e:
        raise ModuloNonValido("Il file non è un modulo Excel leggibile.") from e
    ws = _foglio(wb)
    if ws is None:
        raise ModuloNonValido("Il file non è un modulo di richiesta di tessere.")
    marcatura = _marcatura(wb, ws)
    if marcatura is not None:
        marca, versione, anno, codice, firma = marcatura
        if marca != FIRMA or versione != VERSIONE or not anno.isdigit():
            raise ModuloNonValido("Il file non è un modulo di richiesta di tessere.")
        if not hmac.compare_digest(firma, _firma(anno, codice)):
            raise ModuloNonValido("Modulo non riconosciuto: è stato modificato o viene da "
                                  "un'altra installazione.")  # fmt: skip
        codice, sezione = _codice(codice)
        verificato = True
    else:  # nessuna firma: si riconosce dalle etichette, senza garanzia sull'origine
        if any(str(ws[c].value or "").strip() != t for c, t in ETICHETTE.items()):
            raise ModuloNonValido("Il file non è un modulo di richiesta di tessere.")
        anno = str(ws["B7"].value or "").strip().removesuffix(".0")
        if not anno.isdigit():
            raise ModuloNonValido("Nel modulo manca l'anno di tesseramento.")
        codice, sezione = _codice(ws["B6"].value)
        verificato = False
    if sezione is None:
        raise ModuloNonValido(f"Sezione {codice} non trovata.")
    grezzo = ws[CELLA_QUANTITA].value
    try:
        quantita = int(grezzo) if not isinstance(grezzo, float) or grezzo.is_integer() else -1
    except (TypeError, ValueError):
        quantita = -1
    if quantita < 1:
        raise ModuloNonValido("Nel modulo manca il numero di tessere richieste (cella gialla).")

    def testo(cella):
        valore = ws[cella].value
        if isinstance(valore, float) and valore.is_integer():
            valore = int(valore)  # es. un telefono scritto come numero
        return str(valore or "").strip()

    return {
        "anno": int(anno), "sezione": sezione, "quantita": quantita,
        "referente": testo(CELLA_REFERENTE)[:100], "telefono": testo(CELLA_TELEFONO)[:30],
        "note": testo(CELLA_NOTE)[:500], "verificato": verificato,
        "avviso": "" if verificato else AVVISO_NON_VERIFICATO,
    }  # fmt: skip


def note_richiesta(dati) -> str:
    parti = [dati["note"]] if dati["note"] else []
    if not dati.get("verificato", True):
        parti.append("modulo senza codice di controllo")
    contatto = " ".join(p for p in (dati["referente"], dati["telefono"]) if p)
    if contatto:
        parti.append(f"Referente: {contatto}")
    return " · ".join(parti)[:255]


def cerca_nel_messaggio(messaggio):
    """Primo modulo di richiesta fra gli allegati di un messaggio ricevuto:
    {"indice", "nome", "dati"} se valido, {"indice", "nome", "errore"} se è un modulo con un
    problema (es. quantità mancante), None se non ce ne sono."""
    from django.core.files.storage import default_storage

    for indice, allegato in enumerate(messaggio.allegati or []):
        nome = allegato.get("nome", "")
        minuscolo = nome.lower()
        if "richiesta-tessere" in minuscolo and minuscolo.endswith(ALTRI_FORMATI):
            formato = minuscolo.rsplit(".", 1)[-1]
            return {"indice": indice, "nome": nome, "errore": (
                f"Il modulo è arrivato in formato .{formato} (es. salvato con Numbers): il "
                "gestionale legge solo il file Excel (.xlsx). Chiedete alla sezione di rispondere "
                "con il file Excel (in Numbers: File → Esporta come → Excel), oppure convertitelo "
                "voi e caricatelo dalla campagna delle tessere, «Importa modulo»."
            )}  # fmt: skip
        if not minuscolo.endswith(".xlsx"):
            continue
        try:
            with default_storage.open(allegato["percorso"], "rb") as f:
                contenuto = f.read()
        except (OSError, KeyError):
            continue
        try:
            return {"indice": indice, "nome": nome, "dati": leggi(contenuto)}
        except ModuloNonValido as e:
            if "non è un modulo" in str(e) or "non è un modulo Excel" in str(e):
                continue  # un altro Excel qualunque
            return {"indice": indice, "nome": nome, "errore": str(e)}
    return None


def contenuto_allegato(messaggio, indice):
    from django.core.files.storage import default_storage

    allegato = (messaggio.allegati or [])[indice]
    with default_storage.open(allegato["percorso"], "rb") as f:
        return f.read()
