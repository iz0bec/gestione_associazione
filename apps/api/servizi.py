# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Operazioni sulle controparti dell'API: inviti, abbinamento, conferma
# *              dell'impronta, sospensione, revoca, rotazione delle chiavi e pulizia periodica.
# *              Ogni operazione rilevante finisce nel registro attività.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import hashlib
import secrets
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.core.audit import Azione, registra

from . import chiavi, feed
from .models import (
    AMBITI,
    AMBITI_DATI_PERSONALI,
    ChiamataApi,
    ClienteApi,
    InvitoAbbinamento,
    NonceVisto,
)

VALIDITA_INVITO = timedelta(hours=24)
CONSERVAZIONE_NONCE = timedelta(minutes=10)
CONSERVAZIONE_CHIAMATE = timedelta(days=90)


class OperazioneNonValida(Exception):
    pass


def _impronta_codice(codice: str) -> str:
    return hashlib.sha256(codice.strip().encode()).hexdigest()


def controlla_ambiti(tipo, ambiti, *, dati_personali_confermati=False):
    sconosciuti = set(ambiti) - set(AMBITI)
    if sconosciuti:
        raise OperazioneNonValida(f"Ambiti sconosciuti: {', '.join(sorted(sconosciuti))}.")
    if (
        tipo == ClienteApi.Tipo.INTEGRAZIONE
        and AMBITI_DATI_PERSONALI & set(ambiti)
        and not dati_personali_confermati
    ):
        raise OperazioneNonValida(
            "Per dare a un'integrazione esterna l'accesso ai dati dei soci serve la conferma "
            "esplicita sul trattamento dei dati personali."
        )
    return sorted(set(ambiti))


def crea_invito(utente, *, nome, tipo, ambiti, note="", dati_personali_confermati=False):
    """Nuova controparte in prova e il suo invito monouso. Il codice si mostra una volta sola."""
    ambiti = controlla_ambiti(tipo, ambiti, dati_personali_confermati=dati_personali_confermati)
    with transaction.atomic():
        cliente = ClienteApi.objects.create(
            nome=nome, tipo=tipo, ambiti=ambiti, note=note,
            origine=ClienteApi.Origine.INVITO_NOSTRO,
        )  # fmt: skip
        codice = nuovo_invito(cliente, utente, registra_evento=False)
        registra(Azione.CREAZIONE, cliente, utente=utente, descrizione=f"Controparte API {nome}",
                 tipo=tipo, ambiti=ambiti, invito=True)  # fmt: skip
    return cliente, codice


def nuovo_invito(cliente, utente, *, registra_evento=True):
    if cliente.abbinata:
        raise OperazioneNonValida("La controparte è già abbinata.")
    if cliente.stato == ClienteApi.Stato.REVOCATA:
        raise OperazioneNonValida("La controparte è revocata.")
    codice = "ga1-" + secrets.token_urlsafe(24)
    with transaction.atomic():
        cliente.inviti.filter(usato_il__isnull=True).update(scade_il=timezone.now())
        InvitoAbbinamento.objects.create(
            cliente=cliente,
            impronta_codice=_impronta_codice(codice),
            creato_da=utente,
            scade_il=timezone.now() + VALIDITA_INVITO,
        )
        if registra_evento:
            registra(Azione.MODIFICA, cliente, utente=utente, nuovo_invito=True)
    return codice


def invito_valido(codice):
    """Invito non usato e non scaduto (bloccato per l'aggiornamento), oppure None."""
    return (
        InvitoAbbinamento.objects.select_for_update()
        .select_related("cliente")
        .filter(
            impronta_codice=_impronta_codice(codice or ""),
            usato_il__isnull=True,
            scade_il__gt=timezone.now(),
        )
        .exclude(cliente__stato=ClienteApi.Stato.REVOCATA)
        .first()
    )


def _conflitto_istanza(istanza, escluso=None):
    altri = ClienteApi.objects.filter(istanza=istanza).exclude(stato=ClienteApi.Stato.REVOCATA)
    if escluso is not None:
        altri = altri.exclude(pk=escluso.pk)
    if altri.exists():
        raise OperazioneNonValida(
            "Questa istanza è già registrata come controparte: revocare quella precedente."
        )


def completa_abbinamento(invito, *, istanza, nome, jwks, tls_spki=(), indirizzo_notifiche=""):
    """Lato di chi ha creato l'invito: salva le chiavi della controparte (già verificate dal
    chiamante) e restituisce l'impronta comune. Da chiamare dentro transaction.atomic()."""
    if str(istanza) == str(chiavi.istanza().uuid):
        raise OperazioneNonValida("Un'istanza non può abbinarsi a se stessa.")
    cliente = invito.cliente
    _conflitto_istanza(istanza, escluso=cliente)
    cliente.istanza = istanza
    cliente.nome_dichiarato = nome[:255]
    cliente.jwks = jwks
    cliente.tls_spki = list(tls_spki)
    cliente.indirizzo_notifiche = indirizzo_notifiche
    cliente.impronta = chiavi.impronta_abbinamento(chiavi.jwks(), jwks)
    cliente.abbinata_il = timezone.now()
    cliente.save()
    invito.usato_il = timezone.now()
    invito.save(update_fields=["usato_il"])
    registra(Azione.MODIFICA, cliente, descrizione=f"Abbinamento API {cliente.nome}",
             istanza=str(istanza), nome_dichiarato=cliente.nome_dichiarato,
             impronta=cliente.impronta)  # fmt: skip
    return cliente


def registra_controparte(utente, *, nome, tipo, istanza, nome_dichiarato, jwks, impronta,
                         ambiti, indirizzi, tls_spki=()):  # fmt: skip
    """Lato di chi ha usato l'invito di un'altra installazione: registra la controparte in prova."""
    ambiti = controlla_ambiti(tipo, ambiti)
    with transaction.atomic():
        _conflitto_istanza(istanza)
        cliente = ClienteApi.objects.create(
            nome=nome, tipo=tipo, ambiti=ambiti, origine=ClienteApi.Origine.INVITO_LORO,
            istanza=istanza, nome_dichiarato=nome_dichiarato[:255], jwks=jwks, impronta=impronta,
            tls_spki=list(tls_spki), abbinata_il=timezone.now(), **indirizzi,
        )  # fmt: skip
        registra(Azione.CREAZIONE, cliente, utente=utente, descrizione=f"Controparte API {nome}",
                 istanza=str(istanza), impronta=impronta, ambiti=ambiti)  # fmt: skip
    return cliente


def attiva(cliente, utente, *, impronta_confermata):
    """Passaggio da «in prova» ad «attiva» dopo il confronto dell'impronta per una seconda via."""
    if cliente.stato != ClienteApi.Stato.IN_PROVA:
        raise OperazioneNonValida("Si attivano solo le controparti in prova.")
    if not cliente.abbinata:
        raise OperazioneNonValida("La controparte non ha ancora completato l'abbinamento.")
    if not impronta_confermata:
        raise OperazioneNonValida("Va confermato il confronto dell'impronta con la controparte.")
    cliente.stato = ClienteApi.Stato.ATTIVA
    cliente.attivata_il = timezone.now()
    cliente.attivata_da = utente
    cliente.save(update_fields=["stato", "attivata_il", "attivata_da"])
    registra(Azione.MODIFICA, cliente, utente=utente, stato="attiva", impronta=cliente.impronta)
    return cliente


def sospendi(cliente, utente, motivo=""):
    if cliente.stato != ClienteApi.Stato.ATTIVA:
        raise OperazioneNonValida("Si sospendono solo le controparti attive.")
    cliente.stato = ClienteApi.Stato.SOSPESA
    cliente.save(update_fields=["stato"])
    registra(Azione.MODIFICA, cliente, utente=utente, stato="sospesa", motivo=motivo)


def riattiva(cliente, utente):
    if cliente.stato != ClienteApi.Stato.SOSPESA:
        raise OperazioneNonValida("Si riattivano solo le controparti sospese.")
    if cliente.scade_il and cliente.scade_il < timezone.localdate():
        raise OperazioneNonValida("La controparte è scaduta: aggiornare prima la scadenza.")
    cliente.stato = ClienteApi.Stato.ATTIVA
    cliente.save(update_fields=["stato"])
    registra(Azione.MODIFICA, cliente, utente=utente, stato="attiva")


def revoca(cliente, utente):
    """Revoca definitiva: per ricollegarsi serve un nuovo abbinamento."""
    if cliente.stato == ClienteApi.Stato.REVOCATA:
        raise OperazioneNonValida("La controparte è già revocata.")
    with transaction.atomic():
        cliente.stato = ClienteApi.Stato.REVOCATA
        cliente.save(update_fields=["stato"])
        cliente.inviti.filter(usato_il__isnull=True).update(scade_il=timezone.now())
        registra(Azione.ANNULLAMENTO, cliente, utente=utente, stato="revocata")


def sospendi_se_scaduta(cliente):
    if (
        cliente.stato == ClienteApi.Stato.ATTIVA
        and cliente.scade_il
        and cliente.scade_il < timezone.localdate()
    ):
        cliente.stato = ClienteApi.Stato.SOSPESA
        cliente.save(update_fields=["stato"])
        registra(Azione.MODIFICA, cliente, stato="sospesa", motivo="scadenza")
        return True
    return False


def registra_esito_prova(cliente, esito: str):
    cliente.ultima_prova_il = timezone.now()
    cliente.ultimo_esito_prova = esito[:2000]
    cliente.save(update_fields=["ultima_prova_il", "ultimo_esito_prova"])


def aggiorna_chiavi_controparte(cliente, nuove, *, utente=None, origine="controparte"):
    """Chiavi nuove della controparte (rotazione): presentate da lei con una firma già nota
    (PUT /chiavi) o lette dalla sua JWKS firmata."""
    if nuove == cliente.jwks:
        return False
    prima = sorted(k["kid"] for k in cliente.chiavi("sig") + cliente.chiavi("enc"))
    cliente.jwks = nuove
    cliente.save(update_fields=["jwks"])
    registra(Azione.MODIFICA, cliente, utente=utente, descrizione=f"Chiavi di {cliente} aggiornate",
             origine=origine, prima=prima,
             dopo=sorted(k["kid"] for k in nuove["keys"]))  # fmt: skip
    return True


def aggiorna_impronte_tls(cliente, impronte, *, utente=None):
    prima = list(cliente.tls_spki or [])
    cliente.tls_spki = list(impronte)
    cliente.save(update_fields=["tls_spki"])
    registra(Azione.MODIFICA, cliente, utente=utente,
             descrizione=f"Impronte TLS di {cliente} aggiornate", prima=prima,
             dopo=list(impronte))  # fmt: skip


def riprova_notifiche(cliente, utente):
    from .models import NotificaApi

    n = cliente.notifiche.filter(stato=NotificaApi.Stato.FALLITA).update(
        stato=NotificaApi.Stato.IN_CODA, tentativi=0, prossimo_tentativo=timezone.now()
    )
    if n:
        registra(Azione.MODIFICA, cliente, utente=utente, notifiche_riaccodate=n)
    return n


def ruota_chiavi(utente):
    precedenti, nuove = chiavi.ruota()
    registra(Azione.MODIFICA, None, utente=utente, descrizione="Rotazione delle chiavi dell'API",
             ritirate=[c.kid for c in precedenti], nuove=[c.kid for c in nuove])  # fmt: skip
    return nuove


def pulizia():
    """Lavoro periodico (rieseguibile): nonce vecchi, registro delle chiamate oltre 90 giorni,
    chiavi private fuori dalla sovrapposizione, controparti scadute."""
    adesso = timezone.now()
    risultato = {
        "nonce": NonceVisto.objects.filter(visto_il__lt=adesso - CONSERVAZIONE_NONCE).delete()[0],
        "chiamate": ChiamataApi.objects.filter(
            momento__lt=adesso - CONSERVAZIONE_CHIAMATE
        ).delete()[0],
        "chiavi": chiavi.scarta_scadute(),
        "cambiamenti": feed.conserva(),
        "sospese": sum(
            sospendi_se_scaduta(c)
            for c in ClienteApi.objects.filter(
                stato=ClienteApi.Stato.ATTIVA, scade_il__lt=timezone.localdate()
            )
        ),
    }
    return risultato
