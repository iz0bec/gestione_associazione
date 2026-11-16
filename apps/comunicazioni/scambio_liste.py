# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Liste di destinatari in Excel: esportazione per la modifica fuori linea e
# *              reimportazione con anteprima (abbinamento delle persone all'anagrafica per
# *              codice, codice fiscale o email; schede nuove solo su richiesta).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import io
from dataclasses import dataclass, field

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.anagrafica.models import Categoria, Soggetto
from apps.core.audit import Azione, registra

from .models import Lista

FOGLIO_LISTA = "Lista"
FOGLIO_PERSONE = "Persone"
FOGLIO_DESTINATARI = "Destinatari"
FOGLIO_ISTRUZIONI = "Istruzioni"

CAMPI_LISTA = [
    ("codice", "Codice lista"),
    ("nome", "Nome"),
    ("descrizione", "Descrizione"),
    ("soci_attivi", "Tutti i soci attivi"),
    ("soci_in_regola", "Solo i soci in regola con la quota"),
    ("organo", "Componenti in carica dell'organo"),
    ("categorie", "Categorie dell'anagrafica"),
]
COLONNE_PERSONE = ["Codice", "Tipo", "Cognome o denominazione", "Nome", "Codice fiscale", "Email"]

ISTRUZIONI = [
    "Come modificare la lista fuori linea",
    "",
    "Foglio «Lista»: si modificano solo i valori della colonna B.",
    "  - Codice lista: non modificarlo. Indica quale lista aggiornare; se si cancella, il file "
    "crea una lista nuova (o aggiorna quella con lo stesso nome).",
    "  - Tutti i soci attivi / Solo i soci in regola: «sì» oppure «no».",
    "  - Organo: il nome come appare nel gestionale (es. «Consiglio direttivo»); vuoto = nessuno.",
    "  - Categorie: nomi separati da punto e virgola (es. «Autorità; Stampa»).",
    "",
    "Foglio «Persone»: le persone e gli enti scelti uno per uno.",
    "  - Per togliere qualcuno si cancella la riga.",
    "  - Per aggiungere qualcuno basta una riga con il codice fiscale o l'email di una scheda già",
    "    presente in anagrafica; il codice resta vuoto.",
    "  - Chi non è in anagrafica viene segnalato nell'anteprima; si può chiedere di creare la",
    "    scheda (Tipo «persona» o «ente», cognome o denominazione, email).",
    "",
    "Foglio «Destinatari»: chi riceve oggi le comunicazioni della lista (soci, categorie, organo",
    "e persone scelte). È solo da consultare: all'importazione viene ignorato.",
    "",
    "Poi: Comunicazioni → Liste → Importa da Excel. Prima di salvare si vede l'anteprima.",
]

SI = {"si", "sì", "s", "x", "vero", "true", "1", "yes"}
NO = {"no", "n", "falso", "false", "0", ""}


class FileNonValido(ValidationError):
    pass


# --- esportazione --------------------------------------------------------------------------


def _testuale(foglio):
    """Nessun valore diventa una formula all'apertura del file."""
    for riga in foglio.iter_rows():
        for cella in riga:
            if isinstance(cella.value, str) and cella.value[:1] in ("=", "+", "-", "@"):
                cella.data_type = "s"


def esporta(lista, utente):
    """Lista in .xlsx: impostazioni, persone scelte, destinatari attuali, istruzioni."""
    from openpyxl import Workbook
    from openpyxl.styles import Font

    from .servizi import soggetti_lista

    wb = Workbook()
    ws = wb.active
    ws.title = FOGLIO_LISTA
    valori = {
        "codice": lista.pk,
        "nome": lista.nome,
        "descrizione": lista.descrizione,
        "soci_attivi": "sì" if lista.soci_attivi else "no",
        "soci_in_regola": "sì" if lista.soci_in_regola else "no",
        "organo": str(lista.organo) if lista.organo_id else "",
        "categorie": "; ".join(c.nome for c in lista.categorie.order_by("nome")),
    }
    ws.append(["Impostazione", "Valore"])
    for chiave, etichetta in CAMPI_LISTA:
        ws.append([etichetta, valori[chiave]])
    ws.column_dimensions["A"].width = 38
    ws.column_dimensions["B"].width = 60

    wp = wb.create_sheet(FOGLIO_PERSONE)
    wp.append(COLONNE_PERSONE)
    for s in lista.soggetti.order_by("cognome", "denominazione", "nome"):
        persona = s.tipo == Soggetto.Tipo.PERSONA
        wp.append([
            s.pk, "persona" if persona else "ente", s.cognome if persona else s.denominazione,
            s.nome if persona else "", s.codice_fiscale or "", s.email,
        ])  # fmt: skip
    for lettera, larghezza in zip("ABCDEF", (10, 10, 30, 22, 20, 32), strict=True):
        wp.column_dimensions[lettera].width = larghezza

    wd = wb.create_sheet(FOGLIO_DESTINATARI)
    wd.append([f"Destinatari al {timezone.localdate():%d/%m/%Y} (solo consultazione)"])
    wd.append(["Nome", "Email"])
    for s in soggetti_lista(lista).order_by("cognome", "denominazione", "nome"):
        wd.append([s.nome_completo, s.email or "senza email"])
    wd.column_dimensions["A"].width = 40
    wd.column_dimensions["B"].width = 36

    wi = wb.create_sheet(FOGLIO_ISTRUZIONI)
    for riga in ISTRUZIONI:
        wi.append([riga])
    wi.column_dimensions["A"].width = 110

    for foglio in (ws, wp, wd):
        riga_titoli = 2 if foglio is wd else 1
        for cella in foglio[riga_titoli]:
            cella.font = Font(bold=True)
        _testuale(foglio)
    wi["A1"].font = Font(bold=True)

    buffer = io.BytesIO()
    wb.save(buffer)
    registra(Azione.ESPORTAZIONE, lista, utente=utente, formato="xlsx")
    return buffer.getvalue()


# --- importazione --------------------------------------------------------------------------


@dataclass
class Riga:
    numero: int
    descrizione: str
    esito: str  # "abbinata", "nuova", "non_trovata", "ambigua", "scartata"
    dettaglio: str = ""
    soggetto: Soggetto | None = None
    dati: dict = field(default_factory=dict)


@dataclass
class Piano:
    lista: Lista | None
    nome: str
    descrizione: str
    soci_attivi: bool
    soci_in_regola: bool
    organo: object
    categorie: list
    righe: list
    avvisi: list
    aggiunte: list = field(default_factory=list)
    tolte: list = field(default_factory=list)

    @property
    def nuova(self):
        return self.lista is None

    def conta(self, esito):
        return sum(1 for r in self.righe if r.esito == esito)

    def riepilogo(self):
        return {
            e: self.conta(e) for e in ("abbinata", "nuova", "non_trovata", "ambigua", "scartata")
        }


def _testo(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip()


def _si_no(v, etichetta, avvisi):
    t = _testo(v).lower()
    if t in SI:
        return True
    if t not in NO:
        avvisi.append(f"«{etichetta}»: valore «{_testo(v)}» non riconosciuto, considerato «no».")
    return False


def _norma(testo):
    return " ".join(testo.casefold().split())


def leggi(contenuto):
    """Fogli del file come dizionario {nome: righe}, solo valori (mai formule)."""
    from openpyxl import load_workbook

    try:
        wb = load_workbook(io.BytesIO(contenuto), read_only=True, data_only=True)
    except Exception:  # file corrotto o non xlsx: il messaggio per l'utente basta
        raise FileNonValido("Il file non è un foglio Excel .xlsx leggibile.") from None
    try:
        fogli = {f.title: [list(r) for r in f.iter_rows(values_only=True)] for f in wb.worksheets}
    finally:
        wb.close()
    if FOGLIO_LISTA not in fogli or FOGLIO_PERSONE not in fogli:
        raise FileNonValido(
            "Il file non è una lista esportata dal gestionale: mancano i fogli "
            f"«{FOGLIO_LISTA}» e «{FOGLIO_PERSONE}»."
        )
    return fogli


def _impostazioni(righe):
    per_etichetta = {_norma(e): k for k, e in CAMPI_LISTA}
    valori = {}
    for riga in righe[1:]:
        if not riga or riga[0] is None:
            continue
        chiave = per_etichetta.get(_norma(_testo(riga[0])))
        if chiave:
            valori[chiave] = riga[1] if len(riga) > 1 else None
    return valori


def _trova(codice, cf, email):
    """(soggetto, motivo): per codice, poi codice fiscale, poi email (solo se univoca)."""
    if codice:
        if not codice.isdigit():
            return None, f"codice «{codice}» non valido"
        s = Soggetto.objects.filter(pk=int(codice)).first()
        if s:
            return s, ""
        return None, f"nessuna scheda con codice {codice}"
    if cf:
        s = Soggetto.objects.filter(codice_fiscale__iexact=cf).first()
        if s:
            return s, ""
    if email:
        trovati = list(Soggetto.objects.filter(email__iexact=email)[:2])
        if len(trovati) == 1:
            return trovati[0], ""
        if len(trovati) > 1:
            return None, f"più schede con l'email {email}"
    return None, ""


def _scheda_nuova(tipo, cognome, nome, cf, email):
    """Scheda da creare con i soli dati del file; errori di validazione come testo."""
    tipo = _norma(tipo) or "persona"
    if tipo not in ("persona", "ente"):
        return None, f"tipo «{tipo}» non riconosciuto (persona o ente)"
    if tipo == "persona":
        s = Soggetto(tipo=tipo, cognome=cognome, nome=nome, codice_fiscale=cf or None, email=email)
    else:
        s = Soggetto(tipo=tipo, denominazione=cognome, codice_fiscale=cf or None, email=email)
    try:
        s.full_clean()
    except ValidationError as e:
        return None, "; ".join(f"{m}" for m in e.messages)
    return s, ""


def prepara(fogli, *, crea_schede=False):
    """Confronto fra il file e il gestionale. Non salva nulla."""
    from apps.organi.models import Organo

    avvisi = []
    v = _impostazioni(fogli[FOGLIO_LISTA])
    nome = _testo(v.get("nome"))
    if not nome:
        raise FileNonValido("Nel foglio «Lista» manca il nome della lista.")
    if len(nome) > Lista._meta.get_field("nome").max_length:
        raise FileNonValido("Il nome della lista è troppo lungo (al massimo 100 caratteri).")
    descrizione = _testo(v.get("descrizione"))[:255]

    lista = None
    codice = _testo(v.get("codice"))
    if codice:
        lista = Lista.objects.filter(pk=int(codice)).first() if codice.isdigit() else None
        if lista is None:
            avvisi.append(
                f"La lista con codice {codice} non esiste più: ne verrà creata una nuova."
            )
    if lista is None:
        lista = Lista.objects.filter(nome__iexact=nome).first()
    altra = Lista.objects.filter(nome__iexact=nome).exclude(pk=getattr(lista, "pk", None)).first()
    if altra:
        raise FileNonValido(f"Esiste già un'altra lista chiamata «{altra.nome}».")

    organo = None
    testo_organo = _testo(v.get("organo"))
    if testo_organo:
        organi = {_norma(str(o)): o for o in Organo.objects.select_related("sezione")}
        organo = organi.get(_norma(testo_organo))
        if organo is None:
            avvisi.append(f"Organo «{testo_organo}» non trovato: la lista non avrà un organo.")

    categorie = []
    per_nome = {_norma(c.nome): c for c in Categoria.objects.all()}
    for parte in _testo(v.get("categorie")).replace(",", ";").split(";"):
        if not parte.strip():
            continue
        c = per_nome.get(_norma(parte))
        if c is None:
            avvisi.append(f"Categoria «{parte.strip()}» non trovata: ignorata.")
        elif c not in categorie:
            categorie.append(c)

    righe, visti = [], set()
    for numero, riga in enumerate(fogli[FOGLIO_PERSONE][1:], start=2):
        riga = (list(riga) + [None] * 6)[:6]
        cod, tipo, cognome, nome_p, cf, email = (_testo(c) for c in riga)
        cf, email = cf.upper(), email.lower()
        if not any((cod, cognome, nome_p, cf, email)):
            continue
        etichetta = " ".join(p for p in (cognome, nome_p) if p) or email or cf or f"codice {cod}"
        s, motivo = _trova(cod, cf, email)
        if s is not None:
            if s.pk in visti:
                continue
            visti.add(s.pk)
            righe.append(Riga(numero, s.nome_completo, "abbinata", soggetto=s))
        elif motivo.startswith("più schede"):
            righe.append(Riga(numero, etichetta, "ambigua", motivo))
        elif cod:
            righe.append(Riga(numero, etichetta, "scartata", motivo))
        elif not crea_schede:
            righe.append(Riga(numero, etichetta, "non_trovata", "non presente in anagrafica"))
        else:
            nuova, errore = _scheda_nuova(tipo, cognome, nome_p, cf, email)
            if nuova is None:
                righe.append(Riga(numero, etichetta, "scartata", errore))
            else:
                chiave = cf or email or _norma(etichetta)
                if chiave in visti:
                    continue
                visti.add(chiave)
                righe.append(Riga(numero, etichetta, "nuova", "scheda da creare in anagrafica",
                                  dati={"tipo": nuova.tipo, "cognome": cognome, "nome": nome_p,
                                        "cf": cf, "email": email}))  # fmt: skip

    piano = Piano(
        lista=lista, nome=nome, descrizione=descrizione,
        soci_attivi=_si_no(v.get("soci_attivi"), "Tutti i soci attivi", avvisi),
        soci_in_regola=_si_no(v.get("soci_in_regola"), "Solo i soci in regola", avvisi),
        organo=organo, categorie=categorie, righe=righe, avvisi=avvisi,
    )  # fmt: skip
    nuovi = {r.soggetto.pk for r in righe if r.soggetto}
    attuali = set(lista.soggetti.values_list("pk", flat=True)) if lista else set()
    piano.aggiunte = [
        r for r in righe if r.esito == "nuova" or (r.soggetto and r.soggetto.pk not in attuali)
    ]
    piano.tolte = list(
        Soggetto.objects.filter(pk__in=attuali - nuovi).order_by("cognome", "denominazione", "nome")
    )
    return piano


@transaction.atomic
def applica(piano, utente):
    """Salva la lista come descritta dal piano; crea le schede nuove richieste."""
    lista = piano.lista or Lista()
    nuova = lista.pk is None
    prima = {} if nuova else {
        "soggetti": sorted(lista.soggetti.values_list("pk", flat=True)),
        "categorie": sorted(lista.categorie.values_list("pk", flat=True)),
    }  # fmt: skip
    lista.nome = piano.nome
    lista.descrizione = piano.descrizione
    lista.soci_attivi = piano.soci_attivi
    lista.soci_in_regola = piano.soci_in_regola
    lista.organo = piano.organo
    lista.full_clean()
    lista.save()

    soggetti = [r.soggetto for r in piano.righe if r.esito == "abbinata"]
    creati = 0
    for r in piano.righe:
        if r.esito != "nuova":
            continue
        d = r.dati
        s, errore = _scheda_nuova(d["tipo"], d["cognome"], d["nome"], d["cf"], d["email"])
        if s is None:
            raise ValidationError(f"Riga {r.numero}: {errore}")
        s.save()
        registra(Azione.CREAZIONE, s, utente=utente, origine="importazione lista", lista=lista.pk)
        soggetti.append(s)
        creati += 1
    lista.soggetti.set(soggetti)
    lista.categorie.set(piano.categorie)

    dettagli = {"origine": "importazione da Excel", "schede_create": creati,
                "persone": len(soggetti)}  # fmt: skip
    if prima:
        dettagli["prima"] = prima
    registra(Azione.CREAZIONE if nuova else Azione.MODIFICA, lista, utente=utente, **dettagli)
    return lista, creati
