# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Codice fiscale assistito: calcolo dai dati anagrafici (con scelta fra comuni
# *              omonimi), controllo di coerenza con cognome, nome, sesso, data e luogo di
# *              nascita, esame delle schede e correzione con registro attività.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from functools import cache
from typing import Literal, cast

from codicefiscale import codicefiscale
from codicefiscale.data import get_indexed_data
from django.db import transaction
from django.utils.text import slugify

from apps.core.audit import Azione, registra

_PROVINCIA = re.compile(r"^(?P<nome>.+?)\s*\((?P<provincia>[A-Za-z]{2})\)\s*$")


@cache
def _indice():
    """Comuni (anche soppressi) e stati esteri della libreria, indicizzati una volta sola."""
    return get_indexed_data()


class OperazioneNonValida(Exception):
    """Operazione rifiutata, con un messaggio per l'utente."""


@dataclass(frozen=True)
class Luogo:
    codice: str  # codice catastale (Belfiore), es. A519; Z... per gli stati esteri
    nome: str
    provincia: str  # sigla, «EE» per gli stati esteri

    @property
    def etichetta(self):
        return self.nome if self.provincia == "EE" else f"{self.nome} ({self.provincia})"


@dataclass
class Calcolo:
    codice: str = ""
    candidati: list[Luogo] = field(default_factory=list)  # comuni omonimi: scegliere
    errore: str = ""


def _data(valore):
    if isinstance(valore, datetime):
        return valore.date()
    if isinstance(valore, date):
        return valore
    try:
        return date.fromisoformat(str(valore)) if valore else None
    except ValueError:
        return None


def _valido_alla(opzione, quando):
    if quando is None:
        return True
    creato = _data((opzione.get("date_created") or "")[:10]) or date.min
    soppresso = _data((opzione.get("date_deleted") or "")[:10]) or date.max
    return creato <= quando <= soppresso


def _varianti(testo):
    """Grafie da provare per un nome di luogo, come si trovano negli archivi reali:
    «SANT'ANTONIO» / «Sant Antonio», nomi bilingui («BOLZANO .BOZEN.», «Bolzano/Bozen»),
    accenti resi con l'apostrofo («AGLIE'»), «j» al posto di «i» («BAIARDO» → «Bajardo»)."""
    base = re.split(r"\s*(?:/|\s\.|\(|\s-\s)", testo.strip())[0].strip(" .")
    varianti = [testo, base]
    for t in (testo, base):
        senza = re.sub(r"(\w)'(?=\s|$)", r"\1", t)  # accento come apostrofo finale
        varianti += [t.replace("'", " "), senza, senza.replace("'", " ")]
    varianti += [re.sub(r"(?<=[aeiou])i(?=[aeiou])", "j", v, flags=re.I) for v in list(varianti)]
    return list(dict.fromkeys(v for v in varianti if v))


def luoghi(testo, data_nascita=None):
    """Comuni o stati esteri che corrispondono al testo («Avigliano», «Castro (LE)», «Germania»).

    Più risultati solo per comuni omonimi in province diverse; fra le versioni dello stesso
    comune si tiene quella esistente alla data di nascita.
    """
    testo = (testo or "").strip()
    if not testo:
        return []
    dati = _indice()
    provincia = ""
    if m := _PROVINCIA.match(testo):
        testo, provincia = m["nome"], m["provincia"].lower()
    chiavi = []
    for variante in _varianti(testo):
        for slug in (slugify(variante, allow_unicode=True), slugify(variante)):
            if provincia:
                chiavi.append(f"{slug}-{provincia}")
            chiavi.append(slug)
    opzioni = []
    for chiave in chiavi:
        opzioni = dati["municipalities"].get(chiave) or dati["countries"].get(chiave) or []
        if opzioni:
            break
    if not opzioni and re.fullmatch(r"[A-Za-z]\d{3}", testo):
        opzioni = dati["codes"].get(testo.upper()) or []
    quando = _data(data_nascita)
    if quando:
        validi = [o for o in opzioni if _valido_alla(o, quando)] or opzioni
    else:  # senza data: il comune com'è oggi (es. Bolzano in provincia di BZ, non di TN)
        validi = [o for o in opzioni if o.get("active")] or opzioni
    validi = sorted(validi, key=lambda o: not o.get("active"))
    risultato = {}
    for o in validi:
        risultato.setdefault(o["code"], Luogo(o["code"], o["name"], o.get("province") or ""))
    return sorted(risultato.values(), key=lambda luogo: luogo.etichetta)


def calcola(*, cognome, nome, sesso, data_nascita, luogo_nascita):
    """Codice fiscale dai dati anagrafici (il codice «teorico»: senza omocodie)."""
    mancanti = [
        etichetta
        for etichetta, valore in [
            ("cognome", cognome), ("nome", nome), ("sesso", sesso),
            ("data di nascita", data_nascita), ("luogo di nascita", luogo_nascita),
        ]
        if not valore
    ]  # fmt: skip
    if mancanti:
        return Calcolo(errore="Per calcolarlo servono: " + ", ".join(mancanti) + ".")
    if str(sesso).upper() not in ("M", "F"):
        return Calcolo(errore="Sesso non valido.")
    quando = _data(data_nascita)
    if quando is None:
        return Calcolo(errore="Data di nascita non valida.")
    trovati = luoghi(luogo_nascita, quando)
    if not trovati:
        return Calcolo(
            errore=f"«{luogo_nascita}» non è tra i comuni italiani né tra gli stati esteri."
        )
    if len(trovati) > 1:
        return Calcolo(
            candidati=trovati, errore="Più comuni con questo nome: scegliere quello giusto."
        )
    try:
        codice = codicefiscale.encode(
            lastname=cognome, firstname=nome,
            gender=cast(Literal["M", "F"], str(sesso).upper()),
            birthdate=quando.isoformat(), birthplace=trovati[0].codice,
        )  # fmt: skip
    except ValueError:
        return Calcolo(errore="Dati non sufficienti per il calcolo.")
    return Calcolo(codice=codice)


def anomalie(codice, *, cognome="", nome="", sesso="", data_nascita=None, luogo_nascita=""):
    """Differenze fra un codice fiscale e i dati anagrafici indicati (solo quelli presenti)."""
    codice = (codice or "").strip().upper()
    if not codicefiscale.is_valid(codice):
        return ["codice fiscale non valido"]
    trovate = []
    if cognome and codicefiscale.encode_lastname(cognome) != codice[0:3]:
        trovate.append("il cognome non corrisponde")
    if nome and codicefiscale.encode_firstname(nome) != codice[3:6]:
        trovate.append("il nome non corrisponde")
    decodificato = codicefiscale.decode(codice)
    if sesso and str(sesso).upper() != decodificato["gender"]:
        trovate.append("il sesso non corrisponde")
    quando = _data(data_nascita)
    if quando and quando != decodificato["birthdate"].date():
        trovate.append("la data di nascita non corrisponde")
    luogo_codice = (decodificato.get("birthplace") or {}).get("code")
    if luogo_nascita and luogo_codice:
        codici = {luogo.codice for luogo in luoghi(luogo_nascita, quando)}
        if codici and luogo_codice not in codici:
            trovate.append("il luogo di nascita non corrisponde")
    return trovate


# --- schede dell'anagrafica ---------------------------------------------------------------


@dataclass
class Esame:
    stato: str  # "mancante", "non_valido", "incoerente", "corretto"
    anomalie: list[str] = field(default_factory=list)
    proposta: str = ""  # codice calcolato dai dati, se diverso dall'attuale
    nota: str = ""  # perché manca la proposta (dati incompleti, comune ambiguo...)

    @property
    def da_sistemare(self):
        return self.stato != "corretto"

    @property
    def descrizione(self):
        return {
            "mancante": "Mancante",
            "non_valido": "Non valido",
            "incoerente": "Non corrisponde ai dati",
            "corretto": "Corretto",
        }[self.stato]


def _dati(soggetto):
    return {
        "cognome": soggetto.cognome, "nome": soggetto.nome, "sesso": soggetto.sesso,
        "data_nascita": soggetto.data_nascita, "luogo_nascita": soggetto.luogo_nascita,
    }  # fmt: skip


def _omocodia_di(codice, teorico):
    """Vero se il codice è una variante per omocodia del codice teorico."""
    if not (codicefiscale.is_valid(codice) and codicefiscale.is_omocode(codice)):
        return False
    return codicefiscale.decode(codice)["omocodes"][0] == teorico


def esamina(soggetto):
    """Stato del codice fiscale di una persona, con la correzione proposta quando possibile."""
    attuale = (soggetto.codice_fiscale or "").strip().upper()
    if attuale and len(attuale) == 11 and attuale.isdigit():
        return Esame("corretto")  # codice numerico (es. persona con partita IVA): non si calcola
    if not attuale:
        stato, trovate = "mancante", []
    elif not codicefiscale.is_valid(attuale):
        stato, trovate = "non_valido", []
    else:
        trovate = anomalie(attuale, **_dati(soggetto))
        if not trovate:
            return Esame("corretto")
        stato = "incoerente"
    calcolo = calcola(**_dati(soggetto))
    proposta = calcolo.codice if calcolo.codice and calcolo.codice != attuale else ""
    # un'omocodia legittima (cifre sostituite da lettere) differisce dal codice teorico
    if proposta and _omocodia_di(attuale, proposta):
        proposta = ""
    return Esame(stato, trovate, proposta, "" if calcolo.codice else calcolo.errore)


@transaction.atomic
def correggi(soggetto, codice, utente):
    """Sostituisce il codice fiscale di una persona con quello calcolato (o indicato)."""
    from .models import Soggetto

    soggetto = Soggetto.objects.select_for_update().get(pk=soggetto.pk)
    codice = (codice or "").strip().upper()
    if not soggetto.is_persona:
        raise OperazioneNonValida("Il codice fiscale si calcola solo per le persone.")
    if not codicefiscale.is_valid(codice):
        raise OperazioneNonValida("Il codice indicato non è valido.")
    if trovate := anomalie(codice, **_dati(soggetto)):
        raise OperazioneNonValida("Il codice non corrisponde ai dati: " + ", ".join(trovate) + ".")
    altro = Soggetto.objects.filter(codice_fiscale=codice).exclude(pk=soggetto.pk).first()
    if altro:
        raise OperazioneNonValida(f"Codice già usato da {altro.nome_completo}.")
    precedente = soggetto.codice_fiscale or ""
    soggetto.codice_fiscale = codice
    soggetto.modificato_da = utente
    soggetto.save(update_fields=["codice_fiscale", "modificato_da", "modificato_il"])
    registra(
        Azione.MODIFICA, soggetto, utente=utente,
        codice_fiscale={"prima": precedente, "dopo": codice}, origine="codice fiscale assistito",
    )  # fmt: skip
    return soggetto
