# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Lettura periodica dei flussi delle controparti (ADR-030, F4): flusso «tessere»
# *              fra federazione e sezioni, catena di impronte verificata dal cursore salvato,
# *              documenti scaricati e messi nella coda dei documenti in arrivo.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import logging

from django.db import transaction
from django.utils import timezone

from apps.api import arrivi, feed
from apps.api.models import ClienteApi, CursoreFlusso

from . import client

log = logging.getLogger(__name__)
FLUSSO = "tessere"
PAGINA = 100


def _get(cliente, percorso):
    risposta, _, _ = client.chiama(cliente, "GET", percorso)
    if risposta.stato == 404:
        return None
    if risposta.stato != 200:
        raise client.ErroreCollegamento(f"{percorso}: {client._problema(risposta)}")
    return client.json_risposta(risposta)


def sincronizza(cliente: ClienteApi):
    """Legge i cambiamenti nuovi del flusso «tessere» della controparte. Restituisce il numero
    di documenti nuovi o aggiornati; l'errore resta sul cursore (e si riprova al giro dopo)."""
    tipi = arrivi.tipi_accettati(cliente)
    if not tipi or cliente.stato != ClienteApi.Stato.ATTIVA or not cliente.abbinata:
        return 0
    cursore, _ = CursoreFlusso.objects.get_or_create(cliente=cliente, flusso=FLUSSO)
    ricevuti = 0
    try:
        while True:
            pagina = _get(cliente, f"/cambiamenti?flusso={FLUSSO}&dopo={cursore.progressivo}"
                                   f"&limite={PAGINA}")  # fmt: skip
            voci = (pagina or {}).get("cambiamenti") or []
            if not voci:
                break
            precedente = cursore.impronta if cursore.progressivo else None
            feed.verifica_catena(voci, precedente=precedente)  # voci mancanti o alterate: stop
            documenti = []
            for voce in voci:  # prima si scarica, poi si scrive in una transazione
                risorsa = voce["data"]["risorsa"]
                if risorsa in tipi:
                    dati = _get(cliente, f"/ciclo-tessere/{risorsa}/{voce['subject']}")
                    if dati is not None:
                        documenti.append((risorsa, dati))
            with transaction.atomic():
                for risorsa, dati in documenti:
                    arrivi.ricevi(cliente, risorsa, dati)
                    ricevuti += 1
                cursore.progressivo = voci[-1]["ga_progressivo"]
                cursore.impronta = voci[-1]["ga_impronta"]
                cursore.letto_il = timezone.now()
                cursore.ultimo_errore = ""
                cursore.save()
            if cursore.progressivo >= pagina.get("ultimo", 0):
                break
        if cursore.ultimo_errore:
            cursore.ultimo_errore = ""
        cursore.letto_il = timezone.now()
        cursore.save(update_fields=["letto_il", "ultimo_errore"])
    except (client.ErroreCollegamento, client.ErroreTrasporto, feed.CatenaInterrotta,
            arrivi.OperazioneNonValida, KeyError, ValueError) as e:  # fmt: skip
        cursore.ultimo_errore = str(e)[:1000]
        cursore.save(update_fields=["ultimo_errore"])
        log.warning("Sincronizzazione con %s non riuscita: %s", cliente, e)
    return ricevuti


def sincronizza_tutti():
    controparti = ClienteApi.objects.filter(
        stato=ClienteApi.Stato.ATTIVA,
        ruolo__in=[ClienteApi.Ruolo.FEDERAZIONE, ClienteApi.Ruolo.SEZIONE],
    )
    return {c.nome: sincronizza(c) for c in controparti}
