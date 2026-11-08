# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Importazione dal Protocollo ANCR (PostgreSQL): rubrica in anagrafica, liste di
# *              distribuzione, registrazioni con il numero originale, annullamenti e documenti.
# *              Un anno si importa solo se qui non ha ancora registrazioni proprie.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import json
import re
from datetime import datetime
from pathlib import Path

import psycopg
from django.core.exceptions import ValidationError
from django.core.files import File
from django.db import transaction
from django.utils import timezone
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row

from apps.accounts.models import Utente
from apps.anagrafica.models import Soggetto
from apps.comunicazioni.models import Lista
from apps.core.audit import Azione, registra
from apps.protocollo import servizi as protocollo_servizi
from apps.protocollo.models import Corrispondente, Protocollo

from .comune import FonteNonValida, Rapporto, importato, segna, testo
from .models import Origine

FONTE = Origine.Fonte.PROTOCOLLO
NOME = "Protocollo ANCR"
TABELLE = ("protocolli", "contatti", "users")
MEZZI = {
    "email": Protocollo.Mezzo.EMAIL,
    "messaggistica": Protocollo.Mezzo.MESSAGGISTICA,
    "cartaceo": Protocollo.Mezzo.POSTA,
}
_RE_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")


# --- lettura della fonte ----------------------------------------------------------------


def dsn_da_env(percorso):
    """Connessione dal file .env del Protocollo ANCR (DB_HOST, DB_PORT, DB_NAME, ...)."""
    valori = {}
    for riga in Path(percorso).read_text().splitlines():
        riga = riga.strip()
        if riga and not riga.startswith("#") and "=" in riga:
            chiave, valore = riga.split("=", 1)
            valori[chiave.strip()] = valore.strip().strip("'\"")
    if "DB_NAME" not in valori:
        raise FonteNonValida(f"{percorso}: DB_NAME mancante.")
    return make_conninfo(
        host=valori.get("DB_HOST", "localhost"), port=valori.get("DB_PORT", "5432"),
        dbname=valori["DB_NAME"], user=valori.get("DB_USER", ""),
        password=valori.get("DB_PASSWORD", ""),
    )  # fmt: skip


class Fonte:
    """Lettura in sola lettura del database del Protocollo ANCR."""

    def __init__(self, dsn):
        try:
            self.conn = psycopg.connect(dsn, row_factory=dict_row, autocommit=True)
        except psycopg.Error as e:
            raise FonteNonValida(f"Connessione al Protocollo ANCR non riuscita: {e}") from e
        self.conn.execute("set session characteristics as transaction read only")
        self.tabelle = {
            r["table_name"]
            for r in self.conn.execute(
                "select table_name from information_schema.tables "
                "where table_schema = any(current_schemas(false))"
            )
        }
        mancanti = set(TABELLE) - self.tabelle
        if mancanti:
            self.close()
            raise FonteNonValida(
                "Il database non sembra quello del Protocollo ANCR: mancano "
                + ", ".join(sorted(mancanti))
            )

    def righe(self, tabella, ordine="id"):
        if tabella not in self.tabelle:
            return []
        return list(self.conn.execute(f'select * from "{tabella}" order by {ordine}'))  # noqa: S608

    def conta(self, tabella):
        if tabella not in self.tabelle:
            return 0
        return self.conn.execute(f'select count(*) as n from "{tabella}"').fetchone()["n"]  # noqa: S608

    def close(self):
        self.conn.close()


# --- rubrica ----------------------------------------------------------------------------


def _unico(qs):
    trovati = list(qs[:2])
    return trovati[0] if len(trovati) == 1 else None


def _soggetto_da_contatto(r):
    email = testo(r.get("email")).lower()
    if email:
        s = _unico(Soggetto.objects.filter(email__iexact=email))
        if s:
            return s
    if r.get("tipo") == "organizzazione" or (
        not testo(r.get("cognome")) and r.get("organizzazione")
    ):
        nome = testo(r.get("organizzazione")) or testo(r.get("nome"))
        return _unico(Soggetto.objects.filter(tipo=Soggetto.Tipo.ENTE, denominazione__iexact=nome))
    return _unico(
        Soggetto.objects.filter(
            tipo=Soggetto.Tipo.PERSONA,
            cognome__iexact=testo(r.get("cognome")),
            nome__iexact=testo(r.get("nome")),
        )
    )


def _contatti(fonte, utente, rapporto):
    mappa = {}
    for r in fonte.righe("contatti"):
        ente = r.get("tipo") == "organizzazione" or not testo(r.get("cognome"))
        nome = (
            testo(r.get("organizzazione")) if ente else f"{testo(r['cognome'])} {testo(r['nome'])}"
        )
        nome = nome.strip() or testo(r.get("nome")) or testo(r.get("email")) or "(senza nome)"
        gia = importato(FONTE, "contatti", r["id"], Soggetto)
        if gia:
            mappa[r["id"]] = gia
            rapporto.aggiungi("Rubrica", "invariato", nome, ["già importato"])
            continue
        dati = {
            "email": testo(r.get("email")).lower(), "telefono": testo(r.get("telefono"))[:30],
            "indirizzo": testo(r.get("indirizzo")), "comune": testo(r.get("citta")),
            "cap": testo(r.get("cap"))[:5], "provincia": testo(r.get("provincia")).upper()[:2],
        }  # fmt: skip
        try:
            with transaction.atomic():
                s = _soggetto_da_contatto(r)
                if s is None:
                    campi = {k: v for k, v in dati.items() if v}
                    if ente:
                        s = Soggetto.objects.create(
                            tipo=Soggetto.Tipo.ENTE, denominazione=nome[:200],
                            note=testo(r.get("note")), creato_da=utente, modificato_da=utente,
                            **campi,
                        )  # fmt: skip
                    else:
                        s = Soggetto.objects.create(
                            tipo=Soggetto.Tipo.PERSONA, cognome=testo(r["cognome"]),
                            nome=testo(r.get("nome")), note=testo(r.get("note")),
                            creato_da=utente, modificato_da=utente, **campi,
                        )  # fmt: skip
                    registra(Azione.CREAZIONE, s, utente=utente, origine=NOME)
                    stato, note = "nuovo", []
                else:
                    completati = [k for k, v in dati.items() if v and not getattr(s, k)]
                    for k in completati:
                        setattr(s, k, dati[k])
                    if completati:
                        s.modificato_da = utente
                        s.save()
                        registra(Azione.MODIFICA, s, utente=utente, completati=completati,
                                 origine=NOME)  # fmt: skip
                    stato = "aggiornato" if completati else "invariato"
                    note = [f"abbinato a {s.nome_completo}"] + (
                        ["completati: " + ", ".join(completati)] if completati else []
                    )
                segna(FONTE, "contatti", r["id"], s)
            mappa[r["id"]] = s
            rapporto.aggiungi("Rubrica", stato, nome, note)
        except ValidationError as e:
            rapporto.aggiungi("Rubrica", "errore", nome, e.messages)
    return mappa


def _liste(fonte, mappa, rapporto):
    membri = {}
    for m in fonte.righe("lista_distribuzione_contatti", ordine="1"):
        lista_id = m.get("lista_distribuzione_id") or m.get("ListaDistribuzioneId")
        contatto_id = m.get("contatto_id") or m.get("ContattoId")
        membri.setdefault(lista_id, []).append(contatto_id)
    for r in fonte.righe("liste_distribuzione"):
        nome = testo(r["nome"])[:100] or f"Lista {r['id']}"
        if importato(FONTE, "liste_distribuzione", r["id"], Lista):
            rapporto.aggiungi("Liste", "invariato", nome, ["già importata"])
            continue
        lista, creata = Lista.objects.get_or_create(
            nome=nome, defaults={"descrizione": testo(r.get("descrizione"))[:255]}
        )
        soggetti = [mappa[c] for c in membri.get(r["id"], []) if c in mappa]
        lista.soggetti.add(*soggetti)
        segna(FONTE, "liste_distribuzione", r["id"], lista)
        rapporto.aggiungi(
            "Liste", "nuovo" if creata else "aggiornato", nome, [f"{len(soggetti)} componenti"]
        )


# --- registrazioni ----------------------------------------------------------------------


def _numero(r):
    """«2025-00042» -> (2025, 42); in mancanza l'anno della data di protocollo."""
    testo_numero = testo(r["numero_protocollo"])
    if m := re.fullmatch(r"(\d{4})\D+0*(\d+)", testo_numero):
        return int(m.group(1)), int(m.group(2))
    if testo_numero.isdigit():
        return _data_ora(r["data_protocollo"]).year, int(testo_numero)
    raise ValidationError(f"numero di protocollo «{testo_numero}» non riconosciuto")


def _data_ora(valore):
    if isinstance(valore, datetime):
        return valore if timezone.is_aware(valore) else timezone.make_aware(valore)
    return timezone.make_aware(datetime.fromisoformat(str(valore)))


def _corrispondenti(r):
    """Testi del vecchio protocollo -> corrispondenti; collega l'anagrafica per email esatta."""
    elenco = []
    ruoli = [(Corrispondente.Ruolo.MITTENTE, r.get("mittente"), "")]
    destinatari = [d.strip() for d in re.split(r"[;\n]", testo(r.get("destinatario"))) if d.strip()]
    email_dest = [e.strip() for e in re.split(r"[;,\s]+", testo(r.get("email_destinatario"))) if e]
    if not destinatari and email_dest:
        destinatari = email_dest
    for i, d in enumerate(destinatari):
        indirizzo = email_dest[i] if i < len(email_dest) else ""
        ruoli.append((Corrispondente.Ruolo.DESTINATARIO, d, indirizzo))
    for ruolo, descrizione, indirizzo in ruoli:
        descrizione = testo(descrizione)
        if not descrizione:
            continue
        email = indirizzo or (m.group(0) if (m := _RE_EMAIL.search(descrizione)) else "")
        soggetto = _unico(Soggetto.objects.filter(email__iexact=email)) if email else None
        elenco.append({"ruolo": ruolo, "descrizione": descrizione, "indirizzo": indirizzo,
                       "soggetto": soggetto})  # fmt: skip
    if r["tipo"] == "uscita" and not any(c["ruolo"] == "destinatario" for c in elenco):
        elenco.append({"ruolo": Corrispondente.Ruolo.DESTINATARIO, "descrizione": "(non indicato)"})
    return elenco


def _allegati(valore):
    if not valore:
        return []
    if isinstance(valore, str):
        try:
            valore = json.loads(valore)
        except ValueError:
            return []
    return [a for a in valore if isinstance(a, dict)] if isinstance(valore, list) else []


def _file_allegato(a, cartella):
    nome = a.get("filename") or a.get("nome_file") or a.get("nome") or ""
    percorso = testo(a.get("path") or a.get("percorso"))
    candidati = []
    if percorso.startswith("/uploads/"):
        candidati.append(cartella / percorso.removeprefix("/uploads/"))
    if percorso:
        candidati.append(cartella / Path(percorso).name)
    if nome:
        candidati += [cartella / nome, cartella / "emails" / nome]
    base = cartella.resolve()
    for c in candidati:
        c = c.resolve()
        if c.is_file() and c.is_relative_to(base):  # mai fuori dalla cartella indicata
            return c
    return None


def _protocolli(fonte, cartella, utente, rapporto):
    utenti = {u["id"]: u for u in fonte.righe("users")}
    locali = {u.email.lower(): u for u in Utente.objects.exclude(email="")}
    registrazioni = fonte.righe("protocolli", ordine="data_protocollo, id")
    occupati = anni_occupati()
    rifiutati = set()
    for r in registrazioni:
        descrizione = f"{testo(r['numero_protocollo'])} {testo(r['oggetto'])[:60]}"
        if importato(FONTE, "protocolli", r["id"], Protocollo):
            rapporto.aggiungi("Protocolli", "invariato", descrizione, ["già importato"])
            continue
        try:
            anno, numero = _numero(r)
        except ValidationError as e:
            rapporto.aggiungi("Protocolli", "errore", descrizione, e.messages)
            continue
        if anno in occupati:
            rifiutati.add(anno)
            rapporto.aggiungi("Protocolli", "saltato", descrizione)
            continue
        operatore = utenti.get(r.get("user_id"), {})
        autore = locali.get(testo(operatore.get("email")).lower()) or utente
        note = testo(r.get("note"))
        firma = f"Importato dal {NOME}" + (
            f" (registrato da {operatore['username']})" if operatore.get("username") else ""
        )
        annullato = testo(r.get("status")) == "annullato"
        try:
            with transaction.atomic():
                p = protocollo_servizi.registra_storico(
                    {
                        "direzione": r["tipo"],
                        "mezzo": MEZZI.get(testo(r.get("canale")), Protocollo.Mezzo.ALTRO),
                        "oggetto": testo(r["oggetto"])[:500] or "(senza oggetto)",
                        "note": f"{note}\n\n{firma}".strip(),
                    },
                    anno=anno, numero=numero, registrato_il=_data_ora(r["data_protocollo"]),
                    corrispondenti=_corrispondenti(r), utente=autore, annullato=annullato,
                    motivo_annullamento=testo(r.get("note_annullamento"))
                    or f"Annullato nel {NOME}",
                )  # fmt: skip
                note_esito, mancanti = [], 0
                for i, a in enumerate(_allegati(r.get("allegati"))):
                    percorso = _file_allegato(a, cartella) if cartella else None
                    if percorso is None:
                        mancanti += 1
                        continue
                    with percorso.open("rb") as f:
                        protocollo_servizi.aggiungi_allegato(
                            p, File(f), autore, principale=(i == 0), controlla=False,
                            nome=a.get("originalname") or a.get("nome_originale") or percorso.name,
                        )  # fmt: skip
                if mancanti:
                    note_esito.append(f"{mancanti} documenti non trovati")
                if annullato:
                    note_esito.append("annullato")
                segna(FONTE, "protocolli", r["id"], p)
            rapporto.aggiungi("Protocolli", "nuovo", descrizione, note_esito)
        except ValidationError as e:
            rapporto.aggiungi("Protocolli", "errore", descrizione, e.messages)
    for anno in sorted(rifiutati):
        rapporto.avvisi.append(
            f"Anno {anno}: non importato perché qui ci sono già registrazioni di quell'anno "
            "(la numerazione si sovrapporrebbe)."
        )
    if not cartella and any(_allegati(r.get("allegati")) for r in registrazioni):
        rapporto.avvisi.append("Documenti non importati: indicare la cartella con --allegati.")


def anni_occupati():
    """Anni con registrazioni fatte in questa applicazione (non importate)."""
    importati = Origine.objects.filter(fonte=FONTE, tabella="protocolli").values_list(
        "oggetto_id", flat=True
    )
    return set(
        Protocollo.objects.exclude(pk__in=[int(i) for i in importati])
        .values_list("anno", flat=True)
        .distinct()
    )


# --- ingresso ---------------------------------------------------------------------------


def importa(dsn, utente, *, cartella_allegati=None, esegui=False):
    fonte = Fonte(dsn)
    cartella = Path(cartella_allegati) if cartella_allegati else None
    if cartella and not cartella.is_dir():
        fonte.close()
        raise FonteNonValida(f"Cartella dei documenti {cartella} inesistente.")
    rapporto = Rapporto(NOME, eseguito=esegui)
    try:
        with transaction.atomic():
            mappa = _contatti(fonte, utente, rapporto)
            _liste(fonte, mappa, rapporto)
            _protocolli(fonte, cartella, utente, rapporto)
            for tabella in ("registri_giornalieri", "email_received", "email_logs"):
                if n := fonte.conta(tabella):
                    rapporto.avvisi.append(
                        f"{tabella}: {n} righe non importate (i registri giornalieri si "
                        "rigenerano qui; la posta resta nella casella)."
                    )
            if esegui:
                registra(
                    Azione.CREAZIONE, utente=utente, descrizione=f"Importazione dal {NOME}",
                    **rapporto.conteggi(),
                )  # fmt: skip
            else:
                transaction.set_rollback(True)
    finally:
        fonte.close()
    return rapporto
