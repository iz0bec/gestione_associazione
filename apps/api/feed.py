# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Feed dei cambiamenti (ADR-030 §7): CloudEvents in flussi con progressivo senza
# *              buchi (numerazione.prossimo_numero, sequenza feed_<flusso>) e catena di impronte
# *              SHA-256; lettura a pagine, riepiloghi per la riconciliazione, verifica della
# *              catena, conservazione e notifiche alle controparti.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import hashlib
import json
from datetime import UTC, timedelta

from django.db import connection
from django.utils import timezone

from apps.core.numerazione import prossimo_numero

from .models import Cambiamento, ClienteApi, NotificaApi

ORIGINE = "0" * 64
CONSERVAZIONE = timedelta(days=400)
PREFISSO_TIPO = "it.gestioneassociazione."


class CatenaInterrotta(ValueError):
    pass


def canonico(dati: dict) -> str:
    """JSON canonico (RFC 8785 per i valori usati qui: stringhe, interi, oggetti)."""
    return json.dumps(dati, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def impronta(precedente: str, contenuto: str) -> str:
    return hashlib.sha256((precedente + contenuto).encode()).hexdigest()


def _istanza():
    from .chiavi import istanza

    return istanza().uuid


def registra(flusso, tipo, soggetto, risorsa, versione):
    """Aggiunge un cambiamento al flusso. Va chiamato nella transazione dell'operazione."""
    if not connection.in_atomic_block:
        raise RuntimeError("feed.registra va chiamato dentro transaction.atomic().")
    numero = prossimo_numero(f"feed_{flusso}")  # blocca la sequenza: scritture in fila
    ultimo = (
        Cambiamento.objects.filter(flusso=flusso, progressivo__lt=numero)
        .order_by("-progressivo")
        .values_list("impronta", flat=True)
        .first()
    )
    precedente = ultimo or ORIGINE
    momento = timezone.now().replace(microsecond=0)
    evento = {
        "specversion": "1.0",
        "id": f"{flusso}:{numero}",
        "source": f"urn:uuid:{_istanza()}",
        "type": f"{PREFISSO_TIPO}{tipo}.v1",
        "subject": str(soggetto),
        "time": momento.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "datacontenttype": "application/json",
        "ga_flusso": flusso,
        "ga_progressivo": numero,
        "ga_precedente": precedente,
        "data": {"risorsa": risorsa, "versione": versione},
    }
    contenuto = canonico(evento)
    cambiamento = Cambiamento.objects.create(
        flusso=flusso, progressivo=numero, tipo=tipo, soggetto=soggetto, risorsa=risorsa,
        versione=versione, momento=momento, precedente=precedente,
        impronta=impronta(precedente, contenuto), contenuto=contenuto,
    )  # fmt: skip
    _accoda_notifiche(cambiamento)
    return cambiamento


def come_evento(cambiamento: Cambiamento) -> dict:
    evento = json.loads(cambiamento.contenuto)
    evento["ga_impronta"] = cambiamento.impronta
    return evento


def ultimo(flusso) -> int:
    from apps.core.models import Sequenza

    return (
        Sequenza.objects.filter(chiave=f"feed_{flusso}", anno=0)
        .values_list("ultimo_numero", flat=True)
        .first()
        or 0
    )


def primo_conservato(flusso):
    return (
        Cambiamento.objects.filter(flusso=flusso)
        .order_by("progressivo")
        .values_list("progressivo", flat=True)
        .first()
    )


def pagina(flusso, dopo, limite):
    """(cambiamenti, ultimo) dopo il progressivo `dopo`. CatenaInterrotta se il cursore è più
    vecchio della conservazione."""
    fine = ultimo(flusso)
    primo = primo_conservato(flusso)
    if dopo < fine and (primo is None or dopo < primo - 1):
        raise CatenaInterrotta(
            f"Il cursore {dopo} è più vecchio dei cambiamenti conservati: serve una "
            "risincronizzazione completa."
        )
    voci = Cambiamento.objects.filter(flusso=flusso, progressivo__gt=dopo).order_by("progressivo")
    return [come_evento(c) for c in voci[:limite]], fine


def verifica_catena(eventi, precedente=None):
    """Controlla progressivi consecutivi e impronte di una sequenza di eventi del feed (quello
    che fa chi legge). Restituisce l'ultima impronta."""
    atteso = None
    for evento in eventi:
        dati = {k: v for k, v in evento.items() if k != "ga_impronta"}
        if atteso is not None and evento["ga_progressivo"] != atteso:
            raise CatenaInterrotta(f"Manca il progressivo {atteso}.")
        if precedente is not None and evento["ga_precedente"] != precedente:
            raise CatenaInterrotta(f"Catena interrotta al progressivo {evento['ga_progressivo']}.")
        if impronta(evento["ga_precedente"], canonico(dati)) != evento["ga_impronta"]:
            raise CatenaInterrotta(f"Impronta errata al progressivo {evento['ga_progressivo']}.")
        precedente = evento["ga_impronta"]
        atteso = evento["ga_progressivo"] + 1
    return precedente


def impronta_riepilogo(coppie) -> str:
    """SHA-256 delle righe «uuid:versione» ordinate per uuid, unite da \\n."""
    righe = sorted(f"{u}:{v}" for u, v in coppie)
    return hashlib.sha256("\n".join(righe).encode()).hexdigest()


def conserva():
    """Cancella i cambiamenti oltre la conservazione, tenendo sempre l'ultimo di ogni flusso
    (serve a continuare la catena)."""
    limite = timezone.now() - CONSERVAZIONE
    cancellati = 0
    for flusso in Cambiamento.objects.values_list("flusso", flat=True).distinct():
        ultimo_numero = ultimo(flusso)
        cancellati += (
            Cambiamento.objects.filter(flusso=flusso, momento__lt=limite)
            .exclude(progressivo=ultimo_numero)
            .delete()[0]
        )
    return cancellati


# ---------------------------------------------------------------- notifiche

AMBITO_DEL_FLUSSO = {"eventi": "eventi:lettura", "sezioni": "sezioni:lettura"}


def _accoda_notifiche(cambiamento):
    ambito = AMBITO_DEL_FLUSSO.get(cambiamento.flusso)
    if ambito is None:
        return
    destinatari = ClienteApi.objects.filter(
        stato=ClienteApi.Stato.ATTIVA,
        notifiche_flussi__contains=[cambiamento.flusso],
        ambiti__contains=[ambito],
    ).exclude(indirizzo_notifiche="")
    NotificaApi.objects.bulk_create(
        NotificaApi(cliente=c, cambiamento=cambiamento, prossimo_tentativo=timezone.now())
        for c in destinatari
    )
