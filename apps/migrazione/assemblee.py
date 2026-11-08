# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Importazione da Gestione Assemblee (SQLite): rubrica dei contatti in anagrafica
# *              (prevalgono i dati locali, si completano i vuoti) e modelli email con i
# *              segnaposto convertiti. Assemblee, verbali e comunicazioni sono solo contati.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import re

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.anagrafica.models import Soggetto
from apps.anagrafica.validatori import valida_codice_fiscale
from apps.comunicazioni.models import Modello
from apps.comunicazioni.servizi import SEGNAPOSTO
from apps.core.audit import Azione, registra
from apps.soci import importazione as reg

from .comune import Rapporto, apri_sqlite, importato, righe, segna, testo
from .models import Origine

FONTE = Origine.Fonte.ASSEMBLEE
TABELLE = ("contatti", "template_email")
NOME = "Gestione Assemblee"

CAMPI = {  # colonna di origine -> campo dell'anagrafica
    "email": "email", "telefono": "telefono", "cellulare": "cellulare",
    "indirizzo": "indirizzo", "citta": "comune", "cap": "cap", "provincia": "provincia",
    "luogo_nascita": "luogo_nascita", "professione": "qualifica",
}  # fmt: skip
SEGNAPOSTO_EQUIVALENTI = {"festivita": "ricorrenza", "nome_evento": "riunione"}
_RE_VECCHIO = re.compile(r"\{([a-z_]+)\}")


def converti_segnaposto(testo_modello):
    """«{nome}» -> «{{ nome }}»; i segnaposto senza equivalente restano «[nome]» da correggere."""
    sconosciuti = set()

    def sostituisci(m):
        chiave = SEGNAPOSTO_EQUIVALENTI.get(m.group(1), m.group(1))
        if chiave in SEGNAPOSTO:
            return "{{ " + chiave + " }}"
        sconosciuti.add(m.group(1))
        return f"[{m.group(1)}]"

    return _RE_VECCHIO.sub(sostituisci, testo_modello), sconosciuti


def _trova(d):
    if d["codice_fiscale"]:
        s = Soggetto.objects.filter(codice_fiscale__iexact=d["codice_fiscale"]).first()
        if s:
            return s
    if d["email"]:
        trovati = list(Soggetto.objects.filter(email__iexact=d["email"])[:2])
        if len(trovati) == 1:
            return trovati[0]
    if d["data_nascita"] and d["cognome"]:
        trovati = list(
            Soggetto.objects.filter(
                cognome__iexact=d["cognome"], nome__iexact=d["nome"], data_nascita=d["data_nascita"]
            )[:2]
        )
        if len(trovati) == 1:
            return trovati[0]
        # nome scritto diversamente nei due archivi: stesso cognome e data di nascita, se unico
        trovati = list(
            Soggetto.objects.filter(cognome__iexact=d["cognome"], data_nascita=d["data_nascita"])[
                :2
            ]
        )
        if len(trovati) == 1:
            d["_abbinato"] = f"abbinato a {trovati[0].nome_completo} per cognome e data di nascita"
            return trovati[0]
    return None


def _contatto(r, utente):
    d = {
        "cognome": reg._nome_proprio(testo(r["cognome"])),
        "nome": reg._nome_proprio(testo(r["nome"])),
        "codice_fiscale": testo(r["codice_fiscale"]).replace(" ", "").upper(),
        "data_nascita": reg._data(r["data_nascita"]) if r["data_nascita"] else None,
    }
    for origine, campo in CAMPI.items():
        d[campo] = testo(r.get(origine))
    d["telefono"], d["cellulare"] = reg._telefoni(r.get("telefono"), r.get("cellulare"))
    d["email"] = d["email"].lower()
    d["provincia"] = d["provincia"].upper()[:2]
    for campo in ("comune", "luogo_nascita", "indirizzo"):
        d[campo] = reg._nome_proprio(d[campo], luogo=True) if d[campo] else ""
    note = []
    if d["codice_fiscale"]:
        try:
            valida_codice_fiscale(d["codice_fiscale"])
        except ValidationError:
            note.append(f"codice fiscale {d['codice_fiscale']} non valido: non riportato")
            d["codice_fiscale"] = ""
    soggetto = _trova(d)
    if d.get("_abbinato"):
        note.append(d["_abbinato"])
        if d["codice_fiscale"]:
            note.append(f"codice fiscale {d['codice_fiscale']} non riportato (diverso)")
            d["codice_fiscale"] = ""
    if soggetto is None:
        if not d["cognome"]:
            return "errore", ["cognome mancante"], None
        soggetto = Soggetto.objects.create(
            tipo=Soggetto.Tipo.PERSONA, cognome=d["cognome"], nome=d["nome"],
            codice_fiscale=d["codice_fiscale"] or None, data_nascita=d["data_nascita"],
            note=testo(r.get("note")), creato_da=utente, modificato_da=utente,
            **{c: d[c] for c in CAMPI.values() if d[c]},
        )  # fmt: skip
        registra(Azione.CREAZIONE, soggetto, utente=utente, origine=NOME)
        return "nuovo", note, soggetto
    completati = [c for c in CAMPI.values() if d[c] and not getattr(soggetto, c)]
    if d["data_nascita"] and not soggetto.data_nascita:
        completati.append("data_nascita")
    if d["codice_fiscale"] and not soggetto.codice_fiscale:
        completati.append("codice_fiscale")
    if not completati:
        return "invariato", note, soggetto
    for c in completati:
        setattr(soggetto, c, d[c])
    soggetto.modificato_da = utente
    soggetto.save()
    registra(Azione.MODIFICA, soggetto, utente=utente, completati=completati, origine=NOME)
    return "aggiornato", [*note, "completati: " + ", ".join(completati)], soggetto


def _modelli(conn, utente, rapporto):
    for r in righe(conn, "template_email"):
        nome = f"{testo(r['nome'])} (da {NOME})"[:100]
        if (
            importato(FONTE, "template_email", r["id"], Modello)
            or Modello.objects.filter(nome=nome).exists()
        ):
            rapporto.aggiungi("Modelli email", "invariato", nome, ["già importato"])
            continue
        oggetto, ignoti_o = converti_segnaposto(testo(r["oggetto"]))
        corpo, ignoti_c = converti_segnaposto(testo(r["corpo"]))
        m = Modello.objects.create(nome=nome, oggetto=oggetto[:200], corpo=corpo, attivo=False)
        segna(FONTE, "template_email", r["id"], m)
        registra(Azione.CREAZIONE, m, utente=utente, origine=NOME)
        ignoti = sorted(ignoti_o | ignoti_c)
        note = ["disattivato: da rivedere prima dell'uso"]
        if ignoti:
            note.append("segnaposto da correggere: " + ", ".join(f"[{s}]" for s in ignoti))
        rapporto.aggiungi("Modelli email", "nuovo", nome, note)


def importa(percorso, utente, *, esegui=False):
    conn = apri_sqlite(percorso, TABELLE)
    rapporto = Rapporto(NOME, eseguito=esegui)
    try:
        with transaction.atomic():
            for r in righe(conn, "contatti"):
                nome = f"{testo(r['cognome'])} {testo(r['nome'])}".strip() or "(senza nome)"
                if importato(FONTE, "contatti", r["id"], Soggetto):
                    rapporto.aggiungi("Contatti", "invariato", nome, ["già importato"])
                    continue
                try:
                    with transaction.atomic():
                        stato, note, soggetto = _contatto(r, utente)
                        if soggetto:
                            segna(FONTE, "contatti", r["id"], soggetto)
                except ValidationError as e:
                    stato, note = "errore", e.messages
                rapporto.aggiungi("Contatti", stato, nome, note)
            _modelli(conn, utente, rapporto)
            tabelle = {
                t[0] for t in conn.execute("select name from sqlite_master where type='table'")
            }
            for tabella in ("assemblee", "verbali", "comunicazioni"):
                if tabella in tabelle:
                    n = conn.execute(f"select count(*) from {tabella}").fetchone()[0]  # noqa: S608
                    if n:
                        rapporto.avvisi.append(
                            f"{tabella}: {n} righe non importate (riportare negli Organi sociali "
                            "o nel Protocollo quelle ancora utili)."
                        )
            if esegui:
                registra(
                    Azione.CREAZIONE, utente=utente, descrizione=f"Importazione da {NOME}",
                    **rapporto.conteggi(),
                )  # fmt: skip
            else:
                transaction.set_rollback(True)
    finally:
        conn.close()
    return rapporto
