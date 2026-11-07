# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Operazioni del libro soci: ammissione, cessazione, tessere, incassi,
# *              rinnovo massivo, domande di iscrizione. Tutte atomiche e registrate.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import csv
from datetime import date

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.anagrafica.models import Categoria, Consenso, Soggetto
from apps.anagrafica.servizi import cella_sicura
from apps.core.audit import Azione, campi_modificati, registra
from apps.core.numerazione import prossimo_numero

from .models import (
    SEQ_LIBRO_SOCI,
    SEQ_RICEVUTA,
    SEQ_TESSERA,
    DomandaIscrizione,
    Socio,
    Tessera,
    TipologiaSocio,
)

NOME_CATEGORIA_SOCI = "Socio"


class OperazioneNonValida(ValidationError):
    """Operazione rifiutata per una regola del libro soci (messaggio per l'utente)."""


def _categoria_soci():
    categoria, _ = Categoria.objects.get_or_create(nome=NOME_CATEGORIA_SOCI)
    return categoria


# --- ammissione e cessazione -------------------------------------------------------------


@transaction.atomic
def ammetti_socio(soggetto, tipologia, utente, *, data_ammissione=None, delibera="", note=""):
    """Iscrive il soggetto al libro soci con il primo numero libero e la categoria «Socio»."""
    soggetto = Soggetto.objects.select_for_update().get(pk=soggetto.pk)
    if not soggetto.is_persona:
        raise OperazioneNonValida("Solo le persone fisiche possono essere iscritte al libro soci.")
    if not soggetto.attivo:
        raise OperazioneNonValida("Il soggetto è archiviato: ripristinarlo prima dell'ammissione.")
    if soggetto.deceduto:
        raise OperazioneNonValida("Il soggetto risulta deceduto.")
    if Socio.objects.filter(soggetto=soggetto).exists():
        raise OperazioneNonValida("Il soggetto è già iscritto al libro soci.")
    socio = Socio.objects.create(
        soggetto=soggetto,
        numero=prossimo_numero(SEQ_LIBRO_SOCI),
        tipologia=tipologia,
        data_ammissione=data_ammissione or date.today(),
        delibera_ammissione=delibera,
        note=note,
        creato_da=utente,
        modificato_da=utente,
    )
    soggetto.categorie.add(_categoria_soci())
    registra(Azione.CREAZIONE, socio, utente=utente, numero=socio.numero)
    return socio


@transaction.atomic
def salva_socio(form, utente):
    """Modifica dei dati di iscrizione (tipologia, delibera, note)."""
    dettagli = campi_modificati(form)
    socio = form.save(commit=False)
    socio.modificato_da = utente
    socio.save()
    if dettagli.get("campi"):
        registra(Azione.MODIFICA, socio, utente=utente, **dettagli)
    return socio


@transaction.atomic
def cessa_socio(socio, utente, *, data_cessazione, causa, note=""):
    """Registra la cessazione: il numero resta nel libro soci, la categoria «Socio» si toglie."""
    socio = Socio.objects.select_for_update().select_related("soggetto").get(pk=socio.pk)
    if socio.stato == Socio.Stato.CESSATO:
        raise OperazioneNonValida("Il socio è già cessato.")
    if data_cessazione < socio.data_ammissione:
        raise OperazioneNonValida("La cessazione non può precedere l'ammissione.")
    socio.stato = Socio.Stato.CESSATO
    socio.data_cessazione = data_cessazione
    socio.causa_cessazione = causa
    if note:
        socio.note = f"{socio.note}\n{note}".strip()
    socio.modificato_da = utente
    socio.save()
    socio.soggetto.categorie.remove(_categoria_soci())
    if causa == Socio.Cessazione.DECESSO and not socio.soggetto.data_decesso:
        socio.soggetto.data_decesso = data_cessazione
        socio.soggetto.modificato_da = utente
        socio.soggetto.save(update_fields=["data_decesso", "modificato_da", "modificato_il"])
    registra(
        Azione.ARCHIVIAZIONE,
        socio,
        utente=utente,
        cessazione=str(data_cessazione),
        causa=socio.get_causa_cessazione_display(),
    )
    return socio


@transaction.atomic
def cambia_stato(socio, stato, utente, motivo=""):
    """Sospensione e riattivazione (non per la cessazione, che ha la sua procedura)."""
    socio = Socio.objects.select_for_update().select_related("soggetto").get(pk=socio.pk)
    if stato not in (Socio.Stato.ATTIVO, Socio.Stato.SOSPESO):
        raise OperazioneNonValida("Stato non ammesso.")
    if socio.stato == stato:
        raise OperazioneNonValida(f"Il socio è già {socio.get_stato_display().lower()}.")
    if socio.stato == Socio.Stato.CESSATO and stato == Socio.Stato.SOSPESO:
        raise OperazioneNonValida("Un socio cessato non si sospende.")
    if socio.stato == Socio.Stato.CESSATO:
        if socio.soggetto.deceduto:
            raise OperazioneNonValida("Il socio risulta deceduto.")
        socio.data_cessazione = None
        socio.causa_cessazione = ""
        socio.soggetto.categorie.add(_categoria_soci())
    precedente = socio.stato
    socio.stato = stato
    socio.modificato_da = utente
    socio.save()
    registra(
        Azione.MODIFICA,
        socio,
        utente=utente,
        stato={"prima": precedente, "dopo": stato},
        motivo=motivo,
    )
    return socio


# --- tessere e quote ---------------------------------------------------------------------


def _assegna_ricevuta(tessera):
    tessera.ricevuta_anno = tessera.pagata_il.year
    tessera.ricevuta_numero = prossimo_numero(SEQ_RICEVUTA, tessera.ricevuta_anno)


@transaction.atomic
def rilascia_tessera(
    socio,
    anno,
    utente,
    *,
    importo=None,
    data_rilascio=None,
    pagata_il=None,
    metodo="",
    riferimento="",
):
    """Crea la tessera dell'anno; se `pagata_il` è indicato registra anche l'incasso."""
    socio = Socio.objects.select_for_update().select_related("tipologia").get(pk=socio.pk)
    if socio.stato != Socio.Stato.ATTIVO:
        raise OperazioneNonValida("La tessera si rilascia solo ai soci attivi.")
    if socio.tessere.valide().filter(anno=anno).exists():
        raise OperazioneNonValida(f"Il socio ha già una tessera valida per il {anno}.")
    tessera = Tessera(
        socio=socio,
        anno=anno,
        numero=prossimo_numero(SEQ_TESSERA, anno),
        data_rilascio=data_rilascio or date.today(),
        importo=socio.tipologia.quota_annua if importo is None else importo,
        creato_da=utente,
        modificato_da=utente,
    )
    if pagata_il and tessera.importo > 0:
        tessera.pagata_il = pagata_il
        tessera.metodo_pagamento = metodo or Tessera.Metodo.CONTANTI
        tessera.riferimento_pagamento = riferimento
        _assegna_ricevuta(tessera)
    tessera.save()
    registra(
        Azione.CREAZIONE,
        tessera,
        utente=utente,
        anno=anno,
        importo=str(tessera.importo),
        ricevuta=tessera.codice_ricevuta,
    )
    return tessera


@transaction.atomic
def registra_pagamento(tessera, utente, *, pagata_il, metodo, importo=None, riferimento=""):
    """Registra l'incasso della quota e assegna il numero di ricevuta."""
    tessera = Tessera.objects.select_for_update().get(pk=tessera.pk)
    if tessera.annullata:
        raise OperazioneNonValida("La tessera è annullata.")
    if tessera.pagata:
        raise OperazioneNonValida("Il pagamento è già registrato.")
    if importo is not None:
        tessera.importo = importo
    if tessera.importo <= 0:
        raise OperazioneNonValida("Quota pari a zero: non c'è nulla da incassare.")
    tessera.pagata_il = pagata_il
    tessera.metodo_pagamento = metodo
    tessera.riferimento_pagamento = riferimento
    tessera.modificato_da = utente
    _assegna_ricevuta(tessera)
    tessera.save()
    registra(
        Azione.MODIFICA,
        tessera,
        utente=utente,
        pagamento=str(pagata_il),
        importo=str(tessera.importo),
        ricevuta=tessera.codice_ricevuta,
    )
    return tessera


@transaction.atomic
def annulla_tessera(tessera, utente, motivo):
    """Annulla la tessera: numero e ricevuta non vengono riutilizzati."""
    if not motivo.strip():
        raise OperazioneNonValida("Indicare il motivo dell'annullamento.")
    tessera = Tessera.objects.select_for_update().get(pk=tessera.pk)
    if tessera.annullata:
        raise OperazioneNonValida("La tessera è già annullata.")
    tessera.annullata = True
    tessera.motivo_annullamento = motivo.strip()
    tessera.modificato_da = utente
    tessera.save()
    registra(Azione.ANNULLAMENTO, tessera, utente=utente, motivo=tessera.motivo_annullamento)
    return tessera


def soci_da_rinnovare(anno):
    """Soci attivi che non hanno ancora una tessera valida per l'anno."""
    con_tessera = Tessera.objects.valide().filter(anno=anno).values("socio_id")
    return (
        Socio.objects.attivi().exclude(pk__in=con_tessera).select_related("soggetto", "tipologia")
    )


def rinnovo_massivo(anno, utente):
    """Rilascia la tessera dell'anno (da pagare) a tutti i soci attivi che non l'hanno.

    Una transazione per socio: un errore su un socio non blocca gli altri.
    """
    rilasciate, errori = [], []
    for socio in soci_da_rinnovare(anno).order_by("numero"):
        try:
            rilasciate.append(rilascia_tessera(socio, anno, utente))
        except OperazioneNonValida as e:
            errori.append((socio, e.message))
    registra(
        Azione.CREAZIONE,
        utente=utente,
        descrizione=f"Rinnovo tessere {anno}",
        anno=anno,
        rilasciate=len(rilasciate),
        errori=len(errori),
    )
    return rilasciate, errori


# --- domande di iscrizione ---------------------------------------------------------------


def soggetto_per_domanda(domanda):
    """Soggetto già in anagrafica con lo stesso codice fiscale, se esiste."""
    return Soggetto.objects.filter(codice_fiscale__iexact=domanda.codice_fiscale).first()


@transaction.atomic
def accogli_domanda(
    domanda, utente, *, tipologia, data_ammissione, delibera="", tessera_anno=None, note_esito=""
):
    """Crea (o collega) la scheda anagrafica, iscrive il socio e registra i consensi."""
    domanda = DomandaIscrizione.objects.select_for_update().get(pk=domanda.pk)
    if domanda.stato != DomandaIscrizione.Stato.IN_ATTESA:
        raise OperazioneNonValida("La domanda è già stata valutata.")
    soggetto = soggetto_per_domanda(domanda)
    if soggetto is None:
        soggetto = Soggetto.objects.create(
            tipo=Soggetto.Tipo.PERSONA,
            nome=domanda.nome,
            cognome=domanda.cognome,
            codice_fiscale=domanda.codice_fiscale,
            data_nascita=domanda.data_nascita,
            luogo_nascita=domanda.luogo_nascita,
            email=domanda.email,
            cellulare=domanda.telefono,
            indirizzo=domanda.indirizzo,
            cap=domanda.cap,
            comune=domanda.comune,
            provincia=domanda.provincia,
            creato_da=utente,
            modificato_da=utente,
        )
        registra(Azione.CREAZIONE, soggetto, utente=utente, origine=f"domanda {domanda.pk}")
    elif not soggetto.attivo:
        soggetto.attivo = True
        soggetto.save(update_fields=["attivo"])
    socio = ammetti_socio(
        soggetto, tipologia, utente, data_ammissione=data_ammissione, delibera=delibera
    )
    modalita = f"domanda di iscrizione del {domanda.ricevuta_il:%d/%m/%Y}"
    for finalita, prestato in (
        (Consenso.Finalita.COMUNICAZIONI, domanda.consenso_comunicazioni),
        (Consenso.Finalita.IMMAGINI, domanda.consenso_immagini),
    ):
        Consenso.objects.create(
            soggetto=soggetto,
            finalita=finalita,
            prestato=prestato,
            data=domanda.ricevuta_il.date(),
            modalita=modalita,
        )
    if tessera_anno:
        rilascia_tessera(socio, tessera_anno, utente)
    domanda.stato = DomandaIscrizione.Stato.ACCOLTA
    domanda.esito_il = date.today()
    domanda.esito_note = note_esito or delibera
    domanda.esito_da = utente
    domanda.socio = socio
    domanda.save()
    registra(Azione.MODIFICA, domanda, utente=utente, esito="accolta", socio=socio.numero)
    return socio


@transaction.atomic
def respingi_domanda(domanda, utente, motivo):
    if not motivo.strip():
        raise OperazioneNonValida("Indicare la motivazione del rigetto.")
    domanda = DomandaIscrizione.objects.select_for_update().get(pk=domanda.pk)
    if domanda.stato != DomandaIscrizione.Stato.IN_ATTESA:
        raise OperazioneNonValida("La domanda è già stata valutata.")
    domanda.stato = DomandaIscrizione.Stato.RESPINTA
    domanda.esito_il = date.today()
    domanda.esito_note = motivo.strip()
    domanda.esito_da = utente
    domanda.save()
    registra(Azione.MODIFICA, domanda, utente=utente, esito="respinta", motivo=domanda.esito_note)
    return domanda


# --- esportazioni ------------------------------------------------------------------------

INTESTAZIONE_LIBRO = [
    "numero", "cognome", "nome", "codice_fiscale", "data_nascita", "luogo_nascita", "indirizzo",
    "cap", "comune", "provincia", "email", "telefono", "tipologia", "data_ammissione",
    "delibera_ammissione", "stato", "data_cessazione", "causa_cessazione",
]  # fmt: skip


def esporta_libro_csv(queryset, destinazione, utente):
    writer = csv.writer(destinazione, delimiter=";")
    writer.writerow(INTESTAZIONE_LIBRO)
    n = 0
    for s in queryset.select_related("soggetto", "tipologia"):
        p = s.soggetto
        riga = [
            s.numero, p.cognome, p.nome, p.codice_fiscale, p.data_nascita, p.luogo_nascita,
            p.indirizzo, p.cap, p.comune, p.provincia, p.email, p.cellulare or p.telefono,
            s.tipologia.nome, s.data_ammissione, s.delibera_ammissione, s.get_stato_display(),
            s.data_cessazione, s.get_causa_cessazione_display(),
        ]  # fmt: skip
        writer.writerow([cella_sicura(v) for v in riga])
        n += 1
    registra(Azione.ESPORTAZIONE, utente=utente, descrizione=f"Libro soci CSV ({n} righe)", righe=n)
    return n


def tipologie_attive():
    return TipologiaSocio.objects.filter(attiva=True)
