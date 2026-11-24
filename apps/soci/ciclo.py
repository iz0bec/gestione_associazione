# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Ciclo delle tessere fra sede nazionale, federazione e sezioni
# *              (docs/analisi/ciclo-tessere.md): richieste delle sezioni, ordine al nazionale,
# *              magazzino dei blocchi ricevuti, consegne con il lotto della sezione, pagamenti e
# *              quadratura. Funziona per intero senza API: documenti PDF e file della consegna.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import csv
import io
from dataclasses import dataclass, field
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.core.audit import Azione, registra
from apps.core.models import Organizzazione
from apps.core.numerazione import prossimo_numero

from .models import (
    SEQ_CONSEGNA,
    SEQ_ORDINE,
    BloccoTessere,
    ConsegnaTessere,
    InvitoTessere,
    ListinoTessere,
    LottoTessere,
    OrdineTessere,
    RichiestaTessere,
    Sezione,
)
from .servizi import MASSIMO_PER_LOTTO, OperazioneNonValida, carica_lotto

INTESTAZIONE_CSV = ["anno", "serie", "numero_da", "numero_a", "cifre", "prezzo_unitario",
                    "consegna", "data", "fornitore"]  # fmt: skip


def listino(anno):
    return ListinoTessere.objects.filter(anno=anno).first()


def prezzo_sezioni(anno):
    voce = listino(anno)
    return voce.prezzo_sezioni if voce else Decimal("0")


# --- richieste ------------------------------------------------------------------------------


def registra_richiesta(utente, *, anno, sezione, quantita, data=None, protocollo=None, note="",
                       in_preparazione=False, **origine):  # fmt: skip
    if quantita < 1:
        raise OperazioneNonValida("Indicare almeno una tessera.")
    richiesta = RichiestaTessere(
        anno=anno, sezione=sezione, quantita=quantita, protocollo=protocollo, note=note,
        creato_da=utente, modificato_da=utente,
        inviata_il=None if in_preparazione else timezone.now(), **origine,
    )  # fmt: skip
    if data:
        richiesta.data = data
    richiesta.save()
    registra(Azione.CREAZIONE, richiesta, utente=utente, quantita=quantita, anno=anno,
             sezione=sezione.codice)  # fmt: skip
    return richiesta


def motivo_non_modificabile(richiesta):
    """Perché una richiesta inviata non si può correggere o annullare (None: si può). Si
    correggono quelle registrate qui (a mano o dal modulo Excel); quelle arrivate via API sono
    documenti della sezione, quelle spedite via API alla federazione sono già sue."""
    if richiesta.in_preparazione:
        return "La richiesta è in preparazione: si modifica dal riquadro della preparazione."
    if richiesta.cliente_api_id:
        return ("La richiesta è arrivata dalla sezione tramite il collegamento: la corregge "
                "la sezione.")  # fmt: skip
    if not richiesta.uuid_origine and canale_richiesta() == "api":
        return ("La richiesta è già stata inviata alla federazione tramite il collegamento: "
                "chiedere alla federazione di correggerla.")  # fmt: skip
    return None


def _controlla_modificabile(richiesta):
    if motivo := motivo_non_modificabile(richiesta):
        raise OperazioneNonValida(motivo)


@transaction.atomic
def modifica_richiesta(utente, richiesta, *, quantita, data=None, note=""):
    """Correzione di una richiesta registrata a mano (quantità, data, note)."""
    richiesta = RichiestaTessere.objects.select_for_update().get(pk=richiesta.pk)
    _controlla_modificabile(richiesta)
    if quantita < 1:
        raise OperazioneNonValida("Indicare almeno una tessera.")
    prima = richiesta.quantita
    richiesta.quantita, richiesta.note, richiesta.modificato_da = quantita, note, utente
    if data:
        richiesta.data = data
    richiesta.save()
    registra(Azione.MODIFICA, richiesta, utente=utente, quantita=quantita, quantita_prima=prima,
             descrizione=f"Richiesta di tessere corretta: {richiesta}")  # fmt: skip
    return richiesta


@transaction.atomic
def annulla_richiesta(utente, richiesta, *, motivo=""):
    """Annulla una richiesta registrata a mano (es. doppione di quella arrivata via API): esce
    dal fabbisogno, dall'ordine da fare e dalla quadratura. Resta nel registro delle attività."""
    richiesta = RichiestaTessere.objects.select_for_update().get(pk=richiesta.pk)
    _controlla_modificabile(richiesta)
    registra(Azione.ELIMINAZIONE, richiesta, utente=utente, quantita=richiesta.quantita,
             anno=richiesta.anno, sezione=richiesta.sezione.codice, motivo=motivo[:255],
             descrizione=f"Richiesta di tessere annullata: {richiesta}")  # fmt: skip
    descrizione = str(richiesta)
    richiesta.delete()
    return descrizione


# --- magazzino ------------------------------------------------------------------------------


def _sovrapposti(qs, numero_da, numero_a):
    return qs.filter(numero_da__lte=numero_a, numero_a__gte=numero_da)


def carica_blocco(utente, *, anno, numero_da, numero_a, serie="", cifre=0, **dati):
    """Blocco di tessere arrivato dalla sede nazionale, in magazzino finché non si consegna."""
    serie = (serie or "").strip().upper()
    if numero_a < numero_da:
        raise OperazioneNonValida("Il numero finale precede quello iniziale.")
    with transaction.atomic():
        stesso_anno = BloccoTessere.objects.select_for_update().filter(anno=anno, serie=serie)
        altri = _sovrapposti(stesso_anno, numero_da, numero_a)
        if altri.exists():
            raise OperazioneNonValida(f"I numeri si sovrappongono al blocco {altri.first()}.")
        blocco = BloccoTessere.objects.create(
            anno=anno, serie=serie, numero_da=numero_da, numero_a=numero_a, cifre=cifre,
            creato_da=utente, modificato_da=utente, **dati,
        )  # fmt: skip
        registra(Azione.CREAZIONE, blocco, utente=utente, descrizione=f"Blocco di tessere {blocco}",
                 quantita=blocco.quantita)  # fmt: skip
    return blocco


def intervalli_liberi(blocco):
    """Intervalli del blocco non ancora consegnati: [(da, a)]."""
    liberi, inizio = [], blocco.numero_da
    for da, a in blocco.consegne.order_by("numero_da").values_list("numero_da", "numero_a"):
        if da > inizio:
            liberi.append((inizio, da - 1))
        inizio = max(inizio, a + 1)
    if inizio <= blocco.numero_a:
        liberi.append((inizio, blocco.numero_a))
    return liberi


def in_magazzino(blocco):
    return sum(a - da + 1 for da, a in intervalli_liberi(blocco))


# --- consegne -------------------------------------------------------------------------------


def consegna(utente, *, blocco, sezione, numero_da, numero_a, data=None, modalita=None,
             note_distribuzione="", prezzo_unitario=None):  # fmt: skip
    """Consegna di un intervallo del magazzino a una sezione: documento numerato e lotto della
    sezione con le sue tessere. Possibile anche senza pagamento (la quadratura lo mostra)."""
    if numero_a < numero_da:
        raise OperazioneNonValida("Il numero finale precede quello iniziale.")
    if numero_a - numero_da + 1 > MASSIMO_PER_LOTTO:
        raise OperazioneNonValida(
            f"Una consegna può contenere al massimo {MASSIMO_PER_LOTTO} tessere."
        )
    with transaction.atomic():
        blocco = BloccoTessere.objects.select_for_update().get(pk=blocco.pk)
        if not (blocco.numero_da <= numero_da and numero_a <= blocco.numero_a):
            raise OperazioneNonValida(
                f"I numeri vanno scelti dentro il blocco ({blocco.numero_da}–{blocco.numero_a})."
            )
        gia = _sovrapposti(blocco.consegne.all(), numero_da, numero_a).first()
        if gia is not None:
            raise OperazioneNonValida(
                f"Una parte dei numeri è già stata consegnata ({gia}: "
                f"{gia.numero_da}–{gia.numero_a})."
            )
        if prezzo_unitario is None:
            prezzo_unitario = prezzo_sezioni(blocco.anno)
        numero = prossimo_numero(SEQ_CONSEGNA, blocco.anno)
        org = Organizzazione.corrente()
        lotto = carica_lotto(
            utente, anno=blocco.anno, numero_da=numero_da, numero_a=numero_a, serie=blocco.serie,
            cifre=blocco.cifre, costo_unitario=prezzo_unitario, sezione=sezione,
            fornitore=(org.denominazione_breve or org.denominazione)[:100],
            riferimento=f"Consegna n. {blocco.anno}/{numero}",
        )  # fmt: skip
        documento = ConsegnaTessere(
            anno=blocco.anno, numero=numero, sezione=sezione, blocco=blocco, numero_da=numero_da,
            numero_a=numero_a, prezzo_unitario=prezzo_unitario, lotto=lotto,
            modalita=modalita or ConsegnaTessere.Modalita.RITIRO,
            note_distribuzione=note_distribuzione, creato_da=utente, modificato_da=utente,
        )  # fmt: skip
        if data:
            documento.data = data
        documento.save()
        registra(Azione.CREAZIONE, documento, utente=utente, quantita=documento.quantita,
                 sezione=sezione.codice, importo=str(documento.importo))  # fmt: skip
    return documento


def prendi_in_carico(documento, utente, data):
    documento.presa_in_carico_il = data
    documento.modificato_da = utente
    documento.save(update_fields=["presa_in_carico_il", "modificato_da", "modificato_il"])
    registra(Azione.MODIFICA, documento, utente=utente, presa_in_carico_il=str(data))


def csv_consegna(documento) -> bytes:
    """File con i numeri della consegna, da importare nell'installazione della sezione."""
    uscita = io.StringIO()
    scrittore = csv.writer(uscita, delimiter=";")
    scrittore.writerow(INTESTAZIONE_CSV)
    org = Organizzazione.corrente()
    scrittore.writerow([
        documento.anno, documento.blocco.serie, documento.numero_da, documento.numero_a,
        documento.blocco.cifre, f"{documento.prezzo_unitario:.2f}",
        f"{documento.anno}/{documento.numero}", documento.data.isoformat(),
        org.denominazione_breve or org.denominazione,
    ])  # fmt: skip
    return uscita.getvalue().encode("utf-8")


def leggi_csv_consegna(contenuto: bytes):
    """Righe del file di consegna, controllate: [{anno, serie, numero_da, …}]."""
    try:
        testo = contenuto.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise OperazioneNonValida("Il file non è in UTF-8.") from e
    lettore = csv.DictReader(io.StringIO(testo), delimiter=";")
    if lettore.fieldnames is None or set(INTESTAZIONE_CSV) - set(lettore.fieldnames):
        raise OperazioneNonValida("Il file non è un file di consegna delle tessere.")
    righe = []
    for n, riga in enumerate(lettore, start=2):
        try:
            righe.append({
                "anno": int(riga["anno"]), "serie": riga["serie"].strip(),
                "numero_da": int(riga["numero_da"]), "numero_a": int(riga["numero_a"]),
                "cifre": int(riga["cifre"] or 0),
                "prezzo_unitario": Decimal(riga["prezzo_unitario"]),
                "consegna": riga["consegna"].strip(), "data": riga["data"].strip(),
                "fornitore": riga["fornitore"].strip()[:100],
            })  # fmt: skip
        except (ValueError, ArithmeticError) as e:
            raise OperazioneNonValida(f"Riga {n} del file non valida.") from e
    if not righe:
        raise OperazioneNonValida("Il file non contiene consegne.")
    return righe


def importa_consegna(utente, contenuto: bytes, *, sezione=None, esegui=False):
    """Lato sezione: carica i lotti dal file di consegna della federazione. Senza `esegui`
    restituisce solo l'anteprima (e i controlli), senza salvare nulla."""
    righe = leggi_csv_consegna(contenuto)
    lotti = []
    with transaction.atomic():
        for r in righe:
            lotti.append(carica_lotto(
                utente, anno=r["anno"], numero_da=r["numero_da"], numero_a=r["numero_a"],
                serie=r["serie"], cifre=r["cifre"], costo_unitario=r["prezzo_unitario"],
                sezione=sezione, fornitore=r["fornitore"] or "Federazione",
                riferimento=f"Consegna n. {r['consegna']} del {r['data']}",
            ))  # fmt: skip
        if not esegui:
            transaction.set_rollback(True)
    return righe, lotti


# --- ordine al nazionale --------------------------------------------------------------------


def da_ordinare(anno):
    """Per sezione: richiesto nell'anno meno quanto già ordinato (le integrazioni producono un
    ordine supplementare)."""
    richiesto = {
        r["sezione"]: r["totale"]
        for r in RichiestaTessere.objects.filter(anno=anno, inviata_il__isnull=False)
        .values("sezione")
        .annotate(totale=Sum("quantita"))
    }
    ordinato = {}
    for ordine in OrdineTessere.objects.filter(anno=anno):
        for riga in ordine.dettaglio:
            ordinato[riga["sezione"]] = ordinato.get(riga["sezione"], 0) + riga["quantita"]
    sezioni = Sezione.objects.in_bulk(richiesto)
    return [
        {"sezione": pk, "codice": sezioni[pk].codice, "nome": sezioni[pk].nome,
         "quantita": richiesto[pk] - ordinato.get(pk, 0)}
        for pk in sorted(richiesto, key=lambda pk: (sezioni[pk].ordine, sezioni[pk].nome))
        if richiesto[pk] - ordinato.get(pk, 0) > 0
    ]  # fmt: skip


def crea_ordine(utente, *, anno, data=None, note=""):
    with transaction.atomic():
        dettaglio = da_ordinare(anno)
        quantita = sum(r["quantita"] for r in dettaglio)
        if not quantita:
            raise OperazioneNonValida("Nessuna richiesta da ordinare per questo anno.")
        ordine = OrdineTessere(
            anno=anno, numero=prossimo_numero(SEQ_ORDINE, anno), quantita=quantita,
            dettaglio=dettaglio, note=note, creato_da=utente, modificato_da=utente,
        )  # fmt: skip
        if data:
            ordine.data = data
        ordine.save()
        registra(Azione.CREAZIONE, ordine, utente=utente, quantita=quantita)
    return ordine


# --- quadratura -----------------------------------------------------------------------------


@dataclass
class RigaQuadratura:
    sezione: Sezione
    richieste: int = 0
    consegnate: int = 0
    dovuto: Decimal = Decimal("0")
    pagato: Decimal = Decimal("0")
    consegne_senza_presa: int = 0
    avvisi: list = field(default_factory=list)

    @property
    def saldo(self):
        return self.dovuto - self.pagato

    @property
    def da_consegnare(self):
        return max(self.richieste - self.consegnate, 0)


def pagato_per_sezione(anno):
    """Versamenti netti delle sezioni per le tessere dell'anno (incassi meno storni)."""
    from apps.tesoreria.models import Incasso

    pagato = {}
    incassi = Incasso.objects.filter(
        tipo=Incasso.Tipo.TESSERE, anno_tessere=anno, sezione__isnull=False
    ).prefetch_related("storni")
    for incasso in incassi:
        netto = incasso.importo - sum((s.importo for s in incasso.storni.all()), Decimal("0"))
        pagato[incasso.sezione_id] = pagato.get(incasso.sezione_id, Decimal("0")) + netto
    return pagato


def quadratura(anno):
    """Per sezione: richieste, consegnate, dovuto, pagato, saldo e avvisi."""
    righe = {}

    def riga(sezione):
        return righe.setdefault(sezione.pk, RigaQuadratura(sezione))

    for r in RichiestaTessere.objects.filter(anno=anno, inviata_il__isnull=False).select_related(
        "sezione"
    ):
        riga(r.sezione).richieste += r.quantita
    for c in ConsegnaTessere.objects.filter(anno=anno).select_related("sezione"):
        voce = riga(c.sezione)
        voce.consegnate += c.quantita
        voce.dovuto += c.importo
        if not c.presa_in_carico_il:
            voce.consegne_senza_presa += 1
    pagato = pagato_per_sezione(anno)
    for sezione in Sezione.objects.filter(pk__in=pagato):
        riga(sezione).pagato = pagato[sezione.pk]
    for voce in righe.values():
        if voce.consegnate and not voce.pagato:
            voce.avvisi.append("consegnate senza alcun pagamento")
        elif voce.saldo > 0:
            voce.avvisi.append(f"da versare € {voce.saldo:.2f}")
        elif voce.saldo < 0:
            voce.avvisi.append(f"versato in più € {-voce.saldo:.2f}")
        if voce.da_consegnare:
            voce.avvisi.append(f"{voce.da_consegnare} da consegnare")
        if voce.consegne_senza_presa:
            voce.avvisi.append("presa in carico da confermare")
    return sorted(righe.values(), key=lambda r: (r.sezione.ordine, r.sezione.nome))


def riepilogo_magazzino(anno):
    blocchi = list(BloccoTessere.objects.filter(anno=anno).prefetch_related("consegne"))
    ricevute = sum(b.quantita for b in blocchi)
    disponibili = sum(in_magazzino(b) for b in blocchi)
    return {"blocchi": blocchi, "ricevute": ricevute, "disponibili": disponibili,
            "consegnate": ricevute - disponibili}  # fmt: skip


# --- avvisi alle sezioni (email/PEC con i modelli del ciclo) --------------------------------

DA_INDICARE = "[da indicare]"


def _euro(valore):
    return f"{valore:.2f}".replace(".", ",")


def _data(valore):
    return valore.strftime("%d/%m/%Y") if valore else DA_INDICARE


def descrivi_delibera(delibera):
    if delibera is None:
        return "la delibera " + DA_INDICARE
    giorno = delibera.verbale.riunione.prima_convocazione
    codice = delibera.codice or DA_INDICARE
    return f"la delibera {codice} del {_data(giorno.date())}"


def contesto_anno(anno):
    """Segnaposto comuni agli avvisi dell'anno, dal listino (mai valori inventati)."""
    voce = listino(anno)
    org = Organizzazione.corrente()
    if voce is None:
        return {"anno": anno, "organizzazione": org.denominazione, "quota_tessera": DA_INDICARE,
                "costo_nazionale": DA_INDICARE, "quota_federale": DA_INDICARE,
                "delibera": "la delibera " + DA_INDICARE, "scadenza_richiesta": DA_INDICARE,
                "modalita_pagamento": DA_INDICARE}  # fmt: skip
    return {
        "anno": anno,
        "organizzazione": org.denominazione,
        "quota_tessera": _euro(voce.prezzo_sezioni),
        "costo_nazionale": _euro(voce.costo_acquisto),
        "quota_federale": _euro(voce.quota_federale),
        "delibera": descrivi_delibera(voce.delibera),
        "scadenza_richiesta": _data(voce.scadenza_richieste),
        "modalita_pagamento": voce.istruzioni_pagamento.strip() or DA_INDICARE,
    }


def contesto_consegna(documento):
    """Segnaposto dell'avviso di attribuzione per una consegna, con la quadratura della sezione."""
    riga = next((r for r in quadratura(documento.anno) if r.sezione.pk == documento.sezione_id),
                None)  # fmt: skip
    serie = f"serie {documento.blocco.serie}, " if documento.blocco.serie else ""
    return {
        "numero_consegna": f"{documento.anno}/{documento.numero}",
        "tessere": f"{serie}dal n. {documento.numero_da} al n. {documento.numero_a}",
        "quantita": documento.quantita,
        "importo_dovuto": _euro(riga.dovuto if riga else documento.importo),
        "importo_versato": _euro(riga.pagato if riga else Decimal("0")),
        "saldo": _euro(max(riga.saldo, Decimal("0")) if riga else documento.importo),
        "modalita_distribuzione": documento.get_modalita_display().lower(),
        "note_distribuzione": documento.note_distribuzione.strip(),
    }


def destinatari(sezione):
    """Indirizzo della sezione e presidente in carica della sezione (in copia)."""
    from apps.organi.firme import in_carica_al

    indirizzi = (
        [(f"Direzione della {sezione.denominazione}", sezione.email)] if sezione.email else []
    )
    presidente = in_carica_al("presidente", sezione=sezione)
    soggetti = [presidente] if presidente is not None else []
    return indirizzi, soggetti


def sezioni_senza_richiesta(anno):
    con = RichiestaTessere.objects.filter(anno=anno, inviata_il__isnull=False).values_list(
        "sezione_id", flat=True
    )
    return Sezione.objects.filter(attiva=True).exclude(pk__in=con)


AVVISI = {
    "tesseramento": ("tesseramento", "tessere_avviso"),
    "sollecito": ("sollecito_tess", "tessere_sollecito"),
    "attribuzione": ("attribuz_tess", "tessere_attribuzione"),
}


def modello_avviso(tipo):
    from apps.comunicazioni.models import Modello

    return Modello.objects.filter(uso=AVVISI[tipo][0], attivo=True).order_by("pk").first()


def prepara_avvisi(utente, *, tipo, anno, sezioni=(), consegne=(), riferimento_avviso="",
                   nuova_scadenza=None, servizio=None, protocolla=True, oggetto=None, corpo=None,
                   salva_modello=False):  # fmt: skip
    """Un invio in bozza per ogni sezione (o consegna, per l'attribuzione), con il modello del
    ciclo: si confermano poi da Comunicazioni come gli altri invii. Restituisce (invii, saltate)."""
    from apps.comunicazioni import servizi as comunicazioni
    from apps.comunicazioni.models import Finalita

    _, origine = AVVISI[tipo]
    modello = modello_avviso(tipo)
    if modello is None:
        raise OperazioneNonValida("Manca il modello del messaggio (Comunicazioni → Modelli).")
    oggetto = (oggetto or modello.oggetto).strip()
    corpo = corpo or modello.corpo
    if salva_modello and (oggetto, corpo) != (modello.oggetto, modello.corpo):
        if not utente.has_perm("comunicazioni.change_modello"):
            raise OperazioneNonValida("Non hai il permesso di modificare i modelli.")
        prima = {"oggetto": modello.oggetto, "corpo": modello.corpo}
        modello.oggetto, modello.corpo = oggetto, corpo
        modello.save(update_fields=["oggetto", "corpo"])
        registra(Azione.MODIFICA, modello, utente=utente, campi={
            k: {"prima": v, "dopo": getattr(modello, k)} for k, v in prima.items()
            if v != getattr(modello, k)
        })  # fmt: skip
    if "{{ sezione }}" not in oggetto:  # riconoscibile nell'elenco e per chi lo riceve
        oggetto = f"{oggetto} – {{{{ sezione }}}}"
    base = contesto_anno(anno)
    if tipo == "sollecito":
        base |= {"riferimento_avviso": riferimento_avviso.strip() or DA_INDICARE,
                 "nuova_scadenza": _data(nuova_scadenza)}  # fmt: skip
    voci = (
        [(c.sezione, c) for c in consegne]
        if tipo == "attribuzione"
        else [(s, None) for s in sezioni]
    )
    con_modulo = tipo in ("tesseramento", "sollecito")
    if con_modulo and "tessere_anno_precedente" not in corpo:
        corpo = corpo.rstrip() + (f"\n\nPer informazione, nel {anno - 1} la sezione ha avuto "
                                  "{{ tessere_anno_precedente }} tessere.")  # fmt: skip
    if con_modulo and "istruzioni_risposta" not in corpo:
        corpo = corpo.rstrip() + "\n\n{{ istruzioni_risposta }}"  # come rispondere, sempre
    voce_listino = listino(anno)
    invii, saltate = [], []
    for sezione, documento in voci:
        indirizzi, soggetti = destinatari(sezione)
        if not indirizzi and not soggetti:
            saltate.append((sezione, "senza email della sezione né presidente in carica"))
            continue
        contesto = base | {"sezione": sezione.denominazione}
        allegati = []
        if documento is not None:
            contesto |= contesto_consegna(documento)
        if con_modulo:
            from . import modulo_tessere

            scadenza = (nuova_scadenza if tipo == "sollecito" else None) or (
                voce_listino.scadenza_richieste if voce_listino else None
            )
            precedente = tessere_anno_precedente(anno, sezione)
            contesto["istruzioni_risposta"] = modulo_tessere.istruzioni(anno, sezione, scadenza)
            contesto["tessere_anno_precedente"] = precedente
            allegati = [(f"richiesta-tessere-{anno}-{sezione.codice}.xlsx", modulo_tessere.genera(
                anno, sezione, quota=voce_listino.prezzo_sezioni if voce_listino else None,
                scadenza=scadenza, precedente=precedente,
            ))]  # fmt: skip
        try:
            invio = comunicazioni.crea_invio(
                utente, oggetto=oggetto, corpo=corpo,
                finalita=Finalita.ISTITUZIONALE, soggetti=soggetti, indirizzi=indirizzi,
                modello=modello, protocolla=protocolla, origine=origine,
                origine_id=documento.pk if documento else sezione.pk, contesto=contesto,
                servizio=servizio, allegati=allegati,
            )  # fmt: skip
        except comunicazioni.OperazioneNonValida as e:
            saltate.append((sezione, " ".join(e.messages)))
            continue
        invii.append(invio)
    return invii, saltate


def prepara_risposta(utente, richiesta, *, riferimento_avviso="", servizio=None, protocolla=True):
    """Lato sezione: la richiesta di tessere inviata alla federazione (risposta all'avviso), in
    bozza con il PDF della richiesta allegato. Indirizzo da Sistema → Organizzazione."""
    from apps.comunicazioni import servizi as comunicazioni
    from apps.comunicazioni.models import Finalita, Modello

    if canale_richiesta() == "registro":  # nella federazione: la federazione scriverebbe a sé
        raise OperazioneNonValida("Questa è la federazione: alla sezione si manda la conferma "
                                  "di ricezione della richiesta.")  # fmt: skip
    org = Organizzazione.corrente()
    if not org.federazione_email:
        raise OperazioneNonValida(
            "Manca l'email della federazione: indicarla in Sistema → Organizzazione."
        )
    modello = Modello.objects.filter(uso="risposta_tess", attivo=True).order_by("pk").first()
    if modello is None:
        raise OperazioneNonValida("Manca il modello «Richiesta di tessere alla federazione».")
    rif = riferimento_avviso.strip()
    contesto = {
        "anno": richiesta.anno,
        "sezione": richiesta.sezione.denominazione,
        "quantita": richiesta.quantita,
        "federazione": org.federazione or DA_INDICARE,
        "riferimento_avviso": f" ({rif})" if rif else "",
        "note_richiesta": richiesta.note,
        "organizzazione": org.denominazione,
    }
    pdf = pdf_richiesta(richiesta)
    nome_federazione = f"Federazione {org.federazione}".strip()
    try:
        invio = comunicazioni.crea_invio(
            utente, oggetto=modello.oggetto, corpo=modello.corpo,
            finalita=Finalita.ISTITUZIONALE, indirizzi=[(nome_federazione, org.federazione_email)],
            modello=modello, protocolla=protocolla, origine=ORIGINE_RICHIESTA,
            origine_id=richiesta.pk, contesto=contesto, servizio=servizio,
            allegati=[(f"richiesta-tessere-{richiesta.anno}.pdf", pdf)],
        )  # fmt: skip
    except comunicazioni.OperazioneNonValida as e:
        raise OperazioneNonValida(" ".join(e.messages)) from None
    return invio


ORIGINE_CONFERMA = "tessere_conferma"
OGGETTO_CONFERMA = "Tesseramento {{ anno }}: ricevuta la richiesta di tessere – {{ sezione }}"
TESTO_CONFERMA = """Alla Presidenza della {{ sezione }},

confermiamo di aver ricevuto la richiesta di {{ quantita }} tessere per il tesseramento {{ anno }}, del {{ data_richiesta }}{{ riferimento_richiesta }}.

La richiesta è registrata nel fabbisogno della {{ federazione }}: riceverete l'avviso quando le tessere saranno pronte per la consegna. In allegato il riepilogo della richiesta.
{{ note_richiesta }}
Cordiali saluti
{{ organizzazione }}"""  # noqa: E501


def prepara_conferma(utente, richiesta, *, servizio=None, protocolla=True):
    """Lato federazione: conferma di ricezione della richiesta alla sezione (casella della sezione
    e presidente in carica, come gli avvisi del ciclo), in bozza con il PDF della richiesta."""
    from apps.comunicazioni import servizi as comunicazioni
    from apps.comunicazioni.models import Finalita

    sezione = richiesta.sezione
    indirizzi, soggetti = destinatari(sezione)
    if not indirizzi and not soggetti:
        raise OperazioneNonValida(f"La {sezione.denominazione} non ha un'email né un presidente "
                                  "in carica con l'email (Sistema → Sezioni).")  # fmt: skip
    org = Organizzazione.corrente()
    rif = f", prot. n. {richiesta.protocollo.segnatura}" if richiesta.protocollo_id else ""
    contesto = {
        "anno": richiesta.anno, "sezione": sezione.denominazione,
        "quantita": richiesta.quantita, "data_richiesta": _data(richiesta.data),
        "riferimento_richiesta": rif, "federazione": org.denominazione,
        "note_richiesta": f"\nNote: {richiesta.note}\n" if richiesta.note else "",
        "organizzazione": org.denominazione,
    }  # fmt: skip
    try:
        return comunicazioni.crea_invio(
            utente, oggetto=OGGETTO_CONFERMA, corpo=TESTO_CONFERMA,
            finalita=Finalita.ISTITUZIONALE, soggetti=soggetti, indirizzi=indirizzi,
            protocolla=protocolla, origine=ORIGINE_CONFERMA, origine_id=richiesta.pk,
            contesto=contesto, servizio=servizio,
            allegati=[(f"richiesta-tessere-{richiesta.anno}-{sezione.codice}.pdf",
                       pdf_richiesta(richiesta))],
        )  # fmt: skip
    except comunicazioni.OperazioneNonValida as e:
        raise OperazioneNonValida(" ".join(e.messages)) from None


def pdf_richiesta(richiesta) -> bytes:
    """PDF della richiesta di tessere, firmato da chi chiede: nell'installazione della sezione
    il presidente dell'associazione; in una federazione (più sezioni) il presidente della sezione
    che chiede, dalle cariche dei suoi organi (vacante se manca), mai quello della federazione."""
    from apps.core.pdf import genera_pdf

    from .sezioni import multisezione

    return genera_pdf("soci/pdf/richiesta_tessere.html", {
        "richiesta": richiesta, "listino": listino(richiesta.anno),
        "organizzazione": Organizzazione.corrente(),
        "sezione_firma": richiesta.sezione if multisezione() else None,
    })  # fmt: skip


def pdf_originale_richiesta(richiesta):
    """Il PDF ricevuto dalla sezione, per una richiesta arrivata via API (o None)."""
    from apps.api.models import DocumentoRicevuto

    if not richiesta.uuid_origine:
        return None
    documento = (
        DocumentoRicevuto.objects.filter(tipo="richiesta", uuid_origine=richiesta.uuid_origine)
        .exclude(pdf="")
        .first()
    )
    return documento.pdf if documento else None


def richiesta_da_modulo(utente, contenuto: bytes, *, protocollo=None):
    """Richiesta registrata dal modulo Excel compilato dalla sezione. Lo stesso file non si
    registra due volte (l'impronta del file diventa l'identificativo d'origine)."""
    import hashlib
    import uuid

    from . import modulo_tessere

    try:
        dati = modulo_tessere.leggi(contenuto)
    except modulo_tessere.ModuloNonValido as e:
        raise OperazioneNonValida(str(e)) from None
    origine = uuid.uuid5(uuid.NAMESPACE_URL, "modulo:" + hashlib.sha256(contenuto).hexdigest())
    gia = RichiestaTessere.objects.filter(uuid_origine=origine).first()
    if gia is not None:
        raise OperazioneNonValida(f"Questo modulo è già stato registrato ({gia}).")
    return registra_richiesta(
        utente, anno=dati["anno"], sezione=dati["sezione"], quantita=dati["quantita"],
        protocollo=protocollo, note=modulo_tessere.note_richiesta(dati), uuid_origine=origine,
    )  # fmt: skip


def tessere_anno_precedente(anno, sezione):
    """Quante tessere ebbe la sezione l'anno prima (per informazione negli avvisi): tessere
    rilasciate ai suoi soci e non annullate; se non ce ne sono, quelle consegnate."""
    from .models import Tessera

    rilasciate = Tessera.objects.filter(
        anno=anno - 1, socio__sezione=sezione, annullata=False
    ).count()
    if rilasciate:
        return rilasciate
    return sum(c.quantita for c in ConsegnaTessere.objects.filter(anno=anno - 1, sezione=sezione))


# --- richiesta in preparazione (dal rinnovo) ---------------------------------------------------


def fabbisogno(anno, sezione):
    """Quante tessere chiedere al livello superiore, per differenza: soci rinnovati ancora senza
    tessera fisica, meno le tessere disponibili in carico, meno quelle già chieste e non ancora
    arrivate."""
    from .models import CartaTessera, Tessera
    from .servizi import FORNITORE_REGISTRO

    senza_numero = (
        Tessera.objects.valide()
        .filter(anno=anno, socio__sezione=sezione, carta__isnull=True)
        .count()
    )
    disponibili = (
        CartaTessera.objects.disponibili().filter(anno=anno, lotto__sezione=sezione).count()
    )
    chieste = sum(RichiestaTessere.objects.filter(
        anno=anno, sezione=sezione, inviata_il__isnull=False, uuid_origine__isnull=True
    ).values_list("quantita", flat=True))  # fmt: skip
    arrivate = sum(
        lotto.quantita
        for lotto in LottoTessere.objects.filter(anno=anno, sezione=sezione).exclude(
            fornitore=FORNITORE_REGISTRO
        )
    )
    in_attesa = max(chieste - arrivate, 0)
    return {
        "senza_numero": senza_numero, "disponibili": disponibili, "in_attesa": in_attesa,
        "proposta": max(senza_numero - disponibili - in_attesa, 0),
    }  # fmt: skip


ORIGINE_RICHIESTA = "tessere_richiesta"  # origine degli invii email della richiesta


def email_in_corso(richiesta):
    """L'email della richiesta ancora da spedire (in bozza o in coda), o None."""
    from apps.comunicazioni.models import Invio

    return Invio.objects.filter(
        origine=ORIGINE_RICHIESTA, origine_id=richiesta.pk,
        stato__in=[Invio.Stato.BOZZA, Invio.Stato.IN_CODA],
    ).order_by("-creato_il").first()  # fmt: skip


def richiesta_spedita(invio):
    """Chiamata dalle comunicazioni a invio concluso: la richiesta in preparazione diventa
    inviata, con la data e il protocollo dell'email."""
    richiesta = RichiestaTessere.objects.filter(pk=invio.origine_id,
                                                inviata_il__isnull=True).first()  # fmt: skip
    if richiesta is None:
        return
    richiesta.inviata_il = invio.completato_il or timezone.now()
    richiesta.data = timezone.localdate(richiesta.inviata_il)
    if invio.protocollo_id:
        richiesta.protocollo = invio.protocollo
    richiesta.save()
    registra(Azione.MODIFICA, richiesta, utente=None, inviata="email",
             descrizione=f"Richiesta di tessere spedita per email: {richiesta}")  # fmt: skip


def in_preparazione(anno, sezione):
    return RichiestaTessere.objects.filter(
        anno=anno, sezione=sezione, inviata_il__isnull=True, uuid_origine__isnull=True
    ).first()


@transaction.atomic
def aggiorna_in_preparazione(utente, anno, sezione, *, togli=False):
    """Porta la richiesta in preparazione dell'anno al fabbisogno calcolato (la crea se serve).
    Con fabbisogno zero la toglie solo se richiesto (`togli`, il pulsante «Ricalcola»): una
    richiesta preparata a mano (sezione che non tiene i soci nel gestionale) resta. Non parte
    mai da sola. Restituisce (richiesta o None, calcolo)."""
    calcolo = fabbisogno(anno, sezione)
    bozza = in_preparazione(anno, sezione)
    if bozza is not None and email_in_corso(bozza):
        return bozza, calcolo  # l'email è già scritta con questa quantità: non si cambia
    if not calcolo["proposta"]:
        if bozza and togli:
            registra(Azione.ELIMINAZIONE, bozza, utente=utente,
                     descrizione=f"Richiesta in preparazione tolta: {bozza}")  # fmt: skip
            bozza.delete()
            return None, calcolo
        return bozza, calcolo
    if bozza is None:
        bozza = registra_richiesta(utente, anno=anno, sezione=sezione,
                                   quantita=calcolo["proposta"], in_preparazione=True)  # fmt: skip
    elif bozza.quantita != calcolo["proposta"]:
        bozza.quantita, bozza.modificato_da = calcolo["proposta"], utente
        bozza.save()
        registra(Azione.MODIFICA, bozza, utente=utente, quantita=bozza.quantita)
    return bozza, calcolo


def modifica_in_preparazione(utente, richiesta, *, quantita, note=""):
    if not richiesta.in_preparazione:
        raise OperazioneNonValida("La richiesta è già stata inviata: non si modifica.")
    if email_in_corso(richiesta):
        raise OperazioneNonValida("L'email della richiesta è in bozza: per cambiarla annullare "
                                  "l'email da Comunicazioni.")  # fmt: skip
    if quantita < 1:
        raise OperazioneNonValida("Indicare almeno una tessera.")
    richiesta.quantita, richiesta.note, richiesta.modificato_da = quantita, note, utente
    richiesta.save()
    registra(Azione.MODIFICA, richiesta, utente=utente, quantita=quantita)
    return richiesta


def canale_richiesta():
    """Come parte una richiesta della sezione: «api» (federazione collegata), «email», oppure
    «registro» nella federazione (richiesta di una sua sezione: entra nel fabbisogno)."""
    from apps.api.models import ClienteApi

    from .sezioni import multisezione

    if multisezione():
        return "registro"
    collegata = ClienteApi.objects.filter(
        stato=ClienteApi.Stato.ATTIVA, ruolo=ClienteApi.Ruolo.FEDERAZIONE,
        ambiti__contains=["tessere:scambio"],
    ).exists()  # fmt: skip
    return "api" if collegata else "email"


@transaction.atomic
def invia_richiesta(utente, richiesta):
    """Invia la richiesta in preparazione sul canale previsto. Restituisce (canale, invio
    email in bozza o None)."""
    richiesta = RichiestaTessere.objects.select_for_update().get(pk=richiesta.pk)
    if not richiesta.in_preparazione:
        raise OperazioneNonValida("La richiesta è già stata inviata.")
    canale = canale_richiesta()
    if canale == "email":
        # resta in preparazione finché l'email non parte davvero (richiesta_spedita)
        if email_in_corso(richiesta):
            raise OperazioneNonValida("L'email della richiesta è già in bozza in Comunicazioni.")
        voce = invito(richiesta.anno)  # la richiesta risponde all'invito ricevuto
        rif = ""
        if voce is not None and voce.protocollo_id:
            rif = f"vostra prot. n. {voce.protocollo.segnatura} del {voce.ricevuto_il:%d/%m/%Y}"
        invio = prepara_risposta(utente, richiesta, riferimento_avviso=rif)
        descrizione = f"Email della richiesta di tessere preparata: {richiesta}"
        registra(Azione.MODIFICA, richiesta, utente=utente, descrizione=descrizione)
        return canale, invio
    richiesta.inviata_il, richiesta.data, richiesta.modificato_da = (
        timezone.now(), timezone.localdate(), utente)  # fmt: skip
    richiesta.save()  # via API: da qui la federazione la legge nel flusso «tessere»
    registra(Azione.MODIFICA, richiesta, utente=utente, inviata=canale,
             descrizione=f"Richiesta di tessere inviata ({canale}): {richiesta}")  # fmt: skip
    return canale, None


# --- ordine al nazionale per email -------------------------------------------------------------


def pdf_ordine(ordine) -> bytes:
    from apps.core.pdf import genera_pdf

    voce = listino(ordine.anno)
    totale = (voce.costo_acquisto * ordine.quantita) if voce else None
    return genera_pdf("soci/pdf/ordine_tessere.html", {
        "organizzazione": Organizzazione.corrente(), "ordine": ordine, "listino": voce,
        "totale": totale,
    })  # fmt: skip


def prepara_ordine_email(utente, ordine, *, servizio=None, protocolla=True):
    """L'ordine alla sede nazionale in bozza email, con il PDF allegato (da controllare e
    spedire: non parte da solo)."""
    from apps.comunicazioni import servizi as comunicazioni
    from apps.comunicazioni.models import Finalita, Modello

    org = Organizzazione.corrente()
    if not org.nazionale_email:
        raise OperazioneNonValida(
            "Manca l'email della sede nazionale: indicarla in Sistema → Organizzazione."
        )
    modello = Modello.objects.filter(uso="ordine_tess", attivo=True).order_by("pk").first()
    if modello is None:
        raise OperazioneNonValida("Manca il modello «Ordine di tessere alla sede nazionale».")
    contesto = {
        "anno": ordine.anno, "numero": f"{ordine.anno}/{ordine.numero}",
        "data": f"{ordine.data:%d/%m/%Y}", "quantita": ordine.quantita,
        "federazione": org.federazione or org.denominazione, "note_ordine": ordine.note,
        "organizzazione": org.denominazione,
    }  # fmt: skip
    try:
        return comunicazioni.crea_invio(
            utente, oggetto=modello.oggetto, corpo=modello.corpo,
            finalita=Finalita.ISTITUZIONALE, indirizzi=[("Sede nazionale", org.nazionale_email)],
            modello=modello, protocolla=protocolla, origine="tessere_ordine",
            origine_id=ordine.pk, contesto=contesto, servizio=servizio,
            allegati=[(f"ordine-tessere-{ordine.anno}-{ordine.numero}.pdf", pdf_ordine(ordine))],
        )  # fmt: skip
    except comunicazioni.OperazioneNonValida as e:
        raise OperazioneNonValida(" ".join(e.messages)) from None


# --- pagamenti delle tessere al livello superiore --------------------------------------------

VOCE_TESSERE = "U.A.1.2"  # sottovoce «Acquisto delle tessere» del piano dei conti


def voce_tessere():
    from apps.tesoreria.models import Voce

    return Voce.objects.filter(codice=VOCE_TESSERE, attiva=True).first()


def destinatario_pagamenti():
    from .sezioni import multisezione

    if multisezione():
        return "Sede nazionale"
    org = Organizzazione.corrente()
    return f"Federazione {org.federazione}".strip() if org.federazione else "Federazione"


@transaction.atomic
def registra_pagamento(utente, *, anno, data, importo, conto, riferimento="", ordine=None,
                       documento=None, giustificativo=None):  # fmt: skip
    """Uscita in prima nota per le tessere dell'anno pagate al livello superiore (acconto o
    saldo; il resto rimane da pagare). Da un ordine (federazione) o da una ricevuta arrivata
    (sezione), che diventa il giustificativo."""
    from apps.tesoreria import servizi as tesoreria
    from apps.tesoreria.models import Movimento

    voce = voce_tessere()
    if voce is None:
        raise OperazioneNonValida(
            f"Manca la voce {VOCE_TESSERE} «Acquisto delle tessere» nel piano dei conti."
        )
    if importo is None or importo <= 0:
        raise OperazioneNonValida("Indicare un importo maggiore di zero.")
    if documento is not None and documento.movimento_id:
        raise OperazioneNonValida("Per questa ricevuta l'uscita è già registrata.")
    cosa = f"ordine n. {ordine.anno}/{ordine.numero}" if ordine else (
        f"ricevuta n. {documento.dati.get('ricevuta')}" if documento else "pagamento")  # fmt: skip
    dati = {
        "data": data, "tipo": Movimento.Tipo.USCITA, "conto": conto, "importo": importo,
        "voce": voce, "descrizione": f"Tessere {anno}: {cosa}"[:255],
        "controparte_testo": destinatario_pagamenti()[:200], "documento": riferimento[:100],
        "anno_tessere": anno, "ordine_tessere": ordine,
    }  # fmt: skip
    if giustificativo is None and documento is not None and documento.pdf:
        from django.core.files.base import ContentFile

        with documento.pdf.open("rb") as f:
            giustificativo = ContentFile(f.read(), name=f"ricevuta-{documento.uuid_origine}.pdf")
    try:
        movimento = tesoreria.registra_movimento(dati, utente, giustificativo=giustificativo)
    except tesoreria.OperazioneNonValida as e:
        raise OperazioneNonValida(" ".join(e.messages)) from None
    if documento is not None:
        documento.movimento = movimento
        documento.save(update_fields=["movimento"])
    return movimento


def quadratura_superiore(anno):
    """Debito verso il livello superiore per le tessere dell'anno: dovuto, pagato, da pagare.
    Federazione: tessere ordinate al nazionale × costo nazionale; sezione: tessere ricevute
    dalla federazione × costo per tessera dei lotti."""
    from apps.tesoreria.models import Movimento

    from .servizi import FORNITORE_REGISTRO
    from .sezioni import multisezione

    pagamenti = Movimento.objects.filter(anno_tessere=anno, tipo=Movimento.Tipo.USCITA,
                                         annullato=False).order_by("data", "numero")  # fmt: skip
    pagato = sum((m.importo for m in pagamenti), Decimal("0"))
    if multisezione():
        quantita = sum(OrdineTessere.objects.filter(anno=anno).values_list("quantita", flat=True))
        voce = listino(anno)
        dovuto = (voce.costo_acquisto * quantita) if voce else Decimal("0")
        descrizione = "tessere ordinate alla sede nazionale"
    else:
        lotti = list(LottoTessere.objects.filter(anno=anno).exclude(fornitore=FORNITORE_REGISTRO))
        quantita = sum(lotto.quantita for lotto in lotti)
        dovuto = sum((lotto.quantita * lotto.costo_unitario for lotto in lotti), Decimal("0"))
        descrizione = "tessere ricevute dalla federazione"
    return {
        "destinatario": destinatario_pagamenti(), "descrizione": descrizione,
        "quantita": quantita, "dovuto": dovuto, "pagato": pagato, "da_pagare": dovuto - pagato,
        "pagamenti": list(pagamenti.select_related("conto", "ordine_tessere")),
    }  # fmt: skip


# --- fasi della campagna: verso le sezioni e verso l'ente sovraordinato ----------------------


@dataclass
class Fase:
    numero: int
    titolo: str
    stato: str  # «fatto», «in_corso», «da_fare»
    sintesi: str
    ancora: str


def _stato(fatti, totale):
    if totale and fatti >= totale:
        return "fatto"
    return "in_corso" if fatti else "da_fare"


def e_federazione():
    from .sezioni import multisezione

    return multisezione()


def nome_superiore():
    """Ente sovraordinato, senza articolo (nei testi: «verso la», «dalla», «alla»)."""
    return "sede nazionale" if e_federazione() else "Federazione"


def invito(anno):
    return InvitoTessere.objects.filter(anno=anno).select_related("protocollo").first()


def invito_suggerito(anno):
    """Protocollo in entrata che sembra l'invito dell'anno (oggetto «Tesseramento <anno>»), per
    collegarlo con un clic; i solleciti vengono dopo l'avviso."""
    from apps.protocollo.models import Protocollo

    candidati = Protocollo.objects.filter(
        direzione=Protocollo.Direzione.ENTRATA, annullato=False,
        oggetto__icontains=f"tesseramento {anno}",
    ).order_by("registrato_il")  # fmt: skip
    return candidati.exclude(oggetto__icontains="sollecito").first() or candidati.first()


@transaction.atomic
def registra_invito(utente, *, anno, ricevuto_il, protocollo=None, note=""):
    voce, nuovo = InvitoTessere.objects.update_or_create(
        anno=anno, defaults={"protocollo": protocollo, "ricevuto_il": ricevuto_il, "note": note,
                             "modificato_da": utente},
    )  # fmt: skip
    if nuovo:
        voce.creato_da = utente
        voce.save(update_fields=["creato_da"])
    registra(Azione.CREAZIONE if nuovo else Azione.MODIFICA, voce, utente=utente,
             protocollo=protocollo.segnatura if protocollo else "")  # fmt: skip
    return voce


def _avvisate(anno, origine):
    """Sezioni a cui è partito l'avviso (o il sollecito) dell'anno."""
    from apps.comunicazioni.models import Invio

    partiti = [Invio.Stato.INVIATO, Invio.Stato.CON_ERRORI, Invio.Stato.IN_CODA]
    invii = Invio.objects.filter(origine=origine, stato__in=partiti)
    return {i.origine_id for i in invii if (i.contesto or {}).get("anno") == anno}


def richieste_in_arrivo(anno=None):
    """Richieste arrivate dal collegamento e non ancora registrate (da confermare)."""
    from apps.api.models import DocumentoRicevuto

    documenti = DocumentoRicevuto.objects.filter(
        tipo=DocumentoRicevuto.Tipo.RICHIESTA, stato=DocumentoRicevuto.Stato.DA_ESAMINARE
    ).select_related("cliente__sezione")
    return [d for d in documenti if anno is None or d.dati.get("anno") == anno]


def stato_inviti(anno):
    """Per ogni sezione attiva: avviso e sollecito partiti, richiesta registrata o arrivata dal
    collegamento e ancora da registrare."""
    avviso, sollecito = _avvisate(anno, "tessere_avviso"), _avvisate(anno, "tessere_sollecito")
    in_arrivo = {d.cliente.sezione_id for d in richieste_in_arrivo(anno)}
    con_richiesta = set(RichiestaTessere.objects.filter(
        anno=anno, inviata_il__isnull=False).values_list("sezione_id", flat=True))  # fmt: skip
    return [
        {"sezione": s, "avviso": s.pk in avviso, "sollecito": s.pk in sollecito,
         "richiesta": s.pk in con_richiesta, "in_arrivo": s.pk in in_arrivo}
        for s in Sezione.objects.filter(attiva=True)
    ]  # fmt: skip


def conferme_inviate(richieste):
    from apps.comunicazioni.models import Invio

    return set(Invio.objects.filter(
        origine=ORIGINE_CONFERMA, origine_id__in=[r.pk for r in richieste],
    ).exclude(stato=Invio.Stato.ANNULLATO).values_list("origine_id", flat=True))  # fmt: skip


def fasi_verso_sezioni(anno):
    """Federazione: invito alle sezioni, richieste ricevute (con la conferma), consegne, incassi."""
    stati = stato_inviti(anno)
    attive = len(stati)
    avvisate = sum(1 for s in stati if s["avviso"])
    richieste = list(RichiestaTessere.objects.filter(anno=anno, inviata_il__isnull=False))
    con_richiesta = sum(1 for s in stati if s["richiesta"])
    confermate = len(conferme_inviate(richieste))
    da_registrare = len(richieste_in_arrivo(anno))
    righe = quadratura(anno)
    richiesto = sum(r.richieste for r in righe)
    consegnato = sum(r.consegnate for r in righe)
    dovuto = sum((r.dovuto for r in righe), Decimal("0"))
    pagato = sum((r.pagato for r in righe), Decimal("0"))
    return [
        Fase(1, "Invito alla richiesta", _stato(avvisate, attive),
             f"avvisate {avvisate} sezioni su {attive}", "invito-sezioni"),
        Fase(2, "Richieste ricevute",
             "in_corso" if da_registrare else _stato(con_richiesta, attive),
             f"{con_richiesta} sezioni su {attive}, {richiesto} tessere; confermate "
             f"{confermate} su {len(richieste)}"
             + (f"; da registrare {da_registrare}" if da_registrare else ""),
             "richieste-sezioni"),
        Fase(3, "Consegna alle sezioni", _stato(consegnato, richiesto),
             f"consegnate {consegnato} tessere su {richiesto}", "consegne-sezioni"),
        Fase(4, "Incassi dalle sezioni", _stato(pagato, dovuto) if dovuto else "da_fare",
             f"versati € {pagato:.2f} su € {dovuto:.2f}", "incassi-sezioni"),
    ]  # fmt: skip


def fasi_verso_superiore(anno):
    """Verso l'ente sovraordinato: invito ricevuto, richiesta (sezione) o ordine al nazionale
    (federazione), ricevimento delle tessere, pagamento."""
    federazione = e_federazione()
    voce = invito(anno)
    superiore = quadratura_superiore(anno)
    if federazione:
        ordinato = sum(OrdineTessere.objects.filter(anno=anno).values_list("quantita", flat=True))
        mancano = sum(r["quantita"] for r in da_ordinare(anno))
        richiesta = Fase(2, "Ordine alla sede nazionale",
                         "fatto" if ordinato and not mancano else ("in_corso" if ordinato
                                                                   else "da_fare"),
                         f"ordinate {ordinato} tessere" + (f", da ordinare {mancano}" if mancano
                                                           else ""), "ordini")  # fmt: skip
        ricevute = riepilogo_magazzino(anno)["ricevute"]
        ricevimento = Fase(
            3,
            "Tessere ricevute dal nazionale",
            _stato(ricevute, ordinato),
            f"in magazzino {ricevute} su {ordinato} ordinate",
            "magazzino",
        )
    else:
        inviate = RichiestaTessere.objects.filter(anno=anno, inviata_il__isnull=False)
        chieste = sum(inviate.values_list("quantita", flat=True))
        bozza = RichiestaTessere.objects.filter(anno=anno, inviata_il__isnull=True,
                                                uuid_origine__isnull=True).first()  # fmt: skip
        richiesta = Fase(2, "Richiesta alla Federazione",
                         "fatto" if chieste and not bozza else ("in_corso" if chieste or bozza
                                                                else "da_fare"),
                         f"inviate {chieste} tessere"
                         + (f", in preparazione {bozza.quantita}" if bozza else ""),
                         "richiesta")  # fmt: skip
        ricevute = superiore["quantita"]
        ricevimento = Fase(
            3,
            "Tessere ricevute dalla Federazione",
            _stato(ricevute, chieste),
            f"ricevute {ricevute} su {chieste} chieste",
            "ricevimento",
        )
    return [
        Fase(1, "Invito ricevuto", "fatto" if voce else "da_fare",
             str(voce) if voce else "da collegare al protocollo in entrata", "invito"),
        richiesta,
        ricevimento,
        Fase(4, f"Pagamento alla {nome_superiore()}",
             _stato(superiore["pagato"], superiore["dovuto"]) if superiore["dovuto"]
             else "da_fare",
             f"pagati € {superiore['pagato']:.2f} su € {superiore['dovuto']:.2f}", "pagamento"),
    ]  # fmt: skip
