# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Candidatura (P4b): scrittura guidata della proposta (senza IA: domande guida,
# *              testi composti dai dati del progetto, riuso dei testi), verifica prima dell'invio,
# *              piano economico in Excel, protocollo in uscita della candidatura.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from dataclasses import dataclass
from io import BytesIO

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from apps.core.audit import Azione, registra

from . import piano as piano_economico
from .models import Allegato, Progetto, TestoSezione

# chiave, titolo, domande guida (una per riga)
SCHEMA = [
    (
        "contesto",
        "Contesto e bisogni",
        "Qual è il problema o il bisogno a cui risponde il progetto?\n"
        "Quali dati o testimonianze lo dimostrano?\n"
        "Perché proprio ora e su questo territorio?",
    ),
    (
        "finalita",
        "Coerenza con le finalità statutarie",
        "A quali scopi dello statuto risponde il progetto?\n"
        "Come si lega alle attività abituali dell'associazione?",
    ),
    (
        "obiettivi",
        "Obiettivi e risultati attesi",
        "Qual è l'obiettivo generale?\n"
        "Quali obiettivi specifici, misurabili, e quali risultati concreti?",
    ),
    (
        "destinatari",
        "Destinatari e territorio",
        "Chi ne beneficia direttamente e indirettamente, e quanti sono?\nCome verranno coinvolti?",
    ),
    (
        "attivita",
        "Attività e metodologia",
        "Quali attività, in che ordine e con quali tempi?\nChi le svolge e con quale metodo?",
    ),
    (
        "partenariato",
        "Partenariato",
        "Chi partecipa e con quale ruolo?\nChe cosa porta ciascun partner al progetto?",
    ),
    (
        "esperienza",
        "Esperienza dell'associazione",
        "Quali progetti o iniziative simili ha già realizzato l'associazione?\n"
        "Con quali risultati?",
    ),
    (
        "monitoraggio",
        "Monitoraggio e valutazione",
        "Come si misurano i risultati (indicatori, strumenti, tempi)?\nChi se ne occupa?",
    ),
    (
        "comunicazione",
        "Comunicazione e diffusione",
        "Come si farà conoscere il progetto e i suoi risultati?\n"
        "Con quali canali (sito, stampa, social, eventi)?",
    ),
    (
        "sostenibilita",
        "Impatto e sostenibilità",
        "Che cosa resterà dopo la fine del finanziamento?\n"
        "Il progetto può essere ripetuto o esteso?",
    ),
]

COMPONIBILI = {"finalita", "obiettivi", "destinatari", "attivita", "partenariato", "monitoraggio"}


class ErroreProposta(Exception):
    pass


# --- sezioni -------------------------------------------------------------------------------------


@transaction.atomic
def prepara_sezioni(progetto):
    """Crea le sezioni mancanti: quelle del bando collegato, se le indica, o lo schema predefinito.
    Non tocca i testi già scritti. Restituisce le sezioni del progetto."""
    presenti = {s.titolo for s in progetto.sezioni.all()}
    ordine = len(presenti)
    if progetto.bando_id and progetto.bando.sezioni.exists():
        modello = [
            ("", s.titolo, s.domande, s.massimo_caratteri) for s in progetto.bando.sezioni.all()
        ]
    else:
        modello = [(chiave, titolo, domande, None) for chiave, titolo, domande in SCHEMA]
    for chiave, titolo, domande, massimo in modello:
        if titolo in presenti:
            continue
        if (
            not chiave
        ):  # una sezione del bando con il titolo di una predefinita ne eredita le proposte
            chiave = next((k for k, t, _ in SCHEMA if t.lower() == titolo.lower()), "")
        ordine += 1
        TestoSezione.objects.create(
            progetto=progetto,
            chiave=chiave,
            titolo=titolo,
            domande=domande,
            massimo_caratteri=massimo,
            ordine=ordine,
        )
    return list(progetto.sezioni.all())


def _elenco(righe):
    return "\n".join(f"- {r}" for r in righe if r)


def componi(progetto, chiave):
    """Testo proposto per una sezione, composto dai dati del progetto (da rivedere a mano)."""
    if chiave == "finalita":
        finalita = list(progetto.finalita.all())
        if not finalita:
            raise ErroreProposta("Il progetto non indica le finalità statutarie.")
        righe = [f"{f.codice + ') ' if f.codice else ''}{f.testo or f.titolo}" for f in finalita]
        return (
            "Il progetto risponde alle seguenti finalità dello statuto dell'associazione:\n"
            + _elenco(righe)
        )
    if chiave == "obiettivi":
        if not progetto.obiettivo_generale and not progetto.obiettivi.exists():
            raise ErroreProposta("Il quadro del progetto è ancora vuoto.")
        parti = []
        if progetto.obiettivo_generale:
            parti.append(f"Obiettivo generale: {progetto.obiettivo_generale}")
        for i, o in enumerate(progetto.obiettivi.all(), 1):
            parti.append(f"Obiettivo specifico {i}: {o.testo}")
            if o.risultati:
                parti.append(f"Risultati attesi: {o.risultati}")
        return "\n\n".join(parti)
    if chiave == "destinatari":
        if not (progetto.destinatari or progetto.territorio):
            raise ErroreProposta("Destinatari e territorio non sono indicati nel quadro.")
        parti = [progetto.destinatari]
        if progetto.territorio:
            parti.append(f"Territorio: {progetto.territorio}.")
        return "\n\n".join(p for p in parti if p)
    if chiave == "attivita":
        attivita = list(progetto.attivita.select_related("responsabile"))
        if not attivita:
            raise ErroreProposta("Il cronoprogramma non ha attività.")
        righe = []
        for a in attivita:
            riga = f"{a.titolo} ({a.inizio:%d/%m/%Y} – {a.fine:%d/%m/%Y})"
            if a.descrizione:
                riga += f": {a.descrizione}"
            righe.append(riga)
        return "Il progetto si articola nelle seguenti attività:\n" + _elenco(righe)
    if chiave == "partenariato":
        partner = list(progetto.partner.select_related("soggetto"))
        if not partner:
            raise ErroreProposta("Il progetto non ha partner.")
        righe = [
            f"{p.soggetto} ({p.get_ruolo_display().lower()})"
            + (f": {p.contributo}" if p.contributo else "")
            for p in partner
        ]
        return "Partecipano al progetto:\n" + _elenco(righe)
    if chiave == "monitoraggio":
        indicatori = list(progetto.indicatori.all())
        if not indicatori:
            raise ErroreProposta("Il quadro non ha indicatori.")
        righe = []
        for x in indicatori:
            riga = (
                f"{x.descrizione}: valore atteso {x.valore_atteso.normalize():f} {x.unita}".strip()
            )
            if x.fonte_verifica:
                riga += f" (verifica: {x.fonte_verifica})"
            righe.append(riga)
        return "I risultati si misurano con i seguenti indicatori:\n" + _elenco(righe)
    raise ErroreProposta("Per questa sezione non c'è un testo da comporre.")


def testi_simili(sezione, limite=5):
    """Testi della stessa sezione in altri progetti, da riusare."""
    return (
        TestoSezione.objects.filter(titolo__iexact=sezione.titolo)
        .exclude(progetto=sezione.progetto)
        .exclude(testo="")
        .select_related("progetto")
        .order_by("-modificato_il")[:limite]
    )


@transaction.atomic
def salva_testo(sezione, testo, utente):
    if sezione.progetto.stato != Progetto.Stato.PROGETTAZIONE:
        raise ErroreProposta("La proposta si modifica solo in progettazione.")
    sezione.testo = testo.replace("\r\n", "\n").strip()
    sezione.save(update_fields=["testo", "modificato_il"])
    registra(Azione.MODIFICA, sezione.progetto, utente=utente, proposta=f"sezione «{sezione}»")
    return sezione


# --- verifica ------------------------------------------------------------------------------------


@dataclass
class Voce:
    esito: str  # ok | errore | avviso
    testo: str
    sezione: str = ""  # scheda dove si rimedia


def verifica(progetto):
    """Controlli prima della candidatura: proposta, quadro, cronoprogramma, partner, piano e
    bando."""
    v = []
    sezioni = list(progetto.sezioni.all())
    vuote = [s.titolo for s in sezioni if not s.testo.strip()]
    lunghe = [
        f"{s.titolo} ({s.caratteri}/{s.massimo_caratteri})" for s in sezioni if s.troppo_lungo
    ]
    if not sezioni:
        v.append(Voce("errore", "La proposta non è ancora stata scritta.", "proposta"))
    elif vuote:
        v.append(Voce("errore", f"Sezioni da scrivere: {', '.join(vuote)}.", "proposta"))
    else:
        v.append(Voce("ok", "Tutte le sezioni della proposta sono scritte.", "proposta"))
    if lunghe:
        v.append(Voce("errore", f"Oltre il limite di caratteri: {', '.join(lunghe)}.", "proposta"))
    if not progetto.obiettivo_generale.strip() or not progetto.obiettivi.exists():
        v.append(
            Voce(
                "errore", "Indicare l'obiettivo generale e almeno un obiettivo specifico.", "quadro"
            )
        )
    if not progetto.indicatori.exists():
        v.append(
            Voce("avviso", "Nessun indicatore: i finanziatori di solito li chiedono.", "quadro")
        )
    attivita = list(progetto.attivita.all())
    if not attivita:
        v.append(Voce("errore", "Il cronoprogramma non ha attività.", "cronoprogramma"))
    elif progetto.fine_prevista and max(a.fine for a in attivita) > progetto.fine_prevista:
        v.append(
            Voce(
                "avviso",
                "Alcune attività finiscono dopo la fine prevista del progetto.",
                "cronoprogramma",
            )
        )
    senza_lettera = [
        str(p.soggetto)
        for p in progetto.partner.select_related("soggetto")
        if not p.lettera_ricevuta
    ]
    if senza_lettera:
        v.append(
            Voce(
                "avviso",
                f"Lettere di partenariato da ricevere: {', '.join(senza_lettera)}.",
                "partner",
            )
        )
    p = piano_economico.calcola(progetto)
    if p.errori:
        v.append(
            Voce(
                "errore",
                "Il piano economico non rispetta: " + "; ".join(c.testo for c in p.errori),
                "piano",
            )
        )
    elif p.totale_costi:
        v.append(
            Voce(
                "ok",
                f"Piano economico in regola ({piano_economico.euro(p.totale_costi)}).",
                "piano",
            )
        )
    else:
        v.append(Voce("errore", "Il piano economico è vuoto.", "piano"))
    bando = progetto.bando
    if bando is None:
        v.append(Voce("avviso", "Nessun bando collegato: si candida dalla scheda del progetto."))
    else:
        from . import requisiti

        r = requisiti.riepilogo(bando)
        if r["mancanti"]:
            v.append(Voce("errore", f"Requisiti del bando mancanti: {r['mancanti']}."))
        if r["da_verificare"]:
            v.append(Voce("avviso", f"Requisiti del bando da verificare: {r['da_verificare']}."))
        if bando.scaduto:
            v.append(Voce("errore", "Il termine per la domanda è scaduto."))
    return v


# --- documenti -----------------------------------------------------------------------------------


def nome_file(progetto, tipo, estensione):
    return f"{progetto.codice}-{tipo}.{estensione}"


def piano_excel(progetto):
    """Il piano economico in un foglio Excel (costi per categoria, coperture, controlli)."""
    from openpyxl import Workbook
    from openpyxl.styles import Font

    p = piano_economico.calcola(progetto)
    wb = Workbook()
    ws = wb.active
    ws.title = "Piano economico"
    grassetto = Font(bold=True)
    ws.append([f"{progetto.codice} — {progetto.titolo}"])
    ws["A1"].font = Font(bold=True, size=13)
    if progetto.bando_id:
        ws.append([f"Bando: {progetto.bando}"])
    ws.append([])
    ws.append(["Categoria", "Voce", "Quantità", "Unità", "Costo unitario", "Importo"])
    for cella in ws[ws.max_row]:
        cella.font = grassetto
    for _, etichetta, voci, totale in p.categorie:
        for v in voci:
            ws.append(
                [
                    etichetta,
                    v.descrizione,
                    float(v.quantita),
                    v.unita,
                    float(v.costo_unitario),
                    float(v.importo),
                ]
            )
        ws.append(["", f"Totale {etichetta.lower()}", None, None, None, float(totale)])
        ws.cell(ws.max_row, 2).font = grassetto
    if p.spese_generali:
        ws.append(
            [
                "Spese generali",
                f"{progetto.spese_generali}% dei costi diretti",
                None,
                None,
                None,
                float(p.spese_generali),
            ]
        )
    ws.append(["", "TOTALE COSTI", None, None, None, float(p.totale_costi)])
    ws.cell(ws.max_row, 2).font = grassetto
    ws.append([])
    ws.append(["Coperture", "", None, None, None, "Importo"])
    for cella in ws[ws.max_row]:
        cella.font = grassetto
    for f in p.fonti:
        ws.append([f.get_tipo_display(), f.descrizione, None, None, None, float(f.importo)])
    if p.partner:
        ws.append(["Cofinanziamento dei partner", "", None, None, None, float(p.partner)])
    if p.natura:
        ws.append(
            [
                "Cofinanziamento in natura",
                "Volontariato valorizzato",
                None,
                None,
                None,
                float(p.natura),
            ]
        )
    ws.append(["", "TOTALE COPERTURE", None, None, None, float(p.totale_fonti)])
    ws.cell(ws.max_row, 2).font = grassetto
    ws.append([])
    ws.append(["Controlli"])
    ws.cell(ws.max_row, 1).font = grassetto
    for c in p.controlli:
        ws.append([{"ok": "OK", "errore": "NO", "avviso": "!"}[c.esito], c.testo])
    for riga in ws.iter_rows(min_col=5, max_col=6):
        for cella in riga:
            if isinstance(cella.value, float):
                cella.number_format = '#,##0.00 "€"'
    for colonna, larghezza in zip("ABCDEF", (28, 48, 10, 10, 15, 15), strict=True):
        ws.column_dimensions[colonna].width = larghezza
    uscita = BytesIO()
    wb.save(uscita)
    return uscita.getvalue()


def contesto_pdf(progetto):
    from apps.core.models import Organizzazione

    from .views import gantt

    attivita = list(progetto.attivita.select_related("responsabile"))
    return {
        "organizzazione": Organizzazione.corrente(),
        "progetto": progetto,
        "sezioni": list(progetto.sezioni.all()),
        "obiettivi": progetto.obiettivi.prefetch_related("indicatori"),
        "attivita": attivita,
        "gantt": gantt(attivita, larghezza=640, riga=20),
        "partner": progetto.partner.select_related("soggetto"),
        "piano": piano_economico.calcola(progetto),
        "oggi": timezone.localdate(),
    }


def proposta_pdf(progetto):
    from apps.core.pdf import genera_pdf

    return genera_pdf("progetti/pdf/proposta.html", contesto_pdf(progetto))


# --- protocollo ----------------------------------------------------------------------------------


@transaction.atomic
def protocolla(progetto, utente, *, mezzo, allegati=(), proposta=True, excel=True):
    """Protocollo in uscita della candidatura verso il finanziatore del bando, con la proposta in
    PDF, il piano in Excel e i documenti scelti. Si spedisce poi dalla scheda del protocollo."""
    from apps.protocollo import servizi as prot
    from apps.protocollo.buste import MEZZI_POSTALI

    bando = progetto.bando
    if progetto.stato != Progetto.Stato.CANDIDATO or bando is None:
        raise ErroreProposta("Si protocolla la candidatura di un progetto candidato a un bando.")
    if progetto.protocollo_candidatura_id:
        raise ErroreProposta("La candidatura è già stata protocollata.")
    if bando.finanziatore is None:
        raise ErroreProposta(
            "Indicare nel bando il finanziatore scelto dall'anagrafica (serve il suo indirizzo)."
        )
    file = []
    if proposta:
        file.append(
            ContentFile(proposta_pdf(progetto), name=nome_file(progetto, "proposta", "pdf"))
        )
    if excel:
        file.append(
            ContentFile(piano_excel(progetto), name=nome_file(progetto, "piano-economico", "xlsx"))
        )
    for a in allegati:
        with a.file.open("rb") as f:
            file.append(ContentFile(f.read(), name=a.nome))
    if not file:
        raise ErroreProposta("Scegliere almeno un documento da inviare.")
    corrispondente = prot.corrispondente_da_soggetto(
        bando.finanziatore,
        "destinatario",
        pec_preferita=mezzo == "pec",
        postale=mezzo in MEZZI_POSTALI,
    )
    protocollo = prot.registra_protocollo(
        {
            "direzione": "uscita",
            "mezzo": mezzo,
            "oggetto": f"Candidatura del progetto «{progetto.titolo}» al bando «{bando}»"[:500],
        },
        [corrispondente],
        utente,
        allegati=file,
    )
    progetto.protocollo_candidatura = protocollo
    progetto.save(update_fields=["protocollo_candidatura"])
    registra(Azione.MODIFICA, progetto, utente=utente, candidatura=protocollo.segnatura)
    return protocollo


def allegati_progetto(progetto):
    filtro = {"progetto": progetto}
    qs = Allegato.objects.filter(**filtro)
    if progetto.idea_id:
        qs = qs | Allegato.objects.filter(idea_id=progetto.idea_id)
    return qs.order_by("-caricato_il")
