# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Avviso delle nuove domande di iscrizione (apps/core/avvisi.py, tipo «domande»)
# *              a chi le valuta e vede la sezione, tranne chi l'ha appena registrata.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.conf import settings
from django.db import transaction
from django.urls import reverse

from apps.core import avvisi
from apps.core.audit import contesto_richiesta
from apps.core.models import Organizzazione

from . import sezioni


def testo(domanda):
    org = Organizzazione.corrente()
    persona = f"{domanda.cognome} {domanda.nome}, {domanda.comune} ({domanda.provincia})"
    righe = [f"{org.denominazione}: nuova domanda di iscrizione", persona]
    dettagli = [domanda.get_origine_display()]
    if domanda.sezione_id and sezioni.multisezione():
        dettagli.append(str(domanda.sezione))
    righe.append(" · ".join(dettagli))
    if settings.URL_PUBBLICO:
        righe.append(f"{settings.URL_PUBBLICO}{reverse('soci:domanda', args=[domanda.pk])}")
    return "\n".join(righe)


def avvisa_domanda(domanda, autore=None):
    def vede(utente):
        ids = sezioni.id_sezioni(utente)
        visibile = ids is None or domanda.sezione_id in ids
        return visibile and (autore is None or utente.pk != autore.pk)

    return avvisi.avvisa("domande", testo(domanda), filtro=vede)


def domanda_creata(sender, instance, created, raw=False, **kwargs):
    if not created or raw:
        return
    autore, _ = contesto_richiesta.get()
    if autore is not None and not getattr(autore, "is_authenticated", False):
        autore = None
    transaction.on_commit(lambda: avvisa_domanda(instance, autore))


def collega():
    from django.db.models.signals import post_save

    from .models import DomandaIscrizione

    post_save.connect(domanda_creata, sender=DomandaIscrizione, dispatch_uid="avviso_domanda")
