# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Schermate del manuale (static/img/manuale/*.jpg) prese con Chrome tramite
# *              Playwright da un server con i dati dimostrativi (scripts/manuale/dati_demo.py).
# *              Uso: uv run python scripts/manuale/schermate.py http://127.0.0.1:8010
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
# ruff: noqa: T201, E501

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:8010"
USCITA = Path(__file__).resolve().parents[2] / "static" / "img" / "manuale"
UTENTE, PASSWORD = "demo", "Demo-Manuale-2026"

# nome del file -> (indirizzo, selettore da attendere o None, pagina intera)
SCHERMATE = {
    "cruscotto": ("/", None, False),
    "anagrafica": ("/anagrafica/", "#tabella-soggetti", False),
    "scheda-anagrafica": ("@scheda", None, False),
    "soci": ("/soci/", None, False),
    "scheda-socio": ("@socio", None, False),
    "tesseramento": ("/soci/tessere/", None, False),
    "incasso-quote": ("/soci/tessere/incasso/", None, False),
    "sezioni": ("/soci/sezioni/", None, False),
    "protocollo": ("/protocollo/", None, False),
    "posta": ("/protocollo/posta/", None, False),
    "organi": ("/organi/", None, False),
    "organo": ("@organo", None, False),
    "calendario": ("/calendario/", None, False),
    "calendario-mese": ("/calendario/mese/", None, False),
    "comunicazioni": ("/comunicazioni/", None, False),
    "tesoreria": ("/tesoreria/", None, False),
    "documenti": ("/documenti/", None, False),
    "utenti": ("/sistema/utenti/", None, False),
    "servizi-posta": ("/sistema/posta/", None, False),
    "documenti-pubblici": ("/sistema/documenti-pubblici/", None, False),
}


def primo_link(pagina, elenco, prefisso):
    pagina.goto(BASE + elenco)
    return pagina.locator(f'a[href^="{prefisso}"]').evaluate_all(
        "(a) => a.map(x => x.getAttribute('href')).filter(h => /\\/\\d+\\/$/.test(h))"
    )[0]


def consiglio(pagina):
    """Il Consiglio direttivo dell'associazione (il primo dell'elenco, prima delle sezioni)."""
    pagina.goto(BASE + "/organi/")
    return pagina.locator("a.card-link", has_text="Consiglio direttivo").first.get_attribute("href")


def main():
    USCITA.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        contesto = browser.new_context(viewport={"width": 1366, "height": 820}, locale="it-IT",
                                       color_scheme="light", device_scale_factor=1)  # fmt: skip
        pagina = contesto.new_page()
        # pagina di accesso (prima di entrare)
        pagina.goto(BASE + "/account/login/")
        pagina.screenshot(path=USCITA / "accesso.jpg", type="jpeg", quality=82)
        pagina.fill('input[name="login"]', UTENTE)
        pagina.fill('input[name="password"]', PASSWORD)
        pagina.click('button[type="submit"]')
        pagina.wait_for_url(BASE + "/")
        speciali = {
            "@scheda": lambda: primo_link(pagina, "/anagrafica/?q=rossi", "/anagrafica/"),
            "@socio": lambda: primo_link(pagina, "/soci/?q=rossi", "/soci/"),
            "@organo": lambda: consiglio(pagina),
        }
        for nome, (indirizzo, attesa, intera) in SCHERMATE.items():
            if indirizzo.startswith("@"):
                indirizzo = speciali[indirizzo]()
            pagina.goto(BASE + indirizzo)
            pagina.wait_for_load_state("networkidle")
            if attesa:
                pagina.wait_for_selector(attesa)
            pagina.screenshot(
                path=USCITA / f"{nome}.jpg", type="jpeg", quality=82, full_page=intera
            )
            print("ok", nome, indirizzo)
        # pagina pubblica dei documenti (senza accesso)
        pubblica = browser.new_context(
            viewport={"width": 1366, "height": 820}, locale="it-IT"
        ).new_page()
        pubblica.goto(BASE + "/documenti-pubblici/")
        pubblica.screenshot(path=USCITA / "documenti-pubblici-pagina.jpg", type="jpeg", quality=82)
        browser.close()
    print("Schermate in", USCITA)


if __name__ == "__main__":
    main()
