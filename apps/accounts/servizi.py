# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Gestione degli utenti: creazione, ruoli, password temporanee, secondo fattore
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import secrets

from allauth.mfa.models import Authenticator
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.core.audit import Azione, registra

from .models import PoliticaRuolo, Utente

# Caratteri senza ambiguità (niente 0/O, 1/l/I)
_ALFABETO = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
PERMESSO_GESTIONE = "accounts.change_utente"
FATTORI_FORTI = (Authenticator.Type.TOTP, Authenticator.Type.WEBAUTHN)


class OperazioneNonValida(ValidationError):
    """Operazione rifiutata per una regola sugli utenti (messaggio per l'utente)."""


def password_temporanea() -> str:
    """Password casuale leggibile, es. «Kp7x-Qm3a-Zt9w-Hn4c» (circa 110 bit)."""
    gruppi = ["".join(secrets.choice(_ALFABETO) for _ in range(4)) for _ in range(4)]
    return "-".join(gruppi)


# --- verifiche --------------------------------------------------------------------------


def puo_gestire(attore, utente) -> None:
    """Solo un superutente può intervenire su un superutente."""
    if utente.is_superuser and not attore.is_superuser:
        raise OperazioneNonValida("Solo un superutente può modificare un superutente.")


def _gruppi_danno_gestione(gruppi) -> bool:
    app_label, codename = PERMESSO_GESTIONE.split(".")
    return Permission.objects.filter(
        group__in=list(gruppi), content_type__app_label=app_label, codename=codename
    ).exists()


def controlla_ruoli_propri(attore, utente, gruppi) -> None:
    """Chi gestisce gli utenti non può togliersi da solo questa possibilità."""
    if utente.pk == attore.pk and not attore.is_superuser and not _gruppi_danno_gestione(gruppi):
        raise OperazioneNonValida(
            "Non puoi toglierti i ruoli che ti permettono di gestire gli utenti."
        )


def ha_secondo_fattore(utente) -> bool:
    return Authenticator.objects.filter(user=utente, type__in=FATTORI_FORTI).exists()


def mfa_richiesta(utente) -> bool:
    return PoliticaRuolo.objects.filter(
        ruolo__in=utente.groups.all(), mfa_obbligatoria=True
    ).exists()


def ruoli_con_mfa() -> set[int]:
    return set(
        PoliticaRuolo.objects.filter(mfa_obbligatoria=True).values_list("ruolo_id", flat=True)
    )


# --- operazioni -------------------------------------------------------------------------


@transaction.atomic
def crea_utente(form, attore) -> tuple[Utente, str]:
    """Salva un nuovo utente dal modulo; restituisce l'utente e la password temporanea."""
    utente = form.save(commit=False)
    password = password_temporanea()
    utente.set_password(password)
    utente.deve_cambiare_password = True
    utente.is_staff = False
    utente.is_superuser = False
    utente.save()
    form.save_m2m()
    registra(
        Azione.CREAZIONE,
        utente,
        ruoli=[g.name for g in utente.groups.all()],
        sezioni=[str(s) for s in utente.sezioni.all()],
    )
    return utente, password


@transaction.atomic
def aggiorna_utente(form, attore, dettagli: dict) -> Utente:
    puo_gestire(attore, form.instance)
    controlla_ruoli_propri(attore, form.instance, form.cleaned_data["groups"])
    utente = form.save()
    if dettagli.get("campi"):
        registra(Azione.MODIFICA, utente, **dettagli)
    return utente


@transaction.atomic
def reimposta_password(utente, attore) -> str:
    puo_gestire(attore, utente)
    if utente.pk == attore.pk:
        raise OperazioneNonValida("Per la tua password usa la pagina del tuo profilo.")
    password = password_temporanea()
    utente.set_password(password)
    utente.deve_cambiare_password = True
    utente.save(update_fields=["password", "deve_cambiare_password"])
    registra(Azione.MODIFICA, utente, operazione="password temporanea")
    return password


@transaction.atomic
def azzera_secondo_fattore(utente, attore) -> int:
    """Elimina app di autenticazione, passkey e codici di recupero (es. telefono perso)."""
    puo_gestire(attore, utente)
    if utente.pk == attore.pk:
        raise OperazioneNonValida("Il tuo secondo fattore si gestisce dal tuo profilo.")
    eliminati, _ = Authenticator.objects.filter(user=utente).delete()
    registra(Azione.MODIFICA, utente, operazione="secondo fattore azzerato", eliminati=eliminati)
    return eliminati


@transaction.atomic
def imposta_attivo(utente, attore, attivo: bool) -> None:
    puo_gestire(attore, utente)
    if utente.pk == attore.pk and not attivo:
        raise OperazioneNonValida("Non puoi disattivare il tuo account.")
    if utente.is_active == attivo:
        return
    utente.is_active = attivo
    utente.save(update_fields=["is_active"])
    registra(
        Azione.ARCHIVIAZIONE if not attivo else Azione.MODIFICA,
        utente,
        operazione="disattivato" if not attivo else "riattivato",
    )


@transaction.atomic
def imposta_mfa_ruoli(ruoli_obbligati: set[int], tutti) -> list[str]:
    """Allinea le regole dei ruoli; restituisce i nomi dei ruoli cambiati."""
    cambiati = []
    for ruolo in tutti:
        politica, _ = PoliticaRuolo.objects.get_or_create(ruolo=ruolo)
        valore = ruolo.pk in ruoli_obbligati
        if politica.mfa_obbligatoria != valore:
            politica.mfa_obbligatoria = valore
            politica.save(update_fields=["mfa_obbligatoria"])
            cambiati.append(ruolo.name)
    if cambiati:
        registra(
            Azione.MODIFICA,
            descrizione="Secondo fattore obbligatorio per ruolo",
            ruoli=cambiati,
            obbligatori=sorted(r.name for r in tutti if r.pk in ruoli_obbligati),
        )
    return cambiati
