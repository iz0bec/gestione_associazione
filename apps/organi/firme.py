# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Firme in calce alle stampe: chi ricopriva una carica alla data del documento,
# *              dalle cariche degli Organi sociali (dell'associazione o di una sezione).
# *              Una carica vacante lascia lo spazio per la firma senza nome: mai nomi inventati.
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
}


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


def firme(*ruoli, giorno=None, sezione=None):
    """Firme per i ruoli indicati. «tesoriere|presidente» = il primo in carica fra i due
    (es. ricevute del tesoriere, firmate dal presidente se il tesoriere non c'è);
    «tesoriere?» = solo se la carica è coperta (altrimenti nessuna firma)."""
    risultato = []
    for voce in ruoli:
        facoltativa = voce.endswith("?")
        alternative = [r.strip() for r in voce.rstrip("?").split("|") if r.strip()]
        firma = None
        for ruolo in alternative:
            persona = in_carica_al(ruolo, giorno, sezione)
            if persona:
                firma = Firma(QUALIFICHE.get(ruolo, ruolo.capitalize()), persona.intestazione)
                break
        if firma is None and facoltativa:
            continue
        if firma is None:  # vacante: la qualifica di chi dovrebbe firmare, senza nome
            primo = alternative[-1] if len(alternative) > 1 else alternative[0]
            firma = Firma(QUALIFICHE.get(primo, primo.capitalize()))
        if firma not in risultato:
            risultato.append(firma)
    return risultato
