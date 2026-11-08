# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Operazioni degli organi sociali: cariche, riunioni e convocazioni, aventi
# *              diritto, presenze e deleghe, quorum, verbali e delibere (chiusura con
# *              numerazione, PDF con impronta e protocollazione facoltativa).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import hashlib
from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from apps.core.audit import Azione, campi_modificati, registra
from apps.core.models import Organizzazione
from apps.core.numerazione import prossimo_numero

from .models import Carica, Delibera, Organo, Presenza, PuntoOdg, Riunione, Verbale


class OperazioneNonValida(ValidationError):
    """Operazione rifiutata per una regola degli organi sociali (messaggio per l'utente)."""


def _seq(prefisso, organo):
    return f"{prefisso}_{organo.pk}"


# --- cariche -------------------------------------------------------------------------------


@transaction.atomic
def nomina(organo, soggetto, ruolo, dal, utente, *, atto="", note=""):
    if not soggetto.is_persona:
        raise OperazioneNonValida("Le cariche sono ricoperte da persone.")
    if organo.e_assemblea:
        raise OperazioneNonValida("L'assemblea è formata dai soci: non ha cariche da nominare.")
    if organo.cariche_al(dal).filter(soggetto=soggetto).exists():
        raise OperazioneNonValida(f"{soggetto} ha già una carica in questo organo a quella data.")
    carica = Carica.objects.create(
        organo=organo, soggetto=soggetto, ruolo=ruolo, dal=dal, nomina=atto, note=note,
        creato_da=utente, modificato_da=utente,
    )  # fmt: skip
    registra(Azione.CREAZIONE, carica, utente=utente, organo=str(organo))
    return carica


@transaction.atomic
def termina_carica(carica, al, utente, motivo=""):
    carica = Carica.objects.select_for_update().get(pk=carica.pk)
    if carica.al is not None and carica.al < timezone.localdate():
        raise OperazioneNonValida("La carica è già terminata.")
    if al < carica.dal:
        raise OperazioneNonValida("La fine non può precedere l'inizio.")
    carica.al = al
    if motivo:
        carica.note = f"{carica.note} {motivo}".strip()[:255]
    carica.modificato_da = utente
    carica.save()
    registra(Azione.MODIFICA, carica, utente=utente, fine=str(al), motivo=motivo)
    return carica


# --- riunioni ------------------------------------------------------------------------------


def _salva_punti(riunione, titoli):
    titoli = [t.strip() for t in titoli if t.strip()]
    if not titoli:
        raise OperazioneNonValida("L'ordine del giorno deve avere almeno un punto.")
    esistenti = {p.ordine: p for p in riunione.punti.all()}
    for i, titolo in enumerate(titoli, start=1):
        punto = esistenti.pop(i, None)
        if punto is None:
            PuntoOdg.objects.create(riunione=riunione, ordine=i, titolo=titolo[:500])
        elif punto.titolo != titolo:
            punto.titolo = titolo[:500]
            punto.save(update_fields=["titolo"])
    for punto in esistenti.values():
        if punto.delibere.exists():
            raise OperazioneNonValida(f"Il punto {punto.ordine} ha delibere: non si può togliere.")
        punto.delete()


@transaction.atomic
def salva_riunione(form, punti, utente):
    """Crea o aggiorna una riunione (solo se non ancora verbalizzata) e il suo ordine del giorno."""
    nuova = form.instance.pk is None
    if not nuova and not form.instance.modificabile:
        raise OperazioneNonValida("La riunione non è più modificabile.")
    if not nuova and hasattr(form.instance, "verbale") and form.instance.verbale.chiuso:
        raise OperazioneNonValida("Il verbale è chiuso.")
    dettagli = {} if nuova else campi_modificati(form)
    riunione = form.save(commit=False)
    riunione.anno = timezone.localtime(riunione.prima_convocazione).year
    if nuova:
        riunione.creato_da = utente
    riunione.modificato_da = utente
    riunione.save()
    _salva_punti(riunione, punti)
    if nuova:
        registra(Azione.CREAZIONE, riunione, utente=utente)
    else:
        registra(Azione.MODIFICA, riunione, utente=utente, **dettagli)
    return riunione


def aventi_diritto(riunione):
    """(soggetto, qualifica, vota) di chi ha diritto a partecipare alla riunione."""
    from apps.soci.models import Socio

    giorno = timezone.localtime(riunione.prima_convocazione).date()
    organo = riunione.organo
    if organo.e_assemblea:
        soci = Socio.objects.attivi().filter(data_ammissione__lte=giorno)
        in_regola = set()
        if organo.solo_soci_in_regola:
            in_regola = set(soci.in_regola(giorno.year).values_list("pk", flat=True))
        for s in soci.select_related("soggetto").order_by("soggetto__cognome", "soggetto__nome"):
            vota = not organo.solo_soci_in_regola or s.pk in in_regola
            yield s.soggetto, f"socio n. {s.numero}", vota
    else:
        for c in organo.cariche_al(giorno).select_related("soggetto").order_by("ruolo"):
            yield c.soggetto, c.get_ruolo_display(), c.vota


@transaction.atomic
def convoca(riunione, utente, *, protocolla=False):
    """Assegna il numero, segna la riunione come convocata, genera la lettera (e la protocolla)."""
    riunione = Riunione.objects.select_for_update().select_related("organo").get(pk=riunione.pk)
    if riunione.stato != Riunione.Stato.BOZZA:
        raise OperazioneNonValida("La riunione è già stata convocata.")
    if not riunione.punti.exists():
        raise OperazioneNonValida("Manca l'ordine del giorno.")
    riunione.numero = prossimo_numero(_seq("riunione", riunione.organo), riunione.anno)
    riunione.stato = Riunione.Stato.CONVOCATA
    riunione.data_convocazione = riunione.data_convocazione or timezone.localdate()
    riunione.modificato_da = utente
    riunione.save()
    if protocolla:
        riunione.protocollo_convocazione = _protocolla_convocazione(riunione, utente)
        riunione.save(update_fields=["protocollo_convocazione"])
    registra(Azione.MODIFICA, riunione, utente=utente, convocata=True, numero=riunione.numero)
    return riunione


def pdf_convocazione(riunione):
    from apps.core.pdf import genera_pdf

    return genera_pdf(
        "organi/pdf/convocazione.html",
        {
            "r": riunione,
            "destinatari": [s for s, _, _ in aventi_diritto(riunione)],
            "organizzazione": Organizzazione.corrente(),
        },
    )


def _classificazione_organi():
    from apps.protocollo.models import Classificazione

    return Classificazione.objects.filter(codice="03").first()


def _protocolla_convocazione(riunione, utente):
    from apps.protocollo import servizi as protocollo
    from apps.protocollo.models import Protocollo

    destinatari = [
        protocollo.corrispondente_da_soggetto(s, "destinatario")
        for s, _, _ in aventi_diritto(riunione)
    ]
    if not destinatari:
        raise OperazioneNonValida("Nessun avente diritto da convocare.")
    p = protocollo.registra_protocollo(
        {
            "direzione": Protocollo.Direzione.USCITA,
            "mezzo": Protocollo.Mezzo.EMAIL,
            "oggetto": f"Convocazione {riunione.titolo} - "
            f"{timezone.localtime(riunione.prima_convocazione):%d/%m/%Y}",
            "classificazione": _classificazione_organi(),
        },
        destinatari,
        utente,
    )
    pdf = ContentFile(pdf_convocazione(riunione), name="convocazione.pdf")
    protocollo.aggiungi_allegato(p, pdf, utente, principale=True, controlla=False)
    return p


@transaction.atomic
def annulla_riunione(riunione, utente, motivo):
    motivo = (motivo or "").strip()
    if not motivo:
        raise OperazioneNonValida("Indicare il motivo dell'annullamento.")
    riunione = Riunione.objects.select_for_update().get(pk=riunione.pk)
    if not riunione.modificabile:
        raise OperazioneNonValida("La riunione non si può annullare.")
    if hasattr(riunione, "verbale") and riunione.verbale.delibere.exists():
        raise OperazioneNonValida("Il verbale contiene delibere: eliminarle prima di annullare.")
    riunione.stato = Riunione.Stato.ANNULLATA
    riunione.motivo_annullamento = motivo[:255]
    riunione.modificato_da = utente
    riunione.save()
    registra(Azione.ANNULLAMENTO, riunione, utente=utente, motivo=motivo)
    return riunione


# --- presenze e quorum -----------------------------------------------------------------------


@transaction.atomic
def apri_presenze(riunione):
    """Crea l'elenco degli aventi diritto (rieseguibile: aggiunge solo chi manca)."""
    if riunione.stato != Riunione.Stato.CONVOCATA:
        raise OperazioneNonValida("Le presenze si registrano per le riunioni convocate.")
    presenti = set(riunione.presenze.values_list("soggetto_id", flat=True))
    nuove = [
        Presenza(
            riunione=riunione,
            soggetto=s,
            descrizione=s.nome_completo[:200],
            qualifica=qualifica[:100],
            vota=vota,
        )  # fmt: skip
        for s, qualifica, vota in aventi_diritto(riunione)
        if s.pk not in presenti
    ]
    Presenza.objects.bulk_create(nuove)
    return len(nuove)


@transaction.atomic
def imposta_presenza(presenza, stato, delegato=None):
    presenza = (
        Presenza.objects.select_for_update().select_related("riunione__organo").get(pk=presenza.pk)
    )
    riunione = presenza.riunione
    if riunione.stato != Riunione.Stato.CONVOCATA or _verbale_chiuso(riunione):
        raise OperazioneNonValida("Le presenze non sono più modificabili.")
    if stato == Presenza.Stato.DELEGA:
        organo = riunione.organo
        if not organo.max_deleghe:
            raise OperazioneNonValida(f"Per {organo} le deleghe non sono ammesse.")
        if delegato is None or delegato.riunione_id != riunione.pk or delegato.pk == presenza.pk:
            raise OperazioneNonValida("Scegliere il delegato tra gli intervenuti.")
        delegato = Presenza.objects.select_for_update().get(pk=delegato.pk)  # stato attuale
        if not delegato.intervenuto:
            raise OperazioneNonValida(f"{delegato} non risulta presente.")
        if not presenza.vota:
            raise OperazioneNonValida(f"{presenza} non ha diritto di voto: non può delegare.")
        ricevute = delegato.deleghe_ricevute.exclude(pk=presenza.pk).count()
        if ricevute >= organo.max_deleghe:
            raise OperazioneNonValida(
                f"{delegato} ha già {ricevute} deleghe (massimo {organo.max_deleghe})."
            )
        presenza.delegato = delegato
    else:
        presenza.delegato = None
        if stato not in (Presenza.Stato.PRESENTE, Presenza.Stato.COLLEGATO):
            # chi non è presente non può portare deleghe
            presenza.deleghe_ricevute.update(stato=Presenza.Stato.ASSENTE, delegato=None)
    presenza.stato = stato
    presenza.save(update_fields=["stato", "delegato"])
    return presenza


def _verbale_chiuso(riunione):
    return Verbale.objects.filter(riunione=riunione, chiuso=True).exists()


@dataclass
class Quorum:
    aventi_diritto: int
    intervenuti: int
    rappresentati: int
    richiesto: int
    percentuale: int

    @property
    def totale(self):
        return self.intervenuti + self.rappresentati

    @property
    def valido(self):
        return self.totale >= max(self.richiesto, 1)


def quorum(riunione, convocazione="prima"):
    organo = riunione.organo
    presenze = list(riunione.presenze.filter(vota=True).select_related("delegato"))
    aventi = len(presenze)
    intervenuti = sum(1 for p in presenze if p.intervenuto)
    rappresentati = sum(
        1
        for p in presenze
        if p.stato == Presenza.Stato.DELEGA and p.delegato and p.delegato.intervenuto
    )
    perc = organo.quorum_prima if convocazione == "prima" else organo.quorum_seconda
    # «oltre la percentuale»: con 50% su 10 aventi diritto servono 6 presenti
    richiesto = aventi * perc // 100 + 1 if perc else 1
    return Quorum(aventi, intervenuti, rappresentati, min(richiesto, max(aventi, 1)), perc)


# --- verbale e delibere ----------------------------------------------------------------------


@transaction.atomic
def apri_verbale(riunione, utente):
    if riunione.stato not in (Riunione.Stato.CONVOCATA, Riunione.Stato.VERBALIZZATA):
        raise OperazioneNonValida("Il verbale si redige per le riunioni convocate.")
    verbale, creato = Verbale.objects.get_or_create(
        riunione=riunione,
        defaults={
            "luogo": riunione.luogo,
            "inizio": riunione.prima_convocazione,
            "creato_da": utente,
            "modificato_da": utente,
        },
    )
    if creato:
        _proponi_presidenza(verbale)
        registra(Azione.CREAZIONE, verbale, utente=utente)
    return verbale


def _proponi_presidenza(verbale):
    giorno = timezone.localtime(verbale.riunione.prima_convocazione).date()
    consiglio = Organo.objects.filter(tipo=Organo.Tipo.CONSIGLIO).first()
    organo = verbale.riunione.organo if not verbale.riunione.organo.e_assemblea else consiglio
    if organo is None:
        return
    cariche = {c.ruolo: c for c in organo.cariche_al(giorno).select_related("soggetto")}
    for ruolo, campo in (("presidente", "presidente"), ("segretario", "segretario")):
        if ruolo in cariche:
            setattr(verbale, campo, cariche[ruolo].soggetto.nome_completo)
    verbale.save()


def _controlla_aperto(verbale):
    if verbale.chiuso:
        raise OperazioneNonValida("Il verbale è chiuso e non si modifica più.")


@transaction.atomic
def salva_verbale(form, discussioni, utente):
    """Salva l'intestazione del verbale e la discussione dei punti (`{punto_id: testo}`)."""
    _controlla_aperto(form.instance)
    dettagli = campi_modificati(form)
    verbale = form.save(commit=False)
    verbale.modificato_da = utente
    verbale.save()
    for punto in verbale.riunione.punti.all():
        testo = discussioni.get(punto.pk)
        if testo is not None and testo != punto.discussione:
            punto.discussione = testo
            punto.save(update_fields=["discussione"])
    if dettagli.get("campi"):
        registra(Azione.MODIFICA, verbale, utente=utente, **dettagli)
    return verbale


@transaction.atomic
def salva_delibera(form, verbale):
    _controlla_aperto(verbale)
    delibera = form.save(commit=False)
    delibera.verbale = verbale
    if delibera.unanimita:
        delibera.contrari = delibera.astenuti = 0
    delibera.save()
    return delibera


@transaction.atomic
def elimina_delibera(delibera):
    _controlla_aperto(delibera.verbale)
    delibera.delete()


@transaction.atomic
def chiudi_verbale(verbale, utente, *, protocolla=False):
    """Chiude il verbale: numero nel libro, numeri delle delibere, PDF con impronta."""
    verbale = (
        Verbale.objects.select_for_update().select_related("riunione__organo").get(pk=verbale.pk)
    )
    _controlla_aperto(verbale)
    riunione = verbale.riunione
    organo = riunione.organo
    if not verbale.presidente or not verbale.segretario:
        raise OperazioneNonValida("Indicare presidente e segretario della seduta.")
    if not riunione.presenze.exists():
        raise OperazioneNonValida("Registrare prima le presenze.")
    q = quorum(riunione, verbale.convocazione)
    delibere = list(verbale.delibere.select_related("punto").order_by("punto__ordine", "id"))
    if delibere and not q.valido:
        raise OperazioneNonValida(
            f"Seduta non valida ({q.totale} su {q.aventi_diritto}, ne servono {q.richiesto}): "
            "un verbale senza numero legale non può contenere delibere."
        )
    adesso = timezone.now()
    verbale.numero = prossimo_numero(_seq("verbale", organo))
    anno = timezone.localtime(verbale.inizio or riunione.prima_convocazione).year
    for d in delibere:
        d.anno = anno
        d.numero = prossimo_numero(_seq("delibera", organo), anno)
        d.save(update_fields=["anno", "numero"])
    verbale.presenti = q.intervenuti
    verbale.rappresentati = q.rappresentati
    verbale.aventi_diritto = q.aventi_diritto
    verbale.chiuso = True
    verbale.chiuso_il = adesso
    verbale.chiuso_da = utente
    verbale.modificato_da = utente
    pdf = pdf_verbale(verbale, q)
    verbale.impronta = hashlib.sha256(pdf).hexdigest()
    verbale.file.save(
        f"verbale_{organo.sigla.lower()}_{verbale.numero:04d}.pdf", ContentFile(pdf), save=False
    )
    verbale.save()
    riunione.stato = Riunione.Stato.VERBALIZZATA
    riunione.save(update_fields=["stato"])
    if protocolla:
        verbale.protocollo = _protocolla_verbale(verbale, pdf, utente)
        verbale.save(update_fields=["protocollo"])
    registra(
        Azione.MODIFICA,
        verbale,
        utente=utente,
        chiuso=True,
        numero=verbale.numero,
        delibere=[d.codice for d in delibere],
        impronta=verbale.impronta,
    )
    return verbale


def pdf_verbale(verbale, q=None):
    from apps.core.pdf import genera_pdf

    riunione = verbale.riunione
    return genera_pdf(
        "organi/pdf/verbale.html",
        {
            "v": verbale,
            "r": riunione,
            "q": q or quorum(riunione, verbale.convocazione),
            "punti": riunione.punti.prefetch_related("delibere"),
            "delibere_senza_punto": verbale.delibere.filter(punto__isnull=True),
            "presenze": riunione.presenze.select_related("delegato").order_by("descrizione"),
            "organizzazione": Organizzazione.corrente(),
        },
    )


def _protocolla_verbale(verbale, pdf, utente):
    from apps.protocollo import servizi as protocollo
    from apps.protocollo.models import Protocollo

    p = protocollo.registra_protocollo(
        {
            "direzione": Protocollo.Direzione.INTERNO,
            "mezzo": Protocollo.Mezzo.ALTRO,
            "oggetto": f"Verbale n. {verbale.numero} - {verbale.riunione}",
            "classificazione": _classificazione_organi(),
        },
        [],
        utente,
    )
    protocollo.aggiungi_allegato(
        p, ContentFile(pdf, name="verbale.pdf"), utente, principale=True, controlla=False
    )
    return p


def delibere_registro():
    return Delibera.objects.filter(verbale__chiuso=True).select_related(
        "verbale__riunione__organo", "punto"
    )


# --- organigramma --------------------------------------------------------------------------------

LIVELLI_ORGANIGRAMMA = [
    ["presidente"],
    ["vicepresidente", "segretario", "tesoriere"],
    ["consigliere"],
    ["presidente_controllo", "componente"],
    ["supplente"],
]


def organigramma(organo, giorno=None):
    """Componenti in carica raggruppati per livello (presidenza, ufficio, consiglieri...)."""
    cariche = list(organo.cariche_al(giorno).select_related("soggetto").order_by("dal"))
    livelli = []
    for ruoli in LIVELLI_ORGANIGRAMMA:
        riga = sorted(
            (c for c in cariche if c.ruolo in ruoli),
            key=lambda c: (ruoli.index(c.ruolo), c.soggetto.nome_completo),
        )
        if riga:
            livelli.append(riga)
    return livelli


def pdf_organigramma(organo, utente):
    from apps.core.pdf import genera_pdf

    oggi = timezone.localdate()
    pdf = genera_pdf(
        "organi/pdf/organigramma.html",
        {"organo": organo, "livelli": organigramma(organo, oggi), "oggi": oggi,
         "organizzazione": Organizzazione.corrente()},
    )  # fmt: skip
    registra(Azione.ESPORTAZIONE, organo, utente=utente, documento="organigramma")
    return pdf
