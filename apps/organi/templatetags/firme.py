# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Tag {% firme "presidente" "tesoriere|presidente" giorno=... sezione=... %}
# *              per il blocco firme in calce ai PDF, con immagini e timbro (timbro=False,
# *              immagini=False per escluderli; vedi apps/organi/firme.py)
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
from django import template

from apps.organi import firme as servizio

register = template.Library()


@register.inclusion_tag("pdf/_firme.html")
def firme(*ruoli, giorno=None, sezione=None, timbro=True, immagini=True):
    """`timbro=False` / `immagini=False`: senza timbro o senza le immagini delle firme (es. un
    documento da firmare a mano)."""
    elenco = servizio.firme(*ruoli, giorno=giorno, sezione=sezione, immagini=immagini)
    return {
        "firme": elenco,
        "timbro": servizio.timbro(sezione) if (timbro and immagini and elenco) else None,
    }
