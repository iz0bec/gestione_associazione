# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Scrittura del registro delle attività. Utente e IP vengono presi
# *              dalla richiesta in corso (vedi middleware.ContestoRichiestaMiddleware).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from contextvars import ContextVar

from django.contrib.contenttypes.models import ContentType

from .models import EventoAudit

Azione = EventoAudit.Azione

# (utente, ip) della richiesta HTTP in corso
contesto_richiesta: ContextVar[tuple] = ContextVar("contesto_richiesta", default=(None, None))


def registra(azione, oggetto=None, *, utente=None, ip=None, descrizione=None, **dettagli):
    """Aggiunge un evento al registro delle attività."""
    utente_ctx, ip_ctx = contesto_richiesta.get()
    utente = utente or utente_ctx
    if utente is not None and not getattr(utente, "is_authenticated", False):
        utente = None
    evento = EventoAudit(
        azione=azione,
        utente=utente,
        utente_descrizione=(utente.get_username() if utente else "")[:150],
        indirizzo_ip=ip or ip_ctx,
        dettagli=dettagli,
    )
    if oggetto is not None:
        evento.oggetto_tipo = ContentType.objects.get_for_model(oggetto)
        evento.oggetto_id = str(oggetto.pk)
        evento.oggetto_descrizione = (descrizione or str(oggetto))[:255]
    elif descrizione:
        evento.oggetto_descrizione = descrizione[:255]
    evento.save()
    return evento


def campi_modificati(form) -> dict:
    """Valori prima/dopo dei campi cambiati in un ModelForm (per il dettaglio dell'evento)."""
    if not form.instance.pk:
        return {}
    modifiche = {}
    for nome in form.changed_data:
        prima = form.initial.get(nome)
        dopo = form.cleaned_data.get(nome)
        modifiche[nome] = {"prima": _testo(prima), "dopo": _testo(dopo)}
    return {"campi": modifiche}


def _testo(valore):
    if valore is None:
        return None
    if isinstance(valore, list | tuple | set) or hasattr(valore, "all"):
        elementi = valore.all() if hasattr(valore, "all") else valore
        return [str(v) for v in elementi]
    return str(valore)
