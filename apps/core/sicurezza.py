# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Avvisi di sicurezza agli amministratori che li hanno scelti (apps/core/avvisi.py,
# *              tipo «sicurezza»): accessi falliti ripetuti, accesso di un amministratore da un
# *              indirizzo nuovo, operazioni sugli utenti, lavori periodici non riusciti.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from . import avvisi
from .models import EventoAudit, Organizzazione

FINESTRA_FALLITI = timedelta(minutes=15)
SOGLIE_FALLITI = (5, 20, 100)  # un avviso al raggiungimento di ciascuna, non a ogni tentativo
MEMORIA_INDIRIZZI = timedelta(days=90)
PERMESSO_AMMINISTRATORE = "accounts.change_utente"


def _avvisa(testo, escludi=None):
    org = Organizzazione.corrente()
    contenuto = f"{org.denominazione} - sicurezza\n{testo}"

    def filtro(utente):
        return escludi is None or utente.pk != escludi.pk

    transaction.on_commit(lambda: avvisi.avvisa("sicurezza", contenuto, filtro=filtro))


def accesso_fallito(ip, nome):
    """Dopo la registrazione del tentativo: avviso quando i falliti dallo stesso indirizzo negli
    ultimi 15 minuti raggiungono una soglia."""
    if not ip:
        return
    n = EventoAudit.objects.filter(
        azione=EventoAudit.Azione.ACCESSO_FALLITO,
        indirizzo_ip=ip,
        momento__gte=timezone.now() - FINESTRA_FALLITI,
    ).count()
    if n in SOGLIE_FALLITI:
        _avvisa(f"{n} accessi falliti in 15 minuti dall'indirizzo {ip} (ultimo come «{nome}»).")


def accesso(utente, ip):
    """Prima della registrazione dell'accesso: avviso se un amministratore entra da un indirizzo
    che non ha usato negli ultimi 90 giorni."""
    if not ip or not utente.has_perm(PERMESSO_AMMINISTRATORE):
        return
    noto = EventoAudit.objects.filter(
        azione=EventoAudit.Azione.ACCESSO,
        utente=utente,
        indirizzo_ip=ip,
        momento__gte=timezone.now() - MEMORIA_INDIRIZZI,
    ).exists()
    if not noto:
        _avvisa(f"Accesso dell'amministratore {utente} ({utente.username}) da un indirizzo "
                f"nuovo: {ip}.", escludi=None)  # fmt: skip


def operazione_utenti(descrizione, attore=None):
    """Operazione rilevante sugli utenti: avvisa gli altri amministratori."""
    chi = f" (da {attore})" if attore is not None else ""
    _avvisa(f"{descrizione}{chi}.", escludi=attore)


def lavoro_non_riuscito(comando, errore):
    testo = f"Lavoro periodico «{comando}» non riuscito: {str(errore)[:200]}"
    avvisi.avvisa("sicurezza", f"{Organizzazione.corrente().denominazione} - sicurezza\n{testo}")
