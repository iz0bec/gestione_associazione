# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Relazione al consiglio (preventiva, da discutere prima di una decisione sul
# *              progetto): sezioni guidate con testi proposti dai dati, PDF da stampare o
# *              inviare ai partecipanti della riunione (bozza di comunicazione), punto
# *              all'ordine del giorno.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.core.audit import Azione, registra

from . import piano as piano_economico
from .models import TestoSezione

SCHEMA = [
    (
        "decisione",
        "Che cosa si chiede di decidere",
        "Avviare la progettazione, candidarlo a un bando, approvare una variante, chiuderlo?\n"
        "Entro quando serve la decisione?",
    ),
    (
        "motivazioni",
        "Motivazioni e bisogno",
        "Perché il progetto è utile all'associazione e alla comunità?\nDa chi nasce la proposta?",
    ),
    ("finalita", "Coerenza con le finalità statutarie", "A quali scopi dello statuto risponde?"),
    (
        "bando",
        "Bando e finanziamento",
        "Quale bando, con quale contributo e quali requisiti?\nLi rispettiamo?",
    ),
    (
        "impegno",
        "Impegno per l'associazione",
        "Quanto costa e quanto mette l'associazione (in denaro e in volontariato)?\n"
        "Chi se ne occupa?",
    ),
    (
        "rischi",
        "Rischi e punti aperti",
        "Che cosa manca ancora o potrebbe andare storto?\nQuali alternative ci sono?",
    ),
    ("delibera", "Proposta di delibera", "Il testo della delibera che si propone al consiglio."),
]

COMPONIBILI = {"motivazioni", "finalita", "bando", "impegno", "rischi"}


class ErroreConsiglio(Exception):
    pass


@transaction.atomic
def prepara(progetto):
    presenti = {s.titolo for s in progetto.sezioni_consiglio}
    ordine = len(presenti)
    for chiave, titolo, domande in SCHEMA:
        if titolo not in presenti:
            ordine += 1
            TestoSezione.objects.create(
                progetto=progetto,
                documento="consiglio",
                chiave=chiave,
                titolo=titolo,
                domande=domande,
                ordine=ordine,
            )
    return list(progetto.sezioni_consiglio)


def componi(progetto, chiave):
    from . import proposta, requisiti

    if chiave == "finalita":
        return proposta.componi(progetto, "finalita")
    if chiave == "motivazioni":
        parti = [progetto.sintesi]
        if progetto.idea_id:
            idea = progetto.idea
            if idea.bisogno:
                parti.append(f"Bisogno: {idea.bisogno}")
            if idea.proposta_da:
                parti.append(f"La proposta nasce da: {idea.proposta_da}.")
            from . import servizi

            media = servizi.media_idea(idea)
            if media:
                parti.append(
                    f"L'idea {idea.codice} ha avuto una valutazione media di {media}/5 "
                    f"({idea.valutazioni.count()} valutazioni)."
                )
        return "\n\n".join(p for p in parti if p)
    if chiave == "bando":
        b = progetto.bando
        if b is None:
            raise ErroreConsiglio("Il progetto non è collegato a un bando.")
        parti = [f"Bando: {b}" + (f" ({b.ente})" if b.ente else "") + "."]
        if b.scadenza:
            parti.append(f"Domanda entro il {b.scadenza:%d/%m/%Y}.")
        if b.importo_massimo:
            parti.append(f"Contributo massimo: {piano_economico.euro(b.importo_massimo)}.")
        if b.cofinanziamento is not None:
            parti.append(
                f"Cofinanziamento richiesto: almeno il {b.cofinanziamento.normalize():f}%."
            )
        r = requisiti.riepilogo(b)
        if r["esiti"]:
            parti.append(
                f"Requisiti: {r['soddisfatti']} soddisfatti, {r['mancanti']} mancanti, "
                f"{r['da_verificare']} da verificare."
            )
            for e in r["esiti"]:
                if e.esito != "si":
                    parti.append(f"- {e.requisito.descrizione}: {e.etichetta.lower()}")
        return "\n".join(parti)
    if chiave == "impegno":
        p = piano_economico.calcola(progetto)
        if not p.totale_costi:
            raise ErroreConsiglio("Il piano economico è vuoto.")
        e = piano_economico.euro
        righe = [f"Costo complessivo: {e(p.totale_costi)}."]
        if p.contributo:
            righe.append(f"Contributo richiesto: {e(p.contributo)}.")
        if p.proprio:
            righe.append(f"A carico dell'associazione in denaro: {e(p.proprio)}.")
        if p.natura:
            righe.append(f"Volontariato valorizzato: {e(p.natura)}.")
        if p.partner:
            righe.append(f"Dai partner: {e(p.partner)}.")
        if p.altri:
            righe.append(f"Da altri finanziatori: {e(p.altri)}.")
        if progetto.responsabile_id:
            nome = progetto.responsabile.get_full_name() or progetto.responsabile.get_username()
            righe.append(f"Responsabile del progetto: {nome}.")
        return "\n".join(righe)
    if chiave == "rischi":
        punti = [v.testo for v in proposta.verifica(progetto) if v.esito != "ok"]
        if not punti:
            return "Le verifiche del gestionale non segnalano punti aperti."
        return "Punti segnalati dalle verifiche del gestionale:\n" + "\n".join(
            f"- {t}" for t in punti
        )
    raise ErroreConsiglio("Per questa sezione non c'è un testo da comporre.")


def contesto_pdf(progetto):
    from apps.core.models import Organizzazione

    return {
        "organizzazione": Organizzazione.corrente(),
        "progetto": progetto,
        "sezioni": list(progetto.sezioni_consiglio),
        "piano": piano_economico.calcola(progetto),
        "oggi": timezone.localdate(),
    }


def pdf(progetto):
    from apps.core.pdf import genera_pdf

    return genera_pdf("progetti/pdf/consiglio.html", contesto_pdf(progetto))


def nome_file(progetto):
    return f"{progetto.codice}-relazione-al-consiglio.pdf"


def riunioni_utili():
    """Riunioni in preparazione o convocate, non ancora svolte."""
    from apps.organi.models import Riunione

    return (
        Riunione.objects.filter(
            stato__in=[Riunione.Stato.BOZZA, Riunione.Stato.CONVOCATA],
            prima_convocazione__gte=timezone.now() - timedelta(days=1),
        )
        .select_related("organo")
        .order_by("prima_convocazione")
    )


@transaction.atomic
def invia(progetto, riunione, utente, *, punto=False):
    """Bozza di comunicazione agli aventi diritto della riunione con la relazione in PDF (si
    conferma in Comunicazioni); con `punto`, aggiunge il punto all'ordine del giorno."""
    from apps.comunicazioni import servizi as comunicazioni
    from apps.comunicazioni.models import Finalita
    from apps.organi import servizi as organi

    if not progetto.sezioni_consiglio.exclude(testo="").exists():
        raise ErroreConsiglio("La relazione al consiglio è ancora vuota.")
    titolo_punto = f"Progetto {progetto.codice} «{progetto.titolo}»"
    if punto:
        if riunione.stato != riunione.Stato.BOZZA:
            raise ErroreConsiglio("L'ordine del giorno si cambia solo prima della convocazione.")
        if not riunione.punti.filter(titolo__icontains=progetto.codice).exists():
            ultimo = riunione.punti.order_by("-ordine").first()
            riunione.punti.create(
                ordine=(ultimo.ordine if ultimo else 0) + 1, titolo=titolo_punto[:500]
            )
    soggetti = [s for s, _, _ in organi.aventi_diritto(riunione)]
    if not soggetti:
        raise ErroreConsiglio("La riunione non ha partecipanti con diritto.")
    quando = timezone.localtime(riunione.prima_convocazione)
    invio = comunicazioni.crea_invio(
        utente,
        oggetto=f"{riunione.organo}: relazione sul progetto {progetto.codice}",
        corpo=(
            f"In vista della riunione di {riunione.organo} del {quando:%d/%m/%Y} alle "
            f"{quando:%H:%M}, si trasmette in allegato la relazione sul progetto "
            f"«{progetto.titolo}», da esaminare prima della discussione.\n\nCordiali saluti."
        ),
        finalita=Finalita.ISTITUZIONALE,
        soggetti=soggetti,
        allegati=[(nome_file(progetto), pdf(progetto))],
        origine=f"progetto {progetto.codice}",
    )
    registra(
        Azione.MODIFICA,
        progetto,
        utente=utente,
        relazione_consiglio=f"bozza di invio per {riunione.organo} del {quando:%d/%m/%Y}",
        punto_odg=punto,
    )
    return invio
