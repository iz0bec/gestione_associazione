# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Generazione di PDF da modelli HTML (WeasyPrint). Le risorse sono lette
# *              solo dai file statici e dal logo dell'organizzazione: nessun accesso in rete.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import mimetypes
from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles import finders
from django.http import HttpResponse
from django.template.loader import render_to_string

SCHEMA_INTERNO = "risorsa:"


class RisorsaNonConsentita(ValueError):
    pass


def _percorso_risorsa(url):
    """Converte 'risorsa:static/...' o 'risorsa:media/...' in un file locale verificato."""
    relativo = url.removeprefix(SCHEMA_INTERNO)
    if relativo.startswith("static/"):
        trovato = finders.find(relativo.removeprefix("static/"))
        if trovato:
            return Path(trovato)
        base = Path(settings.STATIC_ROOT)
        relativo = relativo.removeprefix("static/")
    elif relativo.startswith("media/"):
        base = Path(settings.MEDIA_ROOT)
        relativo = relativo.removeprefix("media/")
    else:
        raise RisorsaNonConsentita(url)
    percorso = (base / relativo).resolve()
    if not percorso.is_relative_to(base.resolve()) or not percorso.is_file():
        raise RisorsaNonConsentita(url)
    return percorso


def _fetcher_locale():
    """URL fetcher di WeasyPrint che consente solo risorse locali (niente http, file:, data:)."""
    from weasyprint.urls import URLFetcher, URLFetcherResponse

    class FetcherLocale(URLFetcher):
        def fetch(self, url, headers=None):
            if not url.startswith(SCHEMA_INTERNO):
                raise RisorsaNonConsentita(url)
            percorso = _percorso_risorsa(url)
            tipo = mimetypes.guess_type(percorso.name)[0] or "application/octet-stream"
            return URLFetcherResponse(
                url, body=percorso.read_bytes(), headers={"Content-Type": tipo}
            )

    return FetcherLocale()


def genera_pdf(template, contesto):
    """Restituisce i byte del PDF. Nei modelli: src="risorsa:static/..." o "risorsa:media/..."."""
    from weasyprint import HTML

    html = render_to_string(template, contesto)
    return HTML(string=html, url_fetcher=_fetcher_locale(), base_url=None).write_pdf()


def risposta_pdf(template, contesto, nome_file, *, scarica=False):
    risposta = HttpResponse(genera_pdf(template, contesto), content_type="application/pdf")
    modo = "attachment" if scarica else "inline"
    risposta["Content-Disposition"] = f'{modo}; filename="{nome_file}"'
    return risposta
