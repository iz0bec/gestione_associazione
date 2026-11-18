# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Documenti ricevuti dalle controparti (ADR-030, F4): ricezione nella coda,
# *              conferma (protocollo in entrata con il PDF, poi l'effetto sul ciclo delle
# *              tessere: richiesta registrata, lotto caricato, ricevuta archiviata) e scarto.
# *              La presa in carico di una consegna si registra da sola.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import base64
import binascii
from datetime import date
from decimal import Decimal, InvalidOperation

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from apps.core.audit import Azione, registra

from .models import ClienteApi, DocumentoRicevuto

# tipi accettati secondo il ruolo della controparte
DA_FEDERAZIONE = {"consegna", "ricevuta"}
DA_SEZIONE = {"richiesta", "presa"}


class OperazioneNonValida(Exception):
    pass


def tipi_accettati(cliente):
    if cliente.ruolo == ClienteApi.Ruolo.FEDERAZIONE:
        return DA_FEDERAZIONE
    if cliente.ruolo == ClienteApi.Ruolo.SEZIONE and cliente.sezione_id:
        return DA_SEZIONE
    return set()


def _pdf(dati):
    testo = dati.pop("pdf", None)
    if not testo:
        return None
    try:
        return base64.b64decode(testo, validate=True)
    except (binascii.Error, ValueError):
        return None


@transaction.atomic
def ricevi(cliente, tipo, dati):
    """Mette (o aggiorna) il documento nella coda; la presa in carico si applica subito."""
    if tipo not in tipi_accettati(cliente):
        raise OperazioneNonValida(f"Documento «{tipo}» non previsto da questa controparte.")
    dati = dict(dati)
    pdf = _pdf(dati)
    documento, nuovo = DocumentoRicevuto.objects.select_for_update().get_or_create(
        cliente=cliente, tipo=tipo, uuid_origine=dati["uuid"],
        defaults={"versione": dati.get("versione", 1), "dati": dati},
    )  # fmt: skip
    if not nuovo:
        if dati.get("versione", 1) <= documento.versione:
            return documento, False
        documento.versione, documento.dati = dati.get("versione", 1), dati
        if documento.stato == DocumentoRicevuto.Stato.APPLICATO:
            documento.motivo = "aggiornato dalla controparte dopo la conferma: controllare"
        documento.save()
    if pdf:
        documento.pdf.save(f"{tipo}-{documento.uuid_origine}.pdf", ContentFile(pdf), save=True)
    if tipo == "presa":
        _applica_presa(documento)
    return documento, nuovo


def _applica_presa(documento):
    from apps.soci.models import ConsegnaTessere

    consegna = ConsegnaTessere.objects.filter(
        uuid=documento.dati.get("consegna"), sezione=documento.cliente.sezione
    ).first()
    if consegna is None:
        documento.motivo = "consegna non trovata"
        documento.save(update_fields=["motivo"])
        return
    consegna.presa_in_carico_il = date.fromisoformat(documento.dati["data"])
    consegna.save(update_fields=["presa_in_carico_il", "modificato_il"])
    documento.stato = DocumentoRicevuto.Stato.APPLICATO
    documento.gestito_il = timezone.now()
    documento.save(update_fields=["stato", "gestito_il"])
    registra(Azione.MODIFICA, consegna, descrizione=f"{consegna}: presa in carico (via API)",
             da=documento.cliente.nome)  # fmt: skip


OGGETTI = {
    "richiesta": "Richiesta di tessere {anno} ({quantita})",
    "consegna": "Consegna di tessere n. {anno}/{numero} ({numero_da}–{numero_a})",
    "ricevuta": "Ricevuta n. {ricevuta} per le tessere {anno}",
}


def _protocolla(documento, utente):
    from apps.protocollo import servizi as protocollo

    d = documento.dati
    allegati = []
    if documento.pdf:
        with documento.pdf.open("rb") as f:
            allegati.append(ContentFile(f.read(), name=f"{documento.tipo}.pdf"))
    try:
        return protocollo.registra_protocollo(
            {"direzione": "entrata", "oggetto": OGGETTI[documento.tipo].format(**d),
             "mezzo": "api"},
            [{"ruolo": "mittente", "descrizione": d.get("mittente") or documento.cliente.nome}],
            utente, allegati=allegati,
        )  # fmt: skip
    except protocollo.OperazioneNonValida as e:
        raise OperazioneNonValida(" ".join(e.messages)) from None


@transaction.atomic
def conferma(documento, utente, *, protocolla=True, sezione=None):
    """Conferma un documento in coda: protocollo in entrata (facoltativo) e il suo effetto."""
    from apps.soci import ciclo
    from apps.soci.servizi import OperazioneNonValida as ErroreSoci

    documento = DocumentoRicevuto.objects.select_for_update().get(pk=documento.pk)
    if documento.stato != DocumentoRicevuto.Stato.DA_ESAMINARE:
        raise OperazioneNonValida("Il documento è già stato gestito.")
    d = documento.dati
    if protocolla:
        documento.protocollo = _protocolla(documento, utente)
    try:
        if documento.tipo == "richiesta":
            ciclo.registra_richiesta(
                utente, anno=d["anno"], sezione=documento.cliente.sezione,
                quantita=int(d["quantita"]), data=date.fromisoformat(d["data"]),
                note=d.get("note", ""), protocollo=documento.protocollo,
                uuid_origine=d["uuid"], cliente_api=documento.cliente,
            )  # fmt: skip
        elif documento.tipo == "consegna":
            from apps.soci.servizi import carica_lotto

            carica_lotto(
                utente, anno=d["anno"], numero_da=d["numero_da"], numero_a=d["numero_a"],
                serie=d.get("serie", ""), cifre=d.get("cifre", 0),
                costo_unitario=Decimal(d["prezzo_unitario"]), sezione=sezione,
                fornitore=(d.get("mittente") or documento.cliente.nome)[:100],
                riferimento=f"Consegna n. {d['anno']}/{d['numero']} del {d['data']}"[:200],
                consegna_uuid=d["uuid"],
            )  # fmt: skip
    except (ErroreSoci, KeyError, ValueError, InvalidOperation) as e:
        messaggio = " ".join(getattr(e, "messages", [])) or "dati del documento non validi"
        raise OperazioneNonValida(messaggio) from None
    documento.stato = DocumentoRicevuto.Stato.APPLICATO
    documento.gestito_il = timezone.now()
    documento.gestito_da = utente
    documento.save()
    registra(Azione.MODIFICA, documento, utente=utente, confermato=True,
             protocollo=documento.protocollo.segnatura if documento.protocollo else "")  # fmt: skip
    return documento


def scarta(documento, utente, motivo):
    if documento.stato != DocumentoRicevuto.Stato.DA_ESAMINARE:
        raise OperazioneNonValida("Il documento è già stato gestito.")
    if not motivo.strip():
        raise OperazioneNonValida("Indicare il motivo dello scarto.")
    documento.stato = DocumentoRicevuto.Stato.SCARTATO
    documento.motivo = motivo.strip()[:255]
    documento.gestito_il = timezone.now()
    documento.gestito_da = utente
    documento.save()
    registra(Azione.ANNULLAMENTO, documento, utente=utente, motivo=documento.motivo)
