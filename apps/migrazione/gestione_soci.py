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

import hashlib
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from apps.anagrafica.models import Soggetto
from apps.core.audit import Azione, registra
from apps.core.numerazione import prossimo_numero
from apps.patrimonio.models import (
    SEQ_INVENTARIO,
    Bene,
    CategoriaBene,
    PassaggioConsegne,
    Uscita,
    Valutazione,
)
from apps.soci import importazione as reg
from apps.soci import servizi as soci_servizi
from apps.soci.models import Sezione, Socio, Tessera, TipologiaSocio
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
    cartella_file: str | None = None  # static/uploads del vecchio gestionale (foto, documenti)


TIPI_CESSIONE = {"PRESTITO": "prestito", "DONAZIONE": "donazione", "ALIENAZIONE": "dismissione"}
RIENTRI = {"BUONO": "integro", "DANNEGGIATO": "danneggiato"}


def _cartella(percorso, opzioni):
    """Cartella dei file caricati nel vecchio gestionale: indicata o accanto al database."""
    if opzioni.cartella_file:
        return Path(opzioni.cartella_file)
    return Path(percorso).resolve().parent.parent / "static" / "uploads"


def _trova_file(cartella, nome, sottocartella=""):
    nome = Path(testo(nome)).name
    if not nome or not cartella.is_dir():
        return None
    for candidato in (cartella / sottocartella / nome, cartella / nome):
        if candidato.is_file():
            return candidato
    return next((p for p in cartella.rglob(nome) if p.is_file()), None)


def _foto(soggetto, cartella, nome):
    """Carica la foto del vecchio gestionale se la scheda non ne ha una. Restituisce la nota."""
    from django.core.files import File

    from apps.anagrafica.servizi import imposta_foto

    if not testo(nome) or soggetto.foto:
        return None
    file = _trova_file(cartella, nome, "soci")
    if file is None:
        return f"foto {Path(testo(nome)).name} non trovata nei file del vecchio gestionale"
    try:
        with file.open("rb") as f:
            imposta_foto(soggetto, File(f, name=file.name))
    except ValidationError as e:
        return f"foto non importata: {' '.join(e.messages)}"
    soggetto.save(update_fields=["foto"])
    return "foto importata"


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


def _per_tessera(d, tessere_origine):
    """Persona a cui è già attribuita una delle tessere del record, se ha la stessa data di
    nascita: è la stessa persona con un codice fiscale o un nome diversi nei due archivi."""
    if not d["data_nascita"]:
        return None
    for anno, codice in tessere_origine:
        if not codice.isdigit():
            continue
        t = (
            Tessera.objects.filter(anno=anno, carta__numero=int(codice))
            .select_related("socio__soggetto")
            .first()
        )
        if t and t.socio.soggetto.data_nascita == d["data_nascita"]:
            return t.socio.soggetto
    return None


def _soci(conn, opzioni, utente, rapporto, cartella):
    mappa = {}
    opz = reg.Opzioni(
        sezione=opzioni.sezione, abbina=opzioni.abbina, tipologia=opzioni.tipologia,
        tessere=False, cessazioni=False, crea_sezioni=opzioni.crea_sezioni,
    )  # fmt: skip
    rapporto_reg = reg.Rapporto()
    cache = {}
    tessere_origine = defaultdict(list)
    for t in righe(conn, "tessere"):
        tessere_origine[t["socio_id"]].append((int(t["anno"]), testo(t["numero"]).lstrip("0")))
    for r in righe(conn, "soci"):
        nome = f"{testo(r['cognome'])} {testo(r['nome'])}".strip()
        gia = importato(FONTE, "soci", r["id"], Socio)
        if gia:
            mappa[r["id"]] = gia
            nota = _foto(gia.soggetto, cartella, r.get("foto"))  # rieseguibile: le foto mancanti
            if nota == "foto importata":
                rapporto.aggiungi("Soci", "aggiornato", nome, [nota])
            else:
                rapporto.aggiungi(
                    "Soci", "invariato", nome, ["già importato"] + ([nota] if nota else [])
                )
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
            soggetto, abbinamento = None, []
            cf_noto = (
                d["codice_fiscale"]
                and Soggetto.objects.filter(codice_fiscale__iexact=d["codice_fiscale"]).exists()
            )
            if not cf_noto:
                soggetto = _per_tessera(d, tessere_origine[r["id"]])
                if soggetto:
                    cf = d["codice_fiscale"] or testo(r["codice_fiscale"]) or "assente"
                    abbinamento = [
                        f"abbinato a {soggetto.nome_completo} per tessera e data di nascita "
                        f"(codice fiscale nel vecchio gestionale: {cf})"
                    ]
                    d["codice_fiscale"] = ""  # non completa la scheda con un codice diverso
            with transaction.atomic():
                stato, note, socio = reg._riga(d, sezione, opz, utente, soggetto=soggetto)
                note = abbinamento + note
                segna(FONTE, "soci", r["id"], socio)
            mappa[r["id"]] = socio
            if nota := _foto(socio.soggetto, cartella, r.get("foto")):
                note.append(nota)
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


def _beni(conn, utente, rapporto, cartella):
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
    if "passaggi_consegne" in tabelle:
        _passaggi(conn, tabelle, cartella, utente, rapporto)
    if "cessioni_beni" in tabelle:
        _cessioni(conn, utente, rapporto)


def _data_testo(valore):
    """Date del vecchio gestionale scritte come testo (gg/mm/aaaa) o ISO."""
    t = testo(valore)
    for formato in ("%d/%m/%Y", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(t, formato).date()
        except ValueError:
            continue
    return None


def _passaggi(conn, tabelle, cartella, utente, rapporto):
    """Passaggi di consegne del patrimonio, con l'elenco dei beni fotografato allora."""
    from apps.core.models import Organizzazione
    from apps.core.pdf import genera_pdf

    fotografie = defaultdict(list)
    if "beni_passaggio_snapshot" in tabelle:
        for s in righe(conn, "beni_passaggio_snapshot"):
            fotografie[s["passaggio_consegne_id"]].append(s)
    for r in righe(conn, "passaggi_consegne"):
        consegnante = f"{testo(r['consegnante_nome'])} {testo(r['consegnante_cognome'])}".strip()
        ricevente = f"{testo(r['ricevente_nome'])} {testo(r['ricevente_cognome'])}".strip()
        titolo = f"{consegnante} → {ricevente}"
        if importato(FONTE, "passaggi_consegne", r["id"], PassaggioConsegne):
            rapporto.aggiungi("Passaggi di consegne", "invariato", titolo, ["già importato"])
            continue
        data = (_data_testo(r["consegnante_data"]) or _data_testo(r["ricevente_data"])
                or _data_testo(r["data_creazione"]) or date.today())  # fmt: skip
        beni = [
            {"codice": testo(s["numero_inventario"]), "nome": testo(s["nome"]),
             "categoria": testo(s["categoria"]), "quantita": 1,
             "ubicazione": testo(s["ubicazione"]), "conservazione": testo(s["stato_conservazione"]),
             "stato": "In patrimonio",
             "valore": str(_importo(s["valore_attuale"]) or _importo(s["valore_acquisizione"]))}
            for s in fotografie[r["id"]]
        ]  # fmt: skip
        valore = _importo(r["valore_totale_patrimonio"]) or sum(
            (Decimal(b["valore"]) for b in beni), Decimal("0")
        )
        p = PassaggioConsegne(
            data=data, consegnante=consegnante[:200] or "(non indicato)",
            consegnante_ruolo=testo(r["consegnante_ruolo"])[:100],
            ricevente=ricevente[:200] or "(non indicato)",
            ricevente_ruolo=testo(r["ricevente_ruolo"])[:100],
            note=testo(r["note_osservazioni"]), beni=beni,
            numero_beni=len(beni) or int(r["numero_beni_totali"] or 0), valore_totale=valore,
            creato_da=utente,
        )  # fmt: skip
        note = []
        originale = _trova_file(cartella, r.get("pdf_filename")) if r.get("pdf_filename") else None
        if originale:
            pdf = originale.read_bytes()
            note.append("PDF originale")
        else:
            contesto = {"p": p, "organizzazione": Organizzazione.corrente()}
            pdf = genera_pdf("patrimonio/pdf/passaggio.html", contesto)
            note.append("PDF rigenerato dai dati del vecchio gestionale")
        p.impronta = hashlib.sha256(pdf).hexdigest()
        p.file.save(f"passaggio_consegne_{data:%Y%m%d}.pdf", ContentFile(pdf), save=False)
        p.save()
        segna(FONTE, "passaggi_consegne", r["id"], p)
        registra(Azione.CREAZIONE, p, utente=utente, origine=NOME, beni=p.numero_beni)
        rapporto.aggiungi("Passaggi di consegne", "nuovo", f"{data:%d/%m/%Y} {titolo}",
                          [f"{p.numero_beni} beni", *note])  # fmt: skip


def _cessioni(conn, utente, rapporto):
    """Cessioni dei beni (prestiti, donazioni, alienazioni) come uscite dal patrimonio."""
    for r in righe(conn, "cessioni_beni"):
        bene = importato(FONTE, "beni", r["bene_id"], Bene)
        destinatario = testo(r["destinatario_organizzazione"]) or (
            f"{testo(r['destinatario_nome'])} {testo(r['destinatario_cognome'])}".strip()
        )
        titolo = f"{bene.nome if bene else 'bene ' + str(r['bene_id'])} a {destinatario or '?'}"
        if importato(FONTE, "cessioni_beni", r["id"], Uscita):
            rapporto.aggiungi("Cessioni di beni", "invariato", titolo, ["già importata"])
            continue
        if bene is None:
            rapporto.aggiungi("Cessioni di beni", "errore", titolo, ["bene non importato"])
            continue
        tipo = TIPI_CESSIONE.get(testo(r["tipo_cessione"]).upper(), Uscita.Tipo.DISMISSIONE)
        restituito = _data(r["data_restituzione_effettiva"])
        perso = testo(r["stato_restituzione"]).upper() == "PERSO"
        cf = testo(r["destinatario_codice_fiscale"]).upper()
        controparte = Soggetto.objects.filter(codice_fiscale__iexact=cf).first() if cf else None
        riferimenti = [
            f"{etichetta}: {testo(r[campo])}"
            for etichetta, campo in (("documento", "documento_cessione"),
                                     ("protocollo", "numero_protocollo"))
            if testo(r[campo])
        ]  # fmt: skip
        u = Uscita.objects.create(
            bene=bene, tipo=tipo, data=_data(r["data_cessione"]) or date.today(),
            controparte=controparte, controparte_testo=destinatario[:200],
            motivo=(testo(r["motivo_cessione"]) or f"Importata da {NOME}")[:255],
            condizioni="\n".join([testo(r["condizioni_cessione"]), *riferimenti]).strip(),
            restituzione_prevista=_data(r["data_restituzione_prevista"])
            if tipo == Uscita.Tipo.PRESTITO else None,
            restituito_il=restituito if tipo == Uscita.Tipo.PRESTITO else None,
            rientro=RIENTRI.get(testo(r["stato_restituzione"]).upper(), "")
            if restituito and not perso else "",
            note_rientro=(("bene perso. " if perso else "") + testo(r["note_restituzione"]))[:255],
            importo=_importo(r["valore_cessione"]), creato_da=utente, modificato_da=utente,
        )  # fmt: skip
        if tipo == Uscita.Tipo.PRESTITO and not restituito:
            bene.stato = Bene.Stato.IN_PRESTITO
        elif tipo != Uscita.Tipo.PRESTITO or perso:
            bene.stato = Bene.Stato.USCITO
        bene.modificato_da = utente
        bene.save(update_fields=["stato", "modificato_da", "modificato_il"])
        segna(FONTE, "cessioni_beni", r["id"], u)
        registra(Azione.MODIFICA, bene, utente=utente, uscita=u.get_tipo_display(), origine=NOME)
        stato_bene = bene.get_stato_display().lower()
        rapporto.aggiungi("Cessioni di beni", "nuovo", titolo,
                          [u.get_tipo_display(), f"bene ora: {stato_bene}"])  # fmt: skip


# --- ingresso ---------------------------------------------------------------------------


def importa(percorso, opzioni, utente, *, esegui=False):
    conn = apri_sqlite(percorso, TABELLE)
    rapporto = Rapporto(NOME, eseguito=esegui)
    try:
        with transaction.atomic():
            cartella = _cartella(percorso, opzioni)
            mappa = _soci(conn, opzioni, utente, rapporto, cartella)
            _tessere(conn, mappa, utente, rapporto)
            if opzioni.tesoreria:
                _tesoreria(conn, opzioni, utente, rapporto)
            if opzioni.beni:
                _beni(conn, utente, rapporto, cartella)
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
