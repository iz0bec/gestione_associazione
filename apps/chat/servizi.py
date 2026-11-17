# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Operazioni della chat interna: chi può chattare, conversazioni dirette e di gruppo,
# *              invio e ritiro dei messaggi, messaggi non letti. Solo utenti del gestionale.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import transaction
from django.db.models import Count, F, OuterRef, Prefetch, Q, Subquery, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.core.audit import Azione, registra

from .models import MAX_TESTO, Conversazione, Messaggio, Partecipazione

PERMESSO = "chat.usa_chat"


class OperazioneNonValida(Exception):
    pass


def _nome(utente):
    return utente.get_full_name() or utente.get_username()


def utenti_chat(escluso=None):
    """Utenti attivi che possono usare la chat (per ruolo, permesso diretto o superutente)."""
    perm = Permission.objects.get(content_type__app_label="chat", codename="usa_chat")
    qs = (
        get_user_model()
        .objects.filter(is_active=True)
        .filter(Q(groups__permissions=perm) | Q(user_permissions=perm) | Q(is_superuser=True))
        .distinct()
        .order_by("last_name", "first_name", "username")
    )
    return qs.exclude(pk=escluso.pk) if escluso else qs


def _controlla_destinatari(utente, altri):
    ammessi = set(utenti_chat(escluso=utente).values_list("pk", flat=True))
    for a in altri:
        if a.pk not in ammessi:
            raise OperazioneNonValida(f"{_nome(a)} non può usare la chat.")


def partecipazione(conversazione, utente):
    """La partecipazione attiva dell'utente, oppure OperazioneNonValida: chi non partecipa non
    vede nulla (nemmeno l'amministratore)."""
    p = Partecipazione.objects.filter(
        conversazione=conversazione, utente=utente, uscito_il__isnull=True
    ).first()
    if p is None:
        raise OperazioneNonValida("Non partecipi a questa conversazione.")
    return p


def conversazioni_di(utente):
    """Le conversazioni dell'utente con «non_letti», dalla più recente."""
    mie = Partecipazione.objects.filter(conversazione=OuterRef("pk"), utente=utente)
    non_letti = (
        Messaggio.objects.filter(conversazione=OuterRef("pk"), sistema=False, ritirato_il=None)
        .filter(pk__gt=OuterRef("letto"))
        .exclude(autore=utente)
        .values("conversazione")
        .annotate(n=Count("pk"))
        .values("n")
    )
    return (
        Conversazione.objects.filter(
            partecipazioni__utente=utente, partecipazioni__uscito_il__isnull=True
        )
        .annotate(letto=Subquery(mie.values("letto_fino")[:1]))
        .annotate(non_letti=Coalesce(Subquery(non_letti), Value(0)))
        .prefetch_related(
            Prefetch(
                "partecipazioni",
                queryset=Partecipazione.objects.select_related("utente").order_by("pk"),
            )
        )
    )


def non_letti(utente):
    """Totale dei messaggi non letti dall'utente in tutte le sue conversazioni."""
    return (
        Messaggio.objects.filter(
            conversazione__partecipazioni__utente=utente,
            conversazione__partecipazioni__uscito_il__isnull=True,
            pk__gt=F("conversazione__partecipazioni__letto_fino"),
            sistema=False,
            ritirato_il=None,
        )
        .exclude(autore=utente)
        .count()
    )


@transaction.atomic
def conversazione_diretta(utente, altro):
    """La conversazione a due con «altro» (la stessa di sempre, se esiste già)."""
    if altro.pk == utente.pk:
        raise OperazioneNonValida("Scegli un'altra persona.")
    _controlla_destinatari(utente, [altro])
    esistente = (
        Conversazione.objects.filter(gruppo=False, partecipazioni__utente=utente)
        .filter(partecipazioni__utente=altro)
        .first()
    )
    if esistente:
        return esistente
    c = Conversazione.objects.create(gruppo=False, creata_da=utente)
    Partecipazione.objects.bulk_create(
        [Partecipazione(conversazione=c, utente=u) for u in (utente, altro)]
    )
    registra(Azione.CREAZIONE, c, utente=utente, partecipanti=[utente.username, altro.username])
    return c


@transaction.atomic
def crea_gruppo(utente, titolo, altri):
    titolo = (titolo or "").strip()
    altri = [a for a in altri if a.pk != utente.pk]
    if not titolo:
        raise OperazioneNonValida("Un gruppo ha bisogno di un nome.")
    if not altri:
        raise OperazioneNonValida("Scegli almeno una persona.")
    _controlla_destinatari(utente, altri)
    c = Conversazione.objects.create(gruppo=True, titolo=titolo[:120], creata_da=utente)
    Partecipazione.objects.bulk_create(
        [Partecipazione(conversazione=c, utente=u) for u in [utente, *altri]]
    )
    _avviso(c, f"{_nome(utente)} ha creato il gruppo.")
    registra(Azione.CREAZIONE, c, utente=utente,
             partecipanti=[u.username for u in [utente, *altri]])  # fmt: skip
    return c


def _avviso(conversazione, testo):
    m = Messaggio.objects.create(conversazione=conversazione, testo=testo, sistema=True)
    Conversazione.objects.filter(pk=conversazione.pk).update(ultimo_messaggio_il=m.inviato_il)
    return m


@transaction.atomic
def invia(conversazione, utente, testo):
    p = partecipazione(conversazione, utente)
    testo = (testo or "").strip()
    if not testo:
        raise OperazioneNonValida("Il messaggio è vuoto.")
    if len(testo) > MAX_TESTO:
        raise OperazioneNonValida(
            f"Il messaggio è troppo lungo (al massimo {MAX_TESTO} caratteri)."
        )
    m = Messaggio.objects.create(conversazione=conversazione, autore=utente, testo=testo)
    Conversazione.objects.filter(pk=conversazione.pk).update(ultimo_messaggio_il=m.inviato_il)
    Partecipazione.objects.filter(pk=p.pk).update(letto_fino=m.pk)  # i propri sono letti
    return m


def ritira(messaggio, utente):
    """L'autore ritira un proprio messaggio: il testo si cancella, resta la traccia."""
    partecipazione(messaggio.conversazione, utente)
    if messaggio.autore_id != utente.pk or messaggio.sistema:
        raise OperazioneNonValida("Puoi ritirare solo i tuoi messaggi.")
    if messaggio.ritirato_il is None:
        messaggio.testo = ""
        messaggio.ritirato_il = timezone.now()
        messaggio.save(update_fields=["testo", "ritirato_il"])
    return messaggio


def segna_letti(conversazione, utente, fino_a=None):
    """Segna letti i messaggi fino a «fino_a» (o fino all'ultimo). Il segno non torna indietro."""
    if fino_a is None:
        fino_a = conversazione.messaggi.order_by("-pk").values_list("pk", flat=True).first() or 0
    Partecipazione.objects.filter(
        conversazione=conversazione, utente=utente, letto_fino__lt=fino_a
    ).update(letto_fino=fino_a)


@transaction.atomic
def aggiungi(conversazione, utente, altri):
    partecipazione(conversazione, utente)
    if not conversazione.gruppo:
        raise OperazioneNonValida("Si aggiungono persone solo ai gruppi.")
    _controlla_destinatari(utente, altri)
    aggiunti = []
    for a in altri:
        p, nuova = Partecipazione.objects.get_or_create(conversazione=conversazione, utente=a)
        if not nuova and p.uscito_il is None:
            continue
        if not nuova:  # rientra: vede i messaggi da quando rientra
            p.uscito_il = None
        p.letto_fino = (
            conversazione.messaggi.order_by("-pk").values_list("pk", flat=True).first() or 0
        )
        p.save()
        aggiunti.append(a)
    if aggiunti:
        _avviso(
            conversazione, f"{_nome(utente)} ha aggiunto {', '.join(_nome(a) for a in aggiunti)}."
        )
        registra(Azione.MODIFICA, conversazione, utente=utente,
                 aggiunti=[a.username for a in aggiunti])  # fmt: skip
    return aggiunti


@transaction.atomic
def esci(conversazione, utente):
    p = partecipazione(conversazione, utente)
    if not conversazione.gruppo:
        raise OperazioneNonValida("Da una conversazione a due non si esce.")
    p.uscito_il = timezone.now()
    p.save(update_fields=["uscito_il"])
    _avviso(conversazione, f"{_nome(utente)} ha lasciato il gruppo.")
    registra(Azione.MODIFICA, conversazione, utente=utente, uscito=utente.username)
