# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Ricerca globale: persone, soci, protocolli, riunioni, delibere, beni,
# *              appuntamenti e comunicazioni, solo nei moduli che l'utente può consultare
# *              (soci della propria sezione, protocolli riservati solo con il permesso).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from dataclasses import dataclass, field
from urllib.parse import urlencode

from django.db.models import Q
from django.urls import reverse

MINIMO = 2  # caratteri


@dataclass
class Voce:
    titolo: str
    url: str
    dettaglio: str = ""


@dataclass
class Gruppo:
    titolo: str
    icona: str
    voci: list = field(default_factory=list)
    totale: int = 0
    tutti: str = ""  # elenco completo nel modulo, se esiste


def _parole(testo):
    return [p for p in testo.split() if p]


def _tutte(campi, testo):
    """Ogni parola deve comparire in almeno uno dei campi."""
    filtro = Q()
    for parola in _parole(testo):
        una = Q()
        for c in campi:
            una |= Q(**{f"{c}__icontains": parola})
        filtro &= una
    return filtro


def _gruppo(titolo, icona, qs, per_voce, quanti, tutti=""):
    totale = qs.count()
    if not totale:
        return None
    return Gruppo(titolo, icona, [per_voce(o) for o in qs[:quanti]], totale, tutti)


def _con_q(nome_url, testo, **altri):
    return f"{reverse(nome_url)}?{urlencode({'q': testo, **altri})}"


def _anagrafica(utente, testo, quanti):
    from apps.anagrafica.models import Soggetto

    qs = Soggetto.objects.ricerca(testo).order_by("-attivo", "cognome", "nome", "denominazione")

    def voce(s):
        parti = [s.get_tipo_display() if not s.is_persona else "", s.qualifica, s.comune, s.email]
        dettaglio = " · ".join(p for p in parti if p)
        return Voce(
            s.nome_completo + ("" if s.attivo else " (archiviata)"), s.get_absolute_url(), dettaglio
        )

    return _gruppo(
        "Anagrafica",
        "address-book",
        qs,
        voce,
        quanti,
        _con_q("anagrafica:elenco", testo, stato="tutti"),
    )


def _soci(utente, testo, quanti):
    from apps.soci import sezioni
    from apps.soci.filtri import SocioFilter
    from apps.soci.models import Socio

    base = sezioni.filtra(Socio.objects.select_related("soggetto", "sezione"), utente)
    qs = SocioFilter().filtra_testo(base, "q", testo).order_by("numero")

    def voce(s):
        parti = [
            f"socio n. {s.numero}",
            s.sezione.nome if s.sezione_id else "",
            s.get_stato_display().lower(),
        ]
        return Voce(
            s.soggetto.nome_completo, s.get_absolute_url(), " · ".join(p for p in parti if p)
        )

    return _gruppo("Soci", "users-group", qs.distinct(), voce, quanti, _con_q("soci:elenco", testo))


def _protocolli(utente, testo, quanti):
    from apps.protocollo.filtri import ProtocolloFilter
    from apps.protocollo.models import Protocollo

    base = Protocollo.objects.visibili_a(utente)
    qs = ProtocolloFilter().filtra_testo(base, "q", testo).order_by("-anno", "-numero")

    def voce(p):
        stato = " · annullato" if p.annullato else ""
        return Voce(
            f"{p.segnatura} - {p.oggetto}",
            p.get_absolute_url(),
            f"{p.get_direzione_display()} del {p.registrato_il:%d/%m/%Y}{stato}",
        )

    return _gruppo(
        "Protocollo",
        "file-certificate",
        qs.distinct(),
        voce,
        quanti,
        _con_q("protocollo:elenco", testo),
    )


def _riunioni(utente, testo, quanti):
    from apps.organi.models import Riunione

    filtro = _tutte(["organo__nome", "luogo", "punti__titolo", "premessa"], testo)
    qs = Riunione.objects.filter(filtro).select_related("organo").distinct()

    def voce(r):
        return Voce(
            r.titolo,
            r.get_absolute_url(),
            f"{r.prima_convocazione:%d/%m/%Y} · {r.get_stato_display().lower()}",
        )

    return _gruppo("Riunioni", "calendar-event", qs.order_by("-prima_convocazione"), voce, quanti)


def _delibere(utente, testo, quanti):
    from apps.organi.models import Delibera

    qs = Delibera.objects.filter(_tutte(["oggetto", "testo"], testo)).select_related(
        "verbale__riunione__organo"
    )

    def voce(d):
        return Voce(str(d), d.verbale.get_absolute_url(), str(d.verbale.riunione.organo))

    return _gruppo("Delibere", "gavel", qs, voce, quanti, _con_q("organi:delibere", testo))


def _beni(utente, testo, quanti):
    from apps.patrimonio.models import Bene
    from apps.patrimonio.views import BeneFilter

    qs = BeneFilter().cerca(Bene.objects.all(), "q", testo).order_by("numero")

    def voce(b):
        return Voce(f"{b.codice} - {b.nome}", b.get_absolute_url(), b.get_stato_display())

    return _gruppo(
        "Patrimonio",
        "building-warehouse",
        qs,
        voce,
        quanti,
        _con_q("patrimonio:inventario", testo, stato="tutti"),
    )


def _appuntamenti(utente, testo, quanti):
    from apps.calendario.models import Appuntamento

    qs = Appuntamento.objects.filter(_tutte(["titolo", "luogo", "descrizione"], testo))

    def voce(a):
        return Voce(
            a.titolo,
            a.get_absolute_url(),
            f"{a.get_tipo_display()} del {a.giorno:%d/%m/%Y}"
            + (" · annullato" if a.annullato else ""),
        )

    return _gruppo("Calendario", "calendar", qs.order_by("-giorno"), voce, quanti)


def _comunicazioni(utente, testo, quanti):
    from apps.comunicazioni.models import Invio

    qs = Invio.objects.filter(_tutte(["oggetto", "corpo"], testo)).order_by("-creato_il")

    def voce(i):
        return Voce(
            i.oggetto,
            i.get_absolute_url(),
            f"{i.creato_il:%d/%m/%Y} · {i.get_stato_display().lower()}",
        )

    return _gruppo("Comunicazioni", "mail", qs, voce, quanti)


FONTI = [
    ("anagrafica.view_soggetto", _anagrafica),
    ("soci.view_socio", _soci),
    ("protocollo.view_protocollo", _protocolli),
    ("organi.view_riunione", _riunioni),
    ("organi.view_delibera", _delibere),
    ("patrimonio.view_bene", _beni),
    ("calendario.view_appuntamento", _appuntamenti),
    ("comunicazioni.view_invio", _comunicazioni),
]


def troppo_corto(testo):
    """Un numero (di socio, di protocollo) va bene anche di una cifra."""
    return 0 < len(testo) < MINIMO and not testo.isdigit()


def cerca(utente, testo, quanti=8):
    """Gruppi di risultati (solo quelli non vuoti) nei moduli consentiti all'utente."""
    testo = " ".join((testo or "").split())
    if troppo_corto(testo) or not testo:
        return []
    gruppi = []
    for permesso, fonte in FONTI:
        if utente.has_perm(permesso):
            gruppo = fonte(utente, testo, quanti)
            if gruppo:
                gruppi.append(gruppo)
    return gruppi
