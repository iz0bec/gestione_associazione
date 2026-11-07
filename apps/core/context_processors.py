# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Variabili disponibili in tutti i template
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.conf import settings
from django.utils.functional import SimpleLazyObject

from .models import Organizzazione

# Moduli previsti dalla roadmap, mostrati nel menu come "presto" finché non sono pronti
MODULI_IN_ARRIVO = []


def applicazione(request):
    return {
        "APP_NOME": settings.APP_NOME,
        "APP_VERSIONE": settings.APP_VERSIONE,
        "organizzazione": SimpleLazyObject(Organizzazione.corrente),  # 1 query, solo se usata
        "MODULI_IN_ARRIVO": MODULI_IN_ARRIVO,
    }
