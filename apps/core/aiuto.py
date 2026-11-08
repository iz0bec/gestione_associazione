# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Help in linea: il manuale operativo (docs/operativo/*.md) mostrato
# *              nell'applicazione, con la pagina giusta per la sezione in cui si trova l'utente.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import re
from functools import lru_cache
from pathlib import Path

import markdown
from django.conf import settings
from django.http import Http404
from django.urls import reverse

CARTELLA = Path(settings.BASE_DIR) / "docs" / "operativo"
INDICE = "README"
_RE_PAGINA = re.compile(r"^[a-z0-9-]+$")
_RE_COMMENTO = re.compile(r"<!--.*?-->", re.S)
_RE_LINK = re.compile(r'href="([^"#]*?)\.md(#[^"]*)?"')
_RE_LINK_ESTERNO = re.compile(r'<a href="(\.\./[^"]*)">(.*?)</a>', re.S)
# immagini del manuale: ![didascalia](immagini/nome.jpg) -> static/img/manuale/nome.jpg
_RE_IMMAGINE = re.compile(
    r'(?:<p>)?<img alt="([^"]*)" src="immagini/([a-z0-9-]+\.(?:jpg|png))" ?/?>(?:</p>)?'
)
CARTELLA_IMMAGINI = "img/manuale/"

# namespace (o namespace:nome della vista) -> pagina[#paragrafo]
PAGINE_PER_SEZIONE = {
    "anagrafica": "anagrafica",
    "soci": "soci",
    "soci:sezioni": "sistema#sezioni",
    "soci:sezione_nuova": "sistema#sezioni",
    "soci:sezione_modifica": "sistema#sezioni",
    "protocollo": "protocollo",
    "organi": "organi",
    "comunicazioni": "comunicazioni",
    "tesoreria": "tesoreria",
    "patrimonio": "patrimonio",
    "documenti": "documenti",
    "calendario": "calendario",
    "utenti": "utenti",
    "core:servizi_posta": "sistema#servizi-di-posta",
    "core:cruscotto": "primi-passi",
    "core:aiuto": INDICE,
    "core:aiuto_pagina": INDICE,
    "core:informazioni": INDICE,
    "core": "sistema",
    "configurazione": "configurazione-iniziale",
}


def pagina_per(request):
    """Pagina dell'help (con eventuale paragrafo) per la vista che sta mostrando la richiesta."""
    match = getattr(request, "resolver_match", None)
    if match is None:
        return INDICE
    chiave = f"{match.namespace}:{match.url_name}"
    return (
        PAGINE_PER_SEZIONE.get(chiave)
        or PAGINE_PER_SEZIONE.get(match.namespace)
        or PAGINE_PER_SEZIONE.get(match.url_name or "")
        or INDICE
    )


def url_per(request):
    pagina, _, paragrafo = pagina_per(request).partition("#")
    url = reverse("core:aiuto_pagina", args=[pagina]) if pagina != INDICE else reverse("core:aiuto")
    return f"{url}#{paragrafo}" if paragrafo else url


def _percorso(pagina):
    if not _RE_PAGINA.fullmatch(pagina) and pagina != INDICE:
        raise Http404("Pagina dell'aiuto inesistente.")
    percorso = CARTELLA / f"{pagina}.md"
    if not percorso.is_file():
        raise Http404("Pagina dell'aiuto inesistente.")
    return percorso


def _collegamenti(html):
    """Collegamenti fra le pagine del manuale -> pagine dell'help; quelli verso altri manuali
    (es. ../sistema/...) diventano testo semplice."""

    def interno(m):
        nome = m.group(1)
        if "/" in nome or not _RE_PAGINA.fullmatch(nome):
            return m.group(0)
        url = reverse("core:aiuto") if nome == INDICE else reverse("core:aiuto_pagina", args=[nome])
        return f'href="{url}{m.group(2) or ""}"'

    html = _RE_LINK.sub(interno, html)
    return _RE_LINK_ESTERNO.sub(lambda m: f"<span>{m.group(2)}</span>", html)


@lru_cache(maxsize=64)
def _rendi(percorso, _mtime):
    testo = _RE_COMMENTO.sub("", percorso.read_text(encoding="utf-8"))
    md = markdown.Markdown(extensions=["tables", "fenced_code", "toc", "sane_lists"],
                           extension_configs={"toc": {"permalink": False}})  # fmt: skip
    html = md.convert(testo)
    html = html.replace("<table>", '<table class="table table-sm table-bordered">')
    titolo = next((t["name"] for t in md.toc_tokens), percorso.stem)
    indice = [(t["id"], t["name"]) for t in (md.toc_tokens[0]["children"] if md.toc_tokens else [])]
    return titolo, _collegamenti(html), indice


def licenze():
    """Tabelle delle licenze di terze parti (pagina dei crediti)."""
    percorso = Path(settings.BASE_DIR) / "docs" / "sistema" / "licenze-terze-parti.md"
    if not percorso.is_file():
        return ""
    return _rendi(percorso, percorso.stat().st_mtime)[1]


_RE_VERSIONE = re.compile(r"^## \[(?P<versione>[^\]]+)\](?:\s*-\s*(?P<data>\S+))?\s*$", re.M)


def _data_italiana(iso):
    a, _, resto = (iso or "").partition("-")
    m, _, g = resto.partition("-")
    return f"{g}/{m}/{a}" if a and m and g else (iso or "")


@lru_cache(maxsize=4)
def _novita(percorso, _mtime, quante):
    testo = _RE_COMMENTO.sub("", percorso.read_text(encoding="utf-8"))
    titoli = list(_RE_VERSIONE.finditer(testo))
    versioni = []
    for i, m in enumerate(titoli):
        fine = titoli[i + 1].start() if i + 1 < len(titoli) else len(testo)
        corpo = testo[m.end() : fine].strip()
        if not corpo:  # «Non rilasciato» vuoto
            continue
        html = markdown.markdown(corpo, extensions=["sane_lists"])
        for livello in ("h3", "h4"):  # sezioni (Aggiunto, Corretto...) più piccole
            html = html.replace(f"<{livello}>", '<h4 class="mt-3 mb-1">').replace(
                f"</{livello}>", "</h4>"
            )
        sviluppo = m["versione"].lower() == "non rilasciato"
        versioni.append({
            "versione": "In sviluppo" if sviluppo else m["versione"],
            "data": _data_italiana(m["data"]),
            "html": html,
        })  # fmt: skip
        if len(versioni) == quante:
            break
    return versioni


def novita(quante=5):
    """Ultime versioni del CHANGELOG (la più recente per prima), già convertite in HTML."""
    percorso = Path(settings.BASE_DIR) / "CHANGELOG.md"
    if not percorso.is_file():
        return []
    return _novita(percorso, percorso.stat().st_mtime, quante)


def _immagini(html, sorgente):
    """Figure con didascalia; `sorgente(nome)` dà l'indirizzo dell'immagine (web o PDF)."""

    def figura(m):
        didascalia, nome = m.group(1), m.group(2)
        return (f'<figure class="figura-manuale"><img src="{sorgente(nome)}" alt="{didascalia}" '
                f'loading="lazy"><figcaption>{didascalia}</figcaption></figure>')  # fmt: skip

    return _RE_IMMAGINE.sub(figura, html)


def _url_immagine(nome):
    from django.templatetags.static import static

    return static(CARTELLA_IMMAGINI + nome)


def pagina(nome):
    """(titolo, html, indice dei paragrafi) di una pagina del manuale operativo."""
    percorso = _percorso(nome)
    titolo, html, indice = _rendi(percorso, percorso.stat().st_mtime)
    return titolo, _immagini(html, _url_immagine), indice


# --- manuale in PDF ---------------------------------------------------------------------------


def _firma_manuale():
    """Cambia quando cambiano testi, immagini o versione: il PDF si rigenera solo allora."""
    import hashlib

    from django.contrib.staticfiles import finders

    parti = [settings.APP_VERSIONE]
    for f in sorted(CARTELLA.glob("*.md")):
        parti.append(f"{f.name}:{f.stat().st_mtime_ns}")
    cartella = finders.find(CARTELLA_IMMAGINI.rstrip("/"))
    if cartella:
        for f in sorted(Path(cartella).iterdir()):
            parti.append(f"{f.name}:{f.stat().st_mtime_ns}")
    return hashlib.sha256("|".join(parti).encode()).hexdigest()[:16]


def capitoli():
    """(nome, titolo, html per il PDF) delle pagine nell'ordine dell'indice."""
    risultato = []
    for nome, _titolo in elenco():
        percorso = _percorso(nome)
        titolo, html, _indice = _rendi(percorso, percorso.stat().st_mtime)
        html = _immagini(html, lambda n: f"risorsa:static/{CARTELLA_IMMAGINI}{n}")
        # i collegamenti fra pagine diventano rimandi interni al PDF
        html = re.sub(r'href="/aiuto/([a-z0-9-]+)/(#[^"]*)?"', r'href="#capitolo-\1"', html)
        html = html.replace('href="/aiuto/"', 'href="#indice"')
        risultato.append((nome, titolo, html))
    return risultato


def pdf_manuale():
    """Percorso del PDF del manuale completo (generato e conservato finché non cambia)."""
    from django.utils import timezone

    from .models import Organizzazione
    from .pdf import genera_pdf

    cartella = Path(settings.MEDIA_ROOT) / "manuale"
    cartella.mkdir(parents=True, exist_ok=True)
    destinazione = cartella / f"manuale-{_firma_manuale()}.pdf"
    if not destinazione.is_file():
        contesto = {"capitoli": capitoli(), "organizzazione": Organizzazione.corrente(),
                    "versione": settings.APP_VERSIONE, "oggi": timezone.localdate()}  # fmt: skip
        temporaneo = destinazione.with_suffix(".tmp")
        temporaneo.write_bytes(genera_pdf("core/pdf/manuale.html", contesto))
        temporaneo.replace(destinazione)
        for vecchio in cartella.glob("manuale-*.pdf"):
            if vecchio != destinazione:
                vecchio.unlink(missing_ok=True)
    return destinazione


def elenco():
    """Pagine nell'ordine dell'indice del manuale."""
    testo = _percorso(INDICE).read_text(encoding="utf-8")
    pagine = []
    for nome in re.findall(r"\]\(([a-z0-9-]+)\.md\)", testo):
        if nome not in (p for p, _ in pagine) and (CARTELLA / f"{nome}.md").is_file():
            pagine.append((nome, pagina(nome)[0]))
    return pagine
