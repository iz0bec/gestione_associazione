# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Visibilità per sezione: un utente con sezioni assegnate vede e gestisce solo
# *              soci, tessere, lotti e domande di quelle sezioni; senza sezioni vede tutto.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.core.exceptions import PermissionDenied

from .models import Sezione


def id_sezioni(utente):
    """Insieme degli id delle sezioni dell'utente, o None se non è limitato (tutte)."""
    if not getattr(utente, "is_authenticated", False):
        return set()
    if not hasattr(utente, "_id_sezioni"):
        if utente.is_superuser:
            utente._id_sezioni = None
        else:
            ids = set(utente.sezioni.values_list("pk", flat=True))
            utente._id_sezioni = ids or None
    return utente._id_sezioni


def limitato(utente):
    return id_sezioni(utente) is not None


def sezioni_di(utente):
    """Sezioni attive che l'utente può usare (per i menu di scelta)."""
    qs = Sezione.objects.filter(attiva=True)
    ids = id_sezioni(utente)
    return qs if ids is None else qs.filter(pk__in=ids)


def filtra(queryset, utente, campo="sezione"):
    ids = id_sezioni(utente)
    if ids is None:
        return queryset
    return queryset.filter(**{f"{campo}__in": ids})


def controlla(utente, sezione_id):
    ids = id_sezioni(utente)
    if ids is not None and sezione_id not in ids:
        raise PermissionDenied("Sezione non consentita.")


def multisezione():
    return Sezione.objects.filter(attiva=True).count() > 1
