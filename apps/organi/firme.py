# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Firme in calce alle stampe: chi ricopriva una carica alla data del documento,
# *              dalle cariche degli Organi sociali (dell'associazione o di una sezione).
# *              Una carica vacante lascia lo spazio per la firma senza nome: mai nomi inventati.
# *              «rappresentante_legale»: quello indicato (anche esterno), altrimenti il presidente.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
from dataclasses import dataclass
from datetime import date, datetime

from django.db.models import Case, IntegerField, Q, Value, When
from django.utils import timezone

QUALIFICHE = {
    "presidente": "Il Presidente",
    "vicepresidente": "Il Vicepresidente",
    "segretario": "Il Segretario",
    "tesoriere": "Il Tesoriere",
    "presidente_controllo": "Il Presidente dell'organo di controllo",
    "rappresentante_legale": "Il Legale rappresentante",
}
RAPPRESENTANTE = "rappresentante_legale"


@dataclass(frozen=True)
class Firma:
    qualifica: str
    nome: str = ""  # vuoto: carica vacante, si firma a mano


def _giorno(valore):
    if isinstance(valore, datetime):
        return timezone.localtime(valore).date() if timezone.is_aware(valore) else valore.date()
    if isinstance(valore, date):
        return valore
    return timezone.localdate()


def in_carica_al(ruolo, giorno=None, sezione=None):
    """Persona che ricopriva il ruolo alla data (organi dell'associazione se sezione è None).

    A parità, prima l'organo di amministrazione (es. il presidente del consiglio direttivo,
    non quello di un'altra commissione) e la nomina più recente.
    """
    from .models import Carica, Organo

    giorno = _giorno(giorno)
    carica = (
        Carica.objects.filter(ruolo=ruolo, dal__lte=giorno, organo__sezione=sezione)
        .filter(Q(al__isnull=True) | Q(al__gt=giorno))
        .select_related("soggetto")
        .annotate(
            priorita=Case(
                When(organo__tipo=Organo.Tipo.CONSIGLIO, then=Value(0)),
                When(organo__tipo=Organo.Tipo.CONTROLLO, then=Value(1)),
                default=Value(2),
                output_field=IntegerField(),
            )
        )
        .order_by("priorita", "-dal")
        .first()
    )
    return carica.soggetto if carica else None


def rappresentante_legale_al(giorno=None, sezione=None):
    """Nomina del rappresentante legale valida alla data, o None.

    Per una sezione: la nomina della sezione, altrimenti quella dell'associazione che vale per
    tutta la struttura. Per l'associazione (sezione None): la nomina dell'associazione.
    """
    from .models import RappresentanteLegale

    giorno = _giorno(giorno)
    validi = (
        RappresentanteLegale.objects.filter(dal__lte=giorno)
        .filter(Q(al__isnull=True) | Q(al__gt=giorno))
        .select_related("soggetto")
        .order_by("-dal")
    )
    if sezione is not None:
        propria = validi.filter(sezione=sezione).first()
        if propria:
            return propria
        return validi.filter(sezione__isnull=True, tutta_la_struttura=True).first()
    return validi.filter(sezione__isnull=True).first()


def legale_rappresentante(giorno=None, sezione=None):
    """Firma del rappresentante legale: la persona indicata con la sua qualifica oppure, se non
    è indicato nessuno, il presidente in carica (che di solito lo è per statuto); per una
    sezione senza l'uno né l'altro, quello dell'associazione. None se manca anche quello."""
    nomina = rappresentante_legale_al(giorno, sezione)
    if nomina:
        return Firma(nomina.qualifica or QUALIFICHE[RAPPRESENTANTE], nomina.soggetto.intestazione)
    presidente = in_carica_al("presidente", giorno, sezione)
    if presidente:
        return Firma(QUALIFICHE["presidente"], presidente.intestazione)
    if sezione is not None:  # sezione senza nomina né presidente: vale quello dell'associazione
        return legale_rappresentante(giorno, None)
    return None


def situazione_rappresentanza(giorno=None):
    """Per l'associazione e per ogni sezione attiva: chi firma oggi come legale rappresentante
    e perché (nomina propria, nomina per tutta la struttura, presidente in carica, nessuno)."""
    from apps.soci.models import Sezione

    righe = []
    for sezione in [None, *Sezione.objects.filter(attiva=True)]:
        nomina = rappresentante_legale_al(giorno, sezione)
        if nomina:
            propria = nomina.sezione_id == (sezione.pk if sezione else None)
            origine = "nomina" if propria else "struttura"
        elif in_carica_al("presidente", giorno, sezione):
            origine = "presidente"
        else:
            origine = "associazione" if sezione is not None else "vacante"
        firma = legale_rappresentante(giorno, sezione)
        if firma is None:
            origine = "vacante"
        righe.append({"sezione": sezione, "firma": firma, "origine": origine})
    return righe


def _firma(ruolo, giorno, sezione):
    if ruolo == RAPPRESENTANTE:
        return legale_rappresentante(giorno, sezione)
    persona = in_carica_al(ruolo, giorno, sezione)
    if persona is None:
        return None
    return Firma(QUALIFICHE.get(ruolo, ruolo.capitalize()), persona.intestazione)


def firme(*ruoli, giorno=None, sezione=None):
    """Firme per i ruoli indicati. «tesoriere|presidente» = il primo in carica fra i due
    (es. ricevute del tesoriere, firmate dal presidente se il tesoriere non c'è);
    «rappresentante_legale» = chi rappresenta l'ente (vedi legale_rappresentante);
    «tesoriere?» = solo se la carica è coperta (altrimenti nessuna firma)."""
    risultato = []
    for voce in ruoli:
        facoltativa = voce.endswith("?")
        alternative = [r.strip() for r in voce.rstrip("?").split("|") if r.strip()]
        firma = None
        for ruolo in alternative:
            firma = _firma(ruolo, giorno, sezione)
            if firma:
                break
        if firma is None and facoltativa:
            continue
        if firma is None:  # vacante: la qualifica di chi dovrebbe firmare, senza nome
            primo = alternative[-1] if len(alternative) > 1 else alternative[0]
            firma = Firma(QUALIFICHE.get(primo, primo.capitalize()))
        if firma not in risultato:
            risultato.append(firma)
    return risultato
