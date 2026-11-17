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
from datetime import date

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.core.audit import Azione, campi_modificati, registra
from apps.core.models import Organizzazione
from apps.core.numerazione import prossimo_numero

from .models import (
    Carica,
    Delibera,
    FirmaGrafica,
    Organo,
    Presenza,
    PuntoOdg,
    RappresentanteLegale,
    Riunione,
    Timbro,
    Verbale,
)


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
    if carica.al is not None and carica.al <= timezone.localdate():
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


@transaction.atomic
def modifica_carica(carica, utente, *, dal, al=None, atto="", note=""):
    """Corregge le date (inizio e cessazione; vuota = in carica), l'atto di nomina e le note."""
    from django.db.models import Q

    carica = (
        Carica.objects.select_for_update().select_related("soggetto", "organo").get(pk=carica.pk)
    )
    if al is not None and al < dal:
        raise OperazioneNonValida("La cessazione non può precedere l'inizio.")
    # periodi [dal, al) della stessa persona nello stesso organo: non devono sovrapporsi
    altre = Carica.objects.filter(organo=carica.organo, soggetto=carica.soggetto).exclude(
        pk=carica.pk
    )
    altre = altre.filter(Q(al__isnull=True) | Q(al__gt=dal))
    if al is not None:
        altre = altre.filter(dal__lt=al)
    if altre.exists():
        a = altre.first()
        periodo = f"dal {a.dal:%d/%m/%Y}" + (f" al {a.al:%d/%m/%Y}" if a.al else "")
        raise OperazioneNonValida(
            f"Il periodo si sovrappone a un'altra carica di {carica.soggetto} in questo organo "
            f"({a.get_ruolo_display().lower()} {periodo})."
        )
    prima = {"dal": str(carica.dal), "al": str(carica.al or ""), "nomina": carica.nomina,
             "note": carica.note}  # fmt: skip
    carica.dal, carica.al, carica.nomina, carica.note = dal, al, atto[:200], note[:255]
    dopo = {"dal": str(carica.dal), "al": str(carica.al or ""), "nomina": carica.nomina,
            "note": carica.note}  # fmt: skip
    cambiati = {k: {"prima": prima[k], "dopo": dopo[k]} for k in prima if prima[k] != dopo[k]}
    if not cambiati:
        return carica
    carica.modificato_da = utente
    carica.save()
    registra(Azione.MODIFICA, carica, utente=utente, organo=str(carica.organo), **cambiati)
    return carica


# --- rappresentante legale ----------------------------------------------------------------


def _sovrapposte(sezione, dal, al, escludi=None):
    """Nomine dello stesso ente il cui periodo [dal, al) si sovrappone a quello indicato."""
    from django.db.models import Q

    altre = RappresentanteLegale.objects.filter(sezione=sezione).filter(
        Q(al__isnull=True) | Q(al__gt=dal)
    )
    if al is not None:
        altre = altre.filter(dal__lt=al)
    if escludi is not None:
        altre = altre.exclude(pk=escludi.pk)
    return altre


def _periodo(r):
    return f"dal {r.dal:%d/%m/%Y}" + (f" al {r.al:%d/%m/%Y}" if r.al else "")


@transaction.atomic
def nomina_rappresentante(
    soggetto, dal, utente, *, sezione=None, tutta_la_struttura=False, qualifica="", atto="",
    note="",
):  # fmt: skip
    """Registra il rappresentante legale dell'associazione (sezione None) o di una sezione.

    Chi era in carica senza data di fine cessa dal giorno della nuova nomina; un periodo che si
    sovrapporrebbe a una nomina già conclusa va corretto prima.
    """
    if not soggetto.is_persona:
        raise OperazioneNonValida("Il rappresentante legale è una persona.")
    if sezione is not None and tutta_la_struttura:
        raise OperazioneNonValida(
            "«Tutta la struttura» vale solo per il rappresentante dell'associazione."
        )
    list(RappresentanteLegale.objects.select_for_update().filter(sezione=sezione).order_by("pk"))
    for precedente in _sovrapposte(sezione, dal, None):
        if precedente.al is None and precedente.dal < dal:
            precedente.al = dal
            precedente.modificato_da = utente
            precedente.save()
            registra(Azione.MODIFICA, precedente, utente=utente, fine=str(dal),
                     motivo="nuovo rappresentante legale")  # fmt: skip
        else:
            raise OperazioneNonValida(
                f"Esiste già un rappresentante legale per lo stesso periodo: "
                f"{precedente.soggetto} {_periodo(precedente)}."
            )
    nomina = RappresentanteLegale.objects.create(
        sezione=sezione, tutta_la_struttura=tutta_la_struttura, soggetto=soggetto,
        qualifica=(qualifica or RappresentanteLegale.QUALIFICA_PREDEFINITA)[:100], dal=dal,
        nomina=atto[:200], note=note[:255], creato_da=utente, modificato_da=utente,
    )  # fmt: skip
    registra(Azione.CREAZIONE, nomina, utente=utente, ambito=nomina.ambito)
    return nomina


@transaction.atomic
def modifica_rappresentante(nomina, utente, *, qualifica, dal, al=None, tutta_la_struttura=False,
                            atto="", note=""):  # fmt: skip
    """Corregge qualifica, periodo (al vuoto = in carica), estensione, atto e note."""
    nomina = (
        RappresentanteLegale.objects.select_for_update(of=("self",))
        .select_related("soggetto", "sezione")
        .order_by()
        .get(pk=nomina.pk)
    )
    if al is not None and al < dal:
        raise OperazioneNonValida("La cessazione non può precedere l'inizio.")
    if nomina.sezione_id and tutta_la_struttura:
        raise OperazioneNonValida(
            "«Tutta la struttura» vale solo per il rappresentante dell'associazione."
        )
    altra = _sovrapposte(nomina.sezione, dal, al, escludi=nomina).first()
    if altra:
        raise OperazioneNonValida(
            f"Il periodo si sovrappone a quello di {altra.soggetto} {_periodo(altra)}."
        )
    campi = ("qualifica", "dal", "al", "tutta_la_struttura", "nomina", "note")
    prima = {k: str(getattr(nomina, k) or "") for k in campi}
    nomina.qualifica = (qualifica or RappresentanteLegale.QUALIFICA_PREDEFINITA)[:100]
    nomina.dal, nomina.al, nomina.tutta_la_struttura = dal, al, tutta_la_struttura
    nomina.nomina, nomina.note = atto[:200], note[:255]
    dopo = {k: str(getattr(nomina, k) or "") for k in campi}
    cambiati = {k: {"prima": prima[k], "dopo": dopo[k]} for k in campi if prima[k] != dopo[k]}
    if not cambiati:
        return nomina
    nomina.modificato_da = utente
    nomina.save()
    registra(Azione.MODIFICA, nomina, utente=utente, **cambiati)
    return nomina


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
        if organo.sezione_id:  # assemblea di sezione: i soci di quella sezione
            soci = soci.filter(sezione_id=organo.sezione_id)
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


def _pdf_schede(organi, oggi):
    from apps.core.pdf import genera_pdf

    schede = [(o, organigramma(o, oggi)) for o in organi]
    return genera_pdf(
        "organi/pdf/organigramma.html",
        {"schede": schede, "oggi": oggi, "organizzazione": Organizzazione.corrente()},
    )


def pdf_organigramma(organo, utente):
    oggi = timezone.localdate()
    pdf = _pdf_schede([organo], oggi)
    registra(Azione.ESPORTAZIONE, organo, utente=utente, documento="organigramma")
    return pdf


def organi_con_cariche(sezione):
    """Organi della sezione (None = dell'associazione) che hanno componenti: niente assemblee."""
    return Organo.objects.filter(sezione=sezione, attivo=True).exclude(tipo=Organo.Tipo.ASSEMBLEA)


def pdf_organigramma_sezione(sezione, utente):
    """Un PDF con l'organigramma di ogni organo della sezione (una pagina per organo)."""
    organi = list(organi_con_cariche(sezione))
    if not organi:
        raise OperazioneNonValida(f"La sezione {sezione} non ha organi con cariche.")
    oggi = timezone.localdate()
    pdf = _pdf_schede(organi, oggi)
    registra(Azione.ESPORTAZIONE, sezione, utente=utente, documento="organigramma della sezione")
    return pdf


ORGANI_DI_SEZIONE = [
    ("Consiglio direttivo", "CD", Organo.Tipo.CONSIGLIO),
    ("Assemblea dei soci", "ASS", Organo.Tipo.ASSEMBLEA),
]


@transaction.atomic
def crea_organi_sezione(sezione, utente):
    """Consiglio direttivo e assemblea della sezione, con le regole degli organi omologhi
    dell'associazione. Quelli già presenti non vengono duplicati."""
    creati = []
    regole = ("quorum_prima", "quorum_seconda", "max_deleghe", "solo_soci_in_regola", "ordine")
    for nome, sigla, tipo in ORGANI_DI_SEZIONE:
        if Organo.objects.filter(sezione=sezione, tipo=tipo).exists():
            continue
        modello = Organo.objects.filter(sezione__isnull=True, tipo=tipo).first()
        dati = {r: getattr(modello, r) for r in regole} if modello else {}
        organo = Organo.objects.create(nome=nome, sigla=sigla, tipo=tipo, sezione=sezione, **dati)
        registra(Azione.CREAZIONE, organo, utente=utente, sezione=str(sezione))
        creati.append(organo)
    return creati


# --- firme e timbri per le stampe ------------------------------------------------------------

RUOLI_FIRMATARI = [
    "presidente",
    "vicepresidente",
    "segretario",
    "tesoriere",
    "presidente_controllo",
]


def _salva_immagine(contrassegno, file, utente, sfondo_trasparente):
    """Immagine ripulita (PNG senza metadati, sfondo trasparente, ritagliata) al posto della
    precedente, che si cancella dal disco solo a transazione conclusa."""
    from django.core.files.storage import default_storage

    from apps.core.immagini import ImmagineNonValida, ripulisci_contrassegno

    try:
        png = ripulisci_contrassegno(file, sfondo_trasparente=sfondo_trasparente)
    except ImmagineNonValida as e:
        raise OperazioneNonValida(e.messages) from None
    dati = png.read()
    precedente = contrassegno.immagine.name if contrassegno.immagine else ""
    contrassegno.impronta = hashlib.sha256(dati).hexdigest()
    contrassegno.immagine.save("contrassegno.png", ContentFile(dati), save=False)
    contrassegno.attiva = True
    contrassegno.caricata_da = utente
    contrassegno.save()
    if precedente:
        transaction.on_commit(lambda: default_storage.delete(precedente))


def _elimina_dopo(nome):
    from django.core.files.storage import default_storage

    if nome:
        transaction.on_commit(lambda: default_storage.delete(nome))


@transaction.atomic
def carica_firma(soggetto, file, utente, *, sfondo_trasparente=True, autorizzazione=""):
    if not soggetto.is_persona:
        raise OperazioneNonValida("La firma si carica per una persona, non per un ente.")
    firma = FirmaGrafica.objects.filter(soggetto=soggetto).first()
    nuova = firma is None
    firma = firma or FirmaGrafica(soggetto=soggetto)
    firma.autorizzazione = (autorizzazione or "").strip()[:200]
    _salva_immagine(firma, file, utente, sfondo_trasparente)
    registra(
        Azione.CREAZIONE if nuova else Azione.MODIFICA,
        firma,
        utente=utente,
        descrizione=f"Firma grafica di {soggetto.nome_completo}",
        impronta=firma.impronta,
        autorizzazione=firma.autorizzazione,
    )
    return firma


@transaction.atomic
def carica_timbro(sezione, file, utente, *, sfondo_trasparente=True):
    timbro = Timbro.objects.filter(sezione=sezione).first()
    nuovo = timbro is None
    timbro = timbro or Timbro(sezione=sezione)
    _salva_immagine(timbro, file, utente, sfondo_trasparente)
    registra(
        Azione.CREAZIONE if nuovo else Azione.MODIFICA,
        timbro,
        utente=utente,
        descrizione=str(timbro),
        impronta=timbro.impronta,
    )
    return timbro


@transaction.atomic
def imposta_uso(contrassegno, attiva, utente):
    """Accende o spegne l'uso nelle stampe (l'immagine resta)."""
    if contrassegno.attiva != attiva:
        contrassegno.attiva = attiva
        contrassegno.save(update_fields=["attiva"])
        registra(
            Azione.MODIFICA, contrassegno, utente=utente, descrizione=str(contrassegno),
            usa_nelle_stampe=attiva,
        )  # fmt: skip


@transaction.atomic
def togli_contrassegno(contrassegno, utente):
    descrizione = str(contrassegno)
    _elimina_dopo(contrassegno.immagine.name)
    registra(Azione.ELIMINAZIONE, contrassegno, utente=utente, descrizione=descrizione)
    contrassegno.delete()


@transaction.atomic
def imposta_generici(utente, *, firma_generica=None, timbro_generico=None):
    """Firma e timbro generici; None = lascia com'è (le due impostazioni stanno in pagine
    diverse: firme in Organi sociali, timbro in Sistema → Organizzazione)."""
    org = Organizzazione.corrente()
    prima = (org.firma_generica, org.timbro_generico)
    if firma_generica is not None:
        org.firma_generica = firma_generica
    if timbro_generico is not None:
        org.timbro_generico = timbro_generico
    org.save(update_fields=["firma_generica", "timbro_generico"])
    if prima != (org.firma_generica, org.timbro_generico):
        registra(
            Azione.MODIFICA, org, utente=utente, descrizione="Firme e timbri generici",
            firma_generica=org.firma_generica, timbro_generico=org.timbro_generico,
        )  # fmt: skip


def _sezioni(utente):
    """Id delle sezioni a cui è limitato l'utente (presidente di sezione), None = tutte."""
    from apps.soci import sezioni

    return sezioni.id_sezioni(utente) if utente is not None else None


def firmatari(giorno=None, utente=None):
    """Chi può comparire oggi in calce alle stampe: cariche con firma (presidente, segretario,
    tesoriere...) e rappresentanti legali in carica, più chi ha già una firma caricata.

    Per un utente limitato alle sue sezioni: solo cariche e rappresentanti di quelle sezioni.
    """
    from django.db.models import Q

    from apps.anagrafica.models import Soggetto

    giorno = giorno or timezone.localdate()
    ids = _sezioni(utente)
    ruoli = {}
    cariche = (
        Carica.objects.filter(ruolo__in=RUOLI_FIRMATARI, dal__lte=giorno)
        .filter(Q(al__isnull=True) | Q(al__gt=giorno))
        .select_related("organo__sezione")
    )
    rappresentanti = RappresentanteLegale.objects.filter(dal__lte=giorno).filter(
        Q(al__isnull=True) | Q(al__gt=giorno)
    )
    if ids is not None:
        cariche = cariche.filter(organo__sezione__in=ids)
        rappresentanti = rappresentanti.filter(sezione__in=ids)
    for c in cariche:
        ente = f" (sezione di {c.organo.sezione.nome})" if c.organo.sezione_id else ""
        ruoli.setdefault(c.soggetto_id, []).append(f"{c.get_ruolo_display()} - {c.organo}{ente}")
    for r in rappresentanti.select_related("sezione"):
        ruoli.setdefault(r.soggetto_id, []).append(f"{r.qualifica} ({r.ambito})")
    firme = FirmaGrafica.objects.all()
    if ids is not None:
        firme = firme.filter(soggetto__in=list(ruoli))
    firme = {f.soggetto_id: f for f in firme}
    persone = Soggetto.objects.filter(pk__in=set(ruoli) | set(firme))
    return [
        {"soggetto": p, "ruoli": ruoli.get(p.pk, []), "firma": firme.get(p.pk)}
        for p in persone.order_by("cognome", "nome")
    ]


def timbri_per_ente(utente=None):
    """[(sezione o None, timbro o None)] per l'associazione e le sezioni attive (per un utente
    limitato, solo le sue sezioni)."""
    from apps.soci.models import Sezione

    ids = _sezioni(utente)
    timbri = {t.sezione_id: t for t in Timbro.objects.all()}
    attive = Sezione.objects.filter(attiva=True)
    sezioni = [None, *attive] if ids is None else list(attive.filter(pk__in=ids))
    return [(s, timbri.get(s.pk if s else None)) for s in sezioni]


def puo_gestire_firma(utente, soggetto):
    if _sezioni(utente) is None:
        return True
    return any(r["soggetto"].pk == soggetto.pk for r in firmatari(utente=utente))


def puo_gestire_timbro(utente, sezione):
    ids = _sezioni(utente)
    return ids is None or (sezione is not None and sezione.pk in ids)


def puo_gestire_contrassegno(utente, contrassegno):
    if isinstance(contrassegno, Timbro):
        return puo_gestire_timbro(utente, contrassegno.sezione)
    return puo_gestire_firma(utente, contrassegno.soggetto)


def gestisce_tutto(utente):
    """Associazione e interruttori generali: solo chi non è limitato a una sezione."""
    return _sezioni(utente) is None


# --- scadenza dei mandati ----------------------------------------------------------------------


def mandati_in_scadenza(oggi=None):
    """Cariche in corso il cui mandato scade entro il preavviso dell'organo (anche già scaduto,
    finché non si registra la fine): [(carica, scadenza, giorni mancanti)] in ordine di scadenza."""
    oggi = oggi or date.today()
    elenco = []
    cariche = (
        Carica.objects.filter(organo__attivo=True, organo__durata_mandato__isnull=False)
        .filter(Q(al__isnull=True) | Q(al__gt=oggi))
        .select_related("organo", "soggetto")
    )
    for c in cariche:
        scadenza = c.scadenza_mandato
        if scadenza and (scadenza - oggi).days <= c.organo.preavviso_mandato:
            elenco.append((c, scadenza, (scadenza - oggi).days))
    return sorted(elenco, key=lambda x: (x[1], x[0].organo.ordine, x[0].ruolo))
