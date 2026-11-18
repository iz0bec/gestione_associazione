# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Controlli dell'API in un unico punto: firma della richiesta, destinatario,
# *              digest, nonce, stato della controparte, IP ammessi e ambiti; firma di ogni
# *              risposta; errori come Problem Details (RFC 9457); registro delle chiamate.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import ipaddress
import json
import logging
import secrets
import time
from contextlib import suppress
from functools import wraps

from django.db import IntegrityError, transaction
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.utils.encoding import escape_uri_path
from django.views.decorators.csrf import csrf_exempt

from apps.core import rete
from apps.core.cifratura import ChiaveNonConfigurata, cifratura_disponibile

from . import chiavi
from . import firma as f
from .models import ChiamataApi, ClienteApi, NonceVisto

log = logging.getLogger(__name__)

TITOLI = {
    "firma-non-valida": "Firma non valida",
    "firma-scaduta": "Firma scaduta",
    "nonce-riusato": "Nonce già usato",
    "destinatario-errato": "Destinatario errato",
    "controparte-non-attiva": "Controparte non attiva",
    "ip-non-ammesso": "Indirizzo IP non ammesso",
    "ambito-mancante": "Ambito non concesso",
    "digest-errato": "Content-Digest errato",
    "invito-non-valido": "Invito non valido",
    "operazione-non-valida": "Operazione non valida",
    "non-configurata": "API non configurata",
}


class Problema(Exception):
    def __init__(self, codice, stato, dettaglio=""):
        super().__init__(dettaglio or codice)
        self.codice = codice
        self.stato = stato
        self.dettaglio = dettaglio


def risposta_problema(p: Problema):
    corpo = {
        "type": f"urn:gestione-associazione:problema:{p.codice}",
        "title": TITOLI.get(p.codice, p.codice),
        "status": p.stato,
        "codice": p.codice,
    }
    if p.dettaglio:
        corpo["detail"] = p.dettaglio
    return JsonResponse(corpo, status=p.stato, content_type="application/problem+json")


def messaggio_richiesta(request) -> f.Messaggio:
    return f.Messaggio(
        intestazioni={k.lower(): v for k, v in request.headers.items()},
        metodo=request.method,
        percorso=escape_uri_path(request.path),
        query=request.META.get("QUERY_STRING", ""),
        autorita=request.get_host() if request.headers.get("host") else "",
    )


def controlla_firma(request, chiave_per_keyid):
    """Verifica la firma della richiesta secondo il profilo del contratto, poi destinatario e
    digest. Non registra il nonce (vedi `registra_nonce`)."""
    corpo = request.body
    try:
        verificata = f.verifica(
            messaggio_richiesta(request),
            chiave_per_keyid,
            richiesti=f.richiesti(f.componenti_richiesta(bool(corpo))),
            adesso=time.time(),
        )
    except f.ErroreFirma as e:
        raise Problema(e.codice, 401, e.messaggio) from e
    if request.headers.get("destinatario-istanza", "").lower() != str(chiavi.istanza().uuid):
        raise Problema("destinatario-errato", 421, "La richiesta è indirizzata a un'altra istanza.")
    if corpo and not f.verifica_digest(request.headers.get("content-digest", ""), corpo):
        raise Problema(
            "digest-errato", 400, "Il Content-Digest (sha-256) non corrisponde al corpo."
        )
    request.firma_api = verificata
    return verificata


def registra_nonce(kid, nonce):
    try:
        with transaction.atomic():
            NonceVisto.objects.create(kid=kid, nonce=nonce)
    except IntegrityError as e:
        raise Problema("nonce-riusato", 401, "Richiesta già ricevuta (nonce ripetuto).") from e


def cliente_per_kid(kid):
    candidati = ClienteApi.objects.filter(jwks__keys__contains=[{"kid": kid, "use": "sig"}])
    non_revocati = [c for c in candidati if c.stato != ClienteApi.Stato.REVOCATA]
    return (non_revocati or list(candidati) or [None])[0]


def _ip_ammesso(cliente, ip):
    righe = [r.strip() for r in cliente.ip_ammessi.splitlines() if r.strip()]
    if not righe:
        return True
    try:
        indirizzo = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for riga in righe:
        try:
            if indirizzo in ipaddress.ip_network(riga, strict=False):
                return True
        except ValueError:
            continue
    return False


def autentica(request, *, ambito=None, in_prova=False) -> ClienteApi:
    """Controparte autenticata dalla firma, con tutti i controlli dell'ADR-030 §4."""
    trovato = {}

    def chiave(kid):
        cliente = cliente_per_kid(kid)
        if cliente is None:
            return None
        trovato["cliente"] = cliente
        jwk = next(k for k in cliente.chiavi("sig") if k["kid"] == kid)
        if "exp" in jwk and jwk["exp"] < time.time():
            return None
        return f.chiave_pubblica(jwk["x"])

    verificata = controlla_firma(request, chiave)
    cliente = trovato["cliente"]
    request.cliente_api = cliente
    registra_nonce(verificata.keyid, verificata.parametri["nonce"])
    from . import servizi

    servizi.sospendi_se_scaduta(cliente)
    stati = {ClienteApi.Stato.ATTIVA} | ({ClienteApi.Stato.IN_PROVA} if in_prova else set())
    if cliente.stato not in stati:
        dettaglio = (
            "Controparte in prova: va confermata l'impronta dell'abbinamento."
            if cliente.stato == ClienteApi.Stato.IN_PROVA
            else f"Controparte {cliente.get_stato_display().lower()}."
        )
        raise Problema("controparte-non-attiva", 403, dettaglio)
    if not _ip_ammesso(cliente, rete.ip_client(request)):
        raise Problema("ip-non-ammesso", 403, "Indirizzo IP non ammesso per questa controparte.")
    if ambito and ambito not in cliente.ambiti:
        raise Problema("ambito-mancante", 403, f"Ambito non concesso: {ambito}.")
    return cliente


def firma_risposta(request, risposta):
    """Content-Digest e firma (RFC 9421) su ogni risposta, legata alla firma della richiesta
    quando c'è."""
    corpo = risposta.content
    risposta["Content-Digest"] = f.content_digest(corpo)
    legata = False
    try:
        f.leggi_firma(messaggio_richiesta(request))
        legata = True
    except f.ErroreFirma:
        pass
    msg = f.Messaggio(
        intestazioni={k.lower(): v for k, v in risposta.items()},
        stato=risposta.status_code,
        richiesta=messaggio_richiesta(request) if legata else None,
    )
    ingressi, valori = [], []
    # "ga" con la chiave in uso; "ga1", "ga2"… con quelle in uscita ancora valide, così chi
    # conosce solo le chiavi precedenti verifica la risposta e può accettare le nuove
    for n, (kid, privata) in enumerate(chiavi.chiavi_firma_valide()):
        ingresso, valore = f.firma(
            msg,
            f.componenti_risposta(legata),
            f.parametri_firma(kid, time.time(), secrets.token_urlsafe(18)),
            privata,
            etichetta=f.ETICHETTA + (str(n) if n else ""),
        )
        ingressi.append(ingresso)
        valori.append(valore)
    risposta["Signature-Input"] = ", ".join(ingressi)
    risposta["Signature"] = ", ".join(valori)
    return risposta


def _registra_chiamata(request, risposta, codice, inizio):
    cliente = getattr(request, "cliente_api", None)
    try:
        ChiamataApi.objects.create(
            cliente=cliente if cliente and cliente.pk else None,
            metodo=request.method[:10],
            percorso=request.path[:255],
            stato=risposta.status_code,
            codice=codice[:40],
            indirizzo_ip=rete.ip_client(request) or None,
            durata_ms=int((time.monotonic() - inizio) * 1000),
        )
        if cliente and cliente.pk and not codice:
            ClienteApi.objects.filter(pk=cliente.pk).update(ultima_chiamata_il=timezone.now())
    except Exception:  # noqa: BLE001 - il registro non deve far fallire la risposta
        log.exception("Registro delle chiamate API non scritto")


def endpoint(*, metodi, ambito=None, in_prova=False, autenticato=True):
    """Decoratore delle viste dell'API: metodi ammessi, autenticazione, firma della risposta,
    errori Problem Details e registro."""

    def decoratore(vista):
        @csrf_exempt
        @wraps(vista)
        def interna(request, *args, **kwargs):
            inizio = time.monotonic()
            codice = ""
            if not cifratura_disponibile():
                risposta = risposta_problema(
                    Problema("non-configurata", 503, "Manca CHIAVE_CIFRATURA sul server.")
                )
                _registra_chiamata(request, risposta, "non-configurata", inizio)
                return risposta
            try:
                if request.method not in metodi:
                    risposta = HttpResponse(status=405)
                    risposta["Allow"] = ", ".join(metodi)
                else:
                    if autenticato:
                        autentica(request, ambito=ambito, in_prova=in_prova)
                    risposta = vista(request, *args, **kwargs)
            except Problema as p:
                codice = p.codice
                risposta = risposta_problema(p)
            with suppress(ChiaveNonConfigurata):
                firma_risposta(request, risposta)
            _registra_chiamata(request, risposta, codice, inizio)
            return risposta

        return interna

    return decoratore


def json_richiesta(request) -> dict:
    if request.content_type != "application/json":
        raise Problema("operazione-non-valida", 415, "Serve un corpo application/json.")
    try:
        dati = json.loads(request.body or b"null")
    except ValueError as e:
        raise Problema("operazione-non-valida", 400, "JSON non valido.") from e
    if not isinstance(dati, dict):
        raise Problema("operazione-non-valida", 400, "Il corpo deve essere un oggetto JSON.")
    return dati
