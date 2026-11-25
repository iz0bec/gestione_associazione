# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Rendicontazione e chiusura dei progetti (P6): rendiconto per il finanziatore con i
# *              giustificativi numerati (PDF, Excel, archivio ZIP), relazione finale guidata
# *              (senza IA), verifica prima della chiusura, riuso di un progetto come modello.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import zipfile
from dataclasses import dataclass, field
from decimal import Decimal
from io import BytesIO
from pathlib import PurePath

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.core.audit import Azione, registra

from . import esecuzione
from .models import Imputazione, TestoSezione

ZERO = Decimal("0.00")

SCHEMA_RELAZIONE = [
    (
        "svolte",
        "Attività svolte",
        "Che cosa è stato realizzato, quando e dove?\n"
        "Che cosa è cambiato rispetto al cronoprogramma, e perché?",
    ),
    (
        "risultati",
        "Risultati raggiunti",
        "Quali risultati sono stati ottenuti rispetto a quelli attesi?\n"
        "Che cosa dicono gli indicatori?",
    ),
    (
        "destinatari",
        "Destinatari raggiunti",
        "Quante persone sono state coinvolte e come?\n"
        "Quali riscontri sono arrivati (questionari, testimonianze)?",
    ),
    (
        "volontariato",
        "Volontariato e partenariato",
        "Quanti volontari e quante ore?\nChe cosa hanno fatto i partner?",
    ),
    (
        "criticita",
        "Criticità e soluzioni",
        "Quali difficoltà si sono incontrate?\nCome sono state affrontate?",
    ),
    (
        "comunicazione",
        "Comunicazione e diffusione dei risultati",
        "Come è stato fatto conoscere il progetto (eventi, stampa, sito, social)?",
    ),
    (
        "prospettive",
        "Sostenibilità e prospettive",
        "Che cosa resta dopo il progetto?\nSi può ripetere o estendere?",
    ),
]

COMPONIBILI = {"svolte", "risultati", "volontariato"}


class ErroreRendiconto(Exception):
    pass


# --- relazione finale ----------------------------------------------------------------------------


@transaction.atomic
def prepara_relazione(progetto):
    presenti = {s.titolo for s in progetto.sezioni_relazione}
    ordine = len(presenti)
    for chiave, titolo, domande in SCHEMA_RELAZIONE:
        if titolo not in presenti:
            ordine += 1
            TestoSezione.objects.create(
                progetto=progetto,
                documento="relazione",
                chiave=chiave,
                titolo=titolo,
                domande=domande,
                ordine=ordine,
            )
    return list(progetto.sezioni_relazione)


def componi(progetto, chiave):
    """Testo di partenza dai dati dell'esecuzione (da rivedere)."""
    if chiave == "svolte":
        attivita = list(progetto.attivita.all())
        if not attivita:
            raise ErroreRendiconto("Il cronoprogramma non ha attività.")
        righe = [
            f"- {a.titolo} ({a.inizio:%d/%m/%Y} – {a.fine:%d/%m/%Y})"
            + ("" if a.completata else " – non completata")
            for a in attivita
        ]
        eventi = [f"- {e}" for e in progetto.eventi.all()]
        testo = "Attività del progetto:\n" + "\n".join(righe)
        if eventi:
            testo += "\n\nEventi realizzati:\n" + "\n".join(eventi)
        return testo
    if chiave == "risultati":
        indicatori = list(progetto.indicatori.all())
        if not indicatori:
            raise ErroreRendiconto("Il quadro non ha indicatori.")
        righe = []
        for x in indicatori:
            atteso = f"{x.valore_atteso.normalize():f} {x.unita}".strip()
            if x.valore_raggiunto is None:
                righe.append(f"- {x.descrizione}: atteso {atteso}, valore raggiunto da indicare")
            else:
                raggiunto = f"{x.valore_raggiunto.normalize():f} {x.unita}".strip()
                righe.append(f"- {x.descrizione}: atteso {atteso}, raggiunto {raggiunto}")
        return "Risultati misurati dagli indicatori:\n" + "\n".join(righe)
    if chiave == "volontariato":
        c = esecuzione.consuntivo(progetto)
        persone = progetto.ore.values("soggetto").distinct().count()
        parti = []
        if c.ore:
            parti.append(
                f"Hanno partecipato {persone} volontari per {c.ore.normalize():f} ore"
                + (f", valorizzate in € {c.natura_consuntivo}" if c.tariffa else "")
                + "."
            )
        partner = [
            f"- {p.soggetto} ({p.get_ruolo_display().lower()})"
            for p in progetto.partner.select_related("soggetto")
        ]
        if partner:
            parti.append("Partner del progetto:\n" + "\n".join(partner))
        if not parti:
            raise ErroreRendiconto("Non ci sono ore di volontariato né partner registrati.")
        return "\n\n".join(parti)
    raise ErroreRendiconto("Per questa sezione non c'è un testo da comporre.")


# --- rendiconto ----------------------------------------------------------------------------------


@dataclass
class Spesa:
    numero: int  # numero del giustificativo nell'archivio (0 = senza giustificativo)
    imputazione: Imputazione

    @property
    def movimento(self):
        return self.imputazione.movimento

    @property
    def nome_file(self):
        if not self.numero:
            return ""
        estensione = PurePath(self.movimento.giustificativo.name).suffix.lower()
        return f"giustificativi/{self.numero:03d}-{self.movimento.data:%Y%m%d}{estensione}"


@dataclass
class Rendiconto:
    voci: list = field(default_factory=list)  # [(voce o None, preventivo, [Spesa], totale)]
    entrate: list = field(default_factory=list)  # [Imputazione]
    ore: list = field(default_factory=list)  # [(soggetto, ore)]
    consuntivo: object = None

    @property
    def spese(self):
        return [s for _, _, elenco, _ in self.voci for s in elenco]

    @property
    def senza_giustificativo(self):
        return [s for s in self.spese if not s.numero]


def calcola(progetto):
    r = Rendiconto(consuntivo=esecuzione.consuntivo(progetto))
    costi = list(
        progetto.imputazioni.filter(tipo=Imputazione.Tipo.COSTO)
        .select_related("movimento__controparte", "voce")
        .order_by("movimento__data", "pk")
    )
    numero = 0
    spese = {}
    for imp in costi:
        if imp.movimento.giustificativo:
            numero += 1
            spese[imp.pk] = Spesa(numero, imp)
        else:
            spese[imp.pk] = Spesa(0, imp)
    for v in progetto.voci.exclude(categoria="volontariato"):
        elenco = [spese[i.pk] for i in costi if i.voce_id == v.pk]
        r.voci.append((v, v.importo, elenco, sum((s.imputazione.importo for s in elenco), ZERO)))
    senza = [spese[i.pk] for i in costi if i.voce_id is None]
    if senza:
        r.voci.append((None, ZERO, senza, sum((s.imputazione.importo for s in senza), ZERO)))
    r.entrate = list(
        progetto.imputazioni.exclude(tipo=Imputazione.Tipo.COSTO)
        .select_related("movimento")
        .order_by("movimento__data")
    )
    r.ore = [
        (x["soggetto__cognome"], x["soggetto__nome"], x["totale"])
        for x in progetto.ore.values("soggetto__cognome", "soggetto__nome")
        .annotate(totale=Sum("ore"))
        .order_by("soggetto__cognome", "soggetto__nome")
    ]
    return r


def verifica_chiusura(progetto):
    """Promemoria prima di chiudere il progetto (non bloccano: decide il consiglio)."""
    from .proposta import Voce

    v = []
    av = esecuzione.avanzamento(progetto)
    if av["completate"] < av["attivita"]:
        v.append(Voce("avviso", f"Attività non completate: {av['attivita'] - av['completate']}."))
    if progetto.indicatori.filter(valore_raggiunto__isnull=True).exists():
        v.append(Voce("avviso", "Alcuni indicatori non hanno il valore raggiunto."))
    r = calcola(progetto)
    if r.senza_giustificativo:
        v.append(
            Voce(
                "errore",
                f"Spese senza giustificativo in prima nota: {len(r.senza_giustificativo)}.",
            )
        )
    if r.consuntivo.contributo_da_incassare > 0:
        v.append(
            Voce(
                "avviso",
                f"Contributo ancora da incassare: € {r.consuntivo.contributo_da_incassare}.",
            )
        )
    vuote = [s.titolo for s in progetto.sezioni_relazione if not s.testo.strip()]
    if not progetto.sezioni_relazione.exists():
        v.append(Voce("errore", "La relazione finale non è stata scritta."))
    elif vuote:
        v.append(Voce("errore", f"Sezioni della relazione da scrivere: {', '.join(vuote)}."))
    if progetto.varianti.filter(chiusa_il__isnull=True).exists():
        v.append(Voce("errore", "C'è una variante al piano ancora aperta."))
    if not v:
        v.append(Voce("ok", "Rendiconto e relazione sono completi."))
    return v


def _contesto(progetto):
    from apps.core.models import Organizzazione

    return {
        "organizzazione": Organizzazione.corrente(),
        "progetto": progetto,
        "rendiconto": calcola(progetto),
        "avanzamento": esecuzione.avanzamento(progetto),
        "relazione": list(progetto.sezioni_relazione),
        "indicatori": progetto.indicatori.all(),
        "oggi": timezone.localdate(),
    }


def rendiconto_pdf(progetto):
    from apps.core.pdf import genera_pdf

    return genera_pdf("progetti/pdf/rendiconto.html", _contesto(progetto))


def relazione_pdf(progetto):
    from apps.core.pdf import genera_pdf

    return genera_pdf("progetti/pdf/relazione.html", _contesto(progetto))


def rendiconto_excel(progetto):
    from openpyxl import Workbook
    from openpyxl.styles import Font

    r = calcola(progetto)
    grassetto = Font(bold=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "Spese"
    ws.append([f"Rendiconto {progetto.codice} — {progetto.titolo}"])
    ws["A1"].font = Font(bold=True, size=13)
    ws.append([])
    ws.append(
        [
            "Voce",
            "N. giustificativo",
            "Data",
            "Descrizione",
            "Controparte",
            "Documento",
            "Importo imputato",
            "Preventivo voce",
        ]
    )
    for c in ws[ws.max_row]:
        c.font = grassetto
    for voce, preventivo, elenco, totale in r.voci:
        nome = voce.descrizione if voce else "Spese senza voce"
        for s in elenco:
            m = s.movimento
            ws.append(
                [
                    nome,
                    s.numero or "",
                    m.data,
                    m.descrizione,
                    str(m.controparte) if m.controparte_id else m.controparte_testo,
                    m.documento,
                    float(s.imputazione.importo),
                    None,
                ]
            )
        ws.append(
            [
                f"Totale {nome}",
                None,
                None,
                None,
                None,
                None,
                float(totale),
                float(preventivo) if voce else None,
            ]
        )
        ws.cell(ws.max_row, 1).font = grassetto
    c = r.consuntivo
    ws.append([])
    ws.append(
        [
            "TOTALE SPESE",
            None,
            None,
            None,
            None,
            None,
            float(c.costi_consuntivo),
            float(c.costi_preventivo),
        ]
    )
    ws.cell(ws.max_row, 1).font = grassetto
    for colonna, larghezza in zip("ABCDEFGH", (30, 10, 12, 45, 28, 18, 16, 16), strict=True):
        ws.column_dimensions[colonna].width = larghezza
    for riga in ws.iter_rows(min_col=7, max_col=8):
        for cella in riga:
            if isinstance(cella.value, float):
                cella.number_format = '#,##0.00 "€"'
    for riga in ws.iter_rows(min_col=3, max_col=3):
        for cella in riga:
            if hasattr(cella.value, "year"):
                cella.number_format = "DD/MM/YYYY"
    vo = wb.create_sheet("Volontariato")
    vo.append(["Cognome", "Nome", "Ore", "Tariffa", "Valorizzato"])
    for x in vo[1]:
        x.font = grassetto
    for cognome, nome, ore in r.ore:
        valore = float(ore * c.tariffa) if c.tariffa else None
        vo.append([cognome, nome, float(ore), float(c.tariffa) if c.tariffa else None, valore])
    vo.append(["Totale", None, float(c.ore), None, float(c.natura_consuntivo)])
    en = wb.create_sheet("Entrate")
    en.append(["Data", "Descrizione", "Tipo", "Importo"])
    for x in en[1]:
        x.font = grassetto
    for i in r.entrate:
        en.append(
            [i.movimento.data, i.movimento.descrizione, i.get_tipo_display(), float(i.importo)]
        )
    uscita = BytesIO()
    wb.save(uscita)
    return uscita.getvalue()


def archivio_zip(progetto, utente):
    """Rendiconto, relazione, Excel e i giustificativi numerati come nel rendiconto."""
    r = calcola(progetto)
    uscita = BytesIO()
    base = f"{progetto.codice}-rendiconto"
    with zipfile.ZipFile(uscita, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"{base}/rendiconto.pdf", rendiconto_pdf(progetto))
        z.writestr(f"{base}/rendiconto.xlsx", rendiconto_excel(progetto))
        if progetto.sezioni_relazione.exists():
            z.writestr(f"{base}/relazione-finale.pdf", relazione_pdf(progetto))
        for s in r.spese:
            if s.numero:
                with s.movimento.giustificativo.open("rb") as f:
                    z.writestr(f"{base}/{s.nome_file}", f.read())
    registra(
        Azione.ESPORTAZIONE,
        progetto,
        utente=utente,
        documento="archivio del rendiconto",
        giustificativi=sum(1 for s in r.spese if s.numero),
    )
    return uscita.getvalue()


# --- riuso ---------------------------------------------------------------------------------------


@transaction.atomic
def riusa(progetto, utente, *, titolo):
    """Nuovo progetto in progettazione con quadro, attività (date spostate a oggi), piano e testi
    della proposta di un progetto esistente. Gruppo, partner, bando ed esecuzione non si copiano."""
    from . import servizi
    from .forms import ProgettoForm

    titolo = titolo.strip() or f"{progetto.titolo} (nuovo)"
    dati = {
        "titolo": titolo[:200],
        "sintesi": progetto.sintesi,
        "responsabile": utente.pk,
        "finalita": [f.pk for f in progetto.finalita.all()],
    }
    form = ProgettoForm(data=dati)
    if not form.is_valid():
        raise ErroreRendiconto("Dati del progetto non validi.")
    nuovo = servizi.crea_progetto(form, utente)
    nuovo.obiettivo_generale, nuovo.destinatari = progetto.obiettivo_generale, progetto.destinatari
    nuovo.territorio, nuovo.spese_generali = progetto.territorio, progetto.spese_generali
    nuovo.tariffa_volontariato = progetto.tariffa_volontariato
    nuovo.save()
    obiettivi = {}
    for o in progetto.obiettivi.all():
        obiettivi[o.pk] = nuovo.obiettivi.create(
            testo=o.testo, risultati=o.risultati, ordine=o.ordine
        )
    for x in progetto.indicatori.all():
        nuovo.indicatori.create(
            obiettivo=obiettivi.get(x.obiettivo_id),
            descrizione=x.descrizione,
            unita=x.unita,
            valore_iniziale=x.valore_iniziale,
            valore_atteso=x.valore_atteso,
            fonte_verifica=x.fonte_verifica,
        )
    attivita = list(progetto.attivita.all())
    if attivita:
        spostamento = timezone.localdate() - min(a.inizio for a in attivita)
        copie = {}
        for a in attivita:
            copie[a.pk] = nuovo.attivita.create(
                titolo=a.titolo,
                descrizione=a.descrizione,
                obiettivo=obiettivi.get(a.obiettivo_id),
                inizio=a.inizio + spostamento,
                fine=a.fine + spostamento,
            )
        for a in attivita:
            if a.dopo_id in copie:
                copia = copie[a.pk]
                copia.dopo = copie[a.dopo_id]
                copia.save(update_fields=["dopo"])
    for v in progetto.voci.all():
        nuovo.voci.create(
            categoria=v.categoria,
            descrizione=v.descrizione,
            quantita=v.quantita,
            unita=v.unita,
            costo_unitario=v.costo_unitario,
            ordine=v.ordine,
        )
    for s in progetto.sezioni_proposta:
        nuovo.sezioni.create(
            documento="proposta",
            chiave=s.chiave,
            titolo=s.titolo,
            domande=s.domande,
            massimo_caratteri=s.massimo_caratteri,
            testo=s.testo,
            ordine=s.ordine,
        )
    registra(Azione.CREAZIONE, nuovo, utente=utente, riuso=progetto.codice)
    return nuovo
