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
from django.http import HttpResponse, JsonResponse
from django.urls import reverse

from apps.core import rete
from apps.core.audit import Azione, registra
from apps.core.models import Organizzazione

from . import chiavi, feed, jwe, rappresentazioni, servizi
from . import firma as f
from .sicurezza import (
    Problema,
    controlla_firma,
    corpo,
    endpoint,
    json_richiesta,
    registra_nonce,
    risposta_cifrata,
)

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
    descrizione = {
        "istanza": str(chiavi.istanza().uuid),
        "nome": org.denominazione,
        "versioni_api": VERSIONI,
        "jwks_uri": request.build_absolute_uri(reverse("api_jwks")),
        "software_versione": settings.APP_VERSIONE,
        "tls_spki": impronte_tls(),
        "servizi": servizi_pubblici(request, org),
    }
    if org.recapiti_pubblici:
        descrizione["recapiti"] = recapiti_pubblici(org)
    return descrizione


def servizi_pubblici(request, org):
    """Pagine pubbliche attive (per portali e siti che elencano le installazioni)."""
    assoluto = request.build_absolute_uri
    return {
        "gestionale": assoluto("/"),
        "iscrizione": assoluto(reverse("iscrizione")) if org.iscrizioni_online else None,
        "area_soci": assoluto(reverse("area:accesso")) if org.area_soci else None,
        "presentazione": assoluto("/") if org.pagina_pubblica else None,
    }


def recapiti_pubblici(org):
    """Recapiti istituzionali dell'ente, solo se l'organizzazione ne consente la pubblicazione."""
    return {
        "denominazione": org.denominazione,
        "indirizzo": org.indirizzo, "cap": org.cap, "comune": org.comune,
        "provincia": org.provincia, "telefono": org.telefono, "email": org.email,
        "pec": org.pec, "sito_web": org.sito_web,
    }  # fmt: skip


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
    diagnosi_extra = {}
    if request.content_type == jwe.TIPO:
        try:
            dati = corpo(request)
            cifratura = "valida"
            chiavi_enc = [k for k in cliente.chiavi("enc") if "exp" not in k]
            if chiavi_enc:
                diagnosi_extra["risposta_cifrata"] = jwe.cifra({"eco": dati}, chiavi_enc[0])
        except Problema:
            cifratura = "non-valida"
    else:
        cifratura = "assente"
    return JsonResponse(
        {
            "firma": "valida",
            "orologio": {"scarto_secondi": int(time.time() - creata)},
            "controparte": {"stato": cliente.stato, "ambiti": cliente.ambiti},
            "cifratura": cifratura,
            "indirizzo_ip_visto": rete.ip_client(request),
            "istanza": str(chiavi.istanza().uuid),
            **diagnosi_extra,
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


def _flusso_tessere(request):
    """Il flusso «tessere» è quello della sezione visibile alla controparte che chiama."""
    from . import tessere

    if tessere.AMBITO not in request.cliente_api.ambiti:
        raise Problema("ambito-mancante", 403, f"Ambito non concesso: {tessere.AMBITO}.")
    reale = tessere.flusso_per(request.cliente_api)
    if reale is None:
        dettaglio = "La controparte non è collegata come federazione o come sezione."
        raise Problema("operazione-non-valida", 403, dettaglio)
    return reale


@endpoint(metodi=("GET",))
def cambiamenti(request):
    nome = request.GET.get("flusso", "")
    if nome == "tessere":
        reale = _flusso_tessere(request)
    else:
        _flusso(request, nome)
        reale = nome
    dopo = _intero(request, "dopo", 0)
    limite = _intero(request, "limite", LIMITE_PREDEFINITO, 1, LIMITE_MASSIMO)
    try:
        voci, ultimo = feed.pagina(reale, dopo, limite)
    except feed.CatenaInterrotta as e:
        raise Problema("cursore-scaduto", 410, str(e)) from e
    return JsonResponse({"flusso": nome, "cambiamenti": voci, "ultimo": ultimo})


@endpoint(metodi=("GET",), ambito="tessere:scambio")
def documento_tessere(request, risorsa, uuid_risorsa):
    """Consegna, ricevuta, richiesta o presa in carico della sezione visibile alla controparte,
    con il PDF (base64) da protocollare."""
    from . import tessere

    _flusso_tessere(request)
    dati = tessere.documento(request.cliente_api, risorsa, uuid_risorsa)
    if dati is None:
        raise Problema("operazione-non-valida", 404, "Documento inesistente o non visibile.")
    risposta = JsonResponse(dati)
    risposta["ETag"] = f'"{dati["versione"]}"'
    return risposta


@endpoint(metodi=("GET",), ambito="soci:lettura")
def soci(request):
    """Soci della sezione visibile alla controparte (la federazione vede quelli della sezione
    legata, la sezione i propri), cessati compresi, con le tessere recenti. Sempre cifrato."""
    from apps.soci import allineamento

    from . import tessere

    sezione = tessere.sezione_per(request.cliente_api)
    if sezione is None:
        dettaglio = "La controparte non è collegata come federazione o come sezione."
        raise Problema("operazione-non-valida", 403, dettaglio)
    dati = {"sezione": {"codice": sezione.codice, "nome": sezione.nome},
            # come vediamo chi chiama: serve a lui per accorgersi di ruoli invertiti
            "tu": {"ruolo": request.cliente_api.ruolo},
            "soci": allineamento.elenco(sezione)}  # fmt: skip
    return risposta_cifrata(request, dati)


@endpoint(metodi=("GET",), ambito="soci:lettura")
def tesseramento(request):
    """Numeri del tesseramento della sezione legata alla controparte (solo conteggi)."""
    from apps.soci import allineamento

    from . import tessere

    sezione = tessere.sezione_per(request.cliente_api)
    if sezione is None:
        dettaglio = "La controparte non è collegata come federazione o come sezione."
        raise Problema("operazione-non-valida", 403, dettaglio)
    anno = _intero(request, "anno", date.today().year, 2000, 2100)
    dati = {"sezione": {"codice": sezione.codice, "nome": sezione.nome}}
    return JsonResponse(dati | allineamento.numeri(sezione, anno))


@endpoint(metodi=("POST",), ambito="consegne:scrittura", idempotente=True, cifrato=True)
def consegne(request):
    """Modalità a spinta: la sezione che non si raggiunge invia l'elenco dei suoi soci (stesso
    contenuto di GET /soci). Con l'allineamento automatico acceso si applica subito in ordine di
    tempo, altrimenti resta una verifica da decidere."""
    from apps.collegamenti import soci as allineamento_soci

    try:
        esito = allineamento_soci.ricevi_consegna(request.cliente_api, corpo(request, cifrato=True))
    except allineamento_soci.OperazioneNonValida as e:
        raise Problema("operazione-non-valida", 422, str(e)) from e
    return JsonResponse(esito)


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


# ---------------------------------------------------------------- fase F3: dati dall'esterno


def _richiedi(request, ambito):
    if ambito not in request.cliente_api.ambiti:
        raise Problema("ambito-mancante", 403, f"Ambito non concesso: {ambito}.")


def _messaggi(errore):
    return " ".join(getattr(errore, "messages", None) or [str(errore)])


def _evento_visibile(request, uuid_risorsa):
    e = rappresentazioni.eventi_visibili(request.cliente_api).filter(uuid=uuid_risorsa).first()
    if e is None:
        raise Problema("operazione-non-valida", 404, "Evento inesistente o non visibile.")
    return e


@endpoint(metodi=("GET", "POST"), idempotente=True, cifrato=True)
def adesioni_evento(request, uuid_risorsa):
    from apps.eventi import servizi as eventi
    from apps.eventi.models import Adesione

    evento_ = _evento_visibile(request, uuid_risorsa)
    cliente = request.cliente_api
    if request.method == "GET":
        _richiedi(request, "adesioni:lettura")
        proprie = evento_.adesioni.filter(cliente_api=cliente).order_by("creata_il")
        return risposta_cifrata(request, [rappresentazioni.adesione(a) for a in proprie])
    _richiedi(request, "adesioni:scrittura")
    dati = corpo(request, cifrato=True)
    try:
        adesione = eventi.aderisci(
            evento_, dati, origine=Adesione.Origine.INTEGRAZIONE, cliente_api=cliente,
            riferimento_esterno=str(dati.get("riferimento_esterno") or ""),
        )  # fmt: skip
    except eventi.OperazioneNonValida as e:
        raise Problema("operazione-non-valida", 409, _messaggi(e)) from e
    risposta = risposta_cifrata(request, rappresentazioni.adesione(adesione), 201)
    risposta["Location"] = reverse("api_v1:adesione", args=[adesione.uuid])
    risposta["ETag"] = f'"{adesione.versione}"'
    return risposta


@endpoint(metodi=("DELETE",), ambito="adesioni:scrittura")
def adesione(request, uuid_risorsa):
    from apps.eventi import servizi as eventi
    from apps.eventi.models import Adesione

    trovata = Adesione.objects.filter(uuid=uuid_risorsa, cliente_api=request.cliente_api).first()
    if trovata is None:
        raise Problema("operazione-non-valida", 404, "Adesione inesistente o di un'altra fonte.")
    if request.headers.get("if-match", "") != f'"{trovata.versione}"':
        dettaglio = f"If-Match non corrisponde alla versione attuale ({trovata.versione})."
        raise Problema("operazione-non-valida", 412, dettaglio)
    try:
        eventi.annulla_adesione(trovata)
    except eventi.OperazioneNonValida as e:
        raise Problema("operazione-non-valida", 409, _messaggi(e)) from e
    return HttpResponse(status=204)


CAMPI_DOMANDA_API = [
    "cognome", "nome", "codice_fiscale", "data_nascita", "luogo_nascita", "email", "telefono",
    "cellulare", "indirizzo", "cap", "comune", "provincia", "motivazione", "accetta_statuto",
    "consenso_trattamento", "consenso_particolari", "consenso_immagini",
]  # fmt: skip


@endpoint(metodi=("POST",), ambito="domande:scrittura", idempotente=True, cifrato=True)
def domande(request):
    """Domanda di iscrizione: stessi campi e controlli del modulo, resta «in attesa»."""
    from apps.soci.forms import DomandaForm
    from apps.soci.models import DomandaIscrizione, Sezione, TipologiaSocio

    dati = corpo(request, cifrato=True)
    campi = {c: dati[c] for c in CAMPI_DOMANDA_API if dati.get(c) not in (None, "", False)}
    sezione = Sezione.objects.filter(codice=str(dati.get("sezione") or ""), attiva=True).first()
    if dati.get("sezione") and sezione is None:
        raise Problema("operazione-non-valida", 422, "Sezione sconosciuta.")
    sezione = sezione or Sezione.predefinita()
    campi["sezione"] = sezione.pk
    if dati.get("tipologia"):
        tipologia = TipologiaSocio.objects.filter(nome=dati["tipologia"], attiva=True).first()
        if tipologia is None:
            raise Problema("operazione-non-valida", 422, "Tipologia sconosciuta.")
        campi["tipologia"] = tipologia.pk
    if dati.get("dichiarazione") is not None:
        campi["dichiarazione"] = str(bool(dati["dichiarazione"]))
    form = DomandaForm(data=campi)
    if not form.is_valid():
        errori = "; ".join(
            f"{form.fields[n].label if n in form.fields else n}: {' '.join(e)}"
            for n, e in form.errors.items()
        )
        raise Problema("operazione-non-valida", 422, errori)
    domanda = form.save(commit=False)
    domanda.origine = DomandaIscrizione.Origine.INTEGRAZIONE
    domanda.cliente_api = request.cliente_api
    domanda.save()
    form.save_m2m()
    registra(Azione.CREAZIONE, domanda, descrizione=f"Domanda di iscrizione n. {domanda.pk} da "
             f"{request.cliente_api}", origine="integrazione",
             riferimento_esterno=str(dati.get("riferimento_esterno") or "")[:100],
             consensi_prestati_il=str(dati.get("prestato_il") or "")[:40])  # fmt: skip
    return JsonResponse({"uuid": str(domanda.uuid), "stato": domanda.stato}, status=201)


@endpoint(metodi=("POST",), ambito="contatti:scrittura", idempotente=True, cifrato=True)
def contatti(request):
    """Messaggio del modulo contatti: arriva tra la posta da protocollare."""
    from django.core.validators import validate_email
    from django.forms import ValidationError

    from . import contatti as modulo

    dati = corpo(request, cifrato=True)
    nome = str(dati.get("nome") or "").strip()[:200]
    email = str(dati.get("email") or "").strip()[:254]
    testo = str(dati.get("testo") or "").strip()
    if not nome or not testo:
        raise Problema("operazione-non-valida", 422, "Servono nome e testo del messaggio.")
    if len(testo) > 10000:
        raise Problema("operazione-non-valida", 422, "Testo troppo lungo (al massimo 10000).")
    try:
        validate_email(email)
    except ValidationError as e:
        raise Problema("operazione-non-valida", 422, "Indirizzo email non valido.") from e
    messaggio = modulo.ricevi(
        request.cliente_api, nome=nome, email=email, testo=testo,
        oggetto=str(dati.get("oggetto") or "").strip()[:200],
        telefono=str(dati.get("telefono") or "").strip()[:30],
        riferimento_esterno=str(dati.get("riferimento_esterno") or "").strip()[:100],
    )  # fmt: skip
    return JsonResponse({"ricevuto": True, "riferimento": messaggio.message_id}, status=201)


# ---------------------------------------------------------------- fase F3: dati verso l'esterno


@endpoint(metodi=("GET",), ambito="documenti:lettura")
def documenti(request):
    from apps.core.models import DocumentoPubblico

    elenco = DocumentoPubblico.objects.filter(pubblicato=True).order_by("ordine", "titolo")
    return JsonResponse([rappresentazioni.documento(request, d) for d in elenco], safe=False)


@endpoint(metodi=("GET",), ambito="documenti:lettura")
def documento_file(request, pk):
    from apps.core.models import DocumentoPubblico

    d = DocumentoPubblico.objects.filter(pk=pk, pubblicato=True).first()
    if d is None:
        raise Problema("operazione-non-valida", 404, "Documento inesistente o non pubblicato.")
    with d.file.open("rb") as f_:
        dati = f_.read()
    risposta = HttpResponse(dati, content_type="application/pdf")
    risposta["Content-Disposition"] = f'attachment; filename="{d.nome_file}"'
    return risposta


@endpoint(metodi=("GET",))
def ente(request):
    """Contatti istituzionali dell'organizzazione, per la rubrica della controparte."""
    return JsonResponse(rappresentazioni.ente())


@endpoint(metodi=("GET",), ambito="organigramma:lettura")
def organigramma(request):
    return JsonResponse(rappresentazioni.organigramma(), safe=False)


@endpoint(metodi=("GET",), ambito="tessere:verifica")
def verifica_tessera(request, codice):
    from apps.soci import tessera_digitale

    tessera = tessera_digitale.da_codice(codice)
    if tessera is None:
        raise Problema("operazione-non-valida", 404, "Codice di verifica sconosciuto.")
    esito = tessera_digitale.esito(tessera)
    # solo validità, anno e sezione: nessun altro dato della persona (decisione del 18/11/2026)
    return JsonResponse({"valida": esito.valida, "motivo": esito.motivo, "anno": esito.anno,
                         "sezione": esito.sezione})  # fmt: skip
