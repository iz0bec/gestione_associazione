# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Dati condivisi con federazione e sezioni collegate (ADR-030, F4): cariche
# *              (organigramma), numeri del tesseramento ed eventi condivisi letti dalla
# *              controparte, iscrizione dei propri soci agli eventi condivisi. Rieseguibile.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import logging
import uuid
from datetime import date

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.api.models import ClienteApi, DatiControparte
from apps.core.audit import Azione, registra

from . import client
from .trasporto import ErroreTrasporto

log = logging.getLogger(__name__)
MAX_PAGINE = 20


class OperazioneNonValida(Exception):
    pass


def _errore(risposta):
    if risposta.stato == 403:
        return "la controparte non ci ha concesso l'ambito necessario"
    return client._problema(risposta)


def _leggi(cliente, percorso):
    """GET firmato; restituisce i dati o solleva OperazioneNonValida con un messaggio chiaro."""
    try:
        risposta, _, _ = client.chiama(cliente, "GET", percorso)
    except (client.ErroreCollegamento, ErroreTrasporto) as e:
        raise OperazioneNonValida(f"controparte non raggiungibile: {e}") from e
    if risposta.stato != 200:
        raise OperazioneNonValida(_errore(risposta))
    return client.json_risposta(risposta)


def controparti():
    return ClienteApi.objects.filter(
        stato=ClienteApi.Stato.ATTIVA,
        tipo=ClienteApi.Tipo.INSTALLAZIONE,
    )  # fmt: skip  federazione, sezioni e installazioni pari (sezione ↔ sezione, F5)


# --- cariche e numeri ----------------------------------------------------------------------------


def _salva(cliente, tipo, dati=None, errore=""):
    voce, _ = DatiControparte.objects.get_or_create(cliente=cliente, tipo=tipo)
    voce.tentato_il = timezone.now()
    voce.errore = errore[:1000]
    if not errore:
        voce.dati, voce.letto_il = dati, voce.tentato_il
    voce.save()
    return voce


def aggiorna_dati(cliente):
    """Organigramma e numeri del tesseramento dell'anno in corso. L'errore resta sulla voce
    (e i dati letti prima restano validi)."""
    numeri = cliente.ruolo != ClienteApi.Ruolo.PARI  # fra sezioni pari mai i numeri dei soci
    for tipo, percorso in ((DatiControparte.Tipo.ORGANIGRAMMA, "/organigramma"),
                           (DatiControparte.Tipo.TESSERAMENTO,
                            f"/tesseramento?anno={date.today().year}")):  # fmt: skip
        if tipo == DatiControparte.Tipo.TESSERAMENTO and not numeri:
            continue
        try:
            dati = _leggi(cliente, percorso)
        except OperazioneNonValida as e:
            _salva(cliente, tipo, errore=str(e))
            continue
        _salva(cliente, tipo, dati)


def dati_di(cliente):
    return {v.tipo: v for v in cliente.dati_letti.all()}


# --- eventi condivisi ----------------------------------------------------------------------------


def _data(testo):
    return parse_datetime(testo) if testo else None


def aggiorna_eventi(cliente):
    """Copia locale degli eventi che la controparte ha segnato «condiviso», da oggi in poi
    (gli altri eventi, pur visibili via API, non si mostrano). Quelli non più
    condivisi (o cancellati) spariscono dalla copia, salvo che vi abbiamo iscritto qualcuno."""
    from apps.eventi.models import EventoCondiviso

    oggi = date.today().isoformat()
    percorso, letti = f"/eventi?dal={oggi}", {}
    for _ in range(MAX_PAGINE):
        pagina = _leggi(cliente, percorso)
        for e in pagina.get("risultati") or []:
            if e.get("condiviso"):
                letti[e["uuid"]] = e
        if not pagina.get("successivo"):
            break
        percorso = f"/eventi?dal={oggi}&cursore={pagina['successivo']}"
    adesso = timezone.now()
    with transaction.atomic():
        for u, e in letti.items():
            if not e.get("condiviso") or not _data(e.get("inizio")):
                continue
            EventoCondiviso.objects.update_or_create(
                cliente=cliente, uuid=u,
                defaults={"versione": e.get("versione") or 1, "titolo": e["titolo"][:200],
                          "inizio": _data(e["inizio"]), "fine": _data(e.get("fine")),
                          "luogo": (e.get("luogo") or "")[:200],
                          "annullato": bool(e.get("annullato")), "dati": e, "letto_il": adesso},
            )  # fmt: skip
        spariti = EventoCondiviso.objects.filter(cliente=cliente, inizio__date__gte=oggi).exclude(
            uuid__in=list(letti)
        )
        spariti.filter(adesioni_inviate__isnull=True).delete()
        spariti.update(annullato=True, letto_il=adesso)  # con iscritti: resta, come annullato
    return len(letti)


def aggiorna(cliente):
    """Un giro di lettura: cariche, numeri ed eventi. Restituisce un riepilogo testuale."""
    aggiorna_dati(cliente)
    try:
        n = aggiorna_eventi(cliente)
        return f"{n} eventi condivisi"
    except OperazioneNonValida as e:
        return f"eventi: {e}"


def aggiorna_tutti():
    from . import trasferimenti

    esiti = {c.nome: aggiorna(c) for c in controparti() if c.abbinata}
    if inviati := trasferimenti.invia_esiti_sospesi():
        esiti["trasferimenti"] = f"{inviati} esiti inviati"
    return esiti


# --- iscrizione dei propri soci a un evento condiviso --------------------------------------------


def iscrivi(evento, soggetto, utente, *, accompagnatori=0, note=""):
    """Iscrive un nostro socio (o una persona dell'anagrafica) all'evento della controparte."""
    from apps.eventi.models import AdesioneInviata

    if evento.annullato:
        raise OperazioneNonValida("L'evento è annullato.")
    if evento.adesioni_valide().filter(soggetto=soggetto).exists():
        raise OperazioneNonValida(f"{soggetto.nome_completo} è già iscritto.")
    corpo = {"cognome": soggetto.cognome or soggetto.nome_completo, "nome": soggetto.nome or "",
             "accompagnatori": accompagnatori, "note": note[:255],
             "riferimento_esterno": f"soggetto:{soggetto.pk}"}  # fmt: skip
    try:
        risposta, _, _ = client.chiama(
            evento.cliente, "POST", f"/eventi/{evento.uuid}/adesioni", corpo, cifra=True,
            extra={"Idempotency-Key": uuid.uuid4().hex},
        )  # fmt: skip
    except (client.ErroreCollegamento, ErroreTrasporto) as e:
        raise OperazioneNonValida(f"Controparte non raggiungibile: {e}") from e
    if risposta.stato != 201:
        raise OperazioneNonValida(f"Iscrizione rifiutata: {_errore(risposta)}")
    dati = client.json_risposta(risposta)
    adesione = AdesioneInviata.objects.create(
        evento=evento, soggetto=soggetto, cognome=corpo["cognome"], nome=corpo["nome"],
        accompagnatori=accompagnatori, note=corpo["note"], uuid_remoto=dati.get("uuid"),
        versione_remota=dati.get("versione") or 1, inviata_da=utente,
    )  # fmt: skip
    descrizione = f"Iscrizione all'evento «{evento.titolo}» di {evento.cliente}"
    registra(Azione.CREAZIONE, adesione, utente=utente, descrizione=descrizione)
    return adesione


def annulla(adesione, utente):
    if adesione.annullata:
        return adesione
    if adesione.uuid_remoto:
        try:
            risposta, _, _ = client.chiama(
                adesione.evento.cliente, "DELETE", f"/adesioni/{adesione.uuid_remoto}",
                extra={"If-Match": f'"{adesione.versione_remota}"'},
            )  # fmt: skip
        except (client.ErroreCollegamento, ErroreTrasporto) as e:
            raise OperazioneNonValida(f"Controparte non raggiungibile: {e}") from e
        if risposta.stato not in (204, 404):
            raise OperazioneNonValida(f"Annullamento rifiutato: {_errore(risposta)}")
    adesione.annullata = True
    adesione.save(update_fields=["annullata"])
    registra(Azione.MODIFICA, adesione, utente=utente,
             descrizione=f"Iscrizione all'evento «{adesione.evento.titolo}» annullata")  # fmt: skip
    return adesione
