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


ORGANI = {"direttivo": "consiglio", "generale": "assemblea"}


def _organo(tipo):
    """L'organo dell'associazione corrispondente al tipo del vecchio gestionale."""
    from apps.organi.models import Organo

    voluto = ORGANI.get(testo(tipo).lower())
    qs = Organo.objects.filter(sezione__isnull=True, attivo=True)
    if voluto:
        return qs.filter(tipo=voluto).order_by("ordine", "pk").first()
    return qs.filter(nome__iexact=testo(tipo)).first()


def _momento(valore, giorno=None):
    from datetime import datetime, time

    from django.utils import timezone
    from django.utils.dateparse import parse_date, parse_datetime

    t = testo(valore)
    momento = parse_datetime(t.replace(" ", "T")) if t else None
    if momento is None and (d := parse_date(t[:10]) if t else giorno):
        momento = datetime.combine(d, time(18, 0))
    if momento is not None and timezone.is_naive(momento):
        momento = timezone.make_aware(momento)
    return momento


def _riunioni(conn, tabelle, utente, rapporto):
    """Assemblee e riunioni del direttivo con l'ordine del giorno; i verbali restano aperti, da
    rivedere e chiudere qui (la chiusura assegna il numero nel libro dei verbali)."""
    from apps.organi.models import PuntoOdg, Riunione, Verbale

    verbali = {}
    if "verbali" in tabelle:
        for v in righe(conn, "verbali"):
            verbali.setdefault(v["assemblea_id"], v)
    for r in righe(conn, "assemblee"):
        v = verbali.get(r["id"])
        momento = _momento(r["data_prima_conv"]) or _momento(v["data_riunione"] if v else None)
        titolo = (
            f"{testo(r['tipo']) or 'riunione'} del {momento:%d/%m/%Y}" if momento else "riunione"
        )
        if importato(FONTE, "assemblee", r["id"], Riunione):
            rapporto.aggiungi("Riunioni e verbali", "invariato", titolo, ["già importata"])
            continue
        organo = _organo(r["tipo"])
        if organo is None or momento is None:
            motivo = "organo corrispondente non trovato" if momento else "data mancante"
            rapporto.aggiungi("Riunioni e verbali", "errore", titolo, [motivo])
            continue
        annullata = testo(r["stato"]).lower() == "annullata"
        premessa = []
        if testo(r["numero_protocollo"]):
            premessa.append(f"Convocazione protocollata n. {testo(r['numero_protocollo'])} "
                            f"nel vecchio gestionale.")  # fmt: skip
        riunione = Riunione.objects.create(
            organo=organo, anno=momento.year, prima_convocazione=momento,
            luogo=(testo(r["luogo_prima_conv"]) or (testo(v["luogo_riunione"]) if v else ""))[:200]
            or "(non indicato)",
            seconda_convocazione=_momento(r["data_seconda_conv"]),
            luogo_seconda=testo(r["luogo_seconda_conv"])[:200],
            data_convocazione=_momento(r["data_convocazione"]).date()
            if _momento(r["data_convocazione"]) else None,
            premessa="\n".join(premessa),
            stato=Riunione.Stato.ANNULLATA if annullata else Riunione.Stato.CONVOCATA,
            motivo_annullamento="Annullata nel vecchio gestionale" if annullata else "",
            creato_da=utente, modificato_da=utente,
        )  # fmt: skip
        punti = [p.strip(" -•\t") for p in testo(r["punti_discussione"]).splitlines() if p.strip()]
        discussi = testo(v["punti_discussi"]) if v else ""
        for i, punto in enumerate(punti or ["Ordine del giorno non indicato"], 1):
            PuntoOdg.objects.create(riunione=riunione, ordine=i, titolo=punto[:500],
                                    discussione=discussi if i == 1 else "")  # fmt: skip
        note = [organo.nome, f"{len(punti)} punti all'ordine del giorno"]
        if v and not annullata:
            esiti = "\n\n".join(x for x in (
                f"Decisioni e votazioni:\n{testo(v['decisioni_votazioni'])}"
                if testo(v["decisioni_votazioni"]) else "",
                f"Provvedimenti:\n{testo(v['provvedimenti'])}" if testo(v["provvedimenti"]) else "",
                f"Verbale protocollato n. {testo(v['numero_protocollo'])} nel vecchio gestionale."
                if testo(v["numero_protocollo"]) else "",
            ) if x)  # fmt: skip
            Verbale.objects.create(
                riunione=riunione, luogo=testo(v["luogo_riunione"])[:200],
                inizio=_momento(v["data_riunione"]),
                presidente=testo(v["presidente_riunione"])[:150],
                segretario=testo(v["segretario_riunione"])[:150],
                apertura=f"Partecipanti: {v['num_partecipanti']}." if v["num_partecipanti"] else "",
                varie=esiti, creato_da=utente, modificato_da=utente,
            )  # fmt: skip
            note.append("verbale importato aperto: da rivedere e chiudere")
        segna(FONTE, "assemblee", r["id"], riunione)
        registra(Azione.CREAZIONE, riunione, utente=utente, origine=NOME)
        rapporto.aggiungi("Riunioni e verbali", "nuovo", titolo, note)


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
            colonne = {c[1] for c in conn.execute("pragma table_info(assemblee)")}
            if {"tipo", "data_prima_conv"} <= colonne:
                _riunioni(conn, tabelle, utente, rapporto)
            da_segnalare = ["comunicazioni"]
            if not {"tipo", "data_prima_conv"} <= colonne:  # struttura sconosciuta: si segnala
                da_segnalare = ["assemblee", "verbali", "comunicazioni"]
            for tabella in da_segnalare:
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
