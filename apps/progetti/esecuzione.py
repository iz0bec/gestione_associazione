# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Esecuzione dei progetti (P5): centro di costo sui movimenti di prima nota,
# *              preventivo/consuntivo per voce, ore di volontariato valorizzate, avanzamento
# *              (attività, indicatori, eventi), varianti al piano con la delibera.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.core.audit import Azione, registra

from . import piano as piano_economico
from .models import Categoria, FonteFinanziamento, Imputazione, OreVolontariato, Progetto, Variante

ZERO = Decimal("0.00")
IN_ESECUZIONE = {Progetto.Stato.FINANZIATO, Progetto.Stato.IN_CORSO, Progetto.Stato.RENDICONTAZIONE}


class ErroreEsecuzione(Exception):
    pass


def in_esecuzione(progetto):
    return progetto.stato in IN_ESECUZIONE


def _controlla(progetto):
    if not in_esecuzione(progetto):
        raise ErroreEsecuzione(
            "Il progetto non è in esecuzione (finanziato, in corso o in rendicontazione)."
        )


# --- centro di costo -----------------------------------------------------------------------------


def movimenti_imputabili(progetto, testo=""):
    """Movimenti validi di entrata o uscita non ancora attribuiti a un progetto."""
    from apps.tesoreria.models import Movimento

    qs = (
        Movimento.objects.validi()
        .filter(
            tipo__in=[Movimento.Tipo.ENTRATA, Movimento.Tipo.USCITA],
            imputazione_progetto__isnull=True,
        )
        .select_related("controparte")
        .order_by("-data", "-numero")
    )
    if progetto.inizio_previsto:
        qs = qs.filter(data__gte=progetto.inizio_previsto - timedelta(days=365))
    if testo:
        qs = qs.filter(descrizione__icontains=testo)
    return qs[:100]


@transaction.atomic
def imputa(progetto, movimento, utente, *, voce=None, importo=None, contributo=False, nota=""):
    from apps.tesoreria.models import Movimento

    _controlla(progetto)
    movimento = Movimento.objects.select_for_update().get(pk=movimento.pk)
    if movimento.annullato or movimento.tipo == Movimento.Tipo.GIROCONTO:
        raise ErroreEsecuzione("Si imputano solo entrate e uscite valide.")
    if Imputazione.objects.filter(movimento=movimento).exists():
        raise ErroreEsecuzione("Il movimento è già imputato a un progetto.")
    importo = movimento.importo if importo in (None, "") else Decimal(importo)
    if importo <= 0 or importo > movimento.importo:
        raise ErroreEsecuzione(
            "L'importo imputato deve essere positivo e non superare il movimento."
        )
    if movimento.tipo == Movimento.Tipo.USCITA:
        if voce is not None and (
            voce.progetto_id != progetto.pk or voce.categoria == Categoria.VOLONTARIATO
        ):
            raise ErroreEsecuzione("Scegliere una voce in denaro del piano di questo progetto.")
        tipo = Imputazione.Tipo.COSTO
    else:
        voce = None
        tipo = Imputazione.Tipo.CONTRIBUTO if contributo else Imputazione.Tipo.ENTRATA
    imp = Imputazione.objects.create(
        movimento=movimento,
        progetto=progetto,
        tipo=tipo,
        voce=voce,
        importo=importo,
        nota=nota.strip()[:255],
        creato_da=utente,
    )
    registra(
        Azione.MODIFICA,
        progetto,
        utente=utente,
        imputazione=f"{movimento.descrizione} € {importo} ({imp.get_tipo_display()})"[:200],
    )
    return imp


@transaction.atomic
def togli_imputazione(imputazione, utente):
    progetto = imputazione.progetto
    _controlla(progetto)
    descrizione = str(imputazione.movimento.descrizione)
    imputazione.delete()
    registra(Azione.MODIFICA, progetto, utente=utente, imputazione=f"tolta {descrizione}"[:200])


# --- volontariato --------------------------------------------------------------------------------


@transaction.atomic
def registra_ore(progetto, utente, *, soggetto, data, ore, attivita=None, descrizione=""):
    _controlla(progetto)
    if soggetto.tipo != "persona":
        raise ErroreEsecuzione("Le ore si registrano per una persona dell'anagrafica.")
    if attivita is not None and attivita.progetto_id != progetto.pk:
        raise ErroreEsecuzione("L'attività non è di questo progetto.")
    if data > timezone.localdate():
        raise ErroreEsecuzione("Non si registrano ore future.")
    r = OreVolontariato.objects.create(
        progetto=progetto,
        soggetto=soggetto,
        data=data,
        ore=ore,
        attivita=attivita,
        descrizione=descrizione.strip()[:255],
        creato_da=utente,
    )
    registra(Azione.MODIFICA, progetto, utente=utente, volontariato=f"{ore} ore il {data}")
    return r


@transaction.atomic
def togli_ore(registrazione, utente):
    progetto = registrazione.progetto
    _controlla(progetto)
    descrizione = f"{registrazione.ore} ore il {registrazione.data}"
    registrazione.delete()
    registra(Azione.MODIFICA, progetto, utente=utente, volontariato=f"tolte {descrizione}")


def tariffa(progetto):
    if progetto.tariffa_volontariato is not None:
        return progetto.tariffa_volontariato
    if progetto.bando_id and progetto.bando.tariffa_volontariato is not None:
        return progetto.bando.tariffa_volontariato
    return None


# --- consuntivo ----------------------------------------------------------------------------------


@dataclass
class RigaVoce:
    voce: object
    preventivo: Decimal
    consuntivo: Decimal

    @property
    def scostamento(self):
        return self.consuntivo - self.preventivo

    @property
    def percentuale(self):
        return round(self.consuntivo * 100 / self.preventivo) if self.preventivo else None


@dataclass
class Consuntivo:
    righe: list = field(default_factory=list)
    non_attribuiti: Decimal = ZERO  # costi imputati senza voce
    ore: Decimal = ZERO
    tariffa: Decimal | None = None
    natura_preventivo: Decimal = ZERO
    contributo_previsto: Decimal = ZERO
    contributo_incassato: Decimal = ZERO
    altre_entrate: Decimal = ZERO

    @property
    def natura_consuntivo(self):
        return (self.ore * self.tariffa).quantize(Decimal("0.01")) if self.tariffa else ZERO

    @property
    def costi_preventivo(self):
        return sum((r.preventivo for r in self.righe), ZERO)

    @property
    def costi_consuntivo(self):
        return sum((r.consuntivo for r in self.righe), ZERO) + self.non_attribuiti

    @property
    def contributo_da_incassare(self):
        return self.contributo_previsto - self.contributo_incassato


def consuntivo(progetto):
    c = Consuntivo(tariffa=tariffa(progetto))
    per_voce = dict(
        progetto.imputazioni.filter(tipo=Imputazione.Tipo.COSTO, voce__isnull=False)
        .values_list("voce")
        .annotate(t=Sum("importo"))
    )
    for v in progetto.voci.all():
        if v.categoria == Categoria.VOLONTARIATO:
            c.natura_preventivo += v.importo
            continue
        c.righe.append(RigaVoce(v, v.importo, per_voce.get(v.pk) or ZERO))
    somme = progetto.imputazioni.values("tipo").annotate(t=Sum("importo"))
    totali = {s["tipo"]: s["t"] for s in somme}
    c.non_attribuiti = (
        progetto.imputazioni.filter(tipo=Imputazione.Tipo.COSTO, voce__isnull=True).aggregate(
            t=Sum("importo")
        )["t"]
        or ZERO
    )
    c.contributo_incassato = totali.get(Imputazione.Tipo.CONTRIBUTO) or ZERO
    c.altre_entrate = totali.get(Imputazione.Tipo.ENTRATA) or ZERO
    c.contributo_previsto = (
        progetto.fonti.filter(tipo=FonteFinanziamento.Tipo.CONTRIBUTO).aggregate(t=Sum("importo"))[
            "t"
        ]
        or ZERO
    )
    c.ore = progetto.ore.aggregate(t=Sum("ore"))["t"] or ZERO
    return c


def avanzamento(progetto):
    attivita = list(progetto.attivita.all())
    indicatori = list(progetto.indicatori.all())
    raggiunti = [
        min(Decimal(100), x.valore_raggiunto * 100 / x.valore_atteso)
        for x in indicatori
        if x.valore_raggiunto is not None and x.valore_atteso
    ]
    return {
        "attivita": len(attivita),
        "completate": sum(1 for a in attivita if a.completata),
        "indicatori": len(indicatori),
        "media_indicatori": round(sum(raggiunti) / len(indicatori)) if indicatori else None,
    }


# --- avanzamento ---------------------------------------------------------------------------------


@transaction.atomic
def segna_attivita(attivita, utente, *, completata):
    _controlla(attivita.progetto)
    attivita.completata = completata
    attivita.save(update_fields=["completata"])
    registra(
        Azione.MODIFICA,
        attivita.progetto,
        utente=utente,
        attivita=f"{attivita}: {'completata' if completata else 'riaperta'}",
    )


@transaction.atomic
def aggiorna_indicatore(indicatore, utente, *, valore):
    _controlla(indicatore.progetto)
    indicatore.valore_raggiunto = None if valore in (None, "") else Decimal(valore)
    indicatore.save(update_fields=["valore_raggiunto"])
    registra(
        Azione.MODIFICA,
        indicatore.progetto,
        utente=utente,
        indicatore=f"{indicatore}: {indicatore.valore_raggiunto}",
    )


@transaction.atomic
def collega_evento(progetto, evento, utente, *, collega=True):
    (progetto.eventi.add if collega else progetto.eventi.remove)(evento)
    registra(
        Azione.MODIFICA,
        progetto,
        utente=utente,
        evento=f"{'collegato' if collega else 'scollegato'} {evento}"[:200],
    )


# --- varianti ------------------------------------------------------------------------------------


def fotografia(progetto):
    """Il piano economico in un dizionario (per le varianti)."""
    p = piano_economico.calcola(progetto)
    return {
        "voci": [
            {
                "categoria": v.get_categoria_display(),
                "descrizione": v.descrizione,
                "quantita": str(v.quantita),
                "costo_unitario": str(v.costo_unitario),
                "importo": str(v.importo),
            }
            for v in progetto.voci.all()
        ],
        "fonti": [
            {"tipo": f.get_tipo_display(), "descrizione": f.descrizione, "importo": str(f.importo)}
            for f in progetto.fonti.all()
        ],
        "spese_generali": str(progetto.spese_generali or ""),
        "totale_costi": str(p.totale_costi),
        "totale_coperture": str(p.totale_fonti),
    }


def variante_aperta(progetto):
    return progetto.varianti.filter(chiusa_il__isnull=True).first()


@transaction.atomic
def apri_variante(progetto, utente, *, descrizione, delibera=None):
    _controlla(progetto)
    if variante_aperta(progetto):
        raise ErroreEsecuzione("C'è già una variante aperta.")
    if not descrizione.strip():
        raise ErroreEsecuzione("Descrivere la variante (cosa cambia e perché).")
    v = Variante.objects.create(
        progetto=progetto,
        descrizione=descrizione.strip(),
        delibera=delibera,
        utente=utente,
        piano_prima=fotografia(progetto),
    )
    registra(
        Azione.MODIFICA,
        progetto,
        utente=utente,
        variante="aperta",
        delibera=str(delibera) if delibera else "",
    )
    return v


@transaction.atomic
def chiudi_variante(progetto, utente):
    v = variante_aperta(progetto)
    if v is None:
        raise ErroreEsecuzione("Nessuna variante aperta.")
    v.piano_dopo, v.chiusa_il = fotografia(progetto), timezone.now()
    v.save(update_fields=["piano_dopo", "chiusa_il"])
    registra(
        Azione.MODIFICA,
        progetto,
        utente=utente,
        variante="chiusa",
        totale=f"{v.piano_prima['totale_costi']} → {v.piano_dopo['totale_costi']}",
    )
    return v
