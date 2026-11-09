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
import io
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
    ListinoTessere,
    LottoTessere,
    QuotaListino,
    Sezione,
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


def _per_sezioni(queryset, sezioni, campo="sezione"):
    """Limita a un insieme di id di sezione (None = tutte)."""
    return queryset if sezioni is None else queryset.filter(**{f"{campo}__in": sezioni})


# --- ammissione e cessazione -------------------------------------------------------------


@transaction.atomic
def ammetti_socio(soggetto, tipologia, utente, *, data_ammissione=None, delibera="", note="",
                  sezione=None, matricola=""):  # fmt: skip
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
    matricola = (matricola or "").strip()
    if matricola and Socio.objects.filter(matricola=matricola).exists():
        raise OperazioneNonValida(f"La matricola {matricola} è già di un altro socio.")
    socio = Socio.objects.create(
        soggetto=soggetto,
        sezione=sezione or Sezione.predefinita(),
        matricola=matricola,
        numero=prossimo_numero(SEQ_LIBRO_SOCI),
        tipologia=tipologia,
        data_ammissione=data_ammissione or date.today(),
        delibera_ammissione=delibera,
        note=note,
        creato_da=utente,
        modificato_da=utente,
    )
    soggetto.categorie.add(_categoria_soci())
    registra(
        Azione.CREAZIONE, socio, utente=utente, numero=socio.numero, sezione=socio.sezione.nome
    )
    return socio


@transaction.atomic
def salva_socio(form, utente, *, foto=None, togli_foto=False):
    """Modifica dei dati di iscrizione (sezione, tipologia, delibera, note) e della foto."""
    from apps.anagrafica.servizi import imposta_foto

    dettagli = campi_modificati(form)
    socio = form.save(commit=False)
    socio.modificato_da = utente
    socio.save()
    if foto or togli_foto:
        soggetto = socio.soggetto
        imposta_foto(soggetto, foto, togli=togli_foto)
        soggetto.modificato_da = utente
        soggetto.save()
        registra(Azione.MODIFICA, soggetto, utente=utente, foto=bool(foto))
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


# --- listino annuale: costo d'acquisto e prezzi di distribuzione ---------------------------


def listino(anno):
    return ListinoTessere.objects.filter(anno=anno).prefetch_related("quote").first()


def quota_per(tipologia, anno):
    """Prezzo di distribuzione dell'anno per la tipologia (dal listino, se definito)."""
    q = QuotaListino.objects.filter(listino__anno=anno, tipologia=tipologia).first()
    return q.importo if q else tipologia.quota_annua


def costo_acquisto(anno):
    lst = ListinoTessere.objects.filter(anno=anno).first()
    return lst.costo_acquisto if lst else None


@transaction.atomic
def prepara_listino(anno, utente=None):
    """Crea il listino dell'anno copiando quello precedente (o le quote di riferimento)."""
    esistente = listino(anno)
    if esistente:
        return esistente
    precedente = ListinoTessere.objects.filter(anno__lt=anno).order_by("-anno").first()
    nuovo = ListinoTessere.objects.create(
        anno=anno,
        costo_acquisto=precedente.costo_acquisto if precedente else Decimal("0"),
        creato_da=utente,
        modificato_da=utente,
    )
    da_copiare = {q.tipologia_id: q.importo for q in precedente.quote.all()} if precedente else {}
    for t in TipologiaSocio.objects.filter(attiva=True):
        QuotaListino.objects.create(
            listino=nuovo, tipologia=t, importo=da_copiare.get(t.pk, t.quota_annua)
        )
    registra(Azione.CREAZIONE, nuovo, utente=utente, da=precedente.anno if precedente else None)
    return nuovo


@transaction.atomic
def salva_listino(anno, utente, *, costo_acquisto, quote, note=""):
    """`quote`: {tipologia: importo}. Le tessere già rilasciate conservano la loro quota."""
    lst = prepara_listino(anno, utente)
    prima = {
        "costo": str(lst.costo_acquisto),
        **{q.tipologia.nome: str(q.importo) for q in lst.quote.select_related("tipologia")},
    }
    lst.costo_acquisto = costo_acquisto
    lst.note = note
    lst.modificato_da = utente
    lst.save()
    for tipologia, importo in quote.items():
        QuotaListino.objects.update_or_create(
            listino=lst, tipologia=tipologia, defaults={"importo": importo}
        )
    dopo = {"costo": str(costo_acquisto), **{t.nome: str(v) for t, v in quote.items()}}
    cambiati = {k: {"prima": prima.get(k), "dopo": v} for k, v in dopo.items() if prima.get(k) != v}
    if cambiati:
        registra(Azione.MODIFICA, lst, utente=utente, valori=cambiati)
    return lst


# --- tessere fisiche dalla sede centrale ---------------------------------------------------

MASSIMO_PER_LOTTO = 10_000


@transaction.atomic
def carica_lotto(utente, *, anno, numero_da, numero_a, serie="", cifre=0, costo_unitario=None,
                 sezione=None, **dati):  # fmt: skip
    """Registra un carico di tessere prestampate e crea una riga per ogni tessera fisica.

    Senza `costo_unitario` vale il costo d'acquisto del listino dell'anno.
    """
    serie = serie.strip().upper()
    if costo_unitario is None:
        costo_unitario = costo_acquisto(anno) or Decimal("0")
    if numero_a < numero_da:
        raise OperazioneNonValida("Il numero finale precede quello iniziale.")
    if numero_a - numero_da + 1 > MASSIMO_PER_LOTTO:
        raise OperazioneNonValida(f"Un lotto può contenere al massimo {MASSIMO_PER_LOTTO} tessere.")
    lotto = LottoTessere(
        anno=anno, serie=serie, numero_da=numero_da, numero_a=numero_a, cifre=cifre,
        costo_unitario=costo_unitario, sezione=sezione or Sezione.predefinita(),
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


FORNITORE_REGISTRO = "Registro soci nazionale"


def carta_da_registro(anno, sezione, numero, utente):
    """Tessera fisica indicata dal registro nazionale ma non ancora caricata: la aggiunge al
    lotto «Registro soci nazionale» dell'anno e della sezione (creato se manca)."""
    if CartaTessera.objects.filter(anno=anno, numero=numero).exists():
        return None
    lotto = (
        LottoTessere.objects.select_for_update()
        .filter(anno=anno, sezione=sezione, fornitore=FORNITORE_REGISTRO)
        .first()
    )
    if lotto is None:
        lotto = LottoTessere.objects.create(
            anno=anno, sezione=sezione, numero_da=numero, numero_a=numero,
            fornitore=FORNITORE_REGISTRO, riferimento="Importazione dal registro nazionale",
            costo_unitario=costo_acquisto(anno) or Decimal("0"),
            creato_da=utente, modificato_da=utente,
        )  # fmt: skip
    elif not lotto.numero_da <= numero <= lotto.numero_a:
        lotto.numero_da, lotto.numero_a = min(lotto.numero_da, numero), max(lotto.numero_a, numero)
        lotto.save(update_fields=["numero_da", "numero_a", "modificato_il"])
    return CartaTessera.objects.create(lotto=lotto, anno=anno, numero=numero, codice=str(numero))


def prossima_carta(anno, sezione_id):
    """Prima tessera disponibile dell'anno per la sezione (lotti più vecchi, numeri in ordine)."""
    return (
        CartaTessera.objects.select_for_update(skip_locked=True, of=("self",))
        .filter(anno=anno, lotto__sezione_id=sezione_id, stato=CartaTessera.Stato.DISPONIBILE)
        .order_by("lotto__data_acquisizione", "lotto_id", "numero")
        .first()
    )


def carta_per_codice(anno, codice, sezione_id=None):
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
    if sezione_id and carta.lotto.sezione_id != sezione_id:
        raise OperazioneNonValida(
            f"La tessera {carta.codice} è stata caricata per la sezione {carta.lotto.sezione}."
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
    sezione_id = tessera.socio.sezione_id
    carta = (
        carta_per_codice(tessera.anno, codice, sezione_id)
        if codice
        else prossima_carta(tessera.anno, sezione_id)
    )
    if carta is None:
        raise OperazioneNonValida(
            f"Nessuna tessera {tessera.anno} disponibile per la sezione {tessera.socio.sezione}: "
            "caricare un lotto dalla sede centrale."
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


def da_attribuire(anno, sezioni=None):
    qs = Tessera.objects.valide().filter(anno=anno, carta__isnull=True)
    return _per_sezioni(qs, sezioni, "socio__sezione")


def attribuzione_massiva(anno, utente, ordine="numero", sezioni=None):
    """Attribuisce le tessere disponibili ai tesseramenti dell'anno che ne sono privi.

    `ordine`: "numero" (numero di iscrizione) o "cognome". Si ferma quando le tessere finiscono.
    """
    campi = (
        ["socio__numero"]
        if ordine == "numero"
        else ["socio__soggetto__cognome", "socio__soggetto__nome"]
    )
    fatte, mancanti = [], 0
    for tessera in da_attribuire(anno, sezioni).order_by(*campi):
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


def giacenza(anno, sezioni=None):
    """Riepilogo delle tessere fisiche dell'anno per stato, con costo verso la sede centrale."""
    from django.db.models import Count, Q

    carte = _per_sezioni(CartaTessera.objects.filter(anno=anno), sezioni, "lotto__sezione")
    conteggi = carte.aggregate(
        totale=Count("id"),
        **{s: Count("id", filter=Q(stato=s)) for s in CartaTessera.Stato.values},
    )
    # costo dovuto alla sede centrale: tessere usate o fuori uso (le restituite no)
    costo = sum(
        (
            lotto.costo_unitario * lotto.carte.exclude(stato=CartaTessera.Stato.RESTITUITA).count()
            for lotto in _per_sezioni(LottoTessere.objects.filter(anno=anno), sezioni)
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
        importo=quota_per(socio.tipologia, anno) if importo is None else importo,
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
        if (
            CartaTessera.objects.disponibili()
            .filter(anno=anno, lotto__sezione_id=socio.sezione_id)
            .exists()
        ):
            tessera = attribuisci_carta(tessera, utente)
    elif carta:
        tessera = attribuisci_carta(tessera, utente, carta)
    return tessera


def segna_incasso_esterno(tessera, utente, *, pagata_il, nota=""):
    """Quota già incassata altrove (es. dal registro nazionale): niente ricevuta né prima nota."""
    if tessera.annullata or tessera.pagata or tessera.importo <= 0:
        return tessera
    tessera.pagata_il = pagata_il
    tessera.metodo_pagamento = Tessera.Metodo.ALTRO
    tessera.riferimento_pagamento = nota[:100]
    tessera.incasso_esterno = True
    tessera.modificato_da = utente
    tessera.save()
    registra(Azione.MODIFICA, tessera, utente=utente, incasso_esterno=str(pagata_il), nota=nota)
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


def incasso_massivo(tessere, utente, *, pagata_il, metodo, riferimento=""):
    """Incassa più quote con gli stessi dati: ognuna con la sua ricevuta e la prima nota.

    Una quota che non si può incassare (già pagata, annullata...) non blocca le altre.
    Restituisce (tessere incassate, [(tessera, errore)]).
    """
    fatte, errori = [], []
    for t in sorted(tessere, key=lambda t: (t.socio.numero, t.pk)):
        try:
            with transaction.atomic():
                fatte.append(registra_pagamento(
                    t, utente, pagata_il=pagata_il, metodo=metodo, riferimento=riferimento
                ))  # fmt: skip
        except ValidationError as e:
            errori.append((t, " ".join(e.messages)))
    if fatte:
        registra(
            Azione.MODIFICA,
            utente=utente,
            descrizione="Incasso massivo delle quote",
            quote=len(fatte),
            totale=str(sum(t.importo for t in fatte)),
            ricevute=f"{fatte[0].codice_ricevuta} - {fatte[-1].codice_ricevuta}",
        )
    return fatte, errori


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


def soci_da_rinnovare(anno, sezioni=None):
    """Soci attivi che non hanno ancora una tessera valida per l'anno."""
    con_tessera = Tessera.objects.valide().filter(anno=anno).values("socio_id")
    qs = Socio.objects.attivi().exclude(pk__in=con_tessera)
    return _per_sezioni(qs, sezioni).select_related("soggetto", "tipologia", "sezione")


def rinnovo_massivo(anno, utente, *, attribuisci=False, sezioni=None):
    """Crea il tesseramento dell'anno (da pagare) per tutti i soci attivi che non l'hanno;
    con `attribuisci` assegna anche le tessere fisiche disponibili, in ordine di numero socio.

    Una transazione per socio: un errore su un socio non blocca gli altri.
    """
    rilasciate, errori = [], []
    for socio in soci_da_rinnovare(anno, sezioni).order_by("numero"):
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
    domanda, utente, *, tipologia, data_ammissione, delibera="", tessera_anno=None, note_esito="",
    sezione=None,
):  # fmt: skip
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
            telefono=domanda.telefono if domanda.cellulare else "",
            cellulare=domanda.cellulare or domanda.telefono,
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
        soggetto, tipologia, utente, data_ammissione=data_ammissione, delibera=delibera,
        sezione=sezione or domanda.sezione,
    )  # fmt: skip
    if domanda.dichiarazione is not None:
        socio.dichiarazione = domanda.dichiarazione
        socio.save(update_fields=["dichiarazione"])
    modalita = f"modulo di adesione del {domanda.ricevuta_il:%d/%m/%Y}"
    for finalita, prestato in (
        (Consenso.Finalita.TRATTAMENTO, domanda.consenso_trattamento),
        (Consenso.Finalita.PARTICOLARI, domanda.consenso_particolari),
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


# --- richiesta di adesione firmata (Allegato A) ---------------------------------------------

MODULO_MAX_MB = 20


def modulo_in_pdf(files):
    """Un PDF così com'è, oppure una o più foto/scansioni (JPEG, PNG) unite in un PDF."""
    from apps.core.immagini import ImmagineNonValida, ripulisci

    files = [f for f in files if f]
    if not files:
        raise OperazioneNonValida("Scegliere il file del modulo firmato.")
    if sum(f.size for f in files) > MODULO_MAX_MB * 1024 * 1024:
        raise OperazioneNonValida(f"I file superano {MODULO_MAX_MB} MB.")
    inizio = files[0].read(5)
    files[0].seek(0)
    if inizio == b"%PDF-":
        if len(files) > 1:
            raise OperazioneNonValida("Caricare un solo PDF, oppure solo immagini.")
        return files[0].read()
    from PIL import Image

    pagine = []
    for f in files:
        try:
            pagina = Image.open(ripulisci(f, lato=2400)).convert("RGB")
        except ImmagineNonValida:
            raise OperazioneNonValida(
                f"«{f.name}» non è un PDF né un'immagine leggibile."
            ) from None
        pagine.append(pagina)
    uscita = io.BytesIO()
    pagine[0].save(uscita, "PDF", save_all=True, append_images=pagine[1:], resolution=200)
    return uscita.getvalue()


@transaction.atomic
def carica_modulo(socio, files, utente):
    import hashlib

    from django.core.files.base import ContentFile
    from django.utils import timezone

    pdf = modulo_in_pdf(files)
    socio = Socio.objects.select_for_update().get(pk=socio.pk)
    sostituito = bool(socio.modulo_adesione)
    if sostituito:
        socio.modulo_adesione.delete(save=False)
    socio.modulo_adesione.save("modulo.pdf", ContentFile(pdf), save=False)
    socio.modulo_adesione_il = timezone.now()
    socio.modificato_da = utente
    socio.save(update_fields=["modulo_adesione", "modulo_adesione_il", "modificato_da",
                              "modificato_il"])  # fmt: skip
    registra(Azione.MODIFICA, socio, utente=utente, modulo_adesione="sostituito" if sostituito
             else "caricato", impronta=hashlib.sha256(pdf).hexdigest())  # fmt: skip
    return socio


# --- esportazioni ------------------------------------------------------------------------

INTESTAZIONE_LIBRO = [
    "numero", "sezione", "matricola", "cognome", "nome", "codice_fiscale", "data_nascita",
    "luogo_nascita", "indirizzo", "cap", "comune", "provincia", "email", "telefono",
    "tipologia", "data_ammissione", "delibera_ammissione", "stato", "data_cessazione",
    "causa_cessazione",
]  # fmt: skip


def esporta_libro_csv(queryset, destinazione, utente):
    writer = csv.writer(destinazione, delimiter=";")
    writer.writerow(INTESTAZIONE_LIBRO)
    n = 0
    for s in queryset.select_related("soggetto", "tipologia", "sezione"):
        p = s.soggetto
        riga = [
            s.numero, s.sezione.nome, s.matricola, p.cognome, p.nome, p.codice_fiscale,
            p.data_nascita, p.luogo_nascita, p.indirizzo, p.cap, p.comune, p.provincia,
            p.email, p.cellulare or p.telefono, s.tipologia.nome, s.data_ammissione,
            s.delibera_ammissione, s.get_stato_display(), s.data_cessazione,
            s.get_causa_cessazione_display(),
        ]  # fmt: skip
        writer.writerow([cella_sicura(v) for v in riga])
        n += 1
    registra(Azione.ESPORTAZIONE, utente=utente, descrizione=f"Libro soci CSV ({n} righe)", righe=n)
    return n


INTESTAZIONE_TESSERATI = [
    "tessera", "sezione", "codice_sezione", "numero_socio", "matricola", "cognome", "nome",
    "codice_fiscale", "data_nascita", "luogo_nascita", "indirizzo", "cap", "comune",
    "provincia", "tipologia", "data_rilascio", "quota", "pagata_il",
]  # fmt: skip


def esporta_tesserati_csv(anno, destinazione, utente, sezioni=None):
    """Elenco dei tesserati dell'anno con il numero di tessera (per la sede centrale)."""
    writer = csv.writer(destinazione, delimiter=";")
    writer.writerow(INTESTAZIONE_TESSERATI)
    n = 0
    tessere = (
        _per_sezioni(Tessera.objects.valide(), sezioni, "socio__sezione")
        .filter(anno=anno, carta__isnull=False)
        .select_related("carta", "socio__soggetto", "socio__tipologia", "socio__sezione")
        .order_by("socio__sezione__ordine", "carta__lotto__serie", "carta__numero")
    )
    for t in tessere:
        p = t.socio.soggetto
        riga = [
            t.carta.codice, t.socio.sezione.nome, t.socio.sezione.codice, t.socio.numero,
            t.socio.matricola, p.cognome, p.nome, p.codice_fiscale, p.data_nascita,
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


# --- esportazione di scambio fra installazioni ---------------------------------------------------

INTESTAZIONE_SCAMBIO = [
    "Sezione", "Codice Sezione", "Matricola", "Cognome", "Nome", "Sesso", "Codice Fiscale",
    "Data di nascita", "Luogo di nascita", "Indirizzo", "CAP", "Comune", "Provincia", "Email",
    "Telefono", "Cellulare", "Tipologia", "Data di ammissione", "Data di cessazione",
    "Causa di cessazione",
    "Numero Tessera Anno {precedente}", "Numero Tessera", "Anno Sociale", "Data Tessera",
    "Valido", "Data pagamento",
]  # fmt: skip


def esporta_scambio(queryset, anno, utente):
    """Elenco soci (es. di una sezione) in Excel, con le intestazioni riconosciute
    dall'importazione: si reimporta così com'è in un'altra installazione per allinearla
    (anagrafica, tessere dell'anno e del precedente, pagamenti, cessazioni)."""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = f"Soci {anno}"
    ws.append([c.format(precedente=anno - 1) for c in INTESTAZIONE_SCAMBIO])
    soci = queryset.select_related("soggetto", "tipologia", "sezione").order_by("numero")
    tessere = {}
    for t in (
        Tessera.objects.valide()
        .filter(socio__in=soci, anno__in=(anno, anno - 1))
        .select_related("carta")
    ):
        tessere[(t.socio_id, t.anno)] = t
    n = 0
    for s in soci:
        p, t, prec = s.soggetto, tessere.get((s.pk, anno)), tessere.get((s.pk, anno - 1))
        # SI = quota versata o esente, NO = da versare, vuoto = nessuna tessera dell'anno
        valido = "" if t is None else ("SI" if (t.pagata or t.importo == 0) else "NO")
        riga = [
            s.sezione.nome if s.sezione_id else "", s.sezione.codice if s.sezione_id else "",
            s.matricola, p.cognome, p.nome, p.sesso, p.codice_fiscale or "", p.data_nascita,
            p.luogo_nascita, p.indirizzo, p.cap, p.comune, p.provincia, p.email, p.telefono,
            p.cellulare, s.tipologia.nome, s.data_ammissione, s.data_cessazione,
            s.get_causa_cessazione_display() if s.causa_cessazione else "",
            prec.carta.codice if prec and prec.carta_id else "",
            t.carta.codice if t and t.carta_id else "", anno if t else "",
            t.data_rilascio if t else None, valido, t.pagata_il if t else None,
        ]  # fmt: skip
        ws.append(riga)
        for cella in ws[ws.max_row]:  # i valori restano esatti; nessuno diventa formula
            if isinstance(cella.value, str) and cella.value.startswith("="):
                cella.data_type = "s"
        n += 1
    for colonna in ws.columns:
        ws.column_dimensions[colonna[0].column_letter].width = 16
    buffer = io.BytesIO()
    wb.save(buffer)
    registra(Azione.ESPORTAZIONE, utente=utente, descrizione=f"Soci per scambio ({n} righe)",
             righe=n, anno=anno)  # fmt: skip
    return buffer.getvalue()
