# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Importazione dei soci dall'estratto Excel (o CSV) del registro soci nazionale:
# *              riconoscimento delle colonne, abbinamento per codice fiscale / matricola,
# *              anteprima esatta (simulazione annullata) ed esecuzione riga per riga.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import csv
import io
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.anagrafica.models import Soggetto
from apps.anagrafica.validatori import dati_da_codice_fiscale, valida_codice_fiscale
from apps.core.audit import Azione, registra

from . import servizi
from .models import Sezione, Socio, TipologiaSocio

MAX_MB = 10
MAX_RIGHE = 20_000

# campo -> intestazioni riconosciute (già normalizzate: minuscole, senza accenti e punteggiatura)
COLONNE = {
    "cognome": ["cognome"],
    "nome": ["nome"],
    "nominativo": ["nominativo", "cognome e nome", "cognome nome", "socio"],
    "codice_fiscale": ["codice fiscale", "codicefiscale", "cf", "cod fiscale", "codfiscale", "c f"],
    "sesso": ["sesso", "genere"],
    "data_nascita": ["data nascita", "data di nascita", "nato il", "nata il", "nascita"],
    "luogo_nascita": ["luogo nascita", "luogo di nascita", "comune di nascita", "nato a"],
    "indirizzo": ["indirizzo", "via", "indirizzo residenza", "residenza"],
    "cap": ["cap", "c a p"],
    "comune": ["comune", "citta", "comune residenza", "localita", "comune di residenza"],
    "provincia": ["provincia", "prov", "pr", "sigla provincia"],
    "email": ["email", "e mail", "mail", "posta elettronica", "indirizzo email"],
    "telefono": ["telefono", "tel", "telefono fisso"],
    "cellulare": ["cellulare", "cell", "mobile", "telefono cellulare"],
    "sezione": ["sezione", "nome sezione", "sezione di appartenenza", "denominazione sezione"],
    "codice_sezione": ["codice sezione", "cod sezione", "id sezione", "n sezione"],
    "matricola": ["matricola", "numero socio", "n socio", "id socio", "codice socio"],
    "tessera": ["tessera", "numero tessera", "n tessera", "nr tessera", "codice tessera"],
    "anno_tessera": ["anno sociale", "anno tessera", "anno tesseramento", "anno"],
    "data_tessera": ["data tessera", "data rilascio tessera", "data rilascio"],
    "tipologia": ["tipologia", "categoria", "tipo socio", "tipologia socio", "qualifica"],
    "data_iscrizione": [
        "data iscrizione",
        "data ammissione",
        "iscritto dal",
        "data adesione",
        "data di ammissione a socio",
        "data di ammissione",
        "data di iscrizione",
    ],
    "data_cessazione": [
        "data di annullamento iscrizione",
        "data annullamento",
        "data cessazione",
        "data di cessazione",
    ],
    "incarico": ["codice incarico socio ordinario", "incarico", "carica"],
    "valido": ["valido", "validato", "socio validato", "valida"],
    "data_pagamento": ["data pagamento", "data del pagamento", "pagata il", "data versamento"],
}
# colonne con l'anno nell'intestazione, es. «Numero Tessera Anno 2025»
COLONNE_CON_ANNO = {"tessera_precedente": re.compile(r"^(?:numero |n |nr )?tessera anno (\d{4})$")}
CAMPI_ANAGRAFICI = [
    "sesso", "data_nascita", "luogo_nascita", "indirizzo", "cap", "comune", "provincia",
    "email", "telefono", "cellulare",
]  # fmt: skip


class FileNonValido(ValidationError):
    pass


def normalizza(testo):
    testo = unicodedata.normalize("NFKD", str(testo or "")).encode("ascii", "ignore").decode()
    testo = re.sub(r"[^a-z0-9]+", " ", testo.lower())
    return " ".join(testo.split())


_ALIAS = {alias: campo for campo, nomi in COLONNE.items() for alias in nomi}


# --- lettura del file --------------------------------------------------------------------


def _riconosci(valore):
    """Campo corrispondente all'intestazione (e anno, per le colonne che lo contengono)."""
    n = normalizza(valore)
    if n in _ALIAS:
        return _ALIAS[n], None
    for campo, schema in COLONNE_CON_ANNO.items():
        if m := schema.match(n):
            return campo, int(m.group(1))
    return None, None


def _celle_xlsx(contenuto):
    from openpyxl import load_workbook

    try:
        wb = load_workbook(io.BytesIO(contenuto), read_only=True, data_only=True)
    except Exception:  # file corrotto o non xlsx: il messaggio per l'utente basta
        raise FileNonValido("Il file non è un foglio Excel .xlsx leggibile.") from None
    try:
        foglio = wb.worksheets[0]
        for riga in foglio.iter_rows(values_only=True):
            yield list(riga)
    finally:
        wb.close()


class _PuntoEVirgola(csv.excel):
    delimiter = ";"


def _celle_csv(contenuto):
    try:
        testo = contenuto.decode("utf-8-sig")
    except UnicodeDecodeError:
        testo = contenuto.decode("cp1252", errors="replace")  # CSV salvati da Excel italiano
    try:
        dialetto = csv.Sniffer().sniff(testo[:4096], delimiters=";,\t")
    except csv.Error:
        dialetto = _PuntoEVirgola
    yield from csv.reader(io.StringIO(testo), dialetto)


def leggi(nome_file, contenuto):
    """Restituisce (intestazioni riconosciute {indice: campo}, righe come dizionari, ignorate)."""
    if len(contenuto) > MAX_MB * 1024 * 1024:
        raise FileNonValido(f"Il file supera {MAX_MB} MB.")
    nome = nome_file.lower()
    if nome.endswith(".xlsx"):
        celle = _celle_xlsx(contenuto)
    elif nome.endswith((".csv", ".txt")):
        celle = _celle_csv(contenuto)
    elif nome.endswith(".xls"):
        raise FileNonValido(
            "Il formato .xls (Excel 97-2003) non è supportato: "
            "aprire il file e salvarlo come .xlsx."
        )
    else:
        raise FileNonValido("Caricare un file .xlsx o .csv.")

    mappa, ignorate, righe, anni = None, [], [], {}
    for n, valori in enumerate(celle, start=1):
        if mappa is None:
            if n > 20:
                raise FileNonValido(
                    "Intestazioni non trovate: servono almeno le colonne cognome (o nominativo) "
                    "e codice fiscale nelle prime 20 righe."
                )
            candidata, anni = {}, {}
            for i, v in enumerate(valori):
                campo, anno = _riconosci(v)
                if campo and campo not in candidata.values():
                    candidata[i] = campo
                    if anno:
                        anni[campo] = anno
            campi = set(candidata.values())
            if ("cognome" in campi or "nominativo" in campi) and len(campi) >= 2:
                mappa = candidata
                ignorate = [str(v) for i, v in enumerate(valori) if v and i not in candidata]
            continue
        if not any(v not in (None, "") for v in valori):
            continue
        if len(righe) >= MAX_RIGHE:
            raise FileNonValido(f"Il file ha più di {MAX_RIGHE} righe.")
        riga = {"_riga": n, **{f"_anno_{c}": a for c, a in anni.items()}}
        for i, campo in mappa.items():
            if i < len(valori) and campo not in riga:
                riga[campo] = valori[i]
        righe.append(riga)
    if mappa is None:
        raise FileNonValido("Il file è vuoto o senza intestazioni riconoscibili.")
    return mappa, righe, ignorate


# --- conversione dei valori --------------------------------------------------------------


def _testo(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return " ".join(str(v).split())


MESI = {m: i for i, m in enumerate(
    ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto",
     "settembre", "ottobre", "novembre", "dicembre"], start=1)}  # fmt: skip


SI = {"si", "sì", "s", "x", "1", "true", "vero", "yes", "y", "ok", "valido", "validato", "v"}
NO = {"no", "n", "0", "false", "falso", "non valido", "non validato"}


def _si_no(v):
    """True, False o None (vuoto o non riconosciuto) da una cella sì/no."""
    testo = _testo(v).lower()
    return True if testo in SI else False if testo in NO else None


def _data(v):
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    testo = _testo(v)
    # «04 agosto 1967», come negli estratti del registro nazionale
    if m := re.fullmatch(r"(\d{1,2})\s+([a-zA-Z]+)\s+(\d{4})", testo):
        mese = MESI.get(normalizza(m.group(2)))
        if mese:
            try:
                return date(int(m.group(3)), mese, int(m.group(1)))
            except ValueError:
                return None
    for formato in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d.%m.%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(testo, formato).date()
        except ValueError:
            continue
    return None


MINUSCOLE_LUOGHI = {"di", "del", "della", "dei", "delle", "in", "sul", "sulla", "al", "e"}


def _nome_proprio(testo, luogo=False):
    """MARIO ROSSI -> Mario Rossi; RIONERO IN VULTURE -> Rionero in Vulture (luogo=True).
    Le maiuscole/minuscole già curate restano come sono."""
    testo = _testo(testo)
    if not (testo.isupper() or testo.islower()):
        return testo
    parole = []
    for i, p in enumerate(testo.lower().split()):
        if luogo and i and p in MINUSCOLE_LUOGHI:
            parole.append(p)
        else:
            parole.append(p.title() if "'" in p or "-" in p else p.capitalize())
    return " ".join(parole)


def _telefoni(*valori):
    """Separa fissi e cellulari (in Italia i cellulari iniziano per 3)."""
    fissi, cellulari = [], []
    for v in valori:
        for numero in re.split(r"[,;/]| e ", _testo(v)):
            numero = numero.strip()
            cifre = re.sub(r"\D", "", numero)
            if len(cifre) < 6:
                continue
            # prefisso internazionale italiano: «+39 0971…» è un fisso, «+39 333…» un cellulare
            if numero.startswith("+39") or cifre.startswith("0039"):
                cifre = cifre[2:] if numero.startswith("+39") else cifre[4:]
            (cellulari if cifre.startswith("3") else fissi).append(numero)
    return ", ".join(fissi)[:30], ", ".join(cellulari)[:30]


DATE = ("data_nascita", "data_iscrizione", "data_tessera", "data_cessazione", "data_pagamento")


def _pulisci(riga):
    d = {k: (v if k in DATE or k.startswith("_") else _testo(v)) for k, v in riga.items()}
    if not d.get("cognome") and d.get("nominativo"):
        parti = d["nominativo"].split()
        d["cognome"], d["nome"] = (parti[0], " ".join(parti[1:])) if parti else ("", "")
    d["cognome"] = _nome_proprio(d.get("cognome", ""))
    d["nome"] = _nome_proprio(d.get("nome", ""))
    d["codice_fiscale"] = d.get("codice_fiscale", "").replace(" ", "").upper()
    d["data_nascita"] = _data(d.get("data_nascita"))
    for campo in DATE[1:]:
        d[campo] = _data(d.get(campo))
    d["telefono"], d["cellulare"] = _telefoni(d.get("telefono"), d.get("cellulare"))
    for campo in ("tessera", "tessera_precedente"):
        d[campo] = d.get(campo, "").lstrip("0") if d.get(campo, "").isdigit() else d.get(campo, "")
    d["anno_tessera"] = int(d["anno_tessera"]) if d.get("anno_tessera", "").isdigit() else None
    d["valido"] = _si_no(riga.get("valido"))
    if d.get("incarico", "").lower() in ("socio", "socio ordinario"):
        d["incarico"] = ""
    d["provincia"] = d.get("provincia", "").upper()[:2]
    d["cap"] = d.get("cap", "").zfill(5) if d.get("cap", "").isdigit() else d.get("cap", "")
    d["email"] = d.get("email", "").lower()
    for campo in ("comune", "luogo_nascita"):
        if d.get(campo):
            d[campo] = _nome_proprio(d[campo], luogo=True)
    if d.get("indirizzo"):
        d["indirizzo"] = _nome_proprio(d["indirizzo"], luogo=True)
    if d.get("sezione"):
        d["sezione"] = _nome_proprio(d["sezione"], luogo=True)
    return d


# --- elaborazione ------------------------------------------------------------------------


@dataclass
class Opzioni:
    sezione: Sezione | None = None  # se il file non ha la colonna sezione
    abbina: str = "comune"  # come riconoscere la sezione del file: comune, nome, codice
    tipologia: TipologiaSocio | None = None  # se la tipologia manca o non è riconosciuta
    crea_sezioni: bool = False
    allinea_sezione: bool = False  # sposta i soci esistenti nella sezione del registro
    tessere: bool = True  # registra i tesseramenti con i numeri di tessera del file
    anno_tessere: int | None = None  # anno delle tessere se il file non ha «Anno sociale»
    crea_tessere: bool = True  # crea le tessere fisiche non ancora caricate (lotto «registro»)
    cessazioni: bool = True  # registra le cessazioni (data di annullamento dell'iscrizione)
    quote_pagate: bool = False  # le quote dei tesseramenti importati risultano già incassate
    valido: bool = False  # colonna «Valido» (socio validato = in regola): sì -> quota incassata,
    # no -> quota da incassare; vuota -> vale `quote_pagate`
    sezioni_consentite: set | None = None  # utente limitato a queste sezioni


@dataclass
class Esito:
    riga: int
    nome: str
    stato: str  # nuovo, aggiornato, invariato, errore
    note: list = field(default_factory=list)
    socio_id: int | None = None


@dataclass
class Rapporto:
    esiti: list = field(default_factory=list)
    sezioni_nuove: list = field(default_factory=list)
    abbinamenti: dict = field(default_factory=dict)  # valore del file -> sezione scelta
    assenti: list = field(default_factory=list)  # soci attivi locali non presenti nel file
    eseguito: bool = False

    def conta(self, stato):
        return sum(1 for e in self.esiti if e.stato == stato)

    @property
    def riepilogo(self):
        return {s: self.conta(s) for s in ("nuovo", "aggiornato", "invariato", "errore")}


class _Errore(Exception):
    pass


PAROLE_GENERICHE = {"ancr", "sezione", "sez", "di", "del", "della", "comunale", "a", "n", "c", "r"}


def _nucleo(nome):
    """«ANCR Sezione di Avigliano» e «AVIGLIANO» -> «avigliano»."""
    return " ".join(p for p in normalizza(nome).split() if p not in PAROLE_GENERICHE)


def _cerca_sezione(nome):
    if s := Sezione.objects.filter(nome__iexact=nome).first():
        return s
    nucleo = _nucleo(nome)
    if not nucleo:
        return None
    for s in Sezione.objects.all():
        if nucleo in (_nucleo(s.nome), _nucleo(s.comune)):
            return s
    return None


def _codice_nuovo(nome):
    base = normalizza(nome).upper().replace(" ", "-")[:20] or "SEZ"
    codice, n = base, 2
    while Sezione.objects.filter(codice=codice).exists():
        codice, n = f"{base[:17]}-{n}", n + 1
    return codice


ABBINAMENTI = {
    "comune": "comune",
    "nome": "nome della sezione",
    "codice": "codice della sezione",
}


def comune_normale(testo):
    """«Avigliano, PZ», «AVIGLIANO (PZ)», «Avigliano» -> «avigliano»."""
    testo = re.sub(r"\(.*?\)", " ", testo or "")
    testo = re.sub(r",\s*[A-Za-z]{2}\s*$", "", testo.strip())
    return normalizza(testo)


def _cerca_per(campo, valore):
    """Sezioni attive corrispondenti (a quelle disattivate non si assegnano soci)."""
    attive = Sezione.objects.filter(attiva=True)
    if campo == "codice":
        return list(attive.filter(codice__iexact=valore))
    if campo == "comune":
        n = comune_normale(valore)
        return [s for s in attive if n and comune_normale(s.comune) == n]
    trovata = _cerca_sezione(valore)
    return [trovata] if trovata and trovata.attiva else []


def _sezione(d, opzioni, cache, rapporto):
    """Sezione della riga, cercata per comune, nome o codice (opzioni.abbina)."""
    campo = opzioni.abbina
    valore = d.get("sezione", "")
    if campo == "codice" and d.get("codice_sezione"):
        valore = d["codice_sezione"]
    chiave = valore.lower()
    if chiave in cache:
        if isinstance(cache[chiave], _Errore):
            raise cache[chiave]
        return cache[chiave]
    try:
        if not valore:
            sezione = opzioni.sezione
            if sezione is None:
                raise _Errore("sezione non indicata")
        else:
            trovate = _cerca_per(campo, valore)
            if len(trovate) > 1:
                elenco = ", ".join(f"{s.codice} {s.nome}" for s in trovate)
                raise _Errore(f"più sezioni con {ABBINAMENTI[campo]} «{valore}»: {elenco}")
            if trovate:
                sezione = trovate[0]
            elif not opzioni.crea_sezioni:
                raise _Errore(
                    f"nessuna sezione con {ABBINAMENTI[campo]} «{valore}» "
                    "(correggere le sezioni o abilitare la creazione)"
                )
            else:
                try:
                    with transaction.atomic():
                        sezione = Sezione.objects.create(
                            codice=valore[:20] if campo == "codice" else _codice_nuovo(valore),
                            nome=valore,
                            comune="" if campo == "codice" else valore,
                        )
                except IntegrityError:
                    raise _Errore(f"sezione «{valore}»: codice o nome già usati") from None
                rapporto.sezioni_nuove.append(sezione.nome)
        if opzioni.sezioni_consentite is not None and sezione.pk not in opzioni.sezioni_consentite:
            raise _Errore(f"sezione «{sezione}» non consentita all'utente")
    except _Errore as e:
        cache[chiave] = e
        if valore:
            rapporto.abbinamenti[valore] = f"non abbinata: {e}"
        raise
    cache[chiave] = sezione
    if valore:
        nuova = " (nuova)" if sezione.nome in rapporto.sezioni_nuove else ""
        rapporto.abbinamenti[valore] = f"{sezione.codice} {sezione.nome}{nuova}"
    return sezione


def _tipologia(d, opzioni):
    if nome := d.get("tipologia"):
        t = TipologiaSocio.objects.filter(nome__iexact=nome).first()
        if t:
            return t, []
        if opzioni.tipologia:
            return opzioni.tipologia, [f"tipologia «{nome}» non riconosciuta: {opzioni.tipologia}"]
    if opzioni.tipologia:
        return opzioni.tipologia, []
    raise _Errore("tipologia non riconosciuta e nessuna predefinita")


def _trova_soggetto(d):
    if d["codice_fiscale"]:
        s = Soggetto.objects.filter(codice_fiscale__iexact=d["codice_fiscale"]).first()
        if s:
            return s
    if d.get("matricola"):
        socio = Socio.objects.filter(matricola=d["matricola"]).select_related("soggetto").first()
        if socio:
            return socio.soggetto
    if d["data_nascita"]:
        omonimi = list(
            Soggetto.objects.filter(
                tipo=Soggetto.Tipo.PERSONA,
                cognome__iexact=d["cognome"],
                nome__iexact=d["nome"],
                data_nascita=d["data_nascita"],
            )[:2]
        )
        if len(omonimi) == 1:
            return omonimi[0]
    return None


def _riga(d, sezione, opzioni, utente, soggetto=None):
    """Importa una riga. `soggetto`: persona già individuata dal chiamante (altrimenti si cerca)."""
    note = []
    if not d["cognome"]:
        raise _Errore("cognome mancante")
    if d["codice_fiscale"]:
        try:
            valida_codice_fiscale(d["codice_fiscale"])
        except ValidationError:
            note.append(f"codice fiscale {d['codice_fiscale']} non valido: riportato nelle note")
            d["cf_non_valido"] = d["codice_fiscale"]
            d["codice_fiscale"] = ""
    da_cf = dati_da_codice_fiscale(d["codice_fiscale"]) if d["codice_fiscale"] else None
    if da_cf:
        d.setdefault("sesso", "")
        d["sesso"] = d["sesso"][:1].upper() if d["sesso"] else da_cf["sesso"]
        d["data_nascita"] = d["data_nascita"] or da_cf["data_nascita"]
        # dal codice fiscale anche la provincia: «Ruoti» -> «Ruoti (PZ)»
        luogo_cf = da_cf["luogo_nascita"]
        if not d.get("luogo_nascita") or normalizza(d["luogo_nascita"]) == normalizza(
            luogo_cf.split(" (")[0]
        ):
            d["luogo_nascita"] = luogo_cf
    tipologia, avvisi = _tipologia(d, opzioni)
    note += avvisi

    soggetto = soggetto or _trova_soggetto(d)
    stato = "invariato"
    if soggetto is None:
        soggetto = Soggetto.objects.create(
            tipo=Soggetto.Tipo.PERSONA, cognome=d["cognome"], nome=d["nome"],
            codice_fiscale=d["codice_fiscale"] or None, creato_da=utente, modificato_da=utente,
            note=f"Codice fiscale nel registro nazionale (non valido): {d['cf_non_valido']}"
            if d.get("cf_non_valido") else "",
            **{c: d[c] for c in CAMPI_ANAGRAFICI if d.get(c)},
        )  # fmt: skip
        registra(Azione.CREAZIONE, soggetto, utente=utente, origine="registro nazionale")
        stato = "nuovo"
    else:
        completati = [c for c in CAMPI_ANAGRAFICI if d.get(c) and not getattr(soggetto, c)]
        if d["codice_fiscale"] and not soggetto.codice_fiscale:
            completati.append("codice_fiscale")
        for c in completati:
            setattr(soggetto, c, d[c])
        diversi = [
            c for c in ("email", "comune", "indirizzo")
            if d.get(c) and getattr(soggetto, c)
            and normalizza(getattr(soggetto, c)) != normalizza(d[c])
        ]  # fmt: skip
        if diversi:
            note.append("dati locali diversi, non sovrascritti: " + ", ".join(diversi))
        if completati:
            soggetto.modificato_da = utente
            soggetto.save()
            registra(Azione.MODIFICA, soggetto, utente=utente, completati=completati,
                     origine="registro nazionale")  # fmt: skip
            note.append("completati: " + ", ".join(completati))
            stato = "aggiornato"
        if not soggetto.attivo:
            raise _Errore(f"{soggetto} è archiviato in anagrafica")

    socio = getattr(soggetto, "socio", None)
    if socio is None:
        ammissione = d["data_iscrizione"] or d.get("data_tessera") or date.today()
        if d.get("data_cessazione") and d["data_cessazione"] < ammissione:
            ammissione = d["data_cessazione"]
        socio = servizi.ammetti_socio(
            soggetto, tipologia, utente, data_ammissione=ammissione,
            delibera="Importato dal registro soci nazionale", sezione=sezione,
            matricola=d.get("matricola", ""),
            note=f"Incarico nel registro nazionale: {d['incarico']}" if d.get("incarico") else "",
        )  # fmt: skip
        if stato == "invariato":
            stato = "aggiornato"
        note.append(f"iscritto al libro soci con il n. {socio.numero}")
        if not d["data_iscrizione"]:
            note.append("data di ammissione assente nel registro")
    else:
        cambi = []
        if d.get("matricola") and not socio.matricola:
            if Socio.objects.filter(matricola=d["matricola"]).exclude(pk=socio.pk).exists():
                raise _Errore(f"matricola {d['matricola']} già di un altro socio")
            socio.matricola = d["matricola"]
            cambi.append("matricola")
        elif d.get("matricola") and socio.matricola != d["matricola"]:
            note.append(f"matricola locale {socio.matricola}, nel registro {d['matricola']}")
        if socio.sezione_id != sezione.pk:
            if opzioni.allinea_sezione:
                socio.sezione = sezione
                cambi.append("sezione")
            else:
                note.append(f"sezione locale «{socio.sezione}», nel registro «{sezione}»")
        if socio.stato != Socio.Stato.ATTIVO:
            note.append(f"socio {socio.get_stato_display().lower()} in locale")
        if cambi:
            socio.modificato_da = utente
            socio.save()
            registra(
                Azione.MODIFICA, socio, utente=utente, campi=cambi, origine="registro nazionale"
            )
            stato = "aggiornato" if stato != "nuovo" else stato
            note.append("aggiornati: " + ", ".join(cambi))

    if d.get("incarico"):
        note.append(f"incarico: {d['incarico']}")
    cessato = False
    if d.get("data_cessazione") and opzioni.cessazioni:
        if socio.stato != Socio.Stato.CESSATO:
            servizi.cessa_socio(
                socio, utente, data_cessazione=d["data_cessazione"], causa=Socio.Cessazione.ALTRO,
                note="Iscrizione annullata nel registro soci nazionale",
            )  # fmt: skip
            socio.refresh_from_db()
            stato = "aggiornato" if stato == "invariato" else stato
            note.append(f"cessato il {d['data_cessazione']:%d/%m/%Y} (annullato nel registro)")
        cessato = True

    if opzioni.tessere and not cessato:
        anno = d.get("anno_tessera") or opzioni.anno_tessere
        tessere = []
        if d.get("tessera_precedente") and d.get("_anno_tessera_precedente"):
            tessere.append((d["_anno_tessera_precedente"], d["tessera_precedente"], None,
                            opzioni.quote_pagate))  # fmt: skip
        pagata = opzioni.quote_pagate
        if opzioni.valido and d.get("valido") is not None:
            pagata = d["valido"]
            if not d["valido"]:
                note.append("non validato nel registro: quota da incassare")
        if d.get("tessera") and anno:
            tessere.append((anno, d["tessera"], d.get("data_tessera"), pagata))
        for a, codice, rilascio, quota_pagata in tessere:
            pagata_il = d.get("data_pagamento") if a == anno else None
            esito = _tessera(socio, codice, a, rilascio, opzioni, utente, pagata=quota_pagata,
                             pagata_il=pagata_il)  # fmt: skip
            note += esito
            if stato == "invariato" and any("attribuita" in n or "incassata" in n for n in esito):
                stato = "aggiornato"
    return stato, note, socio


def _incassa_esterno(tessera, utente, pagata_il=None):
    servizi.segna_incasso_esterno(
        tessera, utente, pagata_il=pagata_il or tessera.data_rilascio,
        nota="Registro soci nazionale",
    )  # fmt: skip


def _tessera(socio, codice, anno, rilascio, opzioni, utente, *, pagata=None, pagata_il=None):
    pagata = opzioni.quote_pagate if pagata is None else pagata
    tessera = socio.tessere.valide().filter(anno=anno).first()
    if tessera and tessera.carta_id:
        if tessera.carta.codice != codice and str(tessera.carta.numero) != codice.lstrip("0"):
            return [f"tessera {anno}: locale {tessera.carta.codice}, nel registro {codice}"]
        if pagata and opzioni.valido and not tessera.pagata and tessera.importo > 0:
            _incassa_esterno(tessera, utente, pagata_il)
            return [f"quota {anno} segnata incassata (validato nel registro)"]
        return []
    if socio.stato != Socio.Stato.ATTIVO:
        return []
    try:
        with transaction.atomic():
            if opzioni.crea_tessere and codice.isdigit():
                servizi.carta_da_registro(anno, socio.sezione, int(codice), utente)
            if tessera is None:
                tessera = servizi.rilascia_tessera(
                    socio, anno, utente, data_rilascio=rilascio or date(anno, 1, 1)
                )
            tessera = servizi.attribuisci_carta(tessera, utente, codice)
            if pagata:
                _incassa_esterno(tessera, utente, pagata_il)
    except ValidationError as e:
        return [f"tessera {anno} n. {codice} non attribuita: {' '.join(e.messages)}"]
    return [f"tessera {tessera.codice} attribuita per il {anno}"]


def _assenti(sezioni_file, trovati):
    """Soci attivi delle sezioni presenti nel file che nel file non compaiono."""
    qs = Socio.objects.attivi().filter(sezione__in=sezioni_file).exclude(pk__in=trovati)
    return list(qs.select_related("soggetto").order_by("numero"))


def elabora(righe, opzioni, utente, *, esegui=False, avanzamento=None):
    """Importa le righe. Senza `esegui` tutto avviene in una transazione poi annullata:
    l'anteprima mostra esattamente ciò che accadrà, senza modificare nulla."""
    rapporto = Rapporto(eseguito=esegui)
    with transaction.atomic():
        cache = {}
        for n, grezza in enumerate(righe, start=1):
            if avanzamento:
                avanzamento(n - 1, len(righe))
            d = _pulisci(grezza)
            nome = f"{d['cognome']} {d['nome']}".strip() or "(senza nome)"
            try:
                # la sezione si risolve (o si crea) fuori dal punto di ripristino della riga:
                # resta valida per le righe successive anche se questa fallisce
                sezione = _sezione(d, opzioni, cache, rapporto)
                with transaction.atomic():
                    stato, note, socio = _riga(d, sezione, opzioni, utente)
                rapporto.esiti.append(Esito(grezza["_riga"], nome, stato, note, socio.pk))
            except _Errore as e:
                rapporto.esiti.append(Esito(grezza["_riga"], nome, "errore", [str(e)]))
            except ValidationError as e:
                rapporto.esiti.append(Esito(grezza["_riga"], nome, "errore", e.messages))
        sezioni_file = {s.pk for s in cache.values() if isinstance(s, Sezione)}
        trovati = {e.socio_id for e in rapporto.esiti if e.socio_id}
        rapporto.assenti = [(s.numero, s.soggetto.nome_completo, s.sezione_id)
                            for s in _assenti(sezioni_file, trovati)]  # fmt: skip
        if esegui:
            registra(
                Azione.CREAZIONE,
                utente=utente,
                descrizione="Importazione dal registro soci nazionale",
                **rapporto.riepilogo,
                sezioni_create=rapporto.sezioni_nuove,
            )
        else:
            transaction.set_rollback(True)
    return rapporto
