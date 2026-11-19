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
    atteso = "sezione" if cliente.ruolo == ClienteApi.Ruolo.FEDERAZIONE else "federazione"
    visto = ((dati.get("tu") or {}).get("ruolo") if isinstance(dati, dict) else None) or "?"
    if visto != atteso:
        noi = "una sua sezione" if atteso == "sezione" else "la sua federazione"
        raise OperazioneNonValida(
            f"Ruoli incoerenti: qui «{cliente}» è indicata come "
            f"«{cliente.get_ruolo_display()}», quindi l'altra installazione dovrebbe vederci come "
            f"{noi}, ma ci ha indicati con il ruolo «{visto}». Correggere il ruolo nella scheda "
            "sbagliata (su una delle due installazioni) e ripetere."
        )
    righe = dati.get("soci") if isinstance(dati, dict) else None
    if not isinstance(righe, list) or not all(isinstance(r, dict) for r in righe):
        raise OperazioneNonValida("Risposta della controparte non valida.")
    if len(righe) > MAX_SOCI:
        raise OperazioneNonValida(f"Troppi soci nella risposta (più di {MAX_SOCI}).")
    return righe


def controparti(utente):
    """Controparti con cui l'utente può avviare la Verifica soci: (controparte, sezione)."""
    from apps.soci import sezioni

    consentite = sezioni.id_sezioni(utente)
    risultato = []
    qs = ClienteApi.objects.filter(
        stato=ClienteApi.Stato.ATTIVA, tipo=ClienteApi.Tipo.INSTALLAZIONE
    )
    for c in qs.select_related("sezione").order_by("nome"):
        if not c.abbinata or (sezione := tessere.sezione_per(c)) is None:
            continue
        if consentite is None or sezione.pk in consentite:
            risultato.append((c, sezione))
    return risultato


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
