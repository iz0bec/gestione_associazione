# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Endpoint dell'API v1 (fase F1): descrizione dell'istanza, JWKS, abbinamento con
# *              invito monouso e /prova. Autenticati dalla firma, non dagli utenti del
# *              gestionale: i controlli sono in sicurezza.endpoint.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import base64
import hashlib
import json
import time
import uuid
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.urls import reverse

from apps.core import rete
from apps.core.models import Organizzazione

from . import chiavi, feed, rappresentazioni, servizi
from . import firma as f
from .sicurezza import Problema, controlla_firma, endpoint, json_richiesta, registra_nonce

VERSIONI = ["v1"]


@lru_cache(maxsize=4)
def _spki_da_file(percorso, _modificato):
    try:
        certificato = x509.load_pem_x509_certificate(Path(percorso).read_bytes())
    except (OSError, ValueError):
        return None
    spki = certificato.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return base64.b64encode(hashlib.sha256(spki).digest()).decode()


def impronte_tls():
    """Impronte SPKI dei certificati con cui l'istanza si presenta: quella del certificato
    servito direttamente da Gunicorn (installa.sh --tls-…) più quelle indicate in API_TLS_SPKI
    (es. certificato del proxy locale)."""
    impronte = list(settings.API_TLS_SPKI)
    percorso = settings.API_TLS_CERTIFICATO
    try:
        modificato = Path(percorso).stat().st_mtime if percorso else None
    except OSError:
        modificato = None
    if modificato is not None:
        impronta = _spki_da_file(percorso, modificato)
        if impronta and impronta not in impronte:
            impronte.insert(0, impronta)
    return impronte


def descrizione_istanza(request):
    org = Organizzazione.corrente()
    return {
        "istanza": str(chiavi.istanza().uuid),
        "nome": org.denominazione,
        "versioni_api": VERSIONI,
        "jwks_uri": request.build_absolute_uri(reverse("api_jwks")),
        "software_versione": settings.APP_VERSIONE,
        "tls_spki": impronte_tls(),
    }


@endpoint(metodi=("GET", "HEAD"), autenticato=False)
def well_known(request):
    return JsonResponse(descrizione_istanza(request), json_dumps_params={"ensure_ascii": False})


@endpoint(metodi=("GET", "HEAD"), autenticato=False)
def jwks(request):
    return JsonResponse(chiavi.jwks(), content_type="application/jwk-set+json")


def _campo(dati, nome, tipo, obbligatorio=True):
    valore = dati.get(nome)
    if valore is None and not obbligatorio:
        return None
    if not isinstance(valore, tipo):
        raise Problema("operazione-non-valida", 400, f"Campo {nome} mancante o non valido.")
    return valore


@endpoint(metodi=("POST",), autenticato=False)
def abbinamenti(request):
    """Abbinamento con invito monouso: la richiesta è firmata con la chiave presentata nel corpo
    (prova di possesso). La controparte nasce «in prova»."""
    dati = json_richiesta(request)
    try:
        istanza = uuid.UUID(_campo(dati, "istanza", str))
    except ValueError as e:
        raise Problema("operazione-non-valida", 400, "UUID dell'istanza non valido.") from e
    nome = _campo(dati, "nome", str).strip()[:255]
    tipo = _campo(dati, "tipo", str)
    if tipo not in ("installazione", "integrazione"):
        raise Problema("operazione-non-valida", 400, "Tipo non valido.")
    try:
        jwks_controparte = chiavi.valida_jwks(dati.get("jwks"))
    except chiavi.JwksNonValida as e:
        raise Problema("operazione-non-valida", 400, str(e)) from e
    tls_spki = _campo(dati, "tls_spki", list, obbligatorio=False) or []
    if not all(isinstance(x, str) and len(x) <= 64 for x in tls_spki) or len(tls_spki) > 4:
        raise Problema("operazione-non-valida", 400, "Campo tls_spki non valido.")
    notifiche = _campo(dati, "indirizzo_notifiche", str, obbligatorio=False) or ""
    if notifiche and not notifiche.startswith(("https://", "http://")):
        raise Problema("operazione-non-valida", 400, "Indirizzo delle notifiche non valido.")

    chiavi_firma = {k["kid"]: k for k in jwks_controparte["keys"] if k["use"] == "sig"}
    verificata = controlla_firma(
        request,
        lambda kid: f.chiave_pubblica(chiavi_firma[kid]["x"]) if kid in chiavi_firma else None,
    )
    with transaction.atomic():
        invito = servizi.invito_valido(request.headers.get("invito", ""))
        if invito is None:
            raise Problema("invito-non-valido", 410, "Invito scaduto, già usato o inesistente.")
        if invito.cliente.tipo != tipo:
            raise Problema("operazione-non-valida", 400, "Il tipo non corrisponde all'invito.")
        registra_nonce(verificata.keyid, verificata.parametri["nonce"])
        try:
            cliente = servizi.completa_abbinamento(
                invito, istanza=istanza, nome=nome, jwks=jwks_controparte, tls_spki=tls_spki,
                indirizzo_notifiche=notifiche,
            )  # fmt: skip
        except servizi.OperazioneNonValida as e:
            raise Problema("operazione-non-valida", 409, str(e)) from e
    request.cliente_api = cliente
    return JsonResponse(
        {
            "istanza": str(chiavi.istanza().uuid),
            "stato": cliente.stato,
            "impronta": cliente.impronta,
            "jwks": chiavi.jwks(),
        },
        status=201,
    )


@endpoint(metodi=("POST",), in_prova=True)
def prova(request):
    """Diagnosi del collegamento: non modifica nulla. Anche per le controparti in prova."""
    cliente = request.cliente_api
    creata = request.firma_api.parametri["created"]
    # la cifratura JWE arriva con la fase F4: per ora un corpo cifrato non si decifra
    cifratura = "non-valida" if request.content_type == "application/jose" else "assente"
    return JsonResponse(
        {
            "firma": "valida",
            "orologio": {"scarto_secondi": int(time.time() - creata)},
            "controparte": {"stato": cliente.stato, "ambiti": cliente.ambiti},
            "cifratura": cifratura,
            "indirizzo_ip_visto": rete.ip_client(request),
            "istanza": str(chiavi.istanza().uuid),
        }
    )


# ---------------------------------------------------------------- fase F2: feed e risorse

LIMITE_PREDEFINITO = 100
LIMITE_MASSIMO = 500


def _intero(request, nome, predefinito, minimo=0, massimo=None):
    valore = request.GET.get(nome, "")
    if valore == "":
        return predefinito
    try:
        numero = int(valore)
    except ValueError as e:
        raise Problema("operazione-non-valida", 400, f"Parametro {nome} non valido.") from e
    if numero < minimo or (massimo is not None and numero > massimo):
        raise Problema("operazione-non-valida", 400, f"Parametro {nome} fuori intervallo.")
    return numero


def _flusso(request, nome):
    """(ambito, risorse visibili) del flusso, dopo il controllo dell'ambito."""
    if nome not in rappresentazioni.FLUSSI:
        raise Problema("operazione-non-valida", 404, f"Flusso sconosciuto: {nome}.")
    ambito, visibili = rappresentazioni.FLUSSI[nome]
    if ambito not in request.cliente_api.ambiti:
        raise Problema("ambito-mancante", 403, f"Ambito non concesso: {ambito}.")
    return ambito, visibili


@endpoint(metodi=("GET",))
def cambiamenti(request):
    nome = request.GET.get("flusso", "")
    _flusso(request, nome)
    dopo = _intero(request, "dopo", 0)
    limite = _intero(request, "limite", LIMITE_PREDEFINITO, 1, LIMITE_MASSIMO)
    try:
        voci, ultimo = feed.pagina(nome, dopo, limite)
    except feed.CatenaInterrotta as e:
        raise Problema("cursore-scaduto", 410, str(e)) from e
    return JsonResponse({"flusso": nome, "cambiamenti": voci, "ultimo": ultimo})


@endpoint(metodi=("GET",))
def riepilogo(request, flusso):
    _, visibili = _flusso(request, flusso)
    # progressivo e risorse coerenti: si rilegge finché nel frattempo non cambia nulla
    for _ in range(5):
        progressivo = feed.ultimo(flusso)
        coppie = list(visibili(request.cliente_api).values_list("uuid", "versione"))
        if feed.ultimo(flusso) == progressivo:
            break
    else:
        raise Problema("troppe-richieste", 503, "Flusso in aggiornamento: riprovare.")
    return JsonResponse({
        "flusso": flusso, "risorse": len(coppie), "impronta": feed.impronta_riepilogo(coppie),
        "progressivo": progressivo,
    })  # fmt: skip


def _codifica_cursore(dati):
    return f.b64url(json.dumps(dati).encode())


def _leggi_cursore(testo):
    try:
        inizio, pk = json.loads(f.b64url_decodifica(testo))
        return datetime.fromisoformat(inizio), int(pk)
    except (ValueError, TypeError) as e:
        raise Problema("operazione-non-valida", 400, "Cursore non valido.") from e


@endpoint(metodi=("GET",), ambito="eventi:lettura")
def eventi(request):
    limite = _intero(request, "limite", LIMITE_PREDEFINITO, 1, LIMITE_MASSIMO)
    qs = rappresentazioni.eventi_visibili(request.cliente_api).order_by("inizio", "pk")
    if request.GET.get("dal"):
        try:
            dal = date.fromisoformat(request.GET["dal"])
        except ValueError as e:
            raise Problema("operazione-non-valida", 400, "Parametro dal non valido.") from e
        qs = qs.filter(inizio__date__gte=dal)
    if request.GET.get("cursore"):
        inizio, pk = _leggi_cursore(request.GET["cursore"])
        qs = qs.filter(Q(inizio__gt=inizio) | Q(inizio=inizio, pk__gt=pk))
    righe = list(qs[: limite + 1])
    successivo = None
    if len(righe) > limite:
        righe = righe[:limite]
        successivo = _codifica_cursore([righe[-1].inizio.isoformat(), righe[-1].pk])
    return JsonResponse({"risultati": [rappresentazioni.evento(e) for e in righe],
                         "successivo": successivo})  # fmt: skip


@endpoint(metodi=("GET",), ambito="eventi:lettura")
def evento(request, uuid_risorsa):
    e = rappresentazioni.eventi_visibili(request.cliente_api).filter(uuid=uuid_risorsa).first()
    if e is None:
        raise Problema("operazione-non-valida", 404, "Evento inesistente o non visibile.")
    risposta = JsonResponse(rappresentazioni.evento(e))
    risposta["ETag"] = f'"{e.versione}"'
    return risposta


@endpoint(metodi=("GET",), ambito="sezioni:lettura")
def sezioni(request):
    righe = rappresentazioni.sezioni_visibili(request.cliente_api).order_by("ordine", "nome")
    return JsonResponse([rappresentazioni.sezione(s) for s in righe], safe=False)


@endpoint(metodi=("PUT",), in_prova=True)
def chiavi_controparte(request):
    """La controparte presenta chiavi nuove (rotazione), firmando con una chiave già nota."""
    try:
        nuove = chiavi.valida_jwks(json_richiesta(request).get("jwks"))
    except chiavi.JwksNonValida as e:
        raise Problema("operazione-non-valida", 400, str(e)) from e
    servizi.aggiorna_chiavi_controparte(request.cliente_api, nuove)
    return JsonResponse({"jwks": request.cliente_api.jwks})
