# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Trasferimento di un socio fra installazioni collegate (ADR-030, F5): richiesta
# *              con il consenso del socio, accoglimento o rifiuto all'arrivo, esito che torna
# *              alla partenza (dove il socio cessa per «trasferimento ad altra sezione").
# *              Mai elenchi dei soci altrui: viaggia solo la scheda del socio che si trasferisce.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import logging
import uuid as uuid_mod
from datetime import date

from django.db import transaction
from django.utils import timezone

from apps.api.models import ClienteApi
from apps.core.audit import Azione, registra
from apps.soci import allineamento
from apps.soci import importazione as imp
from apps.soci import servizi as soci_servizi
from apps.soci.models import Socio, Tessera, TrasferimentoEsterno

from . import client
from .trasporto import ErroreTrasporto

log = logging.getLogger(__name__)
Stato = TrasferimentoEsterno.Stato
Direzione = TrasferimentoEsterno.Direzione


class OperazioneNonValida(Exception):
    pass


def destinazioni():
    """Installazioni collegate a cui si può chiedere un trasferimento."""
    return ClienteApi.objects.filter(
        stato=ClienteApi.Stato.ATTIVA, tipo=ClienteApi.Tipo.INSTALLAZIONE
    ).order_by("nome")


def _posta(cliente, percorso, corpo, chiave):
    try:
        risposta, _, _ = client.chiama(cliente, "POST", percorso, corpo, cifra=True,
                                       extra={"Idempotency-Key": chiave})  # fmt: skip
    except (client.ErroreCollegamento, ErroreTrasporto) as e:
        raise OperazioneNonValida(f"Installazione non raggiungibile: {e}") from e
    if risposta.stato == 403:
        raise OperazioneNonValida(
            "L'installazione non ci ha concesso l'ambito «Trasferimento di soci»."
        )
    if risposta.stato not in (200, 201):
        raise OperazioneNonValida(f"Richiesta rifiutata: {client._problema(risposta)}")
    return risposta


# --- partenza ------------------------------------------------------------------------------------


def invia(socio, cliente, utente, *, consenso_il, consenso_modo, motivo=""):
    """Chiede all'installazione collegata di accogliere il socio, con la sua scheda."""
    if socio.stato == Socio.Stato.CESSATO:
        raise OperazioneNonValida("Un socio cessato non si trasferisce.")
    if not consenso_il or not (consenso_modo or "").strip():
        raise OperazioneNonValida("Serve il consenso del socio al trasferimento (data e modo).")
    if consenso_il > date.today():
        raise OperazioneNonValida("La data del consenso non può essere futura.")
    if cliente.stato != ClienteApi.Stato.ATTIVA or cliente.tipo != ClienteApi.Tipo.INSTALLAZIONE:
        raise OperazioneNonValida("Scegliere un'installazione collegata attiva.")
    aperto = TrasferimentoEsterno.objects.filter(socio=socio, direzione=Direzione.USCITA,
                                                 stato=Stato.IN_ATTESA)  # fmt: skip
    if aperto.exists():
        raise OperazioneNonValida("C'è già una richiesta di trasferimento in attesa per il socio.")
    tessere = list(Tessera.objects.valide().filter(socio=socio, anno__gte=date.today().year - 1)
                   .select_related("carta").order_by("anno"))  # fmt: skip
    t = TrasferimentoEsterno(
        direzione=Direzione.USCITA, cliente=cliente, socio=socio,
        nome=socio.soggetto.nome_completo, sezione_origine=socio.sezione.nome,
        codice_origine=socio.sezione.codice, consenso_il=consenso_il,
        consenso_modo=consenso_modo.strip()[:150], motivo=(motivo or "").strip()[:255],
        creato_da=utente,
    )  # fmt: skip
    corpo = {"uuid": str(t.uuid), "socio": allineamento.riga(socio, tessere),
             "sezione": {"codice": socio.sezione.codice, "nome": socio.sezione.nome},
             "consenso_il": consenso_il.isoformat(), "consenso_modo": t.consenso_modo,
             "motivo": t.motivo, "data": t.data.isoformat()}  # fmt: skip
    _posta(cliente, "/trasferimenti", corpo, t.uuid.hex)
    t.save()
    registra(Azione.CREAZIONE, t, utente=utente, consenso_il=str(consenso_il),
             descrizione=f"Richiesta di trasferimento di {t.nome} verso {cliente}")  # fmt: skip
    return t


def ricevi_esito(cliente, uuid, dati):
    """L'installazione di arrivo ci comunica l'esito: se accolto il socio cessa qui."""
    t = TrasferimentoEsterno.objects.filter(uuid=uuid, cliente=cliente,
                                            direzione=Direzione.USCITA).first()  # fmt: skip
    if t is None:
        raise OperazioneNonValida("Richiesta di trasferimento sconosciuta.")
    esito = (dati or {}).get("esito")
    if esito not in (Stato.ACCOLTO, Stato.RESPINTO):
        raise OperazioneNonValida("Esito non valido: «accolto» o «respinto».")
    if t.stato != Stato.IN_ATTESA:
        return t  # ripetizione: nessun effetto
    with transaction.atomic():
        t.stato, t.esito_il = esito, timezone.now()
        t.esito_motivo = str(dati.get("motivo") or "")[:255]
        t.save(update_fields=["stato", "esito_il", "esito_motivo"])
        if esito == Stato.ACCOLTO and t.socio and t.socio.stato != Socio.Stato.CESSATO:
            giorno = max(date.today(), t.socio.data_ammissione)
            soci_servizi.cessa_socio(
                t.socio, None, data_cessazione=giorno, causa=Socio.Cessazione.TRASFERIMENTO,
                note=f"Trasferito a {cliente} (richiesta del {t.data:%d/%m/%Y}).",
            )  # fmt: skip
        registra(Azione.MODIFICA, t, utente=None, esito=esito,
                 descrizione=f"Trasferimento di {t.nome} verso {cliente}: {esito}")  # fmt: skip
    return t


# --- arrivo --------------------------------------------------------------------------------------


def ricevi(cliente, dati):
    """Una richiesta di trasferimento arriva da un'installazione collegata: resta in attesa."""
    from apps.core import avvisi

    if cliente.tipo != ClienteApi.Tipo.INSTALLAZIONE:
        raise OperazioneNonValida("Solo un'installazione collegata può trasferire soci.")
    socio = (dati or {}).get("socio")
    if not isinstance(socio, dict) or not socio.get("cognome"):
        raise OperazioneNonValida("Scheda del socio mancante.")
    try:
        consenso_il = date.fromisoformat(str(dati.get("consenso_il")))
    except ValueError as e:
        raise OperazioneNonValida("Data del consenso del socio mancante o non valida.") from e
    if not str(dati.get("consenso_modo") or "").strip():
        raise OperazioneNonValida("Modo del consenso del socio mancante.")
    try:
        codice = uuid_mod.UUID(str(dati.get("uuid")))
    except ValueError as e:
        raise OperazioneNonValida("Identificativo della richiesta non valido.") from e
    esistente = TrasferimentoEsterno.objects.filter(uuid=codice).first()
    if esistente:
        return esistente
    sezione = dati.get("sezione") or {}
    t = TrasferimentoEsterno.objects.create(
        uuid=codice, direzione=Direzione.ENTRATA, cliente=cliente,
        nome=f"{socio.get('cognome', '')} {socio.get('nome', '')}".strip()[:200],
        sezione_origine=str(sezione.get("nome") or "")[:150],
        codice_origine=str(sezione.get("codice") or "")[:20], consenso_il=consenso_il,
        consenso_modo=str(dati["consenso_modo"])[:150], motivo=str(dati.get("motivo") or "")[:255],
        dati=socio,
    )  # fmt: skip
    registra(Azione.CREAZIONE, t, utente=None,
             descrizione=f"Richiesta di trasferimento di {t.nome} da {cliente}")  # fmt: skip
    avvisi.avvisa("domande", f"Richiesta di trasferimento da {cliente}: {t.nome}, da accogliere "
                             "o respingere in Soci → Trasferimenti.")  # fmt: skip
    return t


def accogli(t, utente, *, sezione=None):
    """Accoglie il socio: si crea con la sua storia di iscrizione e le tessere recenti."""
    from apps.soci.models import Sezione

    if t.direzione != Direzione.ENTRATA or t.stato != Stato.IN_ATTESA:
        raise OperazioneNonValida("Questa richiesta non è in attesa.")
    sezione = sezione or Sezione.predefinita()
    d = allineamento._pulita(t.dati)
    d["stato_socio"], d["data_cessazione"], d["causa_cessazione"] = "attivo", "", ""
    with transaction.atomic():
        try:
            soggetto = allineamento.trova(d, sezione, t.dati.get("tessere") or [])
        except allineamento.Omonimi as e:
            raise OperazioneNonValida(str(e)) from e
        if soggetto is not None and getattr(soggetto, "socio", None) is not None:
            raise OperazioneNonValida(f"{soggetto.nome_completo} è già nel libro soci qui.")
        opzioni = allineamento._opzioni(sezione, str(t.cliente))
        try:
            _, note, socio = imp._riga(d, sezione, opzioni, utente, soggetto=soggetto)
            allineamento._applica_tessere(socio, t.dati.get("tessere") or [], opzioni, utente)
        except imp._Errore as e:
            raise OperazioneNonValida(str(e)) from e
        socio.note = f"{socio.note}\nTrasferito da {t.sezione_origine or t.cliente} il " \
                     f"{date.today():%d/%m/%Y}.".strip()  # fmt: skip
        socio.save(update_fields=["note"])
        t.socio, t.stato, t.esito_il = socio, Stato.ACCOLTO, timezone.now()
        t.deciso_da, t.dati = utente, {}
        t.save()
        registra(Azione.MODIFICA, t, utente=utente, esito="accolto",
                 descrizione=f"Trasferimento di {t.nome} da {t.cliente} accolto")  # fmt: skip
    invia_esito(t)
    return t


def respingi(t, utente, motivo):
    if t.direzione != Direzione.ENTRATA or t.stato != Stato.IN_ATTESA:
        raise OperazioneNonValida("Questa richiesta non è in attesa.")
    if not (motivo or "").strip():
        raise OperazioneNonValida("Indicare il motivo del rifiuto.")
    t.stato, t.esito_il, t.deciso_da = Stato.RESPINTO, timezone.now(), utente
    t.esito_motivo, t.dati = motivo.strip()[:255], {}
    t.save()
    registra(Azione.MODIFICA, t, utente=utente, esito="respinto",
             descrizione=f"Trasferimento di {t.nome} da {t.cliente} respinto")  # fmt: skip
    invia_esito(t)
    return t


def invia_esito(t):
    """Comunica l'esito alla partenza; se non riesce si riprova con il lavoro periodico."""
    corpo = {"esito": t.stato, "motivo": t.esito_motivo,
             "data": (t.esito_il or timezone.now()).date().isoformat()}  # fmt: skip
    try:
        _posta(t.cliente, f"/trasferimenti/{t.uuid}/esito", corpo, f"esito-{t.uuid.hex}")
    except OperazioneNonValida as e:
        log.warning("Esito del trasferimento %s non inviato: %s", t.uuid, e)
        return False
    t.esito_inviato = True
    t.save(update_fields=["esito_inviato"])
    return True


def invia_esiti_sospesi():
    sospesi = TrasferimentoEsterno.objects.filter(
        direzione=Direzione.ENTRATA, esito_inviato=False
    ).exclude(stato=Stato.IN_ATTESA)
    return sum(1 for t in sospesi if invia_esito(t))


def codici_origine(soci):
    """{socio.pk: codice della sezione di provenienza} per i soci arrivati per trasferimento."""
    return dict(
        TrasferimentoEsterno.objects.filter(socio__in=soci, direzione=Direzione.ENTRATA,
                                            stato=Stato.ACCOLTO)
        .exclude(codice_origine="").values_list("socio_id", "codice_origine")
    )  # fmt: skip
