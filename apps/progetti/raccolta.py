# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Raccolta automatica dei bandi (P3): feed RSS/Atom e pagine web sorvegliate,
# *              filtro per parole chiave, proposte da vagliare. Scaricamento solo con il
# *              trasporto sicuro (HTTPS verificato, indirizzi pubblici, limiti), XML letto
# *              con defusedxml.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import html
import logging
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from defusedxml import ElementTree
from django.db import transaction
from django.utils import timezone
from django.utils.html import strip_tags

from apps.core.audit import Azione, registra

from .models import Bando, BandoProposto, FonteBandi, ParolaChiave

log = logging.getLogger(__name__)

MASSIMO_PER_FONTE = 50
REINDIRIZZAMENTI = 3
ATOM = "{http://www.w3.org/2005/Atom}"
RSS1 = "{http://purl.org/rss/1.0/}"
DC = "{http://purl.org/dc/elements/1.1/}"

# portali verificati (novembre 2026): indirizzo del feed e cosa contiene
PORTALI = {
    "regione-basilicata": (
        "Regione Basilicata – Avvisi e bandi",
        "https://portalebandi.regione.basilicata.it/avvisi-e-bandi/feed/",
        False,
        "Tutti gli avvisi della Regione (anche per imprese e personale): servono le parole chiave.",
    ),
    "csv-basilicata": (
        "CSV Basilicata – Bandi",
        "https://www.csvbasilicata.it/category/bandi/feed/",
        True,
        "Bandi e opportunità per il volontariato e il Terzo settore segnalati dal CSV.",
    ),
    "fondazione-con-il-sud": (
        "Fondazione con il Sud",
        "https://www.fondazioneconilsud.it/feed/",
        False,
        "Notizie e bandi della Fondazione: servono le parole chiave.",
    ),
}

PAROLE_SUGGERITE = [
    "terzo settore", "volontariato", "promozione sociale", "associazioni", "comunità", "memoria",
    "storia", "cultura", "patrimonio culturale", "monumenti", "giovani", "scuole", "legalità",
    "pace", "cittadinanza attiva", "anziani",
]  # fmt: skip
ESCLUSE_SUGGERITE = [
    "concessione demaniale", "personale della regione", "affidamento del servizio", "fornitura di",
    "per le imprese", "libri di testo", "concorso", "master",
]  # fmt: skip


class ErroreRaccolta(Exception):
    pass


@dataclass
class Novita:
    titolo: str
    link: str
    sommario: str = ""
    data: datetime | None = None


# --- scaricamento --------------------------------------------------------------------------------


def scarica(url):
    """(contenuto, tipo) dell'indirizzo, seguendo pochi reindirizzamenti, ognuno ricontrollato."""
    from apps.collegamenti.trasporto import Destinazione, ErroreTrasporto, richiesta

    for _ in range(REINDIRIZZAMENTI + 1):
        parti = urlsplit(url)
        if parti.scheme != "https":
            raise ErroreRaccolta("Sono ammessi solo indirizzi https.")
        percorso = (parti.path or "/") + (f"?{parti.query}" if parti.query else "")
        dest = Destinazione(url=f"https://{parti.netloc}")
        try:
            r = richiesta(dest, "GET", percorso, {
                "Accept": "application/rss+xml, application/atom+xml, application/xml, "
                          "text/xml, text/html;q=0.9, */*;q=0.5",
                "User-Agent": "GestioneAssociazione-Bandi/1",
            })  # fmt: skip
        except ErroreTrasporto as e:
            raise ErroreRaccolta(str(e)) from e
        if r.stato in (301, 302, 303, 307, 308) and r.intestazioni.get("location"):
            url = urljoin(url, r.intestazioni["location"])
            continue
        if r.stato != 200:
            raise ErroreRaccolta(f"Risposta {r.stato} da {parti.netloc}.")
        return r.corpo, r.intestazioni.get("content-type", "")
    raise ErroreRaccolta("Troppi reindirizzamenti.")


# --- lettura -------------------------------------------------------------------------------------


def _testo(valore, massimo=2000):
    testo = html.unescape(strip_tags(valore or ""))
    return re.sub(r"\s+", " ", testo).strip()[:massimo]


def _data(valore):
    if not valore:
        return None
    valore = valore.strip()
    try:
        d = parsedate_to_datetime(valore)
    except (TypeError, ValueError, IndexError):
        try:
            d = datetime.fromisoformat(valore.replace("Z", "+00:00"))
        except ValueError:
            return None
    return d if timezone.is_aware(d) else timezone.make_aware(d)


def leggi_feed(contenuto):
    """Novità di un feed RSS 2.0, RSS 1.0 (RDF) o Atom."""
    try:
        radice = ElementTree.fromstring(contenuto)
    except ElementTree.ParseError as e:
        raise ErroreRaccolta("Il contenuto non è un feed leggibile.") from e
    except Exception as e:  # noqa: BLE001 - defusedxml rifiuta entità e DTD pericolose
        raise ErroreRaccolta("Feed rifiutato (contenuto XML non sicuro).") from e
    novita = []
    for item in [*radice.iter("item"), *radice.iter(f"{RSS1}item")]:
        ns = RSS1 if item.tag.startswith(RSS1) else ""
        novita.append(Novita(
            titolo=_testo(item.findtext(f"{ns}title"), 500),
            link=(item.findtext(f"{ns}link") or "").strip(),
            sommario=_testo(item.findtext(f"{ns}description")),
            data=_data(item.findtext("pubDate") or item.findtext(f"{DC}date")),
        ))  # fmt: skip
    for entry in radice.iter(f"{ATOM}entry"):
        link = ""
        for el in entry.findall(f"{ATOM}link"):
            if el.get("rel", "alternate") == "alternate":
                link = el.get("href", "")
                break
        novita.append(Novita(
            titolo=_testo(entry.findtext(f"{ATOM}title"), 500), link=link.strip(),
            sommario=_testo(entry.findtext(f"{ATOM}summary") or entry.findtext(f"{ATOM}content")),
            data=_data(entry.findtext(f"{ATOM}published") or entry.findtext(f"{ATOM}updated")),
        ))  # fmt: skip
    return [n for n in novita if n.titolo and n.link.startswith(("https://", "http://"))]


class _Collegamenti(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.trovati, self._href, self._testo = [], None, []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href, self._testo = dict(attrs).get("href"), []

    def handle_data(self, data):
        if self._href is not None:
            self._testo.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.trovati.append((self._href, " ".join(self._testo)))
            self._href = None


def _decodifica(contenuto, tipo):
    m = re.search(r"charset=([\w-]+)", tipo or "", re.IGNORECASE)
    try:
        return contenuto.decode(m.group(1) if m else "utf-8", errors="replace")
    except LookupError:
        return contenuto.decode("utf-8", errors="replace")


def leggi_pagina(contenuto, tipo, base):
    """Collegamenti di una pagina con un testo significativo (si scartano menu e icone)."""
    parser = _Collegamenti()
    parser.feed(_decodifica(contenuto, tipo))
    visti, novita = set(), []
    for href, testo in parser.trovati:
        testo = _testo(testo, 500)
        if not href or len(testo) < 15 or href.startswith(("#", "mailto:", "javascript:")):
            continue
        link = urljoin(base, href).split("#")[0]
        if link.startswith(("https://", "http://")) and link not in visti:
            visti.add(link)
            novita.append(Novita(titolo=testo, link=link))
    return novita


# --- parole chiave -------------------------------------------------------------------------------


def normalizza(testo):
    """Minuscole, senza accenti; la punteggiatura (anche gli apostrofi tipografici) è uno spazio."""
    senza = unicodedata.normalize("NFKD", testo or "")
    senza = "".join(c for c in senza if not unicodedata.combining(c))
    senza = re.sub(r"[^\w]+", " ", senza.lower())
    return senza.encode("ascii", "ignore").decode().strip()


def _elenco(testo):
    return [p.strip() for p in (testo or "").replace(";", ",").split(",") if p.strip()]


def _trovata(parola, testo_normalizzato):
    return re.search(rf"\b{re.escape(normalizza(parola))}\b", testo_normalizzato) is not None


def escluso(testo, escludi):
    t = normalizza(testo)
    return any(_trovata(p, t) for p in escludi)


def corrisponde(testo, includi, escludi):
    """(interessante, parole trovate): basta una parola esclusa per scartare."""
    if escluso(testo, escludi):
        return False, []
    t = normalizza(testo)
    trovate = [p for p in includi if _trovata(p, t)]
    return bool(trovate), trovate


# --- raccolta ------------------------------------------------------------------------------------


def _gia_noto(link):
    return (
        BandoProposto.objects.filter(link=link).exists() or Bando.objects.filter(link=link).exists()
    )


def raccogli(fonte):
    """Controlla una fonte e registra le novità interessanti. Restituisce quante sono nuove."""
    parole = ParolaChiave.objects.all()
    includi = [p.parola for p in parole if not p.esclusa] + _elenco(fonte.parole_chiave)
    escludi = [p.parola for p in parole if p.esclusa]
    nuove = 0
    try:
        if not fonte.tutte and not includi:
            raise ErroreRaccolta("Nessuna parola chiave: aggiungerne o scegliere «proponi tutto».")
        contenuto, tipo = scarica(fonte.indirizzo)
        if fonte.tipo == FonteBandi.Tipo.FEED:
            novita = leggi_feed(contenuto)
        else:
            novita = leggi_pagina(contenuto, tipo, fonte.indirizzo)
        for n in novita[: MASSIMO_PER_FONTE * 4]:
            if nuove >= MASSIMO_PER_FONTE or _gia_noto(n.link[:1000]):
                continue
            testo = f"{n.titolo} {n.sommario}"
            ok, trovate = corrisponde(testo, includi, escludi)
            if fonte.tutte:
                ok = not escluso(testo, escludi)
            if not ok:
                continue
            BandoProposto.objects.create(
                fonte=fonte, titolo=n.titolo, link=n.link[:1000], sommario=n.sommario,
                pubblicato_il=n.data, parole=", ".join(trovate)[:255],
            )  # fmt: skip
            nuove += 1
        esito = f"{len(novita)} elementi letti, {nuove} propost{'a' if nuove == 1 else 'e'}."
        fonte.errori = 0
    except ErroreRaccolta as e:
        esito = str(e)
        fonte.errori += 1
        log.warning("Fonte dei bandi %s: %s", fonte, e)
    fonte.ultimo_controllo, fonte.ultimo_esito = timezone.now(), esito[:255]
    fonte.save(update_fields=["ultimo_controllo", "ultimo_esito", "errori"])
    return nuove


def raccogli_tutte():
    """Tutte le fonti attive; avvisa chi gestisce i bandi se ci sono novità. Rieseguibile."""
    from django.conf import settings
    from django.urls import reverse

    from apps.core import avvisi

    totale = sum(raccogli(f) for f in FonteBandi.objects.filter(attiva=True))
    if totale:
        testo = f"Bandi da vagliare: {totale} nuov{'o' if totale == 1 else 'i'} dalle fonti."
        if settings.URL_PUBBLICO:
            testo += f"\n{settings.URL_PUBBLICO}{reverse('progetti:proposte')}"
        avvisi.avvisa("bandi", testo)
    return totale


# --- vaglio --------------------------------------------------------------------------------------


@transaction.atomic
def accogli(proposta, utente):
    """La proposta diventa un bando «da valutare» (o si collega a quello con lo stesso link)."""
    if proposta.stato != BandoProposto.Stato.NUOVO:
        raise ErroreRaccolta("Proposta già esaminata.")
    bando = Bando.objects.filter(link=proposta.link[:500]).first()
    if bando is None:
        bando = Bando.objects.create(
            titolo=proposta.titolo[:255], link=proposta.link[:500], descrizione=proposta.sommario,
            finanziatore_testo=(proposta.fonte.nome if proposta.fonte else "")[:200],
            creato_da=utente, modificato_da=utente,
        )  # fmt: skip
        registra(Azione.CREAZIONE, bando, utente=utente, origine="raccolta automatica")
    proposta.stato, proposta.bando = BandoProposto.Stato.ACCOLTO, bando
    proposta.esaminato_da, proposta.esaminato_il = utente, timezone.now()
    proposta.save(update_fields=["stato", "bando", "esaminato_da", "esaminato_il"])
    return bando


def scarta(proposte, utente):
    """Scarta una o più proposte ancora da vagliare. Restituisce quante."""
    return BandoProposto.objects.filter(
        pk__in=[p.pk for p in proposte], stato=BandoProposto.Stato.NUOVO
    ).update(stato=BandoProposto.Stato.SCARTATO, esaminato_da=utente, esaminato_il=timezone.now())


def aggiungi_portale(chiave, utente):
    if chiave not in PORTALI:
        raise ErroreRaccolta("Portale sconosciuto.")
    nome, indirizzo, tutte, _ = PORTALI[chiave]
    fonte, nuova = FonteBandi.objects.get_or_create(
        indirizzo=indirizzo, defaults={"nome": nome, "tutte": tutte}
    )
    if nuova:
        registra(Azione.CREAZIONE, fonte, utente=utente)
    return fonte, nuova


def aggiungi_parole_suggerite(utente):
    n = 0
    for parola in PAROLE_SUGGERITE:
        n += ParolaChiave.objects.get_or_create(parola=parola)[1]
    for parola in ESCLUSE_SUGGERITE:
        n += ParolaChiave.objects.get_or_create(parola=parola, defaults={"esclusa": True})[1]
    return n
