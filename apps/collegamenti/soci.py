# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Verifica dei soci con la controparte (ADR-030, F4): legge via API i soci della
# *              sezione presso la federazione (o presso la sezione), prepara la proposta (chi
# *              manca si popola, chi c'è mostra le modifiche) e applica le voci scelte.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.db import transaction
from django.utils import timezone

from apps.api import tessere
from apps.api.models import ClienteApi, VerificaSoci
from apps.core.audit import Azione, registra
from apps.soci import allineamento

from . import client
from .trasporto import ErroreTrasporto

MAX_SOCI = 20_000


class OperazioneNonValida(Exception):
    pass


def scarica(cliente):
    """Elenco dei soci della sezione presso la controparte (risposta cifrata)."""
    try:
        risposta, _, _ = client.chiama(cliente, "GET", "/soci")
        if risposta.stato != 200:
            raise OperazioneNonValida(f"La controparte ha risposto: {client._problema(risposta)}")
        dati = client.json_risposta(risposta)
    except (client.ErroreCollegamento, ErroreTrasporto) as e:
        raise OperazioneNonValida(f"Controparte non raggiungibile: {e}") from e
    righe = dati.get("soci") if isinstance(dati, dict) else None
    if not isinstance(righe, list) or not all(isinstance(r, dict) for r in righe):
        raise OperazioneNonValida("Risposta della controparte non valida.")
    if len(righe) > MAX_SOCI:
        raise OperazioneNonValida(f"Troppi soci nella risposta (più di {MAX_SOCI}).")
    return righe


def verifica(cliente: ClienteApi, utente):
    """Nuova verifica: legge i soci dalla controparte e prepara la proposta (nulla si modifica)."""
    if cliente.stato != ClienteApi.Stato.ATTIVA or not cliente.abbinata:
        raise OperazioneNonValida("La controparte non è attiva.")
    sezione = tessere.sezione_per(cliente)
    if sezione is None:
        raise OperazioneNonValida(
            "Indicare nella controparte il ruolo (federazione o sezione) e, sulla federazione, "
            "la sezione dell'elenco."
        )
    righe = scarica(cliente)
    da_sezione = cliente.ruolo == ClienteApi.Ruolo.SEZIONE
    proposta = allineamento.confronta(righe, sezione, da_sezione=da_sezione)
    v = VerificaSoci.objects.create(cliente=cliente, sezione=sezione, da_sezione=da_sezione,
                                    creata_da=utente, righe=righe, proposta=proposta)  # fmt: skip
    registra(Azione.CONSULTAZIONE, v, utente=utente, descrizione=f"Verifica soci con {cliente}",
             **proposta["conteggi"])  # fmt: skip
    return v


def applica(v: VerificaSoci, scelti, utente):
    with transaction.atomic():
        v = VerificaSoci.objects.select_for_update().get(pk=v.pk)
        if v.applicata_il:
            raise OperazioneNonValida("Questa verifica è già stata applicata.")
        esiti = allineamento.applica(
            v.righe, v.proposta, scelti, v.sezione, utente,
            da_sezione=v.da_sezione, controparte=v.cliente.nome,
        )  # fmt: skip
        v.esiti, v.righe = esiti, []  # i dati ricevuti non servono più
        v.applicata_il, v.applicata_da = timezone.now(), utente
        v.save()
    return v
