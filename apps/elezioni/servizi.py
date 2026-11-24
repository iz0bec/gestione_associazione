# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Procedura di rinnovo degli organi: termini calcolati dal profilo elettorale,
# *              indizione, convocazione con gli aventi diritto fissati all'avviso, compilazione
# *              e controllo delle liste, ammissione, esiti del voto, proclamazione, ricorsi,
# *              insediamento (nomine automatiche), passaggio di consegne e trasmissione.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import math
from dataclasses import dataclass
from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.core.audit import Azione, registra

from .models import Candidato, Decadenza, Lista, ProfiloElettorale, Ricorso, Rinnovo

ORIGINE = "rinnovo-organi"
Fase = Rinnovo.Fase
Incarico = Candidato.Incarico


class OperazioneNonValida(ValidationError):
    pass


# --- profili preimpostati ------------------------------------------------------------------

PROFILI = [
    {
        "nome": "ANCR - Congresso sezionale",
        "livello": "sezione",
        "riferimento": "Statuto artt. 46-48; Regolamento applicativo artt. 6, 8 e 22",
        "nome_assemblea": "Congresso sezionale",
        "giorni_indizione": 60, "giorni_avviso": 8, "giorni_liste": 15, "giorni_ricorsi": 15,
        "organo_ricorsi": "Consiglio direttivo provinciale della Federazione",
        "giorni_trasmissione": 10,
        "destinatario_verbali": "Federazione provinciale (per la Commissione nazionale verifica "
        "soci)",
        "giorni_consegne": 10, "soglia_soci": 100,
        "consiglieri_sotto_min": 0, "consiglieri_sotto_max": 0,
        "sindaci_sotto_min": 1, "sindaci_sotto_max": 1, "garanti_sotto": 0,
        "consiglieri_sopra": 4, "sindaci_sopra_min": 1, "sindaci_sopra_max": 3,
        "garanti_sopra": 3, "supplenti_max": 4, "max_deleghe": 2,
        "modelli": "ancr_sezione",
    },
    {
        "nome": "ANCR - Congresso provinciale",
        "livello": "federazione",
        "riferimento": "Statuto artt. 34-36 e 45; Regolamento applicativo artt. 6, 8 e 21",
        "nome_assemblea": "Congresso provinciale",
        "giorni_indizione": 60, "giorni_avviso": 30, "giorni_liste": 30, "giorni_ricorsi": 15,
        "organo_ricorsi": "Collegio centrale dei garanti",
        "giorni_trasmissione": 10,
        "destinatario_verbali": "Commissione nazionale verifica soci (Presidenza nazionale)",
        "giorni_consegne": 10, "soglia_soci": 100,
        "consiglieri_sotto_min": 0, "consiglieri_sotto_max": 4,
        "sindaci_sotto_min": 1, "sindaci_sotto_max": 3, "garanti_sotto": 0,
        "consiglieri_sopra": 4, "sindaci_sopra_min": 1, "sindaci_sopra_max": 3,
        "garanti_sopra": 3, "seconda_soglia": 400, "soci_per_consigliere": 100,
        "consiglieri_massimo": 10, "supplenti_max": 4, "max_deleghe": 2,
        "dichiarazione_requisiti": True, "voto_ponderato": True,
        "modelli": "ancr_federazione",
    },
    {
        "nome": "Associazione (ETS) - Assemblea elettiva",
        "livello": "associazione",
        "riferimento": "Statuto dell'associazione (da completare)",
        "nome_assemblea": "Assemblea dei soci",
        "giorni_indizione": 30, "giorni_avviso": 8, "giorni_liste": 8, "giorni_ricorsi": 15,
        "organo_ricorsi": "Organo di garanzia (se previsto dallo statuto)",
        "giorni_trasmissione": 30, "destinatario_verbali": "", "giorni_consegne": 15,
        "soglia_soci": 100, "consiglieri_sotto_min": 0, "consiglieri_sotto_max": 4,
        "sindaci_sotto_min": 0, "sindaci_sotto_max": 1, "garanti_sotto": 0,
        "consiglieri_sopra": 4, "sindaci_sopra_min": 0, "sindaci_sopra_max": 3,
        "garanti_sopra": 0, "supplenti_max": 2, "max_deleghe": 3,
        "sospende_tesseramento": False, "modelli": "generico",
    },
]  # fmt: skip


def crea_profili_predefiniti():
    """Crea i profili preimpostati che mancano (rieseguibile, non tocca quelli modificati)."""
    for dati in PROFILI:
        ProfiloElettorale.objects.get_or_create(nome=dati["nome"], defaults=dati)


# --- scadenze ------------------------------------------------------------------------------


def organo_consiglio(sezione):
    from apps.organi.models import Organo

    return (
        Organo.objects.filter(sezione=sezione, tipo=Organo.Tipo.CONSIGLIO, attivo=True)
        .order_by("ordine", "pk")
        .first()
    )


def scadenza_mandato(sezione):
    """Prima scadenza dei mandati in corso nel consiglio della sezione (o dell'ente)."""
    organo = organo_consiglio(sezione)
    if organo is None:
        return None
    scadenze = [c.scadenza_mandato for c in organo.cariche_al() if c.scadenza_mandato]
    return min(scadenze) if scadenze else None


@dataclass
class Termine:
    codice: str
    titolo: str
    entro: date | None
    fatto: date | None = None
    nota: str = ""

    @property
    def stato(self):
        if self.fatto:
            return "fatto"
        if self.entro and self.entro < timezone.localdate():
            return "scaduto"
        if self.entro and self.entro <= timezone.localdate() + timedelta(days=7):
            return "vicino"
        return "da_fare"


def _giorno(momento):
    if momento is None:
        return None
    return timezone.localtime(momento).date() if hasattr(momento, "hour") else momento


def termini(rinnovo):
    """Le fasi con la data entro cui farle (dal profilo) e quando sono state fatte."""
    p = rinnovo.profilo
    assemblea = _giorno(rinnovo.data_assemblea)
    voto = rinnovo.votato_il
    meno = lambda giorno, n: giorno - timedelta(days=n) if giorno else None  # noqa: E731
    piu = lambda giorno, n: giorno + timedelta(days=n) if giorno else None  # noqa: E731
    return [
        Termine("indizione", f"Indizione ({p.nome_assemblea.lower()})",
                meno(rinnovo.scadenza, p.giorni_indizione), rinnovo.indetto_il,
                f"almeno {p.giorni_indizione} giorni prima " + (
                    "del termine del commissariamento" if rinnovo.straordinario
                    else "della scadenza del mandato")),
        Termine("avviso", "Avviso di convocazione", meno(assemblea, p.giorni_avviso),
                rinnovo.avviso_il, f"almeno {p.giorni_avviso} giorni prima; fissa gli aventi "
                "diritto al voto"),
        Termine("liste", "Presentazione delle liste", rinnovo.termine_liste
                or meno(assemblea, p.giorni_liste),
                _giorno(rinnovo.liste.exclude(stato="bozza").order_by("-presentata_il")
                        .values_list("presentata_il", flat=True).first())
                if rinnovo.fase not in (Fase.PREPARAZIONE, Fase.INDETTO, Fase.CONVOCATO) else None,
                f"entro {p.giorni_liste} giorni prima; poi il consiglio uscente le ammette"),
        Termine("assemblea", p.nome_assemblea, assemblea, voto, rinnovo.luogo),
        Termine("ricorsi", "Termine per i ricorsi", piu(voto, p.giorni_ricorsi), None,
                f"entro {p.giorni_ricorsi} giorni dal voto, a: {p.organo_ricorsi}"),
        Termine("trasmissione", "Trasmissione dei verbali", piu(voto, p.giorni_trasmissione),
                rinnovo.trasmesso_il, f"a: {p.destinatario_verbali}"),
        Termine("consegne", "Passaggio di consegne", piu(voto, p.giorni_consegne),
                rinnovo.consegne_il, "verbale tra presidente uscente e nuovo presidente"),
    ]  # fmt: skip


def prossimo_termine(rinnovo):
    return next((t for t in termini(rinnovo) if not t.fatto and t.entro), None)


# --- creazione e fasi iniziali -------------------------------------------------------------


def _controlla_aperto(rinnovo):
    if not rinnovo.aperto:
        raise OperazioneNonValida("Il rinnovo è concluso o annullato.")


@transaction.atomic
def nuovo_rinnovo(utente, *, profilo, sezione=None, quadriennio=""):
    if (
        Rinnovo.objects.filter(sezione=sezione)
        .exclude(fase__in=[Fase.CONCLUSO, Fase.ANNULLATO])
        .exists()
    ):
        raise OperazioneNonValida("C'è già un rinnovo in corso per questi organi.")
    scadenza = scadenza_mandato(sezione)
    if not quadriennio:
        inizio = (scadenza or timezone.localdate()).year
        quadriennio = f"{inizio}-{inizio + profilo.durata_mandato}"
    rinnovo = Rinnovo.objects.create(
        profilo=profilo, sezione=sezione, quadriennio=quadriennio, scadenza=scadenza,
        creato_da=utente, modificato_da=utente,
    )  # fmt: skip
    registra(Azione.CREAZIONE, rinnovo, utente=utente, profilo=profilo.nome)
    return rinnovo


@transaction.atomic
def indici(rinnovo, utente, *, giorno, atto=""):
    _controlla_aperto(rinnovo)
    if rinnovo.fase != Fase.PREPARAZIONE:
        raise OperazioneNonValida("Il rinnovo è già stato indetto.")
    rinnovo.indetto_il, rinnovo.delibera_indizione = giorno, atto
    rinnovo.fase, rinnovo.modificato_da = Fase.INDETTO, utente
    rinnovo.save()
    registra(Azione.MODIFICA, rinnovo, utente=utente, fase="indetto", atto=atto)
    avvisi = []
    entro = termini(rinnovo)[0].entro
    if entro and giorno > entro:
        avvisi.append(f"Indetto oltre il termine (entro il {entro:%d/%m/%Y}).")
    return avvisi


def controlla_assemblea(rinnovo):
    """Avvisi sui tempi dell'assemblea rispetto al profilo (non bloccanti)."""
    p, avvisi = rinnovo.profilo, []
    if rinnovo.data_assemblea and rinnovo.seconda_convocazione:
        distanza = rinnovo.seconda_convocazione - rinnovo.data_assemblea
        if distanza < timedelta(hours=p.ore_seconda_convocazione):
            avvisi.append(f"La seconda convocazione dev'essere almeno {p.ore_seconda_convocazione}"
                          " ora/e dopo la prima.")  # fmt: skip
    if (
        rinnovo.data_assemblea
        and rinnovo.scadenza
        and (_giorno(rinnovo.data_assemblea) > rinnovo.scadenza)
    ):
        avvisi.append("L'assemblea è dopo la scadenza del mandato.")
    if rinnovo.apertura_seggio and rinnovo.chiusura_seggio:
        inizio = rinnovo.apertura_seggio.hour * 60 + rinnovo.apertura_seggio.minute
        fine = rinnovo.chiusura_seggio.hour * 60 + rinnovo.chiusura_seggio.minute
        if fine - inizio > p.ore_votazione * 60:
            avvisi.append(f"Le operazioni di voto durano al massimo {p.ore_votazione} ore.")
    return avvisi


@transaction.atomic
def salva_assemblea(form, utente):
    rinnovo = form.save(commit=False)
    _controlla_aperto(rinnovo)
    if rinnovo.data_assemblea and not rinnovo.termine_liste:
        rinnovo.termine_liste = _giorno(rinnovo.data_assemblea) - timedelta(
            days=rinnovo.profilo.giorni_liste
        )
    if rinnovo.data_assemblea and not rinnovo.ordine_del_giorno.strip():
        rinnovo.ordine_del_giorno = odg_predefinito(rinnovo)
    rinnovo.modificato_da = utente
    rinnovo.save()
    registra(Azione.MODIFICA, rinnovo, utente=utente, operazione="assemblea")
    return controlla_assemblea(rinnovo)


def odg_predefinito(rinnovo):
    p = rinnovo.profilo
    return "\n".join([
        f"Nomina del presidente e del segretario del {p.nome_assemblea.lower()}",
        "Relazione del presidente uscente",
        "Nomina della commissione elettorale (se è presentata più di una lista)",
        f"Elezione delle cariche sociali per il mandato {rinnovo.quadriennio}",
        "Proclamazione degli eletti",
        "Varie ed eventuali",
    ])  # fmt: skip


# --- aventi diritto e convocazione ---------------------------------------------------------


def _soci(rinnovo):
    from apps.soci.models import Socio

    soci = Socio.objects.attivi()
    if rinnovo.sezione_id:
        soci = soci.filter(sezione_id=rinnovo.sezione_id)
    return soci


def calcola_aventi(rinnovo, giorno):
    """Sezione/associazione: soci in regola alla data dell'avviso. Federazione: le sezioni attive
    con tanti voti quanti sono i loro soci in regola, rappresentate dal presidente."""
    from apps.soci.models import Sezione, Socio

    anno = giorno.year
    if rinnovo.federazione:
        righe = []
        for sezione in Sezione.objects.filter(attiva=True).order_by("nome"):
            voti = (
                Socio.objects.attivi()
                .filter(sezione=sezione, data_ammissione__lte=giorno)
                .in_regola(anno)
                .count()
            )
            consiglio = organo_consiglio(sezione)
            presidente = None
            if consiglio is not None:
                presidente = consiglio.cariche_al(giorno).filter(ruolo="presidente").first()
            righe.append({
                "sezione": sezione.pk, "nome": sezione.nome, "voti": voti,
                "delegato": presidente.soggetto.nome_completo if presidente else "",
                "soggetto": presidente.soggetto_id if presidente else None, "presente": False,
            })  # fmt: skip
        return righe, sum(r["voti"] for r in righe)
    soci = _soci(rinnovo).filter(data_ammissione__lte=giorno).in_regola(anno)
    righe = [
        {"socio": s.pk, "soggetto": s.soggetto_id, "numero": s.numero,
         "nome": s.soggetto.nome_completo}
        for s in soci.select_related("soggetto").order_by("soggetto__cognome", "soggetto__nome")
    ]  # fmt: skip
    return righe, len(righe)


def voti_totali(rinnovo):
    if rinnovo.federazione:
        return sum(r["voti"] for r in rinnovo.aventi_diritto)
    return len(rinnovo.aventi_diritto)


TESTO_AVVISO = """{saluto}

il {organo} uscente ha indetto il {assemblea} per l'elezione delle cariche sociali per il mandato {quadriennio}.

Prima convocazione: {prima}
Seconda convocazione: {seconda}
Luogo: {luogo}
Seggio elettorale: {seggio}, operazioni di voto dalle {apertura} alle {chiusura}.

Ordine del giorno:
{odg}

Le liste dei candidati si presentano entro il {termine_liste}. {diritto}

Cordiali saluti
Il Presidente"""  # noqa: E501


def testo_avviso(rinnovo):
    p = rinnovo.profilo
    fmt = lambda m: timezone.localtime(m).strftime("%d/%m/%Y alle ore %H:%M") if m else "-"  # noqa: E731
    if rinnovo.federazione:
        diritto = ("Partecipano i presidenti delle sezioni attive o i loro delegati (modello D3), "
                   "con tanti voti quanti sono i soci della sezione.")  # fmt: skip
        saluto = "Ai Presidenti delle Sezioni,"
    else:
        diritto = (
            f"Hanno diritto al voto i soci in regola con il tesseramento alla data di "
            f"questo avviso, anche per delega (al massimo {p.max_deleghe} per socio)."
        )
        saluto = "Cara socia, caro socio,"
    righe = [f"{i}. {r}" for i, r in enumerate(rinnovo.ordine_del_giorno.splitlines(), 1) if r]
    return TESTO_AVVISO.format(
        saluto=saluto, organo="Consiglio direttivo", assemblea=p.nome_assemblea,
        quadriennio=rinnovo.quadriennio, prima=fmt(rinnovo.data_assemblea),
        seconda=fmt(rinnovo.seconda_convocazione), luogo=rinnovo.luogo or "-",
        seggio=rinnovo.seggio or rinnovo.luogo or "-",
        apertura=rinnovo.apertura_seggio.strftime("%H:%M") if rinnovo.apertura_seggio else "-",
        chiusura=rinnovo.chiusura_seggio.strftime("%H:%M") if rinnovo.chiusura_seggio else "-",
        odg="\n".join(righe),
        termine_liste=f"{rinnovo.termine_liste:%d/%m/%Y}" if rinnovo.termine_liste else "-",
        diritto=diritto,
    )  # fmt: skip


@transaction.atomic
def convoca(rinnovo, utente, *, giorno=None, comunicazione=True):
    """Fissa gli aventi diritto alla data dell'avviso e prepara la comunicazione in bozza."""
    from apps.anagrafica.models import Soggetto

    _controlla_aperto(rinnovo)
    if rinnovo.fase not in (Fase.INDETTO, Fase.CONVOCATO):
        raise OperazioneNonValida("Prima si indice il rinnovo.")
    if not rinnovo.data_assemblea or not rinnovo.luogo:
        raise OperazioneNonValida("Indicare data e luogo dell'assemblea.")
    giorno = giorno or timezone.localdate()
    avvisi = []
    entro = _giorno(rinnovo.data_assemblea) - timedelta(days=rinnovo.profilo.giorni_avviso)
    if giorno > entro:
        avvisi.append(f"Avviso oltre il termine: andava inviato entro il {entro:%d/%m/%Y}.")
    rinnovo.aventi_diritto, totale = calcola_aventi(rinnovo, giorno)
    rinnovo.soci_alla_soglia = totale
    rinnovo.avviso_il, rinnovo.fase, rinnovo.modificato_da = giorno, Fase.CONVOCATO, utente
    if comunicazione:
        ids = [r["soggetto"] for r in rinnovo.aventi_diritto if r.get("soggetto")]
        destinatari = list(Soggetto.objects.filter(pk__in=ids))
        if destinatari:
            from apps.comunicazioni import servizi as comunicazioni

            rinnovo.invio_avviso = comunicazioni.crea_invio(
                utente, oggetto=f"Convocazione del {rinnovo.profilo.nome_assemblea} – "
                f"{rinnovo.ente}", corpo=testo_avviso(rinnovo), finalita="istituzionale",
                soggetti=destinatari, origine=ORIGINE, origine_id=rinnovo.pk,
            )  # fmt: skip
    rinnovo.save()
    registra(Azione.MODIFICA, rinnovo, utente=utente, fase="convocato", aventi=totale)
    return avvisi


def iscritti_dopo_avviso(rinnovo):
    """Soci entrati dopo l'avviso: partecipano ma non votano (tesseramento sospeso)."""
    if not rinnovo.avviso_il or rinnovo.federazione:
        return []
    return list(_soci(rinnovo).filter(data_ammissione__gt=rinnovo.avviso_il)
                .select_related("soggetto"))  # fmt: skip


# --- composizione e controllo delle liste --------------------------------------------------


def soci_per_soglia(rinnovo):
    if rinnovo.soci_alla_soglia is not None:
        return rinnovo.soci_alla_soglia
    return calcola_aventi(rinnovo, timezone.localdate())[1]


def composizione(rinnovo):
    """{incarico: (minimo, massimo)} secondo il profilo e il numero dei soci."""
    p, soci = rinnovo.profilo, soci_per_soglia(rinnovo)
    regole = {Incarico.PRESIDENTE: (1, 1), Incarico.VICEPRESIDENTE: (1, 1),
              Incarico.SEGRETARIO: (1, 1)}  # fmt: skip
    if soci <= p.soglia_soci:
        regole[Incarico.CONSIGLIERE] = (p.consiglieri_sotto_min, p.consiglieri_sotto_max)
        regole[Incarico.SINDACO] = (p.sindaci_sotto_min, p.sindaci_sotto_max)
        regole[Incarico.GARANTE] = (p.garanti_sotto, p.garanti_sotto)
    else:
        consiglieri = p.consiglieri_sopra
        if p.seconda_soglia and soci > p.seconda_soglia:
            extra = math.ceil((soci - p.seconda_soglia) / max(p.soci_per_consigliere, 1))
            consiglieri = min(consiglieri + extra, p.consiglieri_massimo)
        regole[Incarico.CONSIGLIERE] = (consiglieri, consiglieri)
        regole[Incarico.SINDACO] = (p.sindaci_sopra_min, p.sindaci_sopra_max)
        regole[Incarico.GARANTE] = (p.garanti_sopra, p.garanti_sopra)
    regole[Incarico.SUPPLENTE] = (0, p.supplenti_max)
    return regole


def descrizione_composizione(rinnovo):
    parti = []
    for incarico, (minimo, massimo) in composizione(rinnovo).items():
        if massimo == 0:
            continue
        nome = Incarico(incarico).label.lower()
        quanti = str(minimo) if minimo == massimo else (
            f"fino a {massimo}" if minimo == 0 else f"da {minimo} a {massimo}")  # fmt: skip
        parti.append(f"{nome}: {quanti}")
    return "; ".join(parti)


def problemi_lista(lista):
    """Cosa manca o non va nella lista (vuoto = conforme). Non blocca la presentazione: decide il
    consiglio uscente nell'ammissione."""
    rinnovo, problemi = lista.rinnovo, []
    candidati = list(lista.candidati.select_related("soggetto"))
    conteggi = {}
    for c in candidati:
        conteggi[c.incarico] = conteggi.get(c.incarico, 0) + 1
    for incarico, (minimo, massimo) in composizione(rinnovo).items():
        n, nome = conteggi.get(incarico, 0), Incarico(incarico).label.lower()
        if n < minimo:
            problemi.append(f"Manca: {nome} ({n} su {minimo}).")
        elif n > massimo:
            problemi.append(f"Troppi: {nome} ({n}, al massimo {massimo}).")
    in_regola = _in_regola(rinnovo, [c.soggetto_id for c in candidati])
    for c in candidati:
        if c.soggetto_id not in in_regola:
            problemi.append(f"{c.soggetto.nome_completo} non è un socio in regola con la quota.")
        if not c.accettazione:
            problemi.append(f"Manca l'accettazione firmata di {c.soggetto.nome_completo}.")
    altre = (
        Candidato.objects.filter(lista__rinnovo=rinnovo)
        .exclude(lista=lista)
        .exclude(lista__stato__in=[Lista.Stato.ESCLUSA, Lista.Stato.RITIRATA])
        .filter(soggetto__in=[c.soggetto_id for c in candidati])
        .select_related("soggetto")
    )
    for c in altre:
        problemi.append(f"{c.soggetto.nome_completo} è candidato anche in un'altra lista.")
    return problemi


def _in_regola(rinnovo, soggetti):
    """Soggetti (tra quelli indicati) soci in regola con la quota dell'anno dell'avviso."""
    from apps.soci.models import Socio

    anno = (rinnovo.avviso_il or timezone.localdate()).year
    soci = Socio.objects.attivi().filter(soggetto_id__in=soggetti)
    if not rinnovo.federazione and rinnovo.sezione_id:
        soci = soci.filter(sezione_id=rinnovo.sezione_id)
    return set(soci.in_regola(anno).values_list("soggetto_id", flat=True))


def _lista_modificabile(lista):
    _controlla_aperto(lista.rinnovo)
    if lista.stato != Lista.Stato.BOZZA:
        raise OperazioneNonValida("La lista è già stata presentata: non si modifica.")


@transaction.atomic
def nuova_lista(rinnovo, utente, *, motto="", presentatore=""):
    _controlla_aperto(rinnovo)
    if rinnovo.fase not in (Fase.INDETTO, Fase.CONVOCATO):
        raise OperazioneNonValida("Le liste si compilano dopo l'indizione e prima del voto.")
    lista = Lista.objects.create(rinnovo=rinnovo, motto=motto, presentatore=presentatore,
                                 creato_da=utente, modificato_da=utente)  # fmt: skip
    registra(Azione.CREAZIONE, lista, utente=utente, rinnovo=str(rinnovo))
    return lista


@transaction.atomic
def aggiungi_candidato(lista, utente, *, soggetto, incarico, accettazione=False):
    _lista_modificabile(lista)
    if not soggetto.is_persona:
        raise OperazioneNonValida("I candidati sono persone.")
    if incarico not in Incarico.values:
        raise OperazioneNonValida("Incarico non valido.")
    if lista.candidati.filter(soggetto=soggetto).exists():
        raise OperazioneNonValida(f"{soggetto.nome_completo} è già in questa lista.")
    massimo = composizione(lista.rinnovo)[incarico][1]
    if lista.candidati.filter(incarico=incarico).count() >= massimo:
        raise OperazioneNonValida(
            f"Già raggiunto il massimo di «{Incarico(incarico).label.lower()}» ({massimo})."
        )
    ordine = list(Incarico.values).index(incarico) * 100 + lista.candidati.count()
    candidato = Candidato.objects.create(lista=lista, soggetto=soggetto, incarico=incarico,
                                         ordine=ordine, accettazione=accettazione)  # fmt: skip
    if incarico == Incarico.PRESIDENTE and not lista.presentatore:
        lista.presentatore = soggetto.nome_completo
        lista.save(update_fields=["presentatore"])
    registra(Azione.MODIFICA, lista, utente=utente, candidato=str(candidato))
    return candidato


@transaction.atomic
def togli_candidato(candidato, utente):
    _lista_modificabile(candidato.lista)
    registra(Azione.MODIFICA, candidato.lista, utente=utente, tolto=str(candidato))
    candidato.delete()


@transaction.atomic
def imposta_accettazione(candidato, utente, accettazione):
    _lista_modificabile(candidato.lista)
    candidato.accettazione = accettazione
    candidato.save(update_fields=["accettazione"])


@transaction.atomic
def presenta_lista(lista, utente, *, quando=None, protocolla=False):
    """Deposito della lista: numero d'ordine, data e ora, avviso se fuori termine."""
    _lista_modificabile(lista)
    rinnovo = Rinnovo.objects.select_for_update().get(pk=lista.rinnovo_id)
    if lista.capolista is None:
        raise OperazioneNonValida("Una lista senza candidato presidente non si presenta.")
    quando = quando or timezone.now()
    ultimo = rinnovo.liste.exclude(numero=None).order_by("-numero").first()
    lista.numero = (ultimo.numero if ultimo else 0) + 1
    lista.stato, lista.presentata_il, lista.modificato_da = Lista.Stato.PRESENTATA, quando, utente
    if protocolla:
        lista.protocollo = _protocolla_lista(lista, utente)
    lista.save()
    registra(Azione.MODIFICA, lista, utente=utente, presentata=str(quando), numero=lista.numero)
    avvisi = []
    if rinnovo.termine_liste and _giorno(quando) > rinnovo.termine_liste:
        avvisi.append(f"Oltre il termine del {rinnovo.termine_liste:%d/%m/%Y}: lo valuta "
                      "il consiglio uscente nell'ammissione.")  # fmt: skip
    return avvisi


def _protocolla_lista(lista, utente):
    from django.core.files.base import ContentFile

    from apps.protocollo import servizi as protocollo
    from apps.protocollo.models import Corrispondente, Protocollo

    capolista = lista.capolista
    pr = protocollo.registra_protocollo(
        {"direzione": Protocollo.Direzione.ENTRATA, "mezzo": Protocollo.Mezzo.MANO,
         "oggetto": f"Presentazione della lista n. {lista.numero} (candidato presidente "
                    f"{capolista.soggetto.nome_completo}) - rinnovo {lista.rinnovo.quadriennio}"},
        [{"ruolo": Corrispondente.Ruolo.MITTENTE, "soggetto": capolista.soggetto,
          "descrizione": capolista.soggetto.nome_completo}],
        utente,
    )  # fmt: skip
    protocollo.aggiungi_allegato(pr, ContentFile(pdf("lista", lista.rinnovo, lista=lista),
                                                 name="lista.pdf"),
                                 utente, principale=True, controlla=False)  # fmt: skip
    return pr


@transaction.atomic
def ritira_lista(lista, utente):
    _controlla_aperto(lista.rinnovo)
    if lista.stato not in (Lista.Stato.PRESENTATA, Lista.Stato.AMMESSA):
        raise OperazioneNonValida("Si ritira solo una lista presentata.")
    lista.stato = Lista.Stato.RITIRATA
    lista.save(update_fields=["stato"])
    registra(Azione.MODIFICA, lista, utente=utente, ritirata=True)


@transaction.atomic
def elimina_bozza(lista, utente):
    _lista_modificabile(lista)
    registra(Azione.ELIMINAZIONE, lista, utente=utente, rinnovo=str(lista.rinnovo))
    lista.delete()


@transaction.atomic
def esamina_lista(lista, utente, *, ammessa, motivo="", giorno=None):
    """Ammissione o esclusione da parte del consiglio uscente (esclusione sempre motivata)."""
    _controlla_aperto(lista.rinnovo)
    if lista.stato not in (Lista.Stato.PRESENTATA, Lista.Stato.AMMESSA, Lista.Stato.ESCLUSA):
        raise OperazioneNonValida("Si esamina solo una lista presentata.")
    if lista.rinnovo.fase in (Fase.VOTATO, Fase.PROCLAMATO, Fase.INSEDIATO):
        raise OperazioneNonValida("Il voto si è già svolto.")
    if not ammessa and not motivo.strip():
        raise OperazioneNonValida("Indicare i motivi dell'esclusione (Statuto e Regolamento).")
    lista.stato = Lista.Stato.AMMESSA if ammessa else Lista.Stato.ESCLUSA
    lista.motivo_esclusione = "" if ammessa else motivo.strip()
    lista.esaminata_il = giorno or timezone.localdate()
    lista.save()
    registra(Azione.MODIFICA, lista, utente=utente, ammessa=ammessa, motivo=lista.motivo_esclusione)
    rinnovo = Rinnovo.objects.get(pk=lista.rinnovo_id)
    da_esaminare = rinnovo.liste.filter(stato=Lista.Stato.PRESENTATA).exists()
    ammesse = rinnovo.liste.filter(stato=Lista.Stato.AMMESSA).exists()
    if not da_esaminare and ammesse and rinnovo.fase == Fase.CONVOCATO:
        rinnovo.fase = Fase.LISTE
        rinnovo.save(update_fields=["fase"])
    return lista


# --- voto, proclamazione, ricorsi ----------------------------------------------------------


def modalita_voto(rinnovo):
    ammesse = rinnovo.liste.filter(stato=Lista.Stato.AMMESSA).count()
    if ammesse == 1 and rinnovo.profilo.alzata_di_mano_lista_unica:
        return "alzata"
    return "scrutinio"


@transaction.atomic
def registra_esiti(rinnovo, utente, dati, voti):
    """Esiti della votazione: `dati` (campi del rinnovo), `voti` {lista_id: voti}. Calcola la
    lista eletta; con la parità non proclama (decide l'assemblea secondo lo statuto)."""
    _controlla_aperto(rinnovo)
    if rinnovo.fase not in (Fase.LISTE, Fase.VOTATO):
        raise OperazioneNonValida("Prima si ammettono le liste.")
    ammesse = list(rinnovo.liste.filter(stato=Lista.Stato.AMMESSA))
    if not ammesse:
        raise OperazioneNonValida("Nessuna lista ammessa.")
    for campo, valore in dati.items():
        setattr(rinnovo, campo, valore)
    rinnovo.alzata_di_mano = modalita_voto(rinnovo) == "alzata"
    p = rinnovo.profilo
    if not rinnovo.votato_il:
        raise OperazioneNonValida("Indicare il giorno del voto.")
    if not p.voto_ponderato and rinnovo.deleghe > rinnovo.presenti * p.max_deleghe:
        raise OperazioneNonValida(f"Voti per delega oltre il massimo ({p.max_deleghe} per "
                                  "votante presente).")  # fmt: skip
    totale_liste = 0
    for lista in ammesse:
        lista.voti = int(voti.get(lista.pk, 0) or 0)
        lista.save(update_fields=["voti"])
        totale_liste += lista.voti
    limite = voti_totali(rinnovo)
    espressi = totale_liste + rinnovo.schede_bianche + rinnovo.schede_nulle
    if limite and espressi > limite:
        raise OperazioneNonValida(f"Più voti ({espressi}) degli aventi diritto ({limite}).")
    scrutinio = not rinnovo.alzata_di_mano and not p.voto_ponderato
    if scrutinio and rinnovo.schede_votate and rinnovo.schede_votate != espressi:
        raise OperazioneNonValida(f"Le schede votate ({rinnovo.schede_votate}) non tornano con "
                                  f"voti, bianche e nulle ({espressi}).")  # fmt: skip
    massimo = max(lista.voti for lista in ammesse)
    prime = [lista for lista in ammesse if lista.voti == massimo]
    avvisi = []
    if massimo == 0:
        rinnovo.lista_eletta = None
        avvisi.append("Nessun voto alle liste: non c'è una lista eletta.")
    elif len(prime) > 1:
        rinnovo.lista_eletta = None
        avvisi.append("Parità tra le liste più votate: l'elezione va decisa secondo lo statuto "
                      "(es. nuova votazione) prima della proclamazione.")  # fmt: skip
    else:
        rinnovo.lista_eletta = prime[0]
    rinnovo.fase, rinnovo.modificato_da = Fase.VOTATO, utente
    rinnovo.save()
    registra(Azione.MODIFICA, rinnovo, utente=utente, fase="votato",
             voti={str(lista): lista.voti for lista in ammesse},
             eletta=str(rinnovo.lista_eletta or ""))  # fmt: skip
    return avvisi


@transaction.atomic
def proclama(rinnovo, utente, *, quando=None):
    _controlla_aperto(rinnovo)
    if rinnovo.fase != Fase.VOTATO or rinnovo.lista_eletta is None:
        raise OperazioneNonValida("Non c'è una lista eletta da proclamare.")
    rinnovo.proclamato_il = quando or timezone.now()
    rinnovo.fase, rinnovo.modificato_da = Fase.PROCLAMATO, utente
    rinnovo.save()
    registra(Azione.MODIFICA, rinnovo, utente=utente, fase="proclamato",
             lista=str(rinnovo.lista_eletta))  # fmt: skip


def eletti(rinnovo):
    if rinnovo.lista_eletta is None:
        return []
    return list(rinnovo.lista_eletta.candidati.select_related("soggetto"))


@transaction.atomic
def registra_rinuncia(candidato, utente, rinuncia=True):
    rinnovo = Rinnovo.objects.get(pk=candidato.lista.rinnovo_id)
    _controlla_aperto(rinnovo)
    if candidato.lista_id != rinnovo.lista_eletta_id or rinnovo.fase != Fase.PROCLAMATO:
        raise OperazioneNonValida("La rinuncia riguarda gli eletti proclamati, prima "
                                  "dell'insediamento.")  # fmt: skip
    candidato.rinuncia = rinuncia
    candidato.save(update_fields=["rinuncia"])
    registra(Azione.MODIFICA, rinnovo, utente=utente, rinuncia=str(candidato), valore=rinuncia)


@transaction.atomic
def aggiungi_ricorso(rinnovo, utente, *, presentato_il, presentato_da, motivi):
    if not rinnovo.votato_il:
        raise OperazioneNonValida("I ricorsi riguardano le operazioni di voto già svolte.")
    ricorso = Ricorso.objects.create(rinnovo=rinnovo, presentato_il=presentato_il,
                                     presentato_da=presentato_da, motivi=motivi,
                                     creato_da=utente, modificato_da=utente)  # fmt: skip
    registra(Azione.CREAZIONE, ricorso, utente=utente)
    limite = rinnovo.votato_il + timedelta(days=rinnovo.profilo.giorni_ricorsi)
    if presentato_il > limite:
        return [f"Presentato oltre il termine ({limite:%d/%m/%Y})."]
    return []


@transaction.atomic
def decidi_ricorso(ricorso, utente, *, esito, decisione, giorno=None):
    if esito not in (Ricorso.Esito.ACCOLTO, Ricorso.Esito.RESPINTO):
        raise OperazioneNonValida("Esito non valido.")
    ricorso.esito, ricorso.decisione = esito, decisione
    ricorso.deciso_il = giorno or timezone.localdate()
    ricorso.modificato_da = utente
    ricorso.save()
    registra(Azione.MODIFICA, ricorso, utente=utente, esito=esito)


# --- insediamento, consegne, trasmissione --------------------------------------------------


def _organo(sezione, tipo, nome, sigla, durata):
    from apps.organi.models import Organo

    organo = Organo.objects.filter(sezione=sezione, tipo=tipo, attivo=True)
    if tipo == Organo.Tipo.ALTRO:
        organo = organo.filter(nome__icontains="garant")
    organo = organo.order_by("ordine", "pk").first()
    if organo is None:
        organo = Organo.objects.create(sezione=sezione, tipo=tipo, nome=nome, sigla=sigla,
                                       durata_mandato=durata)  # fmt: skip
    elif not organo.durata_mandato:
        organo.durata_mandato = durata
        organo.save(update_fields=["durata_mandato"])
    return organo


@transaction.atomic
def insedia(rinnovo, utente, *, giorno=None):
    """Chiude le cariche uscenti degli organi rinnovati e nomina gli eletti (esclusi quelli che
    non accettano: i supplenti si cooptano con una delibera del nuovo consiglio)."""
    from apps.organi import servizi as organi
    from apps.organi.models import Carica, Organo

    _controlla_aperto(rinnovo)
    if rinnovo.fase != Fase.PROCLAMATO:
        raise OperazioneNonValida("Prima si proclamano gli eletti.")
    pendenti = rinnovo.ricorsi.filter(esito=Ricorso.Esito.PENDENTE).count()
    if pendenti:
        raise OperazioneNonValida(f"Ci sono {pendenti} ricorsi da decidere.")
    giorno = giorno or timezone.localdate()
    durata, sezione = rinnovo.profilo.durata_mandato, rinnovo.sezione
    nome = "Consiglio direttivo" + (" sezionale" if sezione else "")
    organi_ = {
        "consiglio": organo_consiglio(sezione) or _organo(sezione, Organo.Tipo.CONSIGLIO, nome,
                                                           "CD", durata),
        "controllo": _organo(sezione, Organo.Tipo.CONTROLLO, "Collegio dei sindaci", "CS", durata),
    }  # fmt: skip
    candidati = [c for c in eletti(rinnovo) if not c.rinuncia]
    if any(c.incarico == Incarico.GARANTE for c in candidati):
        organi_["garanti"] = _organo(sezione, Organo.Tipo.ALTRO, "Collegio dei garanti", "CG",
                                     durata)  # fmt: skip
    atto = (f"{rinnovo.profilo.nome_assemblea} del "
            f"{rinnovo.votato_il:%d/%m/%Y} (mandato {rinnovo.quadriennio})")  # fmt: skip
    for organo in organi_.values():
        for carica in organo.cariche_al(giorno):
            organi.termina_carica(carica, giorno, utente, motivo=f"Rinnovo {rinnovo.quadriennio}")
    sindaci = [c for c in candidati if c.incarico == Incarico.SINDACO]
    nominati = 0
    for c in candidati:
        if c.incarico == Incarico.SINDACO:
            organo = organi_["controllo"]
            ruolo = (Carica.Ruolo.PRESIDENTE_CONTROLLO if len(sindaci) > 1 and c == sindaci[0]
                     else Carica.Ruolo.COMPONENTE)  # fmt: skip
        elif c.incarico == Incarico.GARANTE:
            organo, ruolo = organi_["garanti"], Carica.Ruolo.COMPONENTE
        else:
            organo, ruolo = organi_["consiglio"], c.incarico
        organi.nomina(organo, c.soggetto, ruolo, giorno, utente, atto=atto)
        nominati += 1
    rinnovo.insediato_il, rinnovo.fase, rinnovo.modificato_da = giorno, Fase.INSEDIATO, utente
    rinnovo.save()
    Decadenza.objects.filter(rinnovo=rinnovo, chiusa_il__isnull=True).update(chiusa_il=giorno)
    registra(Azione.MODIFICA, rinnovo, utente=utente, fase="insediato", nominati=nominati)
    return nominati


@transaction.atomic
def registra_consegne(rinnovo, utente, dati, *, giorno):
    _controlla_aperto(rinnovo)
    if rinnovo.fase not in (Fase.PROCLAMATO, Fase.INSEDIATO):
        raise OperazioneNonValida("Il passaggio di consegne segue la proclamazione.")
    rinnovo.consegne, rinnovo.consegne_il, rinnovo.modificato_da = dati, giorno, utente
    rinnovo.save()
    registra(Azione.MODIFICA, rinnovo, utente=utente, consegne=str(giorno))


@transaction.atomic
def trasmetti(rinnovo, utente, *, giorno=None, protocolla=False):
    """Trasmissione dei verbali (con protocollo in uscita e i PDF, se richiesto)."""
    _controlla_aperto(rinnovo)
    if rinnovo.fase not in (Fase.PROCLAMATO, Fase.INSEDIATO):
        raise OperazioneNonValida("Si trasmettono i verbali dopo la proclamazione.")
    rinnovo.trasmesso_il = giorno or timezone.localdate()
    if protocolla:
        rinnovo.protocollo_trasmissione = _protocolla_verbali(rinnovo, utente)
    rinnovo.modificato_da = utente
    rinnovo.save()
    registra(Azione.MODIFICA, rinnovo, utente=utente, trasmesso=str(rinnovo.trasmesso_il))


def _protocolla_verbali(rinnovo, utente):
    from django.core.files.base import ContentFile

    from apps.protocollo import servizi as protocollo
    from apps.protocollo.models import Corrispondente, Protocollo

    destinatario = rinnovo.profilo.destinatario_verbali or "Federazione"
    pr = protocollo.registra_protocollo(
        {"direzione": Protocollo.Direzione.USCITA, "mezzo": Protocollo.Mezzo.EMAIL,
         "oggetto": f"Trasmissione dei verbali del {rinnovo.profilo.nome_assemblea} del "
                    f"{rinnovo.votato_il:%d/%m/%Y} - {rinnovo.ente}"},
        [{"ruolo": Corrispondente.Ruolo.DESTINATARIO, "descrizione": destinatario}],
        utente,
    )  # fmt: skip
    for i, codice in enumerate(documenti_da_trasmettere(rinnovo)):
        contenuto = pdf(codice, rinnovo)
        protocollo.aggiungi_allegato(pr, ContentFile(contenuto, name=f"{codice}.pdf"), utente,
                                     principale=i == 0, controlla=False)  # fmt: skip
    return pr


@transaction.atomic
def concludi(rinnovo, utente):
    if rinnovo.fase != Fase.INSEDIATO:
        raise OperazioneNonValida("Si conclude dopo l'insediamento dei nuovi organi.")
    rinnovo.fase, rinnovo.modificato_da = Fase.CONCLUSO, utente
    rinnovo.save()
    registra(Azione.MODIFICA, rinnovo, utente=utente, fase="concluso")


@transaction.atomic
def annulla(rinnovo, utente, motivo):
    _controlla_aperto(rinnovo)
    if rinnovo.fase == Fase.INSEDIATO:
        raise OperazioneNonValida("I nuovi organi sono già insediati: si conclude.")
    if not motivo.strip():
        raise OperazioneNonValida("Indicare il motivo dell'annullamento.")
    rinnovo.fase, rinnovo.motivo_annullamento = Fase.ANNULLATO, motivo.strip()[:255]
    rinnovo.modificato_da = utente
    rinnovo.save()
    registra(Azione.MODIFICA, rinnovo, utente=utente, annullato=motivo)


# --- documenti ------------------------------------------------------------------------------

DOCUMENTI = {
    "avviso": "Avviso di convocazione",
    "aventi": "Elenco degli aventi diritto al voto",
    "lista": "Modulo di presentazione della lista",
    "ammissione": "Verbale di ammissione delle liste",
    "scheda": "Scheda di votazione",
    "delega": "Delega al voto",
    "commissione": "Verbale della commissione elettorale",
    "elezione": "Verbale delle elezioni",
    "proclamazione": "Verbale di proclamazione degli eletti",
    "consegne": "Verbale di passaggio di consegne",
}


def sigla_modello(rinnovo, codice):
    """Allegato del Regolamento ANCR corrispondente (vuoto per il profilo generico)."""
    modelli = rinnovo.profilo.modelli
    if modelli == "ancr_federazione":
        return {"commissione": "B1", "elezione": "C1", "proclamazione": "D1", "delega": "D3",
                "consegne": "G"}.get(codice, "")  # fmt: skip
    if modelli == "ancr_sezione":
        if codice == "elezione":
            return "C3" if rinnovo.alzata_di_mano else "C2"
        return {"commissione": "B2", "proclamazione": "D2", "delega": "D4",
                "consegne": "G1"}.get(codice, "")  # fmt: skip
    return ""


def documenti_da_trasmettere(rinnovo):
    codici = ["ammissione"]
    if not rinnovo.alzata_di_mano:
        codici.append("commissione")
    return [*codici, "elezione", "proclamazione"]


def contesto_documento(codice, rinnovo, **extra):
    from apps.core.models import Organizzazione

    liste = list(rinnovo.liste.exclude(stato=Lista.Stato.BOZZA).prefetch_related(
        "candidati__soggetto"))  # fmt: skip
    return {
        "codice": codice, "titolo": DOCUMENTI[codice], "rinnovo": rinnovo,
        "profilo": rinnovo.profilo, "organizzazione": Organizzazione.corrente(),
        "sigla": sigla_modello(rinnovo, codice), "liste": liste,
        "ammesse": [lista for lista in liste if lista.stato == Lista.Stato.AMMESSA],
        "eletti": eletti(rinnovo), "componenti": [r for r in
                                                  rinnovo.commissione_componenti.splitlines() if r],
        "voti_totali": voti_totali(rinnovo), "composizione": descrizione_composizione(rinnovo),
        "termini": termini(rinnovo), "oggi": timezone.localdate(), **extra,
    }  # fmt: skip


def pdf(codice, rinnovo, **extra):
    from apps.core.pdf import genera_pdf

    if codice not in DOCUMENTI:
        raise OperazioneNonValida("Documento sconosciuto.")
    return genera_pdf(f"elezioni/pdf/{codice}.html", contesto_documento(codice, rinnovo, **extra))


# --- calendario e cruscotto ----------------------------------------------------------------


def rinnovi_aperti():
    return Rinnovo.objects.exclude(fase__in=[Fase.CONCLUSO, Fase.ANNULLATO]).select_related(
        "profilo", "sezione"
    )


def da_avviare(giorni=180):
    """Consigli con il mandato in scadenza entro `giorni` e nessun rinnovo in corso."""
    from apps.organi.models import Organo

    oggi, risultato = timezone.localdate(), []
    in_corso = set(rinnovi_aperti().values_list("sezione_id", flat=True))
    consigli = Organo.objects.filter(tipo=Organo.Tipo.CONSIGLIO, attivo=True,
                                     durata_mandato__isnull=False)  # fmt: skip
    visti = set()
    for organo in consigli.select_related("sezione"):
        if organo.sezione_id in visti or organo.sezione_id in in_corso:
            continue
        visti.add(organo.sezione_id)
        scadenza = scadenza_mandato(organo.sezione)
        if scadenza and scadenza <= oggi + timedelta(days=giorni):
            risultato.append({"sezione": organo.sezione, "scadenza": scadenza})
    return sorted(risultato, key=lambda r: r["scadenza"])


def eventi_calendario(dal, al):
    """(uid, titolo, giorno, percorso) delle scadenze dei rinnovi in corso nel periodo."""
    for rinnovo in rinnovi_aperti():
        for t in termini(rinnovo):
            if t.entro and not t.fatto and dal <= t.entro <= al:
                yield rinnovo, t


def filtra_per_utente(queryset, utente):
    """Rinnovi visibili: chi è limitato ad alcune sezioni vede solo quelle."""
    from apps.soci import sezioni

    ids = sezioni.id_sezioni(utente)
    if ids is None:
        return queryset
    return queryset.filter(Q(sezione_id__in=ids))


# --- decadenza anticipata e commissariamento ------------------------------------------------

MESI_COMMISSARIO = 12


def _piu_mesi(giorno, mesi):
    anno, mese = divmod(giorno.month - 1 + mesi, 12)
    try:
        return giorno.replace(year=giorno.year + anno, month=mese + 1)
    except ValueError:  # es. 31 del mese: ultimo giorno utile
        return (giorno.replace(day=1, year=giorno.year + anno, month=mese + 1)
                + timedelta(days=31)).replace(day=1) - timedelta(days=1)  # fmt: skip


def organi_da_sciogliere(sezione):
    """Organi elettivi della sezione (o dell'ente) che possono decadere: consiglio, controllo,
    garanti. L'assemblea dei soci non decade."""
    from apps.organi.models import Organo

    return Organo.objects.filter(sezione=sezione, attivo=True).exclude(tipo=Organo.Tipo.ASSEMBLEA)


def profilo_per(sezione):
    livelli = ProfiloElettorale.Livello
    livello = livelli.SEZIONE if sezione else livelli.FEDERAZIONE
    profilo = ProfiloElettorale.objects.filter(livello=livello, attivo=True).first()
    return profilo or ProfiloElettorale.objects.filter(attivo=True).first()


@transaction.atomic
def dichiara_decadenza(utente, *, sezione, giorno, motivo, organi_ids=(), commissario=None,
                       termine=None, disposto_da="", atto="", profilo=None, note=""):  # fmt: skip
    """Fine anticipata degli organi: decadono sempre il consiglio e l'organo di controllo (sindaci),
    più gli altri organi indicati in `organi_ids`; le cariche si chiudono. Il commissario (carica
    «commissario» nel consiglio: firma al posto del presidente) è quello nominato dall'ente
    sovraordinato o, finché non è nominato, il presidente decaduto (commissario provvisorio).
    Si apre il rinnovo straordinario entro il termine (dodici mesi, prorogabili); un rinnovo in
    corso si annulla."""
    from apps.organi import servizi as organi
    from apps.organi.models import Organo

    if motivo not in Decadenza.Motivo.values:
        raise OperazioneNonValida("Motivo non valido.")
    if Decadenza.objects.filter(sezione=sezione, chiusa_il__isnull=True).exists():
        raise OperazioneNonValida("C'è già una decadenza o un commissariamento in corso.")
    if commissario is not None and not commissario.is_persona:
        raise OperazioneNonValida("Il commissario è una persona.")
    consiglio = organo_consiglio(sezione)
    interim = False
    if commissario is None:  # il presidente decaduto, fino alla nomina del commissario
        uscente = None
        if consiglio is not None:
            uscente = consiglio.cariche_al(giorno).filter(ruolo="presidente").first()
        if uscente is None:
            raise OperazioneNonValida("Non c'è un presidente in carica che faccia da commissario: "
                                      "indicare il commissario.")  # fmt: skip
        commissario, interim = uscente.soggetto, True
    termine = termine or _piu_mesi(giorno, MESI_COMMISSARIO)
    if termine <= giorno:
        raise OperazioneNonValida("Il termine deve seguire la decadenza.")
    profilo = profilo or profilo_per(sezione)
    if profilo is None:
        raise OperazioneNonValida("Manca un profilo elettorale attivo.")
    sciolti = list(
        organi_da_sciogliere(sezione).filter(
            Q(tipo__in=[Organo.Tipo.CONSIGLIO, Organo.Tipo.CONTROLLO]) | Q(pk__in=organi_ids)
        )
    )
    motivazione = f"Decadenza degli organi dal {giorno:%d/%m/%Y}" + (f" ({atto})" if atto else "")
    chiuse = 0
    for organo in sciolti:
        for carica in organo.cariche_al(giorno):
            organi.termina_carica(carica, giorno, utente, motivo=motivazione)
            chiuse += 1
    nome = "Consiglio direttivo" + (" sezionale" if sezione else "")
    consiglio = consiglio or _organo(
        sezione, Organo.Tipo.CONSIGLIO, nome, "CD", profilo.durata_mandato)  # fmt: skip
    organi.nomina(consiglio, commissario, "commissario", giorno, utente,
                  atto=atto or f"Commissariamento dal {giorno:%d/%m/%Y}",
                  note="commissario provvisorio: presidente decaduto, fino alla nomina del "
                  "commissario" if interim
                  else "")  # fmt: skip
    for vecchio in Rinnovo.objects.filter(sezione=sezione).exclude(
        fase__in=[Fase.CONCLUSO, Fase.ANNULLATO]
    ):
        annulla(vecchio, utente, "Sostituito dal rinnovo straordinario dopo la decadenza")
    inizio = termine.year
    rinnovo = Rinnovo.objects.create(
        profilo=profilo, sezione=sezione,
        quadriennio=f"{inizio}-{inizio + profilo.durata_mandato}",
        scadenza=termine, straordinario=True, creato_da=utente, modificato_da=utente,
    )  # fmt: skip
    decadenza = Decadenza.objects.create(
        sezione=sezione, motivo=motivo, giorno=giorno, disposto_da=disposto_da, atto=atto,
        organi_sciolti=[str(o) for o in sciolti], cariche_chiuse=chiuse, commissario=commissario,
        termine=termine, rinnovo=rinnovo, note=note, interim=interim, creato_da=utente,
        modificato_da=utente,
    )  # fmt: skip
    registra(Azione.CREAZIONE, decadenza, utente=utente, motivo=motivo, cariche_chiuse=chiuse,
             commissario=str(commissario), interim=interim, termine=str(termine))  # fmt: skip
    return decadenza


@transaction.atomic
def nomina_commissario(decadenza, utente, *, commissario, giorno, disposto_da="", atto=""):
    """Il commissario nominato dall'ente sovraordinato (Regolamento art. 19) subentra al presidente
    decaduto: il termine di dodici mesi decorre dalla nomina."""
    from apps.organi import servizi as organi
    from apps.organi.models import Carica

    if decadenza.chiusa_il:
        raise OperazioneNonValida("Il commissariamento è già concluso.")
    if not decadenza.interim:
        raise OperazioneNonValida("Il commissario è già stato nominato.")
    if not commissario.is_persona:
        raise OperazioneNonValida("Il commissario è una persona.")
    if giorno < decadenza.giorno:
        raise OperazioneNonValida("La nomina non può precedere la decadenza.")
    attuale = (
        Carica.objects.filter(
            ruolo="commissario", organo__sezione=decadenza.sezione, dal__lte=giorno
        )
        .filter(Q(al__isnull=True) | Q(al__gt=giorno))
        .first()
    )
    consiglio = organo_consiglio(decadenza.sezione)
    if attuale is not None:
        consiglio = attuale.organo
        if attuale.soggetto_id != commissario.pk:
            organi.termina_carica(attuale, giorno, utente, motivo="Nominato il commissario")
    if attuale is None or attuale.soggetto_id != commissario.pk:
        organi.nomina(consiglio, commissario, "commissario", giorno, utente,
                      atto=atto or f"Nomina del commissario del {giorno:%d/%m/%Y}")  # fmt: skip
    elif atto:
        attuale.note, attuale.nomina = "", atto[:200]
        attuale.save(update_fields=["note", "nomina"])
    decadenza.commissario, decadenza.interim = commissario, False
    decadenza.termine, decadenza.prorogato_al = _piu_mesi(giorno, MESI_COMMISSARIO), None
    if disposto_da:
        decadenza.disposto_da = disposto_da
    if atto:
        decadenza.atto = atto
    decadenza.modificato_da = utente
    decadenza.save()
    if decadenza.rinnovo_id:
        Rinnovo.objects.filter(pk=decadenza.rinnovo_id).update(scadenza=decadenza.termine)
    registra(Azione.MODIFICA, decadenza, utente=utente, commissario=str(commissario),
             nomina=str(giorno), atto=atto)  # fmt: skip
    return decadenza


@transaction.atomic
def proroga(decadenza, utente, *, fino, atto=""):
    """Proroga del commissariamento, al massimo di altri dodici mesi oltre il termine."""
    if decadenza.chiusa_il:
        raise OperazioneNonValida("Il commissariamento è già concluso.")
    massimo = _piu_mesi(decadenza.termine, MESI_COMMISSARIO)
    if fino <= decadenza.termine or fino > massimo:
        raise OperazioneNonValida(f"La proroga va dal {decadenza.termine:%d/%m/%Y} al "
                                  f"{massimo:%d/%m/%Y} al massimo.")  # fmt: skip
    decadenza.prorogato_al, decadenza.atto_proroga = fino, atto
    decadenza.modificato_da = utente
    decadenza.save()
    if decadenza.rinnovo_id:
        Rinnovo.objects.filter(pk=decadenza.rinnovo_id).update(scadenza=fino)
    registra(Azione.MODIFICA, decadenza, utente=utente, proroga=str(fino), atto=atto)


def decadenze_aperte():
    return Decadenza.objects.filter(chiusa_il__isnull=True).select_related(
        "sezione", "commissario", "rinnovo"
    )
