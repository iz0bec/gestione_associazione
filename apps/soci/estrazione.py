# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Domande di iscrizione arrivate per email: riconoscimento dei messaggi probabili
# *              e recupero dei dati dal testo del messaggio e dai PDF allegati (campi del modulo
# *              compilabile o testo). Mai dati inventati: ciò che non si trova resta vuoto.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
import io
import logging
import re
from email.utils import parseaddr

from codicefiscale import codicefiscale
from django.core.files.storage import default_storage

from apps.anagrafica.validatori import dati_da_codice_fiscale

log = logging.getLogger(__name__)

PAROLE_CHIAVE = re.compile(
    r"\b(iscrizion\w*|adesion\w*|tesseramento|ammission\w*|nuovo socio|diventare soci\w*|"
    r"allegato a|modulo di adesione)\b",
    re.I,
)
ESTENSIONI_MODULO = (".pdf", ".jpg", ".jpeg", ".png")
_CF = re.compile(
    r"\b[A-Z]{6}[0-9LMNPQRSTUV]{2}[A-EHLMPRST][0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{3}[A-Z]\b"
)
_TELEFONO = re.compile(
    r"(?<![\d+])(?:\+39[\s.]?)?(3\d{2}[\s./-]?\d{6,7}|0\d{1,3}[\s./-]?\d{5,8})(?!\d)"
)
_CAP = re.compile(r"\b(\d{5})\b")
_MAX_PDF = 5 * 1024 * 1024

# etichette dei campi come si scrivono nei messaggi e nei moduli (anche l'Allegato A)
_ETICHETTE = {
    "cognome": r"cognome",
    "nome": r"nome",
    "luogo_nascita": r"(?:nat[oa]/?a?\s+a|luogo\s+di\s+nascita|nascita\s*\(luogo\))",
    "data_nascita": r"(?:data\s+di\s+nascita|nat[oa]/?a?\s+il|nascita\s*\(data\))",
    "indirizzo": r"(?:indirizzo|residente\s+in\s+via|residente\s+in|via)",
    "cap": r"c\.?a\.?p\.?",
    "comune": r"(?:comune(?:\s+di\s+residenza)?|citt[aà])",
    "provincia": r"(?:provincia|prov\.?)",
    "telefono": r"(?:telefono|tel\.?)",
    "cellulare": r"(?:cellulare|cell\.?)",
    "email": r"(?:e-?mail|posta\s+elettronica)",
}


def probabile_iscrizione(messaggio):
    """Vero se oggetto, testo o nomi degli allegati parlano di iscrizione/adesione."""
    nomi = " ".join(a.get("nome", "") for a in messaggio.allegati or [])
    return bool(PAROLE_CHIAVE.search(f"{messaggio.oggetto} {nomi} {messaggio.testo[:3000]}"))


def allegati_modulo(messaggio):
    """Indici degli allegati che possono essere il modulo firmato (PDF o immagini)."""
    return [
        i
        for i, a in enumerate(messaggio.allegati or [])
        if a.get("nome", "").lower().endswith(ESTENSIONI_MODULO)
    ]


# --- lettura dei PDF ----------------------------------------------------------------------


def _leggi_pdf(percorso):
    """(campi del modulo compilabile, testo) di un PDF allegato; vuoti se illeggibile."""
    from pypdf import PdfReader
    from pypdf.errors import PyPdfError

    try:
        with default_storage.open(percorso, "rb") as f:
            dati = f.read(_MAX_PDF + 1)
        if len(dati) > _MAX_PDF or not dati.startswith(b"%PDF-"):
            return {}, ""
        lettore = PdfReader(io.BytesIO(dati))
        campi = {
            str(k): str(v.get("/V") or "").strip()
            for k, v in (lettore.get_fields() or {}).items()
            if v.get("/V") not in (None, "", "/Off")
        }
        testo = "\n".join((pagina.extract_text() or "") for pagina in lettore.pages[:4])
        return campi, testo
    except (PyPdfError, OSError, ValueError, KeyError, TypeError) as e:
        log.info("PDF allegato non leggibile (%s): %s", percorso, e)
        return {}, ""


# --- riconoscimento dei campi -------------------------------------------------------------


def _pulisci(valore):
    valore = re.sub(r"\s+", " ", valore or "").strip(" :;,.-_\t")
    return "" if re.fullmatch(r"_+|\.+", valore) else valore


def _per_etichetta(testo):
    """Valori scritti come «Etichetta: valore» (una per riga), anche nei campi del modulo."""
    trovati = {}
    for riga in testo.splitlines():
        for campo, etichetta in _ETICHETTE.items():
            if campo in trovati:
                continue
            m = re.match(rf"\s*{etichetta}\s*[:=\-]\s*(.+)$", riga, re.I)
            if m and (valore := _pulisci(m.group(1))):
                trovati[campo] = valore
    return trovati


def _dai_campi_pdf(campi):
    """Campi di un modulo compilabile: il nome del campo fa da etichetta."""
    righe = [f"{nome.replace('_', ' ')}: {valore}" for nome, valore in campi.items()]
    return _per_etichetta("\n".join(righe))


def _data(testo):
    m = re.search(r"\b(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})\b", testo or "")
    if not m:
        return None
    from datetime import date

    try:
        return date(int(m[3]), int(m[2]), int(m[1]))
    except ValueError:
        return None


def _maiuscole(testo):
    return testo.title() if testo.isupper() or testo.islower() else testo


def _nome_dal_mittente(mittente, cf):
    """Cognome e nome dal nome del mittente («Mario Rossi»), nell'ordine indicato dal codice
    fiscale; senza codice fiscale non si indovina quale sia il cognome."""
    nome_visibile = parseaddr(mittente)[0].strip().strip('"')
    parole = nome_visibile.split()
    if not cf or len(parole) < 2:
        return {}
    for i in range(1, len(parole)):
        for cognome, nome in ((parole[i:], parole[:i]), (parole[:i], parole[i:])):
            c, n = " ".join(cognome), " ".join(nome)
            if (
                codicefiscale.encode_lastname(c) == cf[0:3]
                and codicefiscale.encode_firstname(n) == cf[3:6]
            ):
                return {"cognome": _maiuscole(c), "nome": _maiuscole(n)}
    return {}


def estrai(messaggio):
    """Dati della domanda dal messaggio: (valori per il modulo, provenienze per l'utente)."""
    fonti = [("testo del messaggio", messaggio.testo or "", {})]
    for i in allegati_modulo(messaggio):
        a = messaggio.allegati[i]
        if a.get("nome", "").lower().endswith(".pdf"):
            campi, testo = _leggi_pdf(a["percorso"])
            fonti.append((f"allegato «{a['nome']}»", testo, campi))

    valori, provenienza = {}, {}

    def metti(campo, valore, fonte):
        if valore and campo not in valori:
            valori[campo] = valore
            provenienza[campo] = fonte

    for fonte, testo, campi in fonti:
        for campo, valore in {**_dai_campi_pdf(campi), **_per_etichetta(testo)}.items():
            metti(campo, valore, fonte)
        cf = next((c for c in _CF.findall((testo + " " + " ".join(campi.values())).upper())
                   if codicefiscale.is_valid(c)), "")  # fmt: skip
        metti("codice_fiscale", cf, fonte)

    cf = valori.get("codice_fiscale", "")
    if da_cf := dati_da_codice_fiscale(cf):
        metti("data_nascita", da_cf["data_nascita"], "codice fiscale")
        metti("luogo_nascita", da_cf["luogo_nascita"], "codice fiscale")
        provenienza["sesso"] = "codice fiscale"
    if isinstance(valori.get("data_nascita"), str):
        valori["data_nascita"] = _data(valori["data_nascita"]) or (da_cf or {}).get("data_nascita")
        if not valori["data_nascita"]:
            del valori["data_nascita"]
    for campo, valore in _nome_dal_mittente(messaggio.mittente, cf).items():
        metti(campo, valore, "nome del mittente")
    metti("email", messaggio.mittente_email, "mittente del messaggio")
    for fonte, testo, _ in fonti:
        if m := _TELEFONO.search(testo):
            numero = re.sub(r"[\s./-]", "", m.group(1))
            metti("cellulare" if numero.startswith("3") else "telefono", numero, fonte)
    if "cap" in valori:
        cap = _CAP.search(valori["cap"])
        valori["cap"] = cap.group(1) if cap else ""
    if "provincia" in valori:
        sigla = re.search(r"\b([A-Za-z]{2})\b", valori["provincia"])
        valori["provincia"] = sigla.group(1).upper() if sigla else ""
    return {k: v for k, v in valori.items() if v}, provenienza
