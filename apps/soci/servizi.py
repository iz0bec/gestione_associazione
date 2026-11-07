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
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.anagrafica.models import Categoria, Consenso, Soggetto
from apps.anagrafica.servizi import cella_sicura
from apps.core.audit import Azione, campi_modificati, registra
from apps.core.numerazione import prossimo_numero

from .models import (
    SEQ_LIBRO_SOCI,
    SEQ_RICEVUTA,
    CartaTessera,
    DomandaIscrizione,
    LottoTessere,
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


def _in_prima_nota(tessera, utente):
    """Registra l'incasso in tesoreria; se non si può (es. esercizio chiuso) l'incasso resta valido
    e la quota compare tra quelle da registrare."""
    from apps.tesoreria.servizi import registra_quota

    try:
        with transaction.atomic():
            registra_quota(tessera, utente)
    except ValidationError:
        pass


def _assegna_ricevuta(tessera):
    tessera.ricevuta_anno = tessera.pagata_il.year
    tessera.ricevuta_numero = prossimo_numero(SEQ_RICEVUTA, tessera.ricevuta_anno)


# --- tessere fisiche dalla sede centrale ---------------------------------------------------

MASSIMO_PER_LOTTO = 10_000


@transaction.atomic
def carica_lotto(utente, *, anno, numero_da, numero_a, serie="", cifre=0, **dati):
    """Registra un carico di tessere prestampate e crea una riga per ogni tessera fisica."""
    serie = serie.strip().upper()
    if numero_a < numero_da:
        raise OperazioneNonValida("Il numero finale precede quello iniziale.")
    if numero_a - numero_da + 1 > MASSIMO_PER_LOTTO:
        raise OperazioneNonValida(f"Un lotto può contenere al massimo {MASSIMO_PER_LOTTO} tessere.")
    lotto = LottoTessere(
        anno=anno, serie=serie, numero_da=numero_da, numero_a=numero_a, cifre=cifre,
        creato_da=utente, modificato_da=utente, **dati,
    )  # fmt: skip
    codici = [lotto.formatta(n) for n in range(numero_da, numero_a + 1)]
    gia_presenti = list(
        CartaTessera.objects.filter(anno=anno, codice__in=codici).values_list("codice", flat=True)[
            :5
        ]
    )
    if gia_presenti:
        raise OperazioneNonValida(
            f"Tessere già caricate per il {anno}: {', '.join(gia_presenti)}"
            + ("..." if len(gia_presenti) == 5 else "")
        )
    lotto.save()
    CartaTessera.objects.bulk_create(
        CartaTessera(lotto=lotto, anno=anno, numero=n, codice=c)
        for n, c in zip(range(numero_da, numero_a + 1), codici, strict=True)
    )
    registra(
        Azione.CREAZIONE,
        lotto,
        utente=utente,
        descrizione=f"Carico tessere {lotto}",
        quantita=lotto.quantita,
    )
    return lotto


def prossima_carta(anno):
    """Prima tessera disponibile dell'anno (lotti più vecchi prima, numeri in ordine)."""
    return (
        CartaTessera.objects.select_for_update(skip_locked=True, of=("self",))
        .filter(anno=anno, stato=CartaTessera.Stato.DISPONIBILE)
        .order_by("lotto__data_acquisizione", "lotto_id", "numero")
        .first()
    )


def carta_per_codice(anno, codice):
    codice = " ".join(codice.strip().upper().split())
    carta = CartaTessera.objects.select_for_update().filter(anno=anno, codice=codice).first()
    if carta is None and codice.isdigit():
        # numero scritto senza serie o senza zeri iniziali
        candidate = list(
            CartaTessera.objects.select_for_update().filter(anno=anno, numero=int(codice))[:2]
        )
        carta = candidate[0] if len(candidate) == 1 else None
    if carta is None:
        raise OperazioneNonValida(
            f"La tessera {codice} non risulta tra quelle caricate per il {anno}."
        )
    return carta


@transaction.atomic
def attribuisci_carta(tessera, utente, codice=None):
    """Attribuisce al tesseramento una tessera fisica: quella indicata o la prossima disponibile."""
    tessera = (
        Tessera.objects.select_for_update().select_related("socio__soggetto").get(pk=tessera.pk)
    )
    if tessera.annullata:
        raise OperazioneNonValida("Il tesseramento è annullato.")
    if tessera.carta_id:
        raise OperazioneNonValida(f"Tessera già attribuita: {tessera.carta.codice}.")
    carta = carta_per_codice(tessera.anno, codice) if codice else prossima_carta(tessera.anno)
    if carta is None:
        raise OperazioneNonValida(
            f"Nessuna tessera {tessera.anno} disponibile: caricare un lotto dalla sede centrale."
        )
    if carta.stato != CartaTessera.Stato.DISPONIBILE:
        raise OperazioneNonValida(
            f"La tessera {carta.codice} non è disponibile ({carta.get_stato_display().lower()})."
        )
    carta.stato = CartaTessera.Stato.ATTRIBUITA
    carta.save(update_fields=["stato", "modificata_il"])
    tessera.carta = carta
    tessera.modificato_da = utente
    tessera.save(update_fields=["carta", "modificato_da", "modificato_il"])
    registra(Azione.MODIFICA, tessera, utente=utente, tessera_fisica=carta.codice)
    return tessera


def da_attribuire(anno):
    return Tessera.objects.valide().filter(anno=anno, carta__isnull=True)


def attribuzione_massiva(anno, utente, ordine="numero"):
    """Attribuisce le tessere disponibili ai tesseramenti dell'anno che ne sono privi.

    `ordine`: "numero" (numero di iscrizione) o "cognome". Si ferma quando le tessere finiscono.
    """
    campi = (
        ["socio__numero"]
        if ordine == "numero"
        else ["socio__soggetto__cognome", "socio__soggetto__nome"]
    )
    fatte, mancanti = [], 0
    for tessera in da_attribuire(anno).order_by(*campi):
        try:
            fatte.append(attribuisci_carta(tessera, utente))
        except OperazioneNonValida:
            mancanti += 1
    registra(
        Azione.MODIFICA,
        utente=utente,
        descrizione=f"Attribuzione tessere {anno}",
        attribuite=len(fatte),
        senza_tessera=mancanti,
    )
    return fatte, mancanti


@transaction.atomic
def cambia_stato_carta(carta, stato, utente, motivo):
    """Tessera non attribuita: fuori uso (annullata, smarrita), restituita o disponibile."""
    motivo = (motivo or "").strip()
    carta = CartaTessera.objects.select_for_update().get(pk=carta.pk)
    if carta.stato == CartaTessera.Stato.ATTRIBUITA:
        raise OperazioneNonValida(
            "La tessera è attribuita: annullare prima il tesseramento del socio."
        )
    if stato == CartaTessera.Stato.ATTRIBUITA:
        raise OperazioneNonValida("Per attribuire una tessera usare il tesseramento del socio.")
    if stato != CartaTessera.Stato.DISPONIBILE and not motivo:
        raise OperazioneNonValida("Indicare il motivo.")
    precedente = carta.stato
    carta.stato = stato
    carta.motivo = motivo[:255]
    carta.save()
    registra(
        Azione.MODIFICA,
        carta.lotto,
        utente=utente,
        descrizione=f"Tessera {carta.codice}",
        stato={"prima": precedente, "dopo": stato},
        motivo=motivo,
    )
    return carta


def giacenza(anno):
    """Riepilogo delle tessere fisiche dell'anno per stato, con costo verso la sede centrale."""
    from django.db.models import Count, Q

    carte = CartaTessera.objects.filter(anno=anno)
    conteggi = carte.aggregate(
        totale=Count("id"),
        **{s: Count("id", filter=Q(stato=s)) for s in CartaTessera.Stato.values},
    )
    # costo dovuto alla sede centrale: tessere usate o fuori uso (le restituite no)
    costo = sum(
        (
            lotto.costo_unitario * lotto.carte.exclude(stato=CartaTessera.Stato.RESTITUITA).count()
            for lotto in LottoTessere.objects.filter(anno=anno)
        ),
        start=Decimal("0"),
    )
    return {**conteggi, "costo": costo}


# --- tesseramento annuale ----------------------------------------------------------------


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
    carta=None,
):
    """Crea il tesseramento dell'anno; se `pagata_il` è indicato registra anche l'incasso.

    `carta`: None = da attribuire dopo; "prossima" = prima tessera disponibile; altrimenti il
    numero della tessera fisica da attribuire.
    """
    socio = Socio.objects.select_for_update().select_related("tipologia").get(pk=socio.pk)
    if socio.stato != Socio.Stato.ATTIVO:
        raise OperazioneNonValida("La tessera si rilascia solo ai soci attivi.")
    if socio.tessere.valide().filter(anno=anno).exists():
        raise OperazioneNonValida(f"Il socio ha già una tessera valida per il {anno}.")
    tessera = Tessera(
        socio=socio,
        anno=anno,
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
    if tessera.pagata:
        _in_prima_nota(tessera, utente)
    registra(
        Azione.CREAZIONE,
        tessera,
        utente=utente,
        anno=anno,
        importo=str(tessera.importo),
        ricevuta=tessera.codice_ricevuta,
    )
    if carta == "prossima":
        if CartaTessera.objects.filter(anno=anno, stato=CartaTessera.Stato.DISPONIBILE).exists():
            tessera = attribuisci_carta(tessera, utente)
    elif carta:
        tessera = attribuisci_carta(tessera, utente, carta)
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
    _in_prima_nota(tessera, utente)
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
def annulla_tessera(tessera, utente, motivo, *, libera_carta=False):
    """Annulla il tesseramento; la ricevuta non si riutilizza.

    La tessera fisica attribuita diventa annullata, oppure torna disponibile se `libera_carta`
    (es. attribuita per errore e mai consegnata al socio).
    """
    if not motivo.strip():
        raise OperazioneNonValida("Indicare il motivo dell'annullamento.")
    tessera = Tessera.objects.select_for_update().get(pk=tessera.pk)
    if tessera.annullata:
        raise OperazioneNonValida("La tessera è già annullata.")
    tessera.annullata = True
    tessera.motivo_annullamento = motivo.strip()
    tessera.modificato_da = utente
    carta = tessera.carta
    if carta:
        carta.stato = (
            CartaTessera.Stato.DISPONIBILE if libera_carta else CartaTessera.Stato.ANNULLATA
        )
        carta.motivo = (
            "" if libera_carta else f"Tesseramento annullato: {tessera.motivo_annullamento}"[:255]
        )
        carta.save()
        if libera_carta:
            tessera.carta = None  # la tessera fisica torna disponibile per un altro socio
    tessera.save()
    registra(
        Azione.ANNULLAMENTO,
        tessera,
        utente=utente,
        motivo=tessera.motivo_annullamento,
        tessera_fisica=carta.codice if carta else "",
        tessera_fisica_liberata=libera_carta,
    )
    return tessera


def soci_da_rinnovare(anno):
    """Soci attivi che non hanno ancora una tessera valida per l'anno."""
    con_tessera = Tessera.objects.valide().filter(anno=anno).values("socio_id")
    return (
        Socio.objects.attivi().exclude(pk__in=con_tessera).select_related("soggetto", "tipologia")
    )


def rinnovo_massivo(anno, utente, *, attribuisci=False):
    """Crea il tesseramento dell'anno (da pagare) per tutti i soci attivi che non l'hanno;
    con `attribuisci` assegna anche le tessere fisiche disponibili, in ordine di numero socio.

    Una transazione per socio: un errore su un socio non blocca gli altri.
    """
    rilasciate, errori = [], []
    for socio in soci_da_rinnovare(anno).order_by("numero"):
        try:
            rilasciate.append(
                rilascia_tessera(socio, anno, utente, carta="prossima" if attribuisci else None)
            )
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
        rilascia_tessera(socio, tessera_anno, utente, carta="prossima")
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


INTESTAZIONE_TESSERATI = [
    "tessera", "numero_socio", "cognome", "nome", "codice_fiscale", "data_nascita",
    "luogo_nascita", "indirizzo", "cap", "comune", "provincia", "tipologia", "data_rilascio",
    "quota", "pagata_il",
]  # fmt: skip


def esporta_tesserati_csv(anno, destinazione, utente):
    """Elenco dei tesserati dell'anno con il numero di tessera (per la sede centrale)."""
    writer = csv.writer(destinazione, delimiter=";")
    writer.writerow(INTESTAZIONE_TESSERATI)
    n = 0
    tessere = (
        Tessera.objects.valide()
        .filter(anno=anno, carta__isnull=False)
        .select_related("carta", "socio__soggetto", "socio__tipologia")
        .order_by("carta__lotto__serie", "carta__numero")
    )
    for t in tessere:
        p = t.socio.soggetto
        riga = [
            t.carta.codice, t.socio.numero, p.cognome, p.nome, p.codice_fiscale, p.data_nascita,
            p.luogo_nascita, p.indirizzo, p.cap, p.comune, p.provincia, t.socio.tipologia.nome,
            t.data_rilascio, t.importo, t.pagata_il,
        ]  # fmt: skip
        writer.writerow([cella_sicura(v) for v in riga])
        n += 1
    registra(
        Azione.ESPORTAZIONE, utente=utente, descrizione=f"Tesserati {anno} CSV ({n} righe)", righe=n
    )
    return n


def tipologie_attive():
    return TipologiaSocio.objects.filter(attiva=True)
