# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Avvisi della posta da protocollare (apps/core/avvisi.py, tipo «posta»): un
# *              riepilogo per ogni scaricamento che porta messaggi nuovi.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.conf import settings
from django.urls import reverse

from apps.core import avvisi
from apps.core.models import Organizzazione

from .models import MessaggioRicevuto

MAX_ELENCATI = 5


def testo(messaggi):
    org = Organizzazione.corrente()
    n = len(messaggi)
    righe = [f"{org.denominazione}: {n} nuov{'o messaggio' if n == 1 else 'i messaggi'} "
             "da protocollare"]  # fmt: skip
    for m in messaggi[:MAX_ELENCATI]:
        pec = "PEC " if m.casella.pec else ""
        mittente = m.mittente_email or m.mittente
        righe.append(f"- {pec}{(m.oggetto or '(senza oggetto)')[:80]} ({mittente[:60]})")
    if n > MAX_ELENCATI:
        righe.append(f"- e altri {n - MAX_ELENCATI}")
    if settings.URL_PUBBLICO:
        righe.append(f"{settings.URL_PUBBLICO}{reverse('protocollo:posta')}")
    return "\n".join(righe)


def avvisa_nuova_posta(dal):
    """Dopo lo scaricamento: un riepilogo dei messaggi da esaminare arrivati da `dal` a chi
    riceve gli avvisi della posta. Restituisce quanti avvisi sono partiti."""
    nuovi = list(
        MessaggioRicevuto.objects.da_esaminare()
        .filter(scaricato_il__gte=dal)
        .select_related("casella")
        .order_by("-data", "-pk")
    )
    if not nuovi:
        return 0
    return avvisi.avvisa("posta", testo(nuovi))
