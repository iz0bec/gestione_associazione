# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Importazione da Gestione Soci (SQLite): soci, tessere, cassa e beni.
# *              Per i soci già presenti prevalgono i dati locali (registro nazionale): si
# *              completano solo i campi vuoti. Gli anni contabili passati diventano esercizi
# *              chiusi. Senza `esegui` tutto avviene in una transazione poi annullata.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.core.audit import Azione, registra
from apps.core.numerazione import prossimo_numero
from apps.patrimonio.models import SEQ_INVENTARIO, Bene, CategoriaBene, Valutazione
from apps.soci import importazione as reg
from apps.soci import servizi as soci_servizi
from apps.soci.models import Sezione, Socio, TipologiaSocio
from apps.tesoreria import servizi as tesoreria
from apps.tesoreria.models import Conto, Esercizio, Movimento, Voce

from .comune import Rapporto, apri_sqlite, importato, righe, segna, testo
from .models import Origine

FONTE = Origine.Fonte.GESTIONE_SOCI
TABELLE = ("soci", "tessere", "movimenti", "anni_contabili")
NOME = "Gestione Soci"

# categoria del vecchio gestionale -> voce del rendiconto (entrate, uscite)
VOCI = {
    "quote_sociali": ("E.A.1", "U.A.1.2"),
    "donazioni": ("E.A.4.6", "U.A.5"),
    "contributi": ("E.A.8", "U.A.5"),
    "cancelleria": ("E.A.10", "U.E.1.4"),
    "posta": ("E.A.10", "U.E.2.3"),
    "banca": ("E.D.1", "U.D.1.5"),
    "cerimonie": ("E.A.10", "U.A.2.1"),
}
VOCI_ALTRO = ("E.A.10", "U.A.5")

ACQUISIZIONI = {
    "ACQUISTO": Bene.Acquisizione.ACQUISTO,
    "DONAZIONE": Bene.Acquisizione.DONAZIONE,
    "LASCITO": Bene.Acquisizione.LASCITO,
    "COMODATO": Bene.Acquisizione.COMODATO,
}
CONSERVAZIONI = {
    "OTTIMO": Bene.Conservazione.OTTIMO,
    "BUONO": Bene.Conservazione.BUONO,
    "DISCRETO": Bene.Conservazione.DISCRETO,
    "SUFFICIENTE": Bene.Conservazione.DISCRETO,
    "CATTIVO": Bene.Conservazione.CATTIVO,
    "SCADENTE": Bene.Conservazione.CATTIVO,
    "DA RESTAURARE": Bene.Conservazione.DA_RESTAURARE,
}

METODI = {"perizia": "perizia"}


@dataclass
class Opzioni:
    tipologia: TipologiaSocio
    sezione: Sezione | None = None  # per i soci senza sezione
    abbina: str = "comune"  # come riconoscere la sezione: comune, nome, codice
    conto: Conto | None = None  # conto della cassa importata (predefinito: quello dei contanti)
    crea_sezioni: bool = False
    tesoreria: bool = True
    beni: bool = True


def _importo(valore):
    try:
        return Decimal(str(valore or 0)).quantize(Decimal("0.01"))
    except InvalidOperation:
        return Decimal("0")


def _data(valore):
    return reg._data(valore) if valore else None


# --- soci -------------------------------------------------------------------------------


def _sezione_di(valore):
    """«BASILICATA / POTENZA MATERA / RUOTI» -> «RUOTI» (l'ultimo livello è il comune)."""
    return testo(valore).split("/")[-1].strip()


def _soci(conn, opzioni, utente, rapporto):
    mappa = {}
    opz = reg.Opzioni(
        sezione=opzioni.sezione, abbina=opzioni.abbina, tipologia=opzioni.tipologia,
        tessere=False, cessazioni=False, crea_sezioni=opzioni.crea_sezioni,
    )  # fmt: skip
    rapporto_reg = reg.Rapporto()
    cache = {}
    for r in righe(conn, "soci"):
        nome = f"{testo(r['cognome'])} {testo(r['nome'])}".strip()
        gia = importato(FONTE, "soci", r["id"], Socio)
        if gia:
            mappa[r["id"]] = gia
            rapporto.aggiungi("Soci", "invariato", nome, ["già importato"])
            continue
        grezza = {
            "_riga": r["id"], "cognome": r["cognome"], "nome": r["nome"],
            "codice_fiscale": r["codice_fiscale"], "sesso": r["sesso"],
            "data_nascita": r["data_nascita"], "luogo_nascita": r["luogo_nascita"],
            "indirizzo": r["indirizzo"], "comune": r["citta"], "cap": r["cap"],
            "telefono": r["telefono"], "email": r["email"],
            "data_iscrizione": date(int(r["anno_iscrizione"]), 1, 1)
            if r.get("anno_iscrizione") else None,
            "sezione": _sezione_di(r.get("sezione")),
        }  # fmt: skip
        d = reg._pulisci(grezza)
        try:
            sezione = reg._sezione(d, opz, cache, rapporto_reg)
            with transaction.atomic():
                stato, note, socio = reg._riga(d, sezione, opz, utente)
                segna(FONTE, "soci", r["id"], socio)
            mappa[r["id"]] = socio
            if r.get("foto"):
                note.append("foto nel vecchio gestionale: da ricaricare a mano")
            rapporto.aggiungi("Soci", stato, nome, note)
        except reg._Errore as e:
            rapporto.aggiungi("Soci", "errore", nome, [str(e)])
        except ValidationError as e:
            rapporto.aggiungi("Soci", "errore", nome, e.messages)
    for valore, esito in rapporto_reg.abbinamenti.items():
        stato = (
            "errore" if "non abbinata" in esito else "nuovo" if "(nuova)" in esito else "invariato"
        )
        rapporto.aggiungi("Sezioni", stato, f"{valore} → {esito}")
    return mappa


def _tessera(socio, codice, anno, rilascio, quota, utente):
    """Tesseramento dell'anno con la tessera fisica e la quota versata (incassata fuori)."""
    tessera = socio.tessere.valide().filter(anno=anno).first()
    if tessera and tessera.carta_id:
        if tessera.carta.codice != codice and str(tessera.carta.numero) != codice:
            return "invariato", [
                f"tessera locale {tessera.carta.codice}, nel vecchio gestionale {codice}"
            ]
        return "invariato", []
    if socio.stato != Socio.Stato.ATTIVO:
        return "saltato", [f"socio {socio.get_stato_display().lower()}"]
    try:
        with transaction.atomic():
            if codice.isdigit():
                soci_servizi.carta_da_registro(anno, socio.sezione, int(codice), utente)
            if tessera is None:
                tessera = soci_servizi.rilascia_tessera(
                    socio, anno, utente, importo=quota, data_rilascio=rilascio or date(anno, 1, 1)
                )
            tessera = soci_servizi.attribuisci_carta(tessera, utente, codice)
            soci_servizi.segna_incasso_esterno(
                tessera, utente, pagata_il=tessera.data_rilascio, nota=NOME
            )
    except ValidationError as e:
        return "errore", e.messages
    return "nuovo", [f"quota {quota} €"]


def _tessere(conn, mappa, utente, rapporto):
    senza_socio = 0
    for r in righe(conn, "tessere", "anno, id"):
        socio = mappa.get(r["socio_id"])
        numero = testo(r["numero"])
        codice = numero.lstrip("0") if numero.isdigit() else numero
        if socio is None:
            senza_socio += 1
            rapporto.aggiungi("Tessere", "saltato", f"{r['anno']} n. {codice}")
            continue
        descrizione = f"{r['anno']} n. {codice} - {socio.soggetto.nome_completo}"
        if importato(FONTE, "tessere", r["id"], Socio) is not None:
            rapporto.aggiungi("Tessere", "invariato", descrizione, ["già importata"])
            continue
        stato, note = _tessera(
            socio, codice, int(r["anno"]), _data(r["data_rilascio"]), _importo(r["quota_versata"]),
            utente,
        )  # fmt: skip
        if stato in ("nuovo", "invariato"):
            segna(FONTE, "tessere", r["id"], socio)
        rapporto.aggiungi("Tessere", stato, descrizione, note)
    if senza_socio:
        rapporto.avvisi.append(
            f"{senza_socio} tessere saltate perché il socio non è stato importato."
        )


# --- tesoreria --------------------------------------------------------------------------


def _voce(categoria, tipo, cache):
    codici = VOCI.get(testo(categoria).lower(), VOCI_ALTRO)
    codice = codici[0] if tipo == Movimento.Tipo.ENTRATA else codici[1]
    if codice not in cache:
        cache[codice] = Voce.objects.filter(codice=codice).first()
    return cache[codice]


def _tesoreria(conn, opzioni, utente, rapporto):
    conto = opzioni.conto or Conto.objects.filter(per_contanti=True, attivo=True).first()
    if conto is None:
        rapporto.avvisi.append("Tesoreria non importata: nessun conto per i contanti.")
        return
    anni = {r["anno"]: r for r in righe(conn, "anni_contabili", "anno")}
    movimenti = righe(conn, "movimenti", "data, id")
    for m in movimenti:
        anni.setdefault(int(str(m["data"])[:4]), {"anno": int(str(m["data"])[:4])})
    anno_corrente = timezone.localdate().year
    primo = True
    for anno in sorted(anni):
        a = anni[anno]
        esercizio = Esercizio.objects.filter(anno=anno).first()
        note = []
        if esercizio is None:
            esercizio = tesoreria.apri_esercizio(anno, utente)
            stato = "nuovo"
            if primo and tesoreria.saldi_iniziali_modificabili(esercizio):
                iniziale = _importo(a.get("saldo_iniziale"))
                tesoreria.imposta_saldi_iniziali(esercizio, {conto: iniziale}, utente)
                note.append(f"saldo iniziale {iniziale} € su {conto}")
        else:
            stato = "invariato"
        primo = False
        if not esercizio.aperto:
            rapporto.aggiungi(
                "Esercizi", "saltato", str(anno), ["già chiuso: movimenti non importati"]
            )
            continue
        importati = errori = 0
        voci = {}
        for m in (m for m in movimenti if str(m["data"]).startswith(str(anno))):
            if importato(FONTE, "movimenti", m["id"], Movimento):
                continue
            tipo = (
                Movimento.Tipo.ENTRATA
                if testo(m["tipo"]).upper() == "ENTRATA"
                else Movimento.Tipo.USCITA
            )
            try:
                with transaction.atomic():
                    mov = tesoreria.registra_movimento(
                        {
                            "data": _data(m["data"]),
                            "tipo": tipo,
                            "conto": conto,
                            "importo": _importo(m["importo"]),
                            "voce": _voce(m["categoria"], tipo, voci),
                            "descrizione": testo(m["descrizione"])[:255] or "(senza descrizione)",
                            "documento": testo(m["numero_documento"])[:100],
                        },
                        utente,
                    )
                    segna(FONTE, "movimenti", m["id"], mov)
                importati += 1
            except ValidationError as e:
                errori += 1
                rapporto.aggiungi(
                    "Movimenti", "errore", f"{m['data']} {m['descrizione']}", e.messages
                )
        if importati:
            note.append(f"{importati} movimenti in prima nota")
            stato = "aggiornato" if stato == "invariato" else stato
        if anno < anno_corrente and not errori:
            successivo = Esercizio.objects.filter(anno=anno + 1).first()
            if successivo and successivo.saldi.exclude(iniziale=0).exists():
                rapporto.avvisi.append(
                    f"Esercizio {anno + 1}: i saldi iniziali già presenti vengono sostituiti dai "
                    f"saldi finali del {anno} importato."
                )
            tesoreria.chiudi_esercizio(
                esercizio, utente, approvazione=f"Importato da {NOME} (chiuso all'importazione)"
            )
            note.append("chiuso")
            stato = "aggiornato" if stato == "invariato" else stato
        elif anno < anno_corrente:
            note.append("lasciato aperto per gli errori nei movimenti")
        rapporto.aggiungi("Esercizi", stato, str(anno), note)
        if a.get("saldo_finale") is not None and anno < anno_corrente:
            atteso = _importo(a["saldo_finale"])
            calcolato = tesoreria.saldo(conto, esercizio)
            if atteso != calcolato:
                rapporto.avvisi.append(
                    f"Esercizio {anno}: saldo finale {calcolato} €, "
                    f"nel vecchio gestionale {atteso} €."
                )


# --- beni -------------------------------------------------------------------------------


def _beni(conn, utente, rapporto):
    tabelle = {r[0] for r in conn.execute("select name from sqlite_master where type='table'")}
    if "beni_patrimoniali" not in tabelle:
        return
    valutazioni = righe(conn, "valutazioni_beni") if "valutazioni_beni" in tabelle else []
    for r in righe(conn, "beni_patrimoniali"):
        nome = testo(r["nome"])
        if importato(FONTE, "beni", r["id"], Bene):
            rapporto.aggiungi("Beni", "invariato", nome, ["già importato"])
            continue
        categoria, _ = CategoriaBene.objects.get_or_create(nome=testo(r["categoria"]) or "Varie")
        valore_acq = _importo(r["valore_acquisizione"])
        bene = Bene.objects.create(
            numero=prossimo_numero(SEQ_INVENTARIO),
            codice_precedente=testo(r["numero_inventario"])[:30],
            nome=nome[:200],
            categoria=categoria,
            descrizione=testo(r["descrizione"]),
            ubicazione=testo(r["ubicazione"])[:200],
            conservazione=CONSERVAZIONI.get(
                testo(r["stato_conservazione"]).upper(), Bene.Conservazione.BUONO
            ),
            acquisizione=ACQUISIZIONI.get(
                testo(r["modalita_acquisizione"]).upper(), Bene.Acquisizione.ALTRO
            ),
            data_acquisizione=_data(r["data_acquisizione"]),
            documento=testo(r["documento_acquisizione"])[:200],
            valore_acquisizione=valore_acq,
            valore=_importo(r["valore_attuale"]) or valore_acq,
            note=testo(r["note"]),
            creato_da=utente,
            modificato_da=utente,
        )
        for v in (v for v in valutazioni if v["bene_id"] == r["id"]):
            Valutazione.objects.create(
                bene=bene, data=_data(v["data_valutazione"]), valore=_importo(v["valore"]),
                metodo=METODI.get(testo(v["metodo_valutazione"]).lower(), Valutazione.Metodo.STIMA),
                note=testo(v["note"])[:255],
                registrata_da=utente,
            )  # fmt: skip
        segna(FONTE, "beni", r["id"], bene)
        registra(Azione.CREAZIONE, bene, utente=utente, numero=bene.numero, origine=NOME)
        precedente = (
            [f"codice precedente {bene.codice_precedente}"] if bene.codice_precedente else []
        )
        rapporto.aggiungi("Beni", "nuovo", f"n. {bene.numero} {nome}", precedente)
    for tabella in ("passaggi_consegne", "cessioni_beni"):
        if tabella in tabelle:
            n = conn.execute(f"select count(*) from {tabella}").fetchone()[0]  # noqa: S608
            if n:
                rapporto.avvisi.append(
                    f"{tabella}: {n} righe non importate (da riportare a mano se ancora attuali)."
                )


# --- ingresso ---------------------------------------------------------------------------


def importa(percorso, opzioni, utente, *, esegui=False):
    conn = apri_sqlite(percorso, TABELLE)
    rapporto = Rapporto(NOME, eseguito=esegui)
    try:
        with transaction.atomic():
            mappa = _soci(conn, opzioni, utente, rapporto)
            _tessere(conn, mappa, utente, rapporto)
            if opzioni.tesoreria:
                _tesoreria(conn, opzioni, utente, rapporto)
            if opzioni.beni:
                _beni(conn, utente, rapporto)
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
