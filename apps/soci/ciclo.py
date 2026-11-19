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
            modello=modello, protocolla=protocolla, origine="tessere_richiesta",
            origine_id=richiesta.pk, contesto=contesto, servizio=servizio,
            allegati=[(f"richiesta-tessere-{richiesta.anno}.pdf", pdf)],
        )  # fmt: skip
    except comunicazioni.OperazioneNonValida as e:
        raise OperazioneNonValida(" ".join(e.messages)) from None
    return invio


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


def in_preparazione(anno, sezione):
    return RichiestaTessere.objects.filter(
        anno=anno, sezione=sezione, inviata_il__isnull=True, uuid_origine__isnull=True
    ).first()


@transaction.atomic
def aggiorna_in_preparazione(utente, anno, sezione):
    """Porta la richiesta in preparazione dell'anno al fabbisogno calcolato (la crea, o la
    toglie se non serve più). Non parte mai da sola. Restituisce (richiesta o None, calcolo)."""
    calcolo = fabbisogno(anno, sezione)
    bozza = in_preparazione(anno, sezione)
    if not calcolo["proposta"]:
        if bozza:
            registra(Azione.ELIMINAZIONE, bozza, utente=utente,
                     descrizione=f"Richiesta in preparazione tolta: {bozza}")  # fmt: skip
            bozza.delete()
        return None, calcolo
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
    invio = None
    if canale == "email":
        invio = prepara_risposta(utente, richiesta)  # bozza da controllare e spedire
    richiesta.inviata_il, richiesta.data, richiesta.modificato_da = (
        timezone.now(), timezone.localdate(), utente)  # fmt: skip
    richiesta.save()  # via API: da qui la federazione la legge nel flusso «tessere»
    registra(Azione.MODIFICA, richiesta, utente=utente, inviata=canale,
             descrizione=f"Richiesta di tessere inviata ({canale}): {richiesta}")  # fmt: skip
    return canale, invio


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
