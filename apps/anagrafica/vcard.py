# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Schede dell'anagrafica da e verso le rubriche (vCard .vcf): esportazione in
# *              vCard 3.0 (telefoni, Google Contatti, Outlook, Thunderbird) e importazione di
# *              vCard 2.1/3.0/4.0 con abbinamento alle schede esistenti e anteprima.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import quopri
import re
from dataclasses import dataclass, field
from datetime import date

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction

from apps.core.audit import Azione, registra

from .models import Categoria, Soggetto

MAX_CONTATTI = 5000
NAZIONI = {"italia": "IT", "italy": "IT", "it": "IT", "": "IT"}


class FileNonValido(ValueError):
    """Il file non contiene vCard leggibili (messaggio per l'utente)."""


# --- esportazione --------------------------------------------------------------------------


def _esc(valore):
    return (
        str(valore or "")
        .replace("\\", "\\\\")
        .replace("\r\n", "\n")
        .replace("\n", "\\n")
        .replace(",", "\\,")
        .replace(";", "\\;")
    )


def _piega(riga):
    """Righe di al massimo 75 byte (RFC 6350), senza spezzare i caratteri UTF-8."""
    parti, corrente, lung = [], "", 0
    for car in riga:
        n = len(car.encode("utf-8"))
        limite = 75 if not parti else 74
        if lung + n > limite:
            parti.append(corrente)
            corrente, lung = "", 0
        corrente += car
        lung += n
    parti.append(corrente)
    return "\r\n ".join(parti)


def vcard(s, *, numero_socio=None):
    righe = ["BEGIN:VCARD", "VERSION:3.0", f"UID:gestione-associazione-soggetto-{s.pk}"]
    if s.is_persona:
        righe.append(f"N:{_esc(s.cognome)};{_esc(s.nome)};;{_esc(s.titolo)};")
        righe.append(f"FN:{_esc(s.intestazione)}")
        if s.qualifica:
            righe.append(f"TITLE:{_esc(s.qualifica)}")
    else:
        righe.append(f"N:{_esc(s.denominazione)};;;;")
        righe.append(f"FN:{_esc(s.denominazione)}")
        righe.append(f"ORG:{_esc(s.denominazione)}")
        righe.append("X-ABShowAs:COMPANY")
        if s.qualifica:
            righe.append(f"TITLE:{_esc(s.qualifica)}")
    if s.email:
        righe.append(f"EMAIL;TYPE=INTERNET,PREF:{s.email}")
    if s.pec:
        righe.append(f"EMAIL;TYPE=INTERNET,WORK:{s.pec}")
    if s.cellulare:
        righe.append(f"TEL;TYPE=CELL:{_esc(s.cellulare)}")
    if s.telefono:
        righe.append(f"TEL;TYPE=VOICE:{_esc(s.telefono)}")
    if s.indirizzo or s.comune:
        nazione = "Italia" if s.nazione == "IT" else s.nazione
        tipo = "HOME" if s.is_persona else "WORK"
        righe.append(
            f"ADR;TYPE={tipo}:;;{_esc(s.indirizzo)};{_esc(s.comune)};{_esc(s.provincia)};"
            f"{_esc(s.cap)};{_esc(nazione)}"
        )
    if s.data_nascita:
        righe.append(f"BDAY:{s.data_nascita:%Y-%m-%d}")
    categorie = [c.nome for c in s.categorie.all()]
    if categorie:
        righe.append("CATEGORIES:" + ",".join(_esc(c) for c in categorie))
    if numero_socio:
        righe.append(f"NOTE:{_esc(f'Socio n. {numero_socio}')}")
    righe.append("END:VCARD")
    return "".join(_piega(r) + "\r\n" for r in righe)


def esporta(queryset, utente, *, descrizione="Rubrica vCard"):
    """Testo .vcf con una scheda per soggetto (esclusi i deceduti) e annotazione nel registro."""
    from apps.soci.models import Socio

    soggetti = queryset.filter(data_decesso__isnull=True).prefetch_related("categorie")
    numeri = dict(
        Socio.objects.filter(soggetto__in=soggetti, stato=Socio.Stato.ATTIVO).values_list(
            "soggetto_id", "numero"
        )
    )
    testo = "".join(vcard(s, numero_socio=numeri.get(s.pk)) for s in soggetti)
    n = testo.count("BEGIN:VCARD")
    registra(Azione.ESPORTAZIONE, utente=utente, descrizione=f"{descrizione} ({n} schede)",
             schede=n)  # fmt: skip
    return testo, n


# --- lettura --------------------------------------------------------------------------------


def _decodifica(contenuto):
    for codifica in ("utf-8-sig", "cp1252"):
        try:
            return contenuto.decode(codifica)
        except UnicodeDecodeError:
            continue
    return contenuto.decode("latin-1")


def _righe_logiche(testo):
    """Ricompone le righe piegate (spazio iniziale) e le soft line break del quoted-printable."""
    righe = []
    for riga in testo.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if righe and riga[:1] in (" ", "\t"):
            righe[-1] += riga[1:]
        elif righe and righe[-1].endswith("=") and "QUOTED-PRINTABLE" in righe[-1].upper():
            righe[-1] = righe[-1][:-1] + riga
        elif riga.strip():
            righe.append(riga)
    return righe


def _proprieta(riga):
    """(NOME, {parametro: valore}, tipi, valore grezzo) da una riga vCard."""
    in_virgolette, pos = False, -1
    for i, car in enumerate(riga):
        if car == '"':
            in_virgolette = not in_virgolette
        elif car == ":" and not in_virgolette:
            pos = i
            break
    if pos < 0:
        return None
    testa, valore = riga[:pos], riga[pos + 1 :]
    pezzi = testa.split(";")
    nome = pezzi[0].split(".")[-1].upper()  # «item1.EMAIL» -> EMAIL
    parametri, tipi = {}, set()
    for p in pezzi[1:]:
        if "=" in p:
            k, v = p.split("=", 1)
            k, v = k.upper(), v.strip('"')
            parametri[k] = v
            if k == "TYPE":
                tipi.update(t.upper() for t in v.split(","))
        else:
            tipi.add(p.upper())  # vCard 2.1: «TEL;CELL:...»
    codifica = parametri.get("ENCODING", "").upper()
    if codifica in ("QUOTED-PRINTABLE", "QP") or "QUOTED-PRINTABLE" in tipi:
        grezzo = quopri.decodestring(valore.encode("latin-1", errors="ignore"))
        valore = grezzo.decode(parametri.get("CHARSET", "utf-8"), errors="replace")
    return nome, parametri, tipi, valore


def _componenti(valore):
    """Divide sui «;» non preceduti da «\\» e toglie le sequenze di escape."""
    parti = re.split(r"(?<!\\);", valore)
    return [_testo(p) for p in parti]


def _testo(valore):
    return re.sub(r"\\([,;\\])", r"\1", valore).replace("\\n", "\n").replace("\\N", "\n").strip()


def _data(valore):
    v = valore.strip()
    if v.startswith("--"):  # senza anno
        return None
    m = re.match(r"^(\d{4})-?(\d{2})-?(\d{2})", v)
    if not m:
        return None
    try:
        return date(int(m[1]), int(m[2]), int(m[3]))
    except ValueError:
        return None


def _cifre(numero):
    cifre = re.sub(r"\D", "", numero or "")
    return cifre[2:] if cifre.startswith("39") and len(cifre) > 10 else cifre


@dataclass
class Contatto:
    tipo: str = Soggetto.Tipo.PERSONA
    dati: dict = field(default_factory=dict)
    categorie: list = field(default_factory=list)
    altri: list = field(default_factory=list)  # telefoni ed email in più, finiscono nelle note

    @property
    def nome(self):
        d = self.dati
        if self.tipo == Soggetto.Tipo.ENTE:
            return d.get("denominazione", "")
        return " ".join(p for p in (d.get("cognome"), d.get("nome")) if p)


def _contatto(proprieta):
    c = Contatto()
    d = c.dati
    fn = org = titolo_ruolo = ""
    telefoni, email = [], []
    for nome, _parametri, tipi, valore in proprieta:
        if nome == "N":
            parti = _componenti(valore) + [""] * 5
            d["cognome"], d["nome"] = parti[0], " ".join(p for p in parti[1:3] if p)
            if parti[3]:
                d["titolo"] = parti[3][:40]
        elif nome == "FN":
            fn = _testo(valore)
        elif nome == "ORG":
            org = " - ".join(p for p in _componenti(valore) if p)
        elif nome == "TITLE":
            titolo_ruolo = _testo(valore)
        elif nome == "TEL":
            telefoni.append((tipi, _testo(valore)))
        elif nome == "EMAIL":
            email.append(_testo(valore))
        elif nome == "ADR" and "indirizzo" not in d:
            parti = _componenti(valore) + [""] * 7
            d["indirizzo"] = " ".join(p for p in (parti[2], parti[1]) if p)[:255]
            d["comune"] = parti[3][:100]
            if re.fullmatch(r"[A-Za-z]{2}", parti[4]):
                d["provincia"] = parti[4].upper()
            if re.fullmatch(r"\d{5}", parti[5]):
                d["cap"] = parti[5]
            nazione = parti[6].strip()
            if nazione.lower() in NAZIONI:
                d["nazione"] = NAZIONI[nazione.lower()]
            elif re.fullmatch(r"[A-Za-z]{2}", nazione):
                d["nazione"] = nazione.upper()
        elif nome == "BDAY":
            nascita = _data(valore)
            if nascita:
                d["data_nascita"] = nascita
        elif nome == "CATEGORIES":
            c.categorie += [_testo(p) for p in re.split(r"(?<!\\),", valore) if p.strip()]
        elif nome == "NOTE":
            d["note"] = _testo(valore)
    if not d.get("cognome") and not d.get("nome"):
        if org and (not fn or fn == org):
            c.tipo = Soggetto.Tipo.ENTE
        elif fn:
            parole = fn.split()
            d["cognome"] = parole[-1]
            d["nome"] = " ".join(parole[:-1])
        elif org:
            c.tipo = Soggetto.Tipo.ENTE
    if c.tipo == Soggetto.Tipo.ENTE:
        d.pop("cognome", None), d.pop("nome", None), d.pop("titolo", None)
        d.pop("data_nascita", None)
        d["denominazione"] = org[:255]
        if titolo_ruolo:
            d["qualifica"] = titolo_ruolo[:150]
    else:
        qualifica = " - ".join(p for p in (titolo_ruolo, org) if p)
        if qualifica:
            d["qualifica"] = qualifica[:150]
    for tipi, numero in telefoni:
        if not numero:
            continue
        cellulare = bool(tipi & {"CELL", "MOBILE", "IPHONE"}) or (
            not tipi & {"HOME", "WORK", "VOICE", "FAX"} and _cifre(numero).startswith("3")
        )
        chiave = "cellulare" if cellulare else "telefono"
        if "FAX" not in tipi and chiave not in d:
            d[chiave] = numero[:30]
        else:
            c.altri.append(numero)
    for indirizzo in email:
        try:
            validate_email(indirizzo)
        except ValidationError:
            continue
        chiave = "pec" if "pec" in indirizzo.lower().split("@")[-1] else "email"
        if chiave not in d:
            d[chiave] = indirizzo
        else:
            c.altri.append(indirizzo)
    return c


def leggi(contenuto):
    """Contatti di un file .vcf (bytes). Solleva FileNonValido se non ce ne sono."""
    testo = _decodifica(contenuto)
    contatti, corrente = [], None
    for riga in _righe_logiche(testo):
        maiuscola = riga.strip().upper()
        if maiuscola == "BEGIN:VCARD":
            corrente = []
        elif maiuscola == "END:VCARD":
            if corrente is not None:
                contatti.append(_contatto(corrente))
            corrente = None
        elif corrente is not None:
            p = _proprieta(riga)
            if p and p[0] not in ("PHOTO", "LOGO", "SOUND", "KEY"):
                corrente.append(p)
        if len(contatti) > MAX_CONTATTI:
            raise FileNonValido(f"Il file contiene più di {MAX_CONTATTI} contatti: dividerlo.")
    if not contatti:
        raise FileNonValido("Il file non contiene schede vCard (BEGIN:VCARD ... END:VCARD).")
    return contatti


# --- importazione ---------------------------------------------------------------------------


class _Annulla(Exception):
    pass


@dataclass
class Riga:
    nome: str
    esito: str  # nuovo, aggiornato, invariato, ambiguo, scartato
    dettaglio: str = ""
    soggetto: Soggetto | None = None


class _Indice:
    """Schede esistenti per email, telefono e nome, per abbinare i contatti."""

    def __init__(self):
        self.email, self.telefono, self.nome = {}, {}, {}
        for s in Soggetto.objects.all():
            self.aggiungi(s)

    def aggiungi(self, s):
        for e in (s.email, s.pec):
            if e:
                self.email.setdefault(e.lower(), set()).add(s.pk)
        for t in (s.cellulare, s.telefono):
            if len(_cifre(t)) >= 6:
                self.telefono.setdefault(_cifre(t), set()).add(s.pk)
        self.nome.setdefault(self._chiave_nome(s.tipo, s.cognome, s.nome, s.denominazione),
                             set()).add(s.pk)  # fmt: skip

    @staticmethod
    def _chiave_nome(tipo, cognome, nome, denominazione):
        if tipo == Soggetto.Tipo.ENTE:
            return ("ente", (denominazione or "").strip().lower())
        return ("persona", (cognome or "").strip().lower(), (nome or "").strip().lower())

    def cerca(self, c):
        d = c.dati
        for e in (d.get("email"), d.get("pec")):
            if e and e.lower() in self.email:
                return self.email[e.lower()]
        for t in (d.get("cellulare"), d.get("telefono")):
            if t and len(_cifre(t)) >= 6 and _cifre(t) in self.telefono:
                return self.telefono[_cifre(t)]
        chiave = self._chiave_nome(c.tipo, d.get("cognome"), d.get("nome"), d.get("denominazione"))
        return self.nome.get(chiave, set())


def _note_altri(c):
    return ("Altri recapiti: " + ", ".join(c.altri)) if c.altri else ""


def _pulisci(s):
    """Toglie i campi che non superano la validazione (es. CAP o email malformati)."""
    try:
        s.full_clean(exclude=["codice_fiscale"], validate_unique=False, validate_constraints=False)
        return []
    except ValidationError as e:
        tolti = []
        for campo in e.error_dict:
            if campo in ("cognome", "denominazione", "nome", "tipo", "__all__"):
                raise
            predefinito = Soggetto._meta.get_field(campo).get_default()
            setattr(s, campo, predefinito)
            tolti.append(campo)
        s.full_clean(exclude=["codice_fiscale"], validate_unique=False, validate_constraints=False)
        return tolti


def _importa_uno(c, indice, utente, categorie_extra):
    nome = c.nome or "(senza nome)"
    if not c.nome:
        return Riga(nome, "scartato", "manca il nome")
    trovati = indice.cerca(c)
    if len(trovati) > 1:
        return Riga(nome, "ambiguo", f"{len(trovati)} schede corrispondono: da verificare a mano")
    categorie = list(categorie_extra)
    if c.categorie:
        categorie += list(Categoria.objects.filter(nome__in=c.categorie))
    altri = _note_altri(c)
    if trovati:
        s = Soggetto.objects.get(pk=next(iter(trovati)))
        completati = []
        for campo, valore in c.dati.items():
            if campo == "note":
                continue
            if valore and not getattr(s, campo) and campo != "nazione":
                setattr(s, campo, valore)
                completati.append(campo)
        if altri and altri not in s.note:
            s.note = f"{s.note}\n{altri}".strip()
            completati.append("note")
        nuove = [k for k in categorie if not s.categorie.filter(pk=k.pk).exists()]
        if not completati and not nuove:
            return Riga(nome, "invariato", s.nome_completo, s)
        tolti = _pulisci(s)
        s.modificato_da = utente
        s.save()
        s.categorie.add(*nuove)
        indice.aggiungi(s)
        dettaglio = ", ".join(Soggetto._meta.get_field(f).verbose_name for f in completati
                              if f not in tolti)  # fmt: skip
        if nuove:
            dettaglio = ", ".join(p for p in (dettaglio, "categorie") if p)
        return Riga(nome, "aggiornato", f"{s.nome_completo}: {dettaglio}", s)
    s = Soggetto(tipo=c.tipo, creato_da=utente, modificato_da=utente, **c.dati)
    if altri:
        s.note = f"{s.note}\n{altri}".strip()
    try:
        tolti = _pulisci(s)
    except ValidationError as e:
        return Riga(nome, "scartato", "; ".join(e.messages))
    s.save()
    s.categorie.add(*categorie)
    indice.aggiungi(s)
    return Riga(nome, "nuovo", ("ignorati: " + ", ".join(tolti)) if tolti else "", s)


def importa(contatti, utente, *, categoria=None, esegui=False):
    """Crea le schede nuove e completa i campi vuoti di quelle già presenti (abbinate per email,
    telefono o nome; mai sovrascritte). Senza `esegui` è un'anteprima: tutto viene annullato."""
    righe = []
    extra = [categoria] if categoria else []
    try:
        with transaction.atomic():
            indice = _Indice()
            for c in contatti:
                with transaction.atomic():
                    righe.append(_importa_uno(c, indice, utente, extra))
            if not esegui:
                raise _Annulla
            conteggi = riepilogo(righe)
            registra(Azione.CREAZIONE, utente=utente,
                     descrizione=f"Importazione da rubrica vCard: {conteggi['nuovo']} nuove, "
                     f"{conteggi['aggiornato']} completate", **conteggi)  # fmt: skip
    except _Annulla:
        for r in righe:
            r.soggetto = None
    return righe


def riepilogo(righe):
    conteggi = dict.fromkeys(("nuovo", "aggiornato", "invariato", "ambiguo", "scartato"), 0)
    for r in righe:
        conteggi[r.esito] += 1
    return conteggi
