# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Voce di rubrica della controparte collegata (federazione o sezione): legge via
# *              API i contatti istituzionali (/ente) e crea o aggiorna l'ente in anagrafica.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import re

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction

from apps.anagrafica.models import Soggetto
from apps.api.models import ClienteApi
from apps.core.audit import Azione, registra

from . import client
from .trasporto import ErroreTrasporto

# campo ricevuto -> (campo del Soggetto, lunghezza massima)
CAMPI = {
    "denominazione": ("denominazione", 255),
    "codice_fiscale": ("codice_fiscale", 16),
    "partita_iva": ("partita_iva", 11),
    "indirizzo": ("indirizzo", 255),
    "cap": ("cap", 5),
    "comune": ("comune", 100),
    "provincia": ("provincia", 2),
    "telefono": ("telefono", 30),
    "email": ("email", 254),
    "pec": ("pec", 254),
}


class OperazioneNonValida(Exception):
    pass


def da_collegare(cliente: ClienteApi):
    """Solo le installazioni attive con il ruolo di federazione o di sezione."""
    return (
        cliente.tipo == ClienteApi.Tipo.INSTALLAZIONE
        and cliente.stato == ClienteApi.Stato.ATTIVA
        and cliente.abbinata
        and cliente.ruolo in (ClienteApi.Ruolo.FEDERAZIONE, ClienteApi.Ruolo.SEZIONE)
    )


def _pulisci(dati):
    """Solo i campi noti, come testo, accorciati; scartati quelli non validi (mai inventati)."""
    if not isinstance(dati, dict):
        raise OperazioneNonValida("Risposta della controparte non valida.")
    puliti = {}
    for chiave, (campo, massimo) in CAMPI.items():
        valore = dati.get(chiave)
        if not isinstance(valore, str) or not (valore := valore.strip()) or len(valore) > massimo:
            continue
        if campo in ("email", "pec"):
            try:
                validate_email(valore)
            except ValidationError:
                continue
        elif campo == "cap" and not re.fullmatch(r"\d{5}", valore):
            continue
        elif campo == "provincia":
            if not re.fullmatch(r"[A-Za-z]{2}", valore):
                continue
            valore = valore.upper()
        elif campo == "codice_fiscale":
            valore = valore.upper()
        puliti[campo] = valore
    if not puliti.get("denominazione"):
        raise OperazioneNonValida("La controparte non ha indicato la propria denominazione.")
    return puliti


def _trova(cliente, dati):
    """Una voce per controparte. Il codice fiscale non identifica l'ente: le sezioni di
    un'associazione nazionale possono avere tutte quello della sede nazionale. Una voce già
    collegata a un'altra controparte non si riusa (se lo è per errore, la si divide)."""
    stessa = {"denominazione__iexact": dati["denominazione"]}
    s = cliente.soggetto if cliente.soggetto_id else None
    if s is not None and s.anonimizzato_il is None:
        condivisa = s.controparti_api.exclude(pk=cliente.pk).exists()
        if not condivisa or Soggetto.objects.filter(pk=s.pk, **stessa).exists():
            return s
    enti = Soggetto.objects.filter(tipo=Soggetto.Tipo.ENTE, anonimizzato_il__isnull=True).exclude(
        controparti_api__in=ClienteApi.objects.exclude(pk=cliente.pk)
    )
    if trovato := enti.filter(**stessa).first():
        return trovato
    if dati.get("pec") and (trovati := list(enti.filter(pec__iexact=dati["pec"])[:2])):
        return trovati[0] if len(trovati) == 1 else None
    return None


def _completa_sezione(cliente, dati):
    """Sulla federazione: completa i dati vuoti della sezione dell'elenco."""
    sezione = cliente.sezione if cliente.ruolo == ClienteApi.Ruolo.SEZIONE else None
    if sezione is None:
        return
    campi = [c for c in ("email", "comune", "provincia") if not getattr(sezione, c) and dati.get(c)]
    for c in campi:
        setattr(sezione, c, dati[c])
    if campi:
        sezione.save(update_fields=[*campi, "modificato_il"])


def leggi(cliente: ClienteApi):
    try:
        risposta, _, _ = client.chiama(cliente, "GET", "/ente")
    except (client.ErroreCollegamento, ErroreTrasporto) as e:
        raise OperazioneNonValida(f"Controparte non raggiungibile: {e}") from e
    if risposta.stato == 404:
        raise OperazioneNonValida(
            "La controparte non fornisce ancora i suoi contatti: va aggiornata all'ultima versione."
        )
    if risposta.stato != 200:
        raise OperazioneNonValida(f"Contatti rifiutati dalla controparte (HTTP {risposta.stato}).")
    try:
        return _pulisci(client.json_risposta(risposta))
    except client.ErroreCollegamento as e:
        raise OperazioneNonValida(str(e)) from e


def aggiorna(cliente: ClienteApi, utente=None):
    """Crea o aggiorna la voce di rubrica della controparte. Restituisce (soggetto, creato)."""
    if not da_collegare(cliente):
        raise OperazioneNonValida("Solo per le installazioni attive di federazione o di sezione.")
    dati = leggi(cliente)
    with transaction.atomic():
        soggetto = _trova(cliente, dati)
        creato = soggetto is None
        if creato:
            nota = f"Contatti ricevuti dal collegamento API «{cliente.nome}»."
            soggetto = Soggetto(tipo=Soggetto.Tipo.ENTE, creato_da=utente, note=nota)
        elif soggetto.codice_fiscale and dati.get("codice_fiscale", "") not in (
            "",
            soggetto.codice_fiscale,
        ):
            dati.pop("codice_fiscale")  # non si sostituisce un codice fiscale già presente
        if dati.get("codice_fiscale") and (
            Soggetto.objects.filter(codice_fiscale__iexact=dati["codice_fiscale"])
            .exclude(pk=soggetto.pk)
            .exists()
        ):
            dati.pop("codice_fiscale")  # già usato da un'altra scheda
        modificati = {c: v for c, v in dati.items() if getattr(soggetto, c) != v}
        for campo, valore in modificati.items():
            setattr(soggetto, campo, valore)
        if creato or modificati:
            soggetto.modificato_da = utente
            soggetto.save()
        if cliente.soggetto_id != soggetto.pk:
            cliente.soggetto = soggetto
            cliente.save(update_fields=["soggetto"])
        _completa_sezione(cliente, dati)
        if creato or modificati:
            registra(
                Azione.CREAZIONE if creato else Azione.MODIFICA, soggetto, utente=utente,
                descrizione=f"Rubrica dal collegamento API {cliente.nome}",
                campi=sorted(modificati),
            )  # fmt: skip
    return soggetto, creato


def aggiorna_se_possibile(cliente: ClienteApi, utente=None):
    """Come `aggiorna`, ma un errore non ferma l'operazione in corso: (soggetto, creato, errore)."""
    if not da_collegare(cliente):
        return None, False, ""
    try:
        soggetto, creato = aggiorna(cliente, utente)
    except OperazioneNonValida as e:
        return None, False, str(e)
    return soggetto, creato, ""
