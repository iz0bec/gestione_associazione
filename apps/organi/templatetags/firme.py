# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Tag {% firme "presidente" "tesoriere|presidente" giorno=... sezione=... %}
# *              per il blocco firme in calce ai PDF (vedi apps/organi/firme.py)
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
from django import template

from apps.organi import firme as servizio

register = template.Library()


@register.inclusion_tag("pdf/_firme.html")
def firme(*ruoli, giorno=None, sezione=None):
    return {"firme": servizio.firme(*ruoli, giorno=giorno, sezione=sezione)}
