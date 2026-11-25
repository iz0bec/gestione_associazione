# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Operazioni del modulo Progetti (P1): idee e necessità (anche da protocollo e
# *              posta), valutazioni con i criteri pesati, priorità, progetti con i passaggi di
# *              stato e le delibere, gruppo di lavoro, scadenze, commenti e allegati.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import re
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db import models, transaction
from django.utils import timezone

from apps.core.audit import Azione, registra
from apps.core.numerazione import prossimo_numero

from .models import (
    SEQ_IDEA,
    SEQ_PROGETTO,
    Allegato,
    Bando,
    Commento,
    CriterioValutazione,
    FinalitaStatutaria,
    Idea,
    LimiteCategoria,
    Membro,
    PassaggioStato,
    Progetto,
    Requisito,
    Scadenza,
    Valutazione,
)

DIMENSIONE_MASSIMA = 20 * 1024 * 1024
MOTIVO_OBBLIGATORIO = {Progetto.Stato.ACCANTONATO, Progetto.Stato.NON_FINANZIATO}


class OperazioneNonValida(Exception):
    pass


# --- idee --------------------------------------------------------------------------------------


@transaction.atomic
def crea_idea(form, utente, *, protocollo=None, messaggio=None):
    """Salva l'idea del modulo (con le finalità) assegnandole il numero dell'anno."""
    idea = form.save(commit=False)
    idea.anno = timezone.localdate().year
    idea.numero = prossimo_numero(SEQ_IDEA, idea.anno)
    idea.proponente = idea.creato_da = idea.modificato_da = utente
    idea.protocollo, idea.messaggio = protocollo, messaggio
    if protocollo or messaggio:
        idea.fonte = Idea.Fonte.ESTERNA
    idea.save()
    form.save_m2m()
    registra(Azione.CREAZIONE, idea, utente=utente, codice=idea.codice, fonte=idea.fonte)
    return idea


@transaction.atomic
def modifica_idea(form, utente):
    idea = form.save(commit=False)
    if idea.stato == Idea.Stato.APPROVATA:
        raise OperazioneNonValida("L'idea è già diventata un progetto: si modifica il progetto.")
    idea.modificato_da = utente
    idea.save()
    form.save_m2m()
    registra(Azione.MODIFICA, idea, utente=utente)
    return idea


def dati_da_protocollo(protocollo):
    """Valori iniziali di un'idea nata da un protocollo (lettera, email, PEC)."""
    corrispondenti = protocollo.mittenti or list(protocollo.corrispondenti.all())
    mittente = corrispondenti[0] if corrispondenti else None
    soggetto = mittente.soggetto if mittente else None
    testo_mitt = mittente.descrizione if mittente else ""
    return {
        "titolo": protocollo.oggetto[:200],
        "descrizione": (protocollo.testo or "").strip()[:4000],
        "fonte": Idea.Fonte.ESTERNA,
        "fonte_soggetto": soggetto,
        "fonte_testo": "" if soggetto else str(testo_mitt)[:255],
    }


def dati_da_messaggio(messaggio):
    """Valori iniziali di un'idea nata da un messaggio della posta da protocollare."""
    from apps.anagrafica.models import Soggetto

    soggetto = None
    if messaggio.mittente_email:
        soggetto = Soggetto.objects.filter(email__iexact=messaggio.mittente_email).first()
    return {
        "titolo": (messaggio.oggetto or "Idea dalla posta")[:200],
        "descrizione": (messaggio.testo or "").strip()[:4000],
        "fonte": Idea.Fonte.ESTERNA,
        "fonte_soggetto": soggetto,
        "fonte_testo": "" if soggetto else (messaggio.mittente or "")[:255],
    }


def criteri():
    return list(CriterioValutazione.objects.filter(attivo=True))


def _media(punteggi, elenco):
    pesi = {c.pk: c.peso for c in elenco}
    totale = sum(pesi[int(k)] * v for k, v in punteggi.items() if int(k) in pesi)
    peso = sum(pesi[int(k)] for k in punteggi if int(k) in pesi)
    if not peso:
        return Decimal("0")
    return (Decimal(totale) / Decimal(peso)).quantize(Decimal("0.01"), ROUND_HALF_UP)


@transaction.atomic
def valuta(idea, utente, punteggi, commento=""):
    """Valutazione (una per utente, si aggiorna): punteggi da 1 a 5 per ogni criterio attivo."""
    if idea.stato in (Idea.Stato.APPROVATA, Idea.Stato.ACCANTONATA):
        raise OperazioneNonValida("L'idea non è più in valutazione.")
    elenco = criteri()
    if not elenco:
        raise OperazioneNonValida("Non ci sono criteri di valutazione attivi.")
    puliti = {}
    for c in elenco:
        valore = punteggi.get(c.pk, punteggi.get(str(c.pk)))
        try:
            valore = int(valore)
        except (TypeError, ValueError):
            raise OperazioneNonValida(f"Manca il punteggio per «{c.nome}».") from None
        if not 1 <= valore <= 5:
            raise OperazioneNonValida(f"Il punteggio per «{c.nome}» va da 1 a 5.")
        puliti[str(c.pk)] = valore
    v, _ = Valutazione.objects.update_or_create(
        idea=idea,
        utente=utente,
        defaults={
            "punteggi": puliti,
            "media": _media(puliti, elenco),
            "commento": commento.strip(),
        },
    )
    if idea.stato == Idea.Stato.NUOVA:
        idea.stato = Idea.Stato.IN_VALUTAZIONE
        idea.save(update_fields=["stato", "modificato_il"])
    registra(Azione.MODIFICA, idea, utente=utente, valutazione=str(v.media))
    return v


def media_idea(idea):
    valori = [v.media for v in idea.valutazioni.all()]
    if not valori:
        return None
    return (sum(valori) / len(valori)).quantize(Decimal("0.01"), ROUND_HALF_UP)


def riepilogo_valutazioni(idea):
    """Per ogni criterio attivo la media dei punteggi dati, e la media generale."""
    elenco = criteri()
    valutazioni = list(idea.valutazioni.select_related("utente"))
    per_criterio = []
    for c in elenco:
        voti = [v.punteggi.get(str(c.pk)) for v in valutazioni if v.punteggi.get(str(c.pk))]
        media = round(sum(voti) / len(voti), 1) if voti else None
        per_criterio.append({"criterio": c, "media": media, "voti": len(voti)})
    return {"criteri": per_criterio, "media": media_idea(idea), "valutazioni": valutazioni}


@transaction.atomic
def cambia_stato_idea(idea, stato, utente, motivo=""):
    if stato not in (Idea.Stato.NUOVA, Idea.Stato.IN_VALUTAZIONE, Idea.Stato.ACCANTONATA):
        raise OperazioneNonValida("Stato non ammesso: un'idea diventa progetto con «Trasforma».")
    if idea.stato == Idea.Stato.APPROVATA:
        raise OperazioneNonValida("L'idea è già diventata un progetto.")
    if stato == Idea.Stato.ACCANTONATA and not motivo.strip():
        raise OperazioneNonValida("Indicare perché l'idea si accantona.")
    prima = idea.get_stato_display()
    idea.stato, idea.motivo_stato, idea.modificato_da = stato, motivo.strip()[:255], utente
    idea.save(update_fields=["stato", "motivo_stato", "modificato_da", "modificato_il"])
    registra(
        Azione.MODIFICA,
        idea,
        utente=utente,
        stato=f"{prima} → {idea.get_stato_display()}",
        motivo=motivo,
    )
    return idea


@transaction.atomic
def imposta_priorita(idea, priorita, utente, *, delibera=None):
    if priorita and priorita not in Idea.Priorita.values:
        raise OperazioneNonValida("Priorità non valida.")
    idea.priorita, idea.delibera_priorita, idea.modificato_da = priorita, delibera, utente
    idea.save(update_fields=["priorita", "delibera_priorita", "modificato_da", "modificato_il"])
    registra(
        Azione.MODIFICA,
        idea,
        utente=utente,
        priorita=priorita or "nessuna",
        delibera=str(delibera) if delibera else "",
    )
    return idea


# --- progetti ------------------------------------------------------------------------------------


@transaction.atomic
def crea_progetto(form, utente, *, idea=None, delibera=None):
    """Nuovo progetto (in progettazione), eventualmente dall'idea, che risulta approvata."""
    if idea is not None:
        idea = Idea.objects.select_for_update().get(pk=idea.pk)
        if idea.stato == Idea.Stato.APPROVATA:
            raise OperazioneNonValida("L'idea è già diventata un progetto.")
    progetto = form.save(commit=False)
    progetto.anno = timezone.localdate().year
    progetto.numero = prossimo_numero(SEQ_PROGETTO, progetto.anno)
    progetto.idea = idea
    progetto.creato_da = progetto.modificato_da = utente
    progetto.save()
    form.save_m2m()
    PassaggioStato.objects.create(
        progetto=progetto,
        a=progetto.stato,
        utente=utente,
        motivo="Avvio della progettazione",
        delibera=delibera,
    )
    if progetto.responsabile_id:
        Membro.objects.create(progetto=progetto, utente=progetto.responsabile, ruolo="Responsabile")
    if idea is not None:
        idea.stato, idea.modificato_da = Idea.Stato.APPROVATA, utente
        idea.save(update_fields=["stato", "modificato_da", "modificato_il"])
    registra(
        Azione.CREAZIONE,
        progetto,
        utente=utente,
        codice=progetto.codice,
        idea=idea.codice if idea else "",
    )
    return progetto


@transaction.atomic
def modifica_progetto(form, utente):
    progetto = form.save(commit=False)
    if not progetto.aperto:
        raise OperazioneNonValida("Il progetto è chiuso o accantonato.")
    progetto.modificato_da = utente
    progetto.save()
    form.save_m2m()
    registra(Azione.MODIFICA, progetto, utente=utente)
    return progetto


@transaction.atomic
def cambia_stato(progetto, nuovo, utente, *, motivo="", delibera=None):
    progetto = Progetto.objects.select_for_update().get(pk=progetto.pk)
    if nuovo not in progetto.PASSAGGI.get(progetto.stato, []):
        raise OperazioneNonValida(
            f"Da «{progetto.get_stato_display()}» non si passa a «{Progetto.Stato(nuovo).label}»."
        )
    if nuovo in MOTIVO_OBBLIGATORIO and not motivo.strip():
        raise OperazioneNonValida("Indicare il motivo.")
    prima = progetto.stato
    progetto.stato, progetto.modificato_da = nuovo, utente
    progetto.save(update_fields=["stato", "modificato_da", "modificato_il"])
    PassaggioStato.objects.create(
        progetto=progetto,
        da=prima,
        a=nuovo,
        utente=utente,
        motivo=motivo.strip()[:255],
        delibera=delibera,
    )
    registra(
        Azione.MODIFICA,
        progetto,
        utente=utente,
        stato=f"{Progetto.Stato(prima).label} → {progetto.get_stato_display()}",
        delibera=str(delibera) if delibera else "",
    )
    return progetto


def _aperto(progetto):
    if not progetto.aperto:
        raise OperazioneNonValida("Il progetto è chiuso o accantonato.")


def aggiungi_membro(
    progetto, utente, *, ruolo, membro_utente=None, soggetto=None, volontario=False
):
    _aperto(progetto)
    if not (membro_utente or soggetto):
        raise OperazioneNonValida("Indicare un utente o una persona dell'anagrafica.")
    if not ruolo.strip():
        raise OperazioneNonValida("Indicare il ruolo nel gruppo.")
    m = Membro.objects.create(
        progetto=progetto,
        utente=membro_utente,
        soggetto=soggetto,
        ruolo=ruolo.strip()[:100],
        volontario=volontario,
    )
    registra(Azione.MODIFICA, progetto, utente=utente, gruppo=f"aggiunto {m}")
    return m


def togli_membro(membro, utente):
    _aperto(membro.progetto)
    descrizione = str(membro)
    progetto = membro.progetto
    membro.delete()
    registra(Azione.MODIFICA, progetto, utente=utente, gruppo=f"tolto {descrizione}")


def aggiungi_scadenza(progetto, utente, *, titolo, data):
    _aperto(progetto)
    if not titolo.strip():
        raise OperazioneNonValida("Indicare la scadenza.")
    s = Scadenza.objects.create(progetto=progetto, titolo=titolo.strip()[:200], data=data)
    registra(Azione.MODIFICA, progetto, utente=utente, scadenza=str(s))
    return s


def segna_scadenza(scadenza, utente, *, fatta=True):
    scadenza.fatta = fatta
    scadenza.save(update_fields=["fatta"])
    registra(
        Azione.MODIFICA,
        scadenza.progetto,
        utente=utente,
        scadenza=f"{scadenza} {'fatta' if fatta else 'da fare'}",
    )
    return scadenza


# --- commenti e allegati -------------------------------------------------------------------------


def _destinazione(oggetto):
    return {"idea": oggetto} if isinstance(oggetto, Idea) else {"progetto": oggetto}


def commenta(oggetto, utente, testo):
    if not (testo or "").strip():
        raise OperazioneNonValida("Il commento è vuoto.")
    c = Commento.objects.create(utente=utente, testo=testo.strip(), **_destinazione(oggetto))
    registra(Azione.MODIFICA, oggetto, utente=utente, commento="aggiunto")
    return c


def allega(oggetto, file, utente, descrizione=""):
    if file.size > DIMENSIONE_MASSIMA:
        raise OperazioneNonValida("Il file supera i 20 MB.")
    nome = re.sub(r"[^\w.\- ()]", "_", file.name)[:200] or "documento"
    a = Allegato(
        nome=nome,
        descrizione=descrizione.strip()[:255],
        caricato_da=utente,
        **_destinazione(oggetto),
    )
    a.file.save(nome, file, save=False)
    a.save()
    registra(Azione.MODIFICA, oggetto, utente=utente, allegato=nome)
    return a


# --- finalità statutarie -------------------------------------------------------------------------

_RE_FINALITA = re.compile(r"^\s*([a-z0-9]{1,3})[).]\s+(.+)$", re.IGNORECASE)


def carica_finalita(testo, *, sostituisci=False):
    """Finalità da un testo con una per riga, es. «a) Il culto della Patria;». Il titolo è la
    prima parte (fino a 150 caratteri). Restituisce quante ne ha create."""
    righe = [m for riga in testo.splitlines() if (m := _RE_FINALITA.match(riga))]
    if not righe:
        raise OperazioneNonValida("Nessuna finalità riconosciuta (formato: «a) testo»).")
    with transaction.atomic():
        if sostituisci:
            FinalitaStatutaria.objects.filter(
                idee__isnull=True, progetti__isnull=True, bandi__isnull=True
            ).delete()
        creati = 0
        for i, m in enumerate(righe, 1):
            codice, testo_f = m.group(1).lower(), m.group(2).strip().rstrip(";.")
            _, nuovo = FinalitaStatutaria.objects.update_or_create(
                codice=codice,
                defaults={"titolo": testo_f[:150], "testo": testo_f, "ordine": i, "attiva": True},
            )
            creati += nuovo
    return creati


# --- bandi (P2) ----------------------------------------------------------------------------------

GIORNI_PROMEMORIA = (7, 2)  # avvisi prima della scadenza della domanda


@transaction.atomic
def crea_bando(form, utente):
    bando = form.save(commit=False)
    bando.creato_da = bando.modificato_da = utente
    bando.save()
    form.save_m2m()
    registra(Azione.CREAZIONE, bando, utente=utente, ente=bando.ente)
    return bando


@transaction.atomic
def modifica_bando(form, utente):
    bando = form.save(commit=False)
    if "scadenza" in form.changed_data:
        bando.promemoria = []  # nuova scadenza: i promemoria ripartono
    bando.modificato_da = utente
    bando.save()
    form.save_m2m()
    registra(Azione.MODIFICA, bando, utente=utente, campi=", ".join(form.changed_data))
    return bando


@transaction.atomic
def cambia_stato_bando(bando, stato, utente, motivo=""):
    if stato not in Bando.Stato.values:
        raise OperazioneNonValida("Stato non valido.")
    if stato == Bando.Stato.SCARTATO and not motivo.strip():
        raise OperazioneNonValida("Indicare perché il bando si scarta.")
    prima = bando.get_stato_display()
    bando.stato, bando.motivo, bando.modificato_da = stato, motivo.strip()[:255], utente
    bando.save(update_fields=["stato", "motivo", "modificato_da", "modificato_il"])
    registra(Azione.MODIFICA, bando, utente=utente, stato=f"{prima} → {bando.get_stato_display()}")
    return bando


@transaction.atomic
def aggiungi_requisito(bando, utente, *, descrizione, verifica="", parametro=""):
    from . import requisiti

    if verifica and verifica not in requisiti.VERIFICHE:
        raise OperazioneNonValida("Verifica non prevista.")
    if errore := requisiti.controlla_parametro(verifica, parametro):
        raise OperazioneNonValida(errore)
    descrizione = descrizione.strip() or (requisiti.VERIFICHE[verifica].nome if verifica else "")
    if not descrizione:
        raise OperazioneNonValida("Descrivere il requisito.")
    ordine = (bando.requisiti.aggregate(m=models.Max("ordine"))["m"] or 0) + 1
    r = Requisito.objects.create(bando=bando, descrizione=descrizione[:255], verifica=verifica,
                                 parametro=parametro.strip()[:100], ordine=ordine)  # fmt: skip
    registra(Azione.MODIFICA, bando, utente=utente, requisito=f"aggiunto {r}")
    return r


@transaction.atomic
def indica_esito(requisito, utente, *, esito="", nota=""):
    """Esito indicato a mano (prevale sulla verifica automatica); vuoto = torna automatico."""
    if esito and esito not in Requisito.Esito.values:
        raise OperazioneNonValida("Esito non valido.")
    requisito.esito_manuale, requisito.nota = esito, nota.strip()[:255]
    requisito.save(update_fields=["esito_manuale", "nota"])
    indicato = requisito.get_esito_manuale_display() or "automatico"
    registra(Azione.MODIFICA, requisito.bando, utente=utente, requisito=f"{requisito}: {indicato}")
    return requisito


@transaction.atomic
def togli_requisito(requisito, utente):
    bando, descrizione = requisito.bando, str(requisito)
    requisito.delete()
    registra(Azione.MODIFICA, bando, utente=utente, requisito=f"tolto {descrizione}")


@transaction.atomic
def candida(progetto, bando, utente, *, delibera=None):
    """Candida il progetto al bando: lo collega e lo porta allo stato «Candidato»."""
    if progetto.stato != Progetto.Stato.PROGETTAZIONE:
        raise OperazioneNonValida("Si candida un progetto in progettazione.")
    if bando.stato == Bando.Stato.SCARTATO:
        raise OperazioneNonValida("Il bando è stato scartato.")
    if bando.scaduto:
        raise OperazioneNonValida("Il termine per la domanda è già scaduto.")
    progetto.bando = bando
    progetto.save(update_fields=["bando"])
    cambia_stato(progetto, Progetto.Stato.CANDIDATO, utente,
                 motivo=f"Candidato al bando «{bando}»", delibera=delibera)  # fmt: skip
    if bando.stato != Bando.Stato.PARTECIPATO:
        cambia_stato_bando(bando, Bando.Stato.PARTECIPATO, utente)
    progetto.refresh_from_db()
    return progetto


def testo_promemoria(bando, giorni):
    from django.conf import settings
    from django.urls import reverse

    quando = "oggi" if giorni == 0 else "domani" if giorni == 1 else f"fra {giorni} giorni"
    righe = [f"Bando in scadenza {quando}: {bando}"]
    if bando.ente:
        righe.append(f"Finanziatore: {bando.ente}")
    righe.append(f"Domanda entro il {bando.scadenza:%d/%m/%Y}")
    if settings.URL_PUBBLICO:
        righe.append(f"{settings.URL_PUBBLICO}{reverse('progetti:bando', args=[bando.pk])}")
    return "\n".join(righe)


def promemoria_bandi(oggi=None):
    """Avvisa delle domande in scadenza (bandi da valutare o interessanti). Rieseguibile: ogni
    soglia di GIORNI_PROMEMORIA si avvisa una volta sola. Restituisce i bandi avvisati."""
    from apps.core import avvisi

    oggi = oggi or timezone.localdate()
    avvisati = 0
    bandi = Bando.objects.filter(
        stato__in=[Bando.Stato.SEGNALATO, Bando.Stato.INTERESSANTE],
        scadenza__gte=oggi,
        scadenza__lte=oggi + timedelta(days=max(GIORNI_PROMEMORIA)),
    )
    for bando in bandi:
        giorni = bando.giorni_alla_scadenza(oggi)
        dovute = [g for g in GIORNI_PROMEMORIA if giorni <= g and g not in bando.promemoria]
        if not dovute:
            continue
        avvisi.avvisa("bandi", testo_promemoria(bando, giorni))
        bando.promemoria = sorted({*bando.promemoria, *dovute})
        bando.save(update_fields=["promemoria"])
        avvisati += 1
    return avvisati


# --- progettazione (P4) --------------------------------------------------------------------------

SEZIONI_BLOCCATE = {"quadro", "partner", "piano"}  # dopo la candidatura le varianti sono in P5


def modificabile(progetto, sezione):
    """Quadro, partner e piano si cambiano in progettazione; il cronoprogramma finché è aperto."""
    if sezione in SEZIONI_BLOCCATE:
        return progetto.stato == Progetto.Stato.PROGETTAZIONE
    return progetto.aperto


def _controlla(progetto, sezione):
    if not modificabile(progetto, sezione):
        if sezione in SEZIONI_BLOCCATE:
            raise OperazioneNonValida(
                "Si modifica solo in progettazione: dopo la candidatura le varianti si registrano "
                "con la loro delibera."
            )
        raise OperazioneNonValida("Il progetto è chiuso.")


@transaction.atomic
def salva_in_progetto(progetto, form, utente, sezione):
    """Salva un elemento della progettazione (obiettivo, indicatore, attività, partner, voce,
    fonte) o i campi del progetto stesso (quadro, spese generali)."""
    from django.db import IntegrityError

    _controlla(progetto, sezione)
    oggetto = form.save(commit=False)
    if isinstance(oggetto, Progetto):
        oggetto.modificato_da = utente
    else:
        oggetto.progetto = progetto
    try:
        with transaction.atomic():
            oggetto.save()
    except IntegrityError as e:
        raise OperazioneNonValida("È già presente nel progetto.") from e
    registra(Azione.MODIFICA, progetto, utente=utente, **{sezione: f"salvato {oggetto}"[:200]})
    return oggetto


@transaction.atomic
def togli_da_progetto(oggetto, utente, sezione):
    progetto = oggetto.progetto
    _controlla(progetto, sezione)
    descrizione = str(oggetto)
    oggetto.delete()
    registra(Azione.MODIFICA, progetto, utente=utente, **{sezione: f"tolto {descrizione}"[:200]})


@transaction.atomic
def imposta_limite(bando, utente, *, categoria, percentuale_massima):
    limite, _ = LimiteCategoria.objects.update_or_create(
        bando=bando, categoria=categoria, defaults={"percentuale_massima": percentuale_massima}
    )
    registra(Azione.MODIFICA, bando, utente=utente, limite=str(limite))
    return limite


@transaction.atomic
def togli_limite(limite, utente):
    bando, descrizione = limite.bando, str(limite)
    limite.delete()
    registra(Azione.MODIFICA, bando, utente=utente, limite=f"tolto {descrizione}")
