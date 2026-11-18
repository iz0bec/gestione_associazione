# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Client verso le altre installazioni: usa solo l'API pubblica (ADR-030 §1).
# *              Richieste firmate, risposte verificate (legate alla richiesta), indirizzo
# *              interno prima di quello pubblico, abbinamento con l'invito ricevuto e /prova.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import json
import logging
import re
import secrets
import time
import uuid
from datetime import timedelta
from urllib.parse import urlsplit

from apps.api import chiavi, endpoint, servizi
from apps.api import firma as f
from apps.api.models import ClienteApi
from apps.core.models import Organizzazione

from .trasporto import Destinazione, ErroreTrasporto, richiesta

log = logging.getLogger(__name__)
PREFISSO_API = "/api/v1"
WELL_KNOWN = "/.well-known/gestione-associazione"


class ErroreCollegamento(Exception):
    pass


def destinazioni(cliente: ClienteApi):
    """Indirizzi da provare, nell'ordine dell'ADR-030 §6: interno, poi pubblico."""
    elenco = []
    if cliente.indirizzo_interno:
        elenco.append(
            Destinazione(
                url=cliente.indirizzo_interno.rstrip("/"),
                verifica=cliente.verifica_tls,
                ca_pem=cliente.ca_pem,
                spki=list(cliente.tls_spki or []),
                privati_ammessi=cliente.rete_interna,
                http_ammesso=cliente.http_in_chiaro,
            )
        )
    if cliente.indirizzo_pubblico:
        elenco.append(Destinazione(url=cliente.indirizzo_pubblico.rstrip("/")))
    return elenco


def _verifica_risposta(risposta, jwks, msg_richiesta=None):
    """Firma della risposta con le chiavi della controparte; se c'era una richiesta firmata,
    la risposta deve esserle legata."""
    if not f.verifica_digest(risposta.intestazioni.get("content-digest", ""), risposta.corpo):
        raise ErroreCollegamento("Risposta con Content-Digest assente o errato.")
    chiavi_firma = {k["kid"]: k for k in jwks.get("keys", []) if k.get("use") == "sig"}
    msg = f.Messaggio(intestazioni=risposta.intestazioni, stato=risposta.stato,
                      richiesta=msg_richiesta)  # fmt: skip
    # "ga" è la chiave in uso; durante una rotazione "ga1", "ga2"… sono quelle in uscita
    try:
        etichette = [e for e in f.leggi_dizionario(msg.intestazione("signature-input") or "")
                     if re.fullmatch(rf"{f.ETICHETTA}\d*", e)] or [f.ETICHETTA]  # fmt: skip
    except ValueError:
        etichette = [f.ETICHETTA]
    errore = None
    for etichetta in etichette:
        try:
            return f.verifica(
                msg,
                lambda kid: (
                    f.chiave_pubblica(chiavi_firma[kid]["x"]) if kid in chiavi_firma else None
                ),
                richiesti=f.richiesti(f.componenti_risposta(msg_richiesta is not None)),
                adesso=time.time(),
                etichetta=etichetta,
            )
        except f.ErroreFirma as e:
            errore = e
    raise ErroreCollegamento(f"Firma della risposta non valida: {errore.messaggio}")


def _json(risposta):
    try:
        return json.loads(risposta.corpo or b"null")
    except ValueError as e:
        raise ErroreCollegamento(f"Risposta non JSON (HTTP {risposta.stato}).") from e


def _richiesta_firmata(dest, metodo, percorso, destinatario, corpo=None, extra=None,
                       tipo="application/json"):  # fmt: skip
    """Esegue una richiesta firmata; restituisce (risposta, messaggio della richiesta)."""
    dati = b"" if corpo is None else json.dumps(corpo, ensure_ascii=False).encode()
    solo_percorso, _, query = percorso.partition("?")
    percorso_completo = urlsplit(dest.url).path.rstrip("/") + solo_percorso
    intestazioni = {"Destinatario-Istanza": str(destinatario), **(extra or {})}
    if dati:
        intestazioni["Content-Type"] = tipo
        intestazioni["Content-Digest"] = f.content_digest(dati)
    msg = f.Messaggio(
        intestazioni={k.lower(): v for k, v in intestazioni.items()},
        metodo=metodo,
        percorso=percorso_completo,
        query=query,
    )
    kid, privata = chiavi.chiave_firma()
    ingresso, valore = f.firma(
        msg,
        f.componenti_richiesta(bool(dati)),
        f.parametri_firma(kid, time.time(), secrets.token_urlsafe(18)),
        privata,
    )
    intestazioni["Signature-Input"] = ingresso
    intestazioni["Signature"] = valore
    msg.intestazioni.update({"signature-input": ingresso, "signature": valore})
    return richiesta(dest, metodo, percorso, intestazioni, dati), msg


def _problema(risposta):
    try:
        dati = json.loads(risposta.corpo)
        return dati.get("detail") or dati.get("title") or f"HTTP {risposta.stato}"
    except ValueError:
        return f"HTTP {risposta.stato}"


def scopri(dest: Destinazione):
    """Descrizione e JWKS dell'istanza remota; la descrizione deve essere firmata con una chiave
    della JWKS (la fiducia nasce dal confronto dell'impronta)."""
    descrizione_r = richiesta(dest, "GET", WELL_KNOWN)
    if descrizione_r.stato != 200:
        raise ErroreCollegamento(f"{dest.url} non risponde come Gestione Associazione "
                                 f"(HTTP {descrizione_r.stato}).")  # fmt: skip
    descrizione = _json(descrizione_r)
    if "v1" not in (descrizione.get("versioni_api") or []):
        raise ErroreCollegamento("L'istanza remota non supporta l'API v1.")
    jwks_r = richiesta(dest, "GET", WELL_KNOWN + "/jwks.json")
    if jwks_r.stato != 200:
        raise ErroreCollegamento(f"Chiavi dell'istanza non disponibili (HTTP {jwks_r.stato}).")
    try:
        jwks = chiavi.valida_jwks(_json(jwks_r))
        uuid.UUID(str(descrizione.get("istanza")))
    except (chiavi.JwksNonValida, ValueError) as e:
        raise ErroreCollegamento(f"Identità dell'istanza remota non valida: {e}") from e
    _verifica_risposta(descrizione_r, jwks)
    _verifica_risposta(jwks_r, jwks)
    return descrizione, jwks


def abbina(utente, *, codice, nome, ambiti, indirizzo_pubblico="", indirizzo_interno="",
           rete_interna=False, verifica_tls="pubblica", ca_pem="", tls_spki=(),
           http_in_chiaro=False):  # fmt: skip
    """Usa l'invito ricevuto da un'altra installazione e la registra come controparte in prova."""
    indirizzi = {
        "indirizzo_pubblico": indirizzo_pubblico.rstrip("/"),
        "indirizzo_interno": indirizzo_interno.rstrip("/"),
        "rete_interna": rete_interna,
        "verifica_tls": verifica_tls,
        "ca_pem": ca_pem,
        "http_in_chiaro": http_in_chiaro,
    }
    provvisorio = ClienteApi(**indirizzi, tls_spki=list(tls_spki))
    ultimo_errore = None
    for dest in destinazioni(provvisorio):
        try:
            descrizione, jwks_remota = scopri(dest)
            risposta, msg = _richiesta_firmata(
                dest, "POST", PREFISSO_API + "/abbinamenti", descrizione["istanza"],
                corpo={
                    "istanza": str(chiavi.istanza().uuid),
                    "nome": Organizzazione.corrente().denominazione,
                    "tipo": "installazione",
                    "jwks": chiavi.jwks(),
                    "tls_spki": endpoint.impronte_tls(),
                },
                extra={"Invito": codice.strip()},
            )  # fmt: skip
        except (ErroreTrasporto, ErroreCollegamento) as e:
            ultimo_errore = f"{dest.descrizione}: {e}"
            log.info("Abbinamento: %s", ultimo_errore)
            continue
        if risposta.stato != 201:
            raise ErroreCollegamento(f"Abbinamento rifiutato: {_problema(risposta)}")
        _verifica_risposta(risposta, jwks_remota, msg)
        esito = _json(risposta)
        impronta = chiavi.impronta_abbinamento(chiavi.jwks(), jwks_remota)
        if esito.get("istanza") != descrizione["istanza"] or esito.get("impronta") != impronta:
            raise ErroreCollegamento(
                "L'impronta calcolata dalle due parti non coincide: abbinamento interrotto."
            )
        return servizi.registra_controparte(
            utente, nome=nome, tipo=ClienteApi.Tipo.INSTALLAZIONE,
            istanza=uuid.UUID(descrizione["istanza"]), nome_dichiarato=descrizione.get("nome", ""),
            jwks=jwks_remota, impronta=impronta, ambiti=ambiti, indirizzi=indirizzi,
            tls_spki=descrizione.get("tls_spki") or tls_spki,
        )  # fmt: skip
    raise ErroreCollegamento(ultimo_errore or "Nessun indirizzo indicato.")


def chiama(cliente: ClienteApi, metodo, percorso, corpo=None):
    """Chiamata firmata all'API della controparte; prova gli indirizzi in ordine. Restituisce
    (risposta verificata, destinazione usata, errori sugli indirizzi precedenti)."""
    if not cliente.abbinata:
        raise ErroreCollegamento("Controparte non abbinata.")
    errori = []
    for dest in destinazioni(cliente):
        try:
            risposta, msg = _richiesta_firmata(dest, metodo, PREFISSO_API + percorso,
                                               cliente.istanza, corpo)  # fmt: skip
        except ErroreTrasporto as e:
            errori.append(f"{dest.descrizione}: {e}")
            continue
        try:
            _verifica_risposta(risposta, cliente.jwks, msg)
        except ErroreCollegamento:
            # forse la controparte ha ruotato le chiavi: si rileggono (firmate da una già nota)
            if not aggiorna_identita(cliente)[0]:
                raise
            _verifica_risposta(risposta, cliente.jwks, msg)
        if errori:
            log.warning("Controparte %s raggiunta su %s dopo: %s", cliente, dest.url, errori)
        return risposta, dest, errori
    raise ErroreCollegamento("; ".join(errori) or "Nessun indirizzo configurato.")


def prova(cliente: ClienteApi):
    """Esegue /prova sulla controparte e salva l'esito (testo per l'amministratore)."""
    try:
        risposta, dest, errori = chiama(cliente, "POST", "/prova", {"prova": True})
        if risposta.stato != 200:
            esito = f"Rifiutata da {dest.url}: {_problema(risposta)}"
            riuscita = False
        else:
            diagnosi = _json(risposta)
            esito = (
                f"Riuscita su {dest.url}: firma {diagnosi.get('firma')}, scarto dell'orologio "
                f"{diagnosi.get('orologio', {}).get('scarto_secondi')} s, stato presso la "
                f"controparte «{diagnosi.get('controparte', {}).get('stato')}», "
                f"IP visto {diagnosi.get('indirizzo_ip_visto')}."
            )
            riuscita = True
        if errori:
            esito += " Indirizzi non raggiunti: " + "; ".join(errori)
    except (ErroreCollegamento, ErroreTrasporto) as e:
        esito, riuscita = f"Non riuscita: {e}", False
    servizi.registra_esito_prova(cliente, esito)
    return riuscita, esito


def aggiorna_identita(cliente: ClienteApi):
    """Rilegge chiavi e impronte TLS di un'altra installazione dalla sua /.well-known. Le
    accetta solo se la risposta è firmata da una chiave già nota e l'istanza è la stessa.
    Restituisce (cambiate, messaggio)."""
    if cliente.tipo != ClienteApi.Tipo.INSTALLAZIONE or not cliente.abbinata:
        return False, "Solo per le installazioni abbinate."
    errori = []
    for dest in destinazioni(cliente):
        try:
            descrizione_r = richiesta(dest, "GET", WELL_KNOWN)
            jwks_r = richiesta(dest, "GET", WELL_KNOWN + "/jwks.json")
            _verifica_risposta(descrizione_r, cliente.jwks)
            _verifica_risposta(jwks_r, cliente.jwks)
            descrizione = _json(descrizione_r)
            nuove = chiavi.valida_jwks(_json(jwks_r))
        except (ErroreTrasporto, ErroreCollegamento, chiavi.JwksNonValida) as e:
            errori.append(f"{dest.descrizione}: {e}")
            continue
        if descrizione.get("istanza") != str(cliente.istanza):
            return False, "L'indirizzo risponde con un'altra istanza: nessun aggiornamento."
        cambiate = servizi.aggiorna_chiavi_controparte(cliente, nuove, origine="jwks")
        spki = [s for s in descrizione.get("tls_spki") or [] if isinstance(s, str)][:4]
        if spki and spki != cliente.tls_spki:
            servizi.aggiorna_impronte_tls(cliente, spki)
            cambiate = True
        return cambiate, ("Chiavi o impronte aggiornate." if cambiate else "Nessuna novità.")
    return False, "; ".join(errori) or "Nessun indirizzo configurato."


def _destinazione_notifiche(cliente: ClienteApi):
    parti = urlsplit(cliente.indirizzo_notifiche)
    origine = f"{parti.scheme}://{parti.netloc}"
    interno = urlsplit(cliente.indirizzo_interno or "")
    stessa = interno.netloc and (interno.scheme, interno.netloc) == (parti.scheme, parti.netloc)
    dest = Destinazione(
        url=origine,
        verifica=cliente.verifica_tls if stessa else "pubblica",
        ca_pem=cliente.ca_pem if stessa else "",
        spki=list(cliente.tls_spki or []) if stessa else [],
        privati_ammessi=cliente.rete_interna,
        http_ammesso=cliente.http_in_chiaro,
    )
    return dest, (parti.path or "/") + (f"?{parti.query}" if parti.query else "")


def invia_notifica(notifica):
    """Un tentativo di consegna; aggiorna stato, tentativi e prossimo tentativo."""
    from django.utils import timezone

    from apps.api import feed
    from apps.api.models import NotificaApi

    cliente = notifica.cliente
    try:
        if cliente.stato != ClienteApi.Stato.ATTIVA or not cliente.indirizzo_notifiche:
            raise ErroreCollegamento("Controparte non attiva o senza indirizzo delle notifiche.")
        dest, percorso = _destinazione_notifiche(cliente)
        risposta, _ = _richiesta_firmata(dest, "POST", percorso, cliente.istanza,
                                         feed.come_evento(notifica.cambiamento),
                                         tipo="application/cloudevents+json")  # fmt: skip
        if not 200 <= risposta.stato < 300:
            raise ErroreCollegamento(f"HTTP {risposta.stato}")
    except (ErroreTrasporto, ErroreCollegamento) as e:
        notifica.tentativi += 1
        notifica.ultimo_errore = str(e)[:1000]
        attesa = 60 * 2 ** (notifica.tentativi - 1)
        if attesa > 24 * 3600 or cliente.stato == ClienteApi.Stato.REVOCATA:
            notifica.stato = NotificaApi.Stato.FALLITA
        else:
            notifica.prossimo_tentativo = timezone.now() + timedelta(seconds=attesa)
        notifica.save(update_fields=["tentativi", "ultimo_errore", "stato", "prossimo_tentativo"])
        return False
    notifica.stato = NotificaApi.Stato.CONSEGNATA
    notifica.consegnata_il = timezone.now()
    notifica.tentativi += 1
    notifica.ultimo_errore = ""
    notifica.save(update_fields=["stato", "consegnata_il", "tentativi", "ultimo_errore"])
    return True


def invia_notifiche(limite=100):
    """Consegna le notifiche dovute (lavoro del pianificatore, rieseguibile)."""
    from django.utils import timezone

    from apps.api.models import NotificaApi

    dovute = (
        NotificaApi.objects.filter(stato=NotificaApi.Stato.IN_CODA,
                                   prossimo_tentativo__lte=timezone.now())
        .select_related("cliente", "cambiamento")
        .order_by("cambiamento__flusso", "cambiamento__progressivo")[:limite]
    )  # fmt: skip
    esiti = [invia_notifica(n) for n in dovute]
    return sum(esiti), len(esiti) - sum(esiti)
