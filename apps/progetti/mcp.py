# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Connettore MCP (Model Context Protocol, trasporto Streamable HTTP, JSON-RPC 2.0)
# *              per l'assistenza alle valutazioni: il gestionale non contiene IA, espone a un
# *              client scelto dall'utente i dati di idee, bandi e progetti. Sola lettura (commenti
# *              «Assistente» solo se ammessi), spento di norma, token personali con i permessi
# *              dell'utente, ogni chiamata nel registro, nessun dato personale dei soci.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import hashlib
import json
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from urllib.parse import urlsplit

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from apps.core.audit import Azione, registra

from .models import ConnettoreMCP, TokenMCP

VERSIONI = ["2025-06-18", "2025-03-26", "2024-11-05"]
PREFISSO_TOKEN = "ga_mcp_"  # noqa: S105 - prefisso riconoscibile, non un segreto
ISTRUZIONI = (
    "Strumenti di sola lettura sui progetti dell'associazione: idee e necessità con le "
    "valutazioni, bandi con i requisiti verificati, progetti con quadro, cronoprogramma, partner, "
    "piano economico e proposta, finalità statutarie e criteri. Aiuta a confrontare e motivare: "
    "le decisioni spettano alle persone. I dati personali dei soci non sono disponibili (solo "
    "numeri aggregati); le persone fisiche compaiono come «persona (riservato)»."
)


class ErroreStrumento(Exception):
    pass


# --- token ---------------------------------------------------------------------------------------


def impronta(valore):
    return hashlib.sha256(valore.encode()).hexdigest()


def crea_token(utente, nome, *, commenti=False, scade_il=None):
    """Restituisce (token, valore in chiaro). Il valore si mostra una sola volta."""
    valore = PREFISSO_TOKEN + secrets.token_urlsafe(32)
    token = TokenMCP.objects.create(
        utente=utente,
        nome=nome.strip()[:100] or "Client MCP",
        prefisso=valore[:14],
        impronta=impronta(valore),
        commenti=commenti,
        scade_il=scade_il,
    )
    registra(Azione.CREAZIONE, token, utente=utente, descrizione=f"Token MCP {token}")
    return token, valore


def revoca(token, utente):
    if token.revocato_il is None:
        token.revocato_il = timezone.now()
        token.save(update_fields=["revocato_il"])
        registra(
            Azione.MODIFICA,
            token,
            utente=utente,
            descrizione=f"Token MCP {token}",
            stato="revocato",
        )


def token_da_richiesta(request):
    intestazione = request.headers.get("Authorization", "")
    tipo, _, valore = intestazione.partition(" ")
    if tipo.lower() != "bearer" or not valore.startswith(PREFISSO_TOKEN):
        return None
    token = TokenMCP.objects.select_related("utente").filter(impronta=impronta(valore)).first()
    return token if token and token.valido else None


# --- dati (senza dati personali dei soci) --------------------------------------------------------


def _soggetto(s):
    if s is None:
        return None
    return "persona (riservato)" if s.tipo == "persona" else str(s)


def _num(valore):
    if valore is None:
        return None
    return float(valore) if isinstance(valore, Decimal) else valore


def _data(valore):
    return valore.isoformat() if valore else None


def _finalita(qs):
    return [f.codice or f.titolo for f in qs.all()]


def dati_associazione(utente, **_):
    from . import requisiti

    org = requisiti._org()
    from apps.soci.models import Socio

    anno = timezone.localdate().year
    rendiconto = requisiti._rendiconto(None, "")
    return {
        "denominazione": org.denominazione,
        "comune": org.comune,
        "provincia": org.provincia,
        "iscritta_runts": bool(org.iscrizione_runts.strip()),
        "codice_fiscale_presente": bool(org.codice_fiscale.strip()),
        "pec_presente": bool(org.pec.strip()),
        "soci_attivi": Socio.objects.attivi().count(),
        f"soci_in_regola_{anno}": Socio.objects.attivi().in_regola(anno).count(),
        "rendiconto_anno_precedente": {"esito": rendiconto[0], "dettaglio": rendiconto[1]},
    }


def finalita_e_criteri(utente, **_):
    from .models import CriterioValutazione, FinalitaStatutaria

    return {
        "finalita_statutarie": [
            {"codice": f.codice, "titolo": f.titolo, "testo": f.testo}
            for f in FinalitaStatutaria.objects.filter(attiva=True)
        ],
        "criteri_di_valutazione": [
            {
                "id": c.pk,
                "nome": c.nome,
                "descrizione": c.descrizione,
                "peso": c.peso,
                "scala": "da 1 (poco) a 5 (molto)",
            }
            for c in CriterioValutazione.objects.filter(attivo=True)
        ],
    }


def elenca_idee(utente, stato="aperte", **_):
    from . import servizi
    from .models import Idea

    qs = Idea.objects.prefetch_related("finalita", "valutazioni")
    if stato == "aperte":
        qs = qs.filter(stato__in=[Idea.Stato.NUOVA, Idea.Stato.IN_VALUTAZIONE])
    elif stato in Idea.Stato.values:
        qs = qs.filter(stato=stato)
    return [
        {
            "id": i.pk,
            "codice": i.codice,
            "titolo": i.titolo,
            "stato": i.get_stato_display(),
            "priorita": i.get_priorita_display() or None,
            "finalita": _finalita(i.finalita),
            "media_valutazioni": _num(servizi.media_idea(i)),
            "valutazioni": len(i.valutazioni.all()),
            "fonte": i.get_fonte_display(),
        }
        for i in qs[:100]
    ]


def scheda_idea(utente, id, **_):
    from django.shortcuts import get_object_or_404

    from . import servizi
    from .models import Idea

    i = get_object_or_404(Idea.objects.select_related("fonte_soggetto"), pk=id)
    r = servizi.riepilogo_valutazioni(i)
    return {
        "id": i.pk,
        "codice": i.codice,
        "titolo": i.titolo,
        "descrizione": i.descrizione,
        "bisogno": i.bisogno,
        "destinatari": i.destinatari,
        "costo_stimato": _num(i.costo_stimato),
        "finalita": _finalita(i.finalita),
        "stato": i.get_stato_display(),
        "priorita": i.get_priorita_display() or None,
        "fonte": i.get_fonte_display(),
        # il testo libero della fonte può contenere nomi di persone: non si espone
        "proposta_da": _soggetto(i.fonte_soggetto)
        or ("indicata a testo (riservato)" if i.fonte_testo else None),
        "valutazione": {
            "media": _num(r["media"]),
            "per_criterio": [
                {
                    "criterio": x["criterio"].nome,
                    "peso": x["criterio"].peso,
                    "media": _num(x["media"]),
                }
                for x in r["criteri"]
            ],
            "valutazioni": len(r["valutazioni"]),
            "commenti_dei_valutatori": [v.commento for v in r["valutazioni"] if v.commento],
        },
        "discussione": [c.testo for c in i.commenti.all()],
        "progetto": i.progetto.codice if hasattr(i, "progetto") else None,
    }


def elenca_bandi(utente, stato="aperti", **_):
    from django.db.models import Q

    from .models import Bando

    oggi = timezone.localdate()
    qs = Bando.objects.select_related("finanziatore").prefetch_related("finalita")
    if stato == "aperti":
        qs = qs.exclude(stato=Bando.Stato.SCARTATO).filter(
            Q(scadenza__gte=oggi) | Q(scadenza__isnull=True)
        )
    elif stato in Bando.Stato.values:
        qs = qs.filter(stato=stato)
    return [
        {
            "id": b.pk,
            "titolo": b.titolo,
            "finanziatore": b.ente,
            "stato": b.get_stato_display(),
            "scadenza": _data(b.scadenza),
            "giorni_alla_scadenza": b.giorni_alla_scadenza(oggi),
            "contributo_massimo": _num(b.importo_massimo),
            "finalita": _finalita(b.finalita),
        }
        for b in qs[:100]
    ]


def scheda_bando(utente, id, **_):
    from django.shortcuts import get_object_or_404

    from . import requisiti
    from .models import Bando

    b = get_object_or_404(Bando.objects.select_related("finanziatore"), pk=id)
    r = requisiti.riepilogo(b)
    return {
        "id": b.pk,
        "titolo": b.titolo,
        "finanziatore": b.ente,
        "link": b.link,
        "descrizione": b.descrizione,
        "stato": b.get_stato_display(),
        "finalita": _finalita(b.finalita),
        "contributo_massimo": _num(b.importo_massimo),
        "cofinanziamento_minimo_percentuale": _num(b.cofinanziamento),
        "spese_generali_massime_percentuale": _num(b.spese_generali_massime),
        "natura_massima_percentuale": _num(b.natura_massima),
        "limiti_per_categoria": [str(x) for x in b.limiti.all()],
        "apertura": _data(b.apertura),
        "scadenza": _data(b.scadenza),
        "requisiti": [
            {
                "requisito": e.requisito.descrizione,
                "esito": e.etichetta,
                "dettaglio": e.spiegazione,
                "verificato_sui_dati": e.automatico,
            }
            for e in r["esiti"]
        ],
        "formulario": [
            {"sezione": s.titolo, "istruzioni": s.domande, "massimo_caratteri": s.massimo_caratteri}
            for s in b.sezioni.all()
        ],
        "progetti_candidati": [p.codice for p in b.progetti.all()],
    }


def elenca_progetti(utente, stato="aperti", **_):
    from .models import Progetto

    qs = Progetto.objects.select_related("bando").prefetch_related("finalita")
    if stato == "aperti":
        qs = qs.exclude(stato__in=[Progetto.Stato.CHIUSO, Progetto.Stato.ACCANTONATO])
    elif stato in Progetto.Stato.values:
        qs = qs.filter(stato=stato)
    return [
        {
            "id": p.pk,
            "codice": p.codice,
            "titolo": p.titolo,
            "stato": p.get_stato_display(),
            "bando": str(p.bando) if p.bando_id else None,
            "finalita": _finalita(p.finalita),
            "inizio_previsto": _data(p.inizio_previsto),
            "fine_prevista": _data(p.fine_prevista),
        }
        for p in qs[:100]
    ]


def scheda_progetto(utente, id, **_):
    from django.shortcuts import get_object_or_404

    from . import piano, proposta
    from .models import Progetto

    p = get_object_or_404(Progetto.objects.select_related("bando"), pk=id)
    pe = piano.calcola(p)
    return {
        "id": p.pk,
        "codice": p.codice,
        "titolo": p.titolo,
        "sintesi": p.sintesi,
        "stato": p.get_stato_display(),
        "bando": p.bando_id and {"id": p.bando_id, "titolo": str(p.bando)},
        "finalita": _finalita(p.finalita),
        "quadro": {
            "obiettivo_generale": p.obiettivo_generale,
            "destinatari": p.destinatari,
            "territorio": p.territorio,
            "obiettivi_specifici": [
                {
                    "obiettivo": o.testo,
                    "risultati_attesi": o.risultati,
                    "indicatori": [
                        {
                            "indicatore": x.descrizione,
                            "unita": x.unita,
                            "iniziale": _num(x.valore_iniziale),
                            "atteso": _num(x.valore_atteso),
                            "verifica": x.fonte_verifica,
                        }
                        for x in o.indicatori.all()
                    ],
                }
                for o in p.obiettivi.all()
            ],
        },
        "attivita": [
            {
                "attivita": a.titolo,
                "descrizione": a.descrizione,
                "inizio": _data(a.inizio),
                "fine": _data(a.fine),
                "dopo": a.dopo.titolo if a.dopo_id else None,
                "con_responsabile": a.responsabile_id is not None,
            }
            for a in p.attivita.select_related("dopo")
        ],
        "partner": [
            {
                "partner": _soggetto(x.soggetto),
                "ruolo": x.get_ruolo_display(),
                "contributo": x.contributo,
                "cofinanziamento": _num(x.cofinanziamento),
                "lettera_ricevuta": x.lettera_ricevuta,
            }
            for x in p.partner.select_related("soggetto")
        ],
        "piano_economico": {
            "costi_per_categoria": {etichetta: _num(tot) for _, etichetta, _, tot in pe.categorie},
            "spese_generali": _num(pe.spese_generali),
            "totale_costi": _num(pe.totale_costi),
            "contributo_richiesto": _num(pe.contributo),
            "proprio": _num(pe.proprio),
            "partner": _num(pe.partner),
            "in_natura": _num(pe.natura),
            "altri": _num(pe.altri),
            "controlli": [{"esito": c.esito, "controllo": c.testo} for c in pe.controlli],
        },
        "proposta": [
            {
                "sezione": s.titolo,
                "testo": s.testo,
                "caratteri": s.caratteri,
                "massimo_caratteri": s.massimo_caratteri,
            }
            for s in p.sezioni_proposta
        ],
        "verifica_candidatura": [
            {"esito": v.esito, "controllo": v.testo} for v in proposta.verifica(p)
        ],
        "esecuzione": _esecuzione(p),
        "relazione_al_consiglio": [
            {"sezione": s.titolo, "testo": s.testo} for s in p.sezioni_consiglio if s.testo
        ],
        "relazione_finale": [
            {"sezione": s.titolo, "testo": s.testo} for s in p.sezioni_relazione if s.testo
        ],
    }


def _esecuzione(p):
    from . import esecuzione

    if not esecuzione.in_esecuzione(p) and p.stato != "chiuso":
        return None
    c, av = esecuzione.consuntivo(p), esecuzione.avanzamento(p)
    return {
        "avanzamento": av,
        "preventivo_consuntivo": [
            {
                "voce": r.voce.descrizione,
                "preventivo": _num(r.preventivo),
                "consuntivo": _num(r.consuntivo),
                "scostamento": _num(r.scostamento),
            }
            for r in c.righe
        ],
        "costi_senza_voce": _num(c.non_attribuiti),
        "contributo_previsto": _num(c.contributo_previsto),
        "contributo_incassato": _num(c.contributo_incassato),
        "ore_di_volontariato": _num(c.ore),
        "volontariato_valorizzato": _num(c.natura_consuntivo),
        "varianti": p.varianti.count(),
    }


def bandi_da_vagliare(utente, **_):
    from .models import BandoProposto

    return [
        {
            "id": x.pk,
            "titolo": x.titolo,
            "link": x.link,
            "fonte": str(x.fonte) if x.fonte else None,
            "pubblicato_il": _data(x.pubblicato_il),
            "parole_trovate": x.parole,
            "sommario": x.sommario,
        }
        for x in BandoProposto.objects.filter(stato="nuovo").select_related("fonte")[:50]
    ]


def aggiungi_commento(utente, tipo, id, testo, token=None, **_):
    from django.shortcuts import get_object_or_404

    from . import servizi
    from .models import Idea, Progetto

    if not (ConnettoreMCP.corrente().commenti_ammessi and token is not None and token.commenti):
        raise ErroreStrumento("I commenti dell'assistente non sono abilitati per questo token.")
    testo = (testo or "").strip()
    if not testo:
        raise ErroreStrumento("Il commento è vuoto.")
    modello = {"idea": Idea, "progetto": Progetto}.get(tipo)
    if modello is None:
        raise ErroreStrumento("Il tipo deve essere «idea» o «progetto».")
    if not utente.has_perm(f"progetti.view_{tipo}"):
        raise ErroreStrumento("Permesso negato.")
    oggetto = get_object_or_404(modello, pk=id)
    servizi.commenta(oggetto, utente, f"[Assistente] {testo[:4000]}")
    return {"esito": "commento aggiunto", "a": str(oggetto)}


# --- strumenti -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Strumento:
    funzione: Callable
    descrizione: str
    permesso: str
    parametri: dict
    obbligatori: tuple = ()
    scrive: bool = False


_ID = {"id": {"type": "integer", "description": "Identificativo (dagli elenchi)"}}
STRUMENTI = {
    "dati_associazione": Strumento(
        dati_associazione,
        "Dati dell'associazione utili ai requisiti dei bandi: sede, RUNTS, "
        "codice fiscale, PEC, numero di soci attivi e in regola, rendiconto dell'anno precedente "
        "(solo numeri aggregati).",
        "progetti.view_bando",
        {},
    ),
    "finalita_e_criteri": Strumento(
        finalita_e_criteri,
        "Finalità statutarie dell'associazione e criteri di valutazione delle idee con i pesi.",
        "progetti.view_idea",
        {},
    ),
    "elenca_idee": Strumento(
        elenca_idee,
        "Idee e necessità con stato, priorità, finalità e media delle valutazioni.",
        "progetti.view_idea",
        {
            "stato": {
                "type": "string",
                "enum": ["aperte", "tutte", "nuova", "valutazione", "approvata", "accantonata"],
                "default": "aperte",
            }
        },
    ),
    "scheda_idea": Strumento(
        scheda_idea,
        "Un'idea: descrizione, bisogno, destinatari, costo stimato, finalità, "
        "valutazioni per criterio e discussione.",
        "progetti.view_idea",
        _ID,
        ("id",),
    ),
    "elenca_bandi": Strumento(
        elenca_bandi,
        "Bandi registrati con finanziatore, scadenza, contributo e finalità.",
        "progetti.view_bando",
        {
            "stato": {
                "type": "string",
                "enum": ["aperti", "tutti", "segnalato", "interessante", "partecipato", "scartato"],
                "default": "aperti",
            }
        },
    ),
    "scheda_bando": Strumento(
        scheda_bando,
        "Un bando: limiti economici, requisiti con l'esito verificato sui dati del "
        "gestionale, formulario e progetti candidati.",
        "progetti.view_bando",
        _ID,
        ("id",),
    ),
    "elenca_progetti": Strumento(
        elenca_progetti,
        "Progetti con stato, bando e finalità.",
        "progetti.view_progetto",
        {
            "stato": {
                "type": "string",
                "enum": [
                    "aperti",
                    "tutti",
                    "progettazione",
                    "candidato",
                    "finanziato",
                    "in_corso",
                    "chiuso",
                ],
                "default": "aperti",
            }
        },
    ),
    "scheda_progetto": Strumento(
        scheda_progetto,
        "Un progetto: quadro con obiettivi e indicatori, attività, partner, piano "
        "economico con i controlli del bando, testi della proposta e verifica della candidatura.",
        "progetti.view_progetto",
        _ID,
        ("id",),
    ),
    "bandi_da_vagliare": Strumento(
        bandi_da_vagliare,
        "Novità raccolte automaticamente dalle fonti, ancora da vagliare.",
        "progetti.gestisci_bandi",
        {},
    ),
    "aggiungi_commento": Strumento(
        aggiungi_commento,
        "Aggiunge alla discussione di un'idea o di un progetto un commento "
        "firmato «Assistente» (solo se abilitato). Non cambia nient'altro.",
        "progetti.view_idea",
        {
            "tipo": {"type": "string", "enum": ["idea", "progetto"]},
            **_ID,
            "testo": {"type": "string", "description": "Il commento, motivato"},
        },
        ("tipo", "id", "testo"),
        scrive=True,
    ),
}


def disponibili(utente, token):
    commenti = ConnettoreMCP.corrente().commenti_ammessi and token.commenti
    return {
        nome: s
        for nome, s in STRUMENTI.items()
        if utente.has_perm(s.permesso) and (commenti or not s.scrive)
    }


def descrizioni(utente, token):
    return [
        {
            "name": nome,
            "description": s.descrizione,
            "inputSchema": {
                "type": "object",
                "properties": s.parametri,
                "required": list(s.obbligatori),
                "additionalProperties": False,
            },
            "annotations": {"readOnlyHint": not s.scrive},
        }
        for nome, s in disponibili(utente, token).items()
    ]


def chiama(utente, token, nome, argomenti):
    from django.http import Http404

    strumento = disponibili(utente, token).get(nome)
    if strumento is None:
        raise ErroreStrumento(f"Strumento non disponibile: {nome}.")
    argomenti = {k: v for k, v in (argomenti or {}).items() if k in strumento.parametri}
    for obbligatorio in strumento.obbligatori:
        if obbligatorio not in argomenti:
            raise ErroreStrumento(f"Manca il parametro «{obbligatorio}».")
    if "id" in argomenti:
        try:
            argomenti["id"] = int(argomenti["id"])
        except (TypeError, ValueError) as e:
            raise ErroreStrumento("«id» deve essere un numero.") from e
    registra(
        Azione.CONSULTAZIONE if not strumento.scrive else Azione.MODIFICA,
        token,
        utente=utente,
        descrizione=f"MCP: {nome}",
        strumento=nome,
        argomenti=json.dumps(argomenti, ensure_ascii=False)[:500],
    )
    try:
        return strumento.funzione(utente, token=token, **argomenti)
    except Http404 as e:
        raise ErroreStrumento("Non trovato.") from e


# --- JSON-RPC ------------------------------------------------------------------------------------


def _risposta(id_, risultato=None, errore=None):
    corpo = {"jsonrpc": "2.0", "id": id_}
    if errore is not None:
        corpo["error"] = {"code": errore[0], "message": errore[1]}
    else:
        corpo["result"] = risultato
    return JsonResponse(corpo, json_dumps_params={"ensure_ascii": False})


def gestisci(messaggio, utente, token):
    metodo, id_ = messaggio.get("method"), messaggio.get("id")
    if id_ is None:  # notifica (es. notifications/initialized): nessuna risposta
        return HttpResponse(status=202)
    if metodo == "initialize":
        richiesta = (messaggio.get("params") or {}).get("protocolVersion")
        return _risposta(
            id_,
            {
                "protocolVersion": richiesta if richiesta in VERSIONI else VERSIONI[0],
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {
                    "name": "gestione-associazione-progetti",
                    "version": settings.APP_VERSIONE,
                },
                "instructions": ISTRUZIONI,
            },
        )
    if metodo == "ping":
        return _risposta(id_, {})
    if metodo == "tools/list":
        return _risposta(id_, {"tools": descrizioni(utente, token)})
    if metodo == "tools/call":
        params = messaggio.get("params") or {}
        try:
            dati = chiama(utente, token, params.get("name"), params.get("arguments"))
        except ErroreStrumento as e:
            return _risposta(id_, {"content": [{"type": "text", "text": str(e)}], "isError": True})
        testo = json.dumps(dati, ensure_ascii=False, indent=1, default=str)
        return _risposta(id_, {"content": [{"type": "text", "text": testo}], "isError": False})
    return _risposta(id_, errore=(-32601, f"Metodo non supportato: {metodo}"))


def _origine_ammessa(request):
    origine = request.headers.get("Origin")
    return not origine or urlsplit(origine).netloc == request.get_host()


@csrf_exempt
def endpoint(request):
    """POST /progetti/mcp/ con «Authorization: Bearer ga_mcp_…». Senza SSE: risposte JSON."""
    if not ConnettoreMCP.corrente().attivo:
        return HttpResponse("Connettore MCP non attivo.", status=404, content_type="text/plain")
    if request.method != "POST":
        r = HttpResponse(status=405)
        r["Allow"] = "POST"
        return r
    if not _origine_ammessa(request):
        return HttpResponse(status=403)
    token = token_da_richiesta(request)
    if token is None:
        r = JsonResponse({"error": "token mancante, non valido, scaduto o revocato"}, status=401)
        r["WWW-Authenticate"] = 'Bearer realm="mcp"'
        return r
    try:
        messaggio = json.loads(request.body or b"")
    except (ValueError, UnicodeDecodeError):
        return _risposta(None, errore=(-32700, "JSON non valido"))
    if not isinstance(messaggio, dict) or messaggio.get("jsonrpc") != "2.0":
        return _risposta(None, errore=(-32600, "Richiesta non valida (un solo messaggio JSON-RPC)"))
    adesso = timezone.now()
    if token.ultimo_uso is None or adesso - token.ultimo_uso > timedelta(minutes=5):
        TokenMCP.objects.filter(pk=token.pk).update(ultimo_uso=adesso)
    return gestisci(messaggio, token.utente, token)
