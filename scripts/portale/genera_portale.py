#!/usr/bin/env python3
# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Portale dei servizi: pagina statica che elenca le installazioni del gestionale
# *              (federazione, sezioni...) con i servizi attivi e i recapiti, letti dalla scheda
# *              pubblica di ciascuna (/.well-known/gestione-associazione). Solo libreria standard;
# *              se un'installazione non risponde si usano i dati dell'ultima lettura riuscita.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
"""Uso: genera_portale.py portale.toml --uscita /var/www/portale

La configurazione (vedi esempio.toml) indica testi, colori, immagini e le installazioni per livello
e gruppo; tutto il resto (servizi attivi, recapiti) arriva dai gestionali.
"""

import argparse
import json
import re
import shutil
import sys
import tomllib
import urllib.request
from datetime import datetime
from html import escape
from pathlib import Path

SCHEDA = "/.well-known/gestione-associazione"
TIMEOUT = 15
COLORI = {"testata": "#0e2525", "accento": "#a0876e", "sfondo": "#f1ede6"}
ICONE = """<svg xmlns="http://www.w3.org/2000/svg" class="icone" width="0" height="0" aria-hidden="true">
<symbol id="i-mail" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-width="1.8" d="M3 6h18v12H3zM3 7l9 6 9-6"/></symbol>
<symbol id="i-pec" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-width="1.8" d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6zM9 12l2 2 4-4"/></symbol>
<symbol id="i-tel" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-width="1.8" d="M5 4h4l2 5-2.5 1.5a11 11 0 005 5L15 13l5 2v4a2 2 0 01-2 2A16 16 0 013 6a2 2 0 012-2z"/></symbol>
<symbol id="i-web" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 010 18M12 3a14 14 0 000 18"/></g></symbol>
<symbol id="i-sede" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 21s-7-6.2-7-11a7 7 0 0114 0c0 4.8-7 11-7 11z"/><circle cx="12" cy="10" r="2.5"/></g></symbol>
<symbol id="i-vai" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-width="2" d="M7 17L17 7M9 7h8v8"/></symbol>
</svg>"""  # noqa: E501
GUIDA = [
    ("Gestionale", "Accesso riservato a dirigenti e operatori incaricati: soci e tesseramento, "
     "protocollo, organi sociali, tesoreria e comunicazioni. Le credenziali sono personali."),
    ("Area soci", "I soci entrano con il proprio indirizzo email: ricevono un collegamento "
     "personale e vedono tessere, quote, ricevute ed eventi."),
    ("Iscrizione online", "Modulo pubblico per presentare la domanda di adesione."),
    ("Sito web", "Notizie, attività e informazioni istituzionali."),
]  # fmt: skip


def e(testo):
    return escape(str(testo or ""))


# --- lettura dei gestionali ---------------------------------------------------------------------


def leggi_scheda(url):
    if not url.startswith(("https://", "http://")):
        raise ValueError("indirizzo non http(s)")
    richiesta = urllib.request.Request(  # noqa: S310 - schema controllato sopra
        url.rstrip("/") + SCHEDA,
        headers={"Accept": "application/json", "User-Agent": "portale-servizi"},
    )
    with urllib.request.urlopen(richiesta, timeout=TIMEOUT) as risposta:  # noqa: S310
        return json.load(risposta)


def schede(installazioni, cache_file):
    """{url: scheda} letta ora o, se non risponde, dall'ultima lettura riuscita."""
    try:
        cache = json.loads(cache_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cache = {}
    risultato, problemi = {}, []
    for url in installazioni:
        try:
            scheda = leggi_scheda(url)
            scheda["_letta_il"] = datetime.now().isoformat(timespec="seconds")
            cache[url] = scheda
        except (OSError, ValueError) as errore:
            problemi.append(f"{url}: {errore}")
        risultato[url] = cache.get(url)
    cache_file.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    return risultato, problemi


# --- composizione --------------------------------------------------------------------------------


def icona(nome):
    return f'<svg aria-hidden="true"><use href="#i-{nome}"/></svg>'


def bottone(testo, url, primario=False):
    classe = "servizio primario" if primario else "servizio"
    return f'<a class="{classe}" href="{e(url)}" rel="noopener">{e(testo)} {icona("vai")}</a>'


def recapiti(r, escludi, senza):
    righe = []
    luogo = " ".join(x for x in (r.get("cap"), r.get("comune")) if x)
    if luogo and r.get("provincia"):
        luogo += f" ({r['provincia']})"
    sede = " — ".join(x for x in (r.get("indirizzo"), luogo) if x)
    if r.get("indirizzo") and "sede" not in escludi:
        righe.append(f"<li>{icona('sede')}<span>{e(sede)}</span></li>")
    if (tel := r.get("telefono")) and "telefono" not in escludi:
        numero = "".join(c for c in tel if c.isdigit() or c == "+")
        numero = numero if numero.startswith("+") else f"+39{numero}"
        righe.append(f'<li>{icona("tel")}<a href="tel:{e(numero)}">{e(tel)}</a></li>')
    if (email := r.get("email")) and "email" not in escludi:
        righe.append(f'<li>{icona("mail")}<a href="mailto:{e(email)}">{e(email)}</a></li>')
    if (pec := r.get("pec")) and "pec" not in escludi:
        righe.append(f'<li>{icona("pec")}<span><span class="etichetta">PEC</span> '
                     f'<a href="mailto:{e(pec)}">{e(pec)}</a></span></li>')  # fmt: skip
    if (sito := r.get("sito_web")) and "sito" not in escludi:
        visibile = sito.removeprefix("https://").removeprefix("http://").rstrip("/")
        righe.append(f'<li>{icona("web")}<a href="{e(sito)}" rel="noopener">{e(visibile)}</a></li>')
    if not righe:
        return f'<p class="senza">{e(senza)}</p>' if senza else ""
    return '<ul class="recapiti">' + "".join(righe) + "</ul>"


def scheda_voce(voce, letta, config):
    """Una scheda: dati della configurazione, completati da quelli letti dal gestionale."""
    letta = letta or {}
    servizi = letta.get("servizi") or {}
    r = {**(letta.get("recapiti") or {}), **voce.get("recapiti", {})}
    escludi = set(voce.get("escludi", []))
    nome = voce.get("nome") or r.get("denominazione") or letta.get("nome") or voce.get("gestionale")
    sottotitolo = voce.get("sottotitolo", r.get("comune", ""))
    bottoni = []
    if url := voce.get("gestionale"):
        indirizzo = servizi.get("gestionale") or url.rstrip("/") + "/"
        bottoni.append(bottone(voce.get("etichetta", "Gestionale"), indirizzo, True))
    if servizi.get("area_soci"):
        bottoni.append(bottone("Area soci", servizi["area_soci"]))
    if servizi.get("iscrizione"):
        bottoni.append(bottone("Iscrizione online", servizi["iscrizione"]))
    sito = voce.get("sito") or r.get("sito_web")
    if sito and "sito" not in escludi:
        bottoni.append(bottone("Sito web", sito))
    for c in voce.get("collegamenti", []):
        bottoni.append(bottone(c["testo"], c["url"], c.get("primario", not bottoni)))
    senza = voce.get("senza_recapiti", config.get("senza_recapiti", ""))
    corpo = recapiti(r, escludi, senza if voce.get("gestionale") else "")
    classi = "scheda" + (" ampia" if voce.get("ampia") else "")
    sotto = f'<p class="denominazione">{e(sottotitolo)}</p>' if sottotitolo else ""
    return (f'<article class="{classi}"><h3>{e(nome)}</h3>{sotto}{corpo}'
            f'<div class="servizi">{"".join(bottoni)}</div></article>')  # fmt: skip


def colori_css(config):
    """Variabili dei colori in un file: la CSP del portale può vietare gli stili in linea."""
    c = {**COLORI, **config.get("colori", {})}
    for nome, valore in c.items():
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", valore):
            raise ValueError(f"colore {nome} non valido: {valore}")
    sfondo = config.get("sfondo")
    foto = f'url("{Path(sfondo).name}")' if sfondo else "none"
    return (f":root {{ --testata: {c['testata']}; --accento: {c['accento']}; "
            f"--sfondo: {c['sfondo']}; --foto: {foto}; }}\n")  # fmt: skip


def pagina(config, lette):
    livelli = []
    for i, livello in enumerate(config.get("livelli", [])):
        gruppi = []
        for gruppo in livello.get("gruppi", []):
            titolo = gruppo.get("titolo")
            titolo = f'<h3 class="gruppo">{e(titolo)}</h3>' if titolo else ""
            schede_ = "".join(scheda_voce(v, lette.get(v.get("gestionale")), config)
                              for v in gruppo.get("voci", []))  # fmt: skip
            gruppi.append(f'{titolo}<div class="griglia">{schede_}</div>')
        grado = f'<span class="grado">{e(livello["grado"])}</span>' if livello.get("grado") else ""
        intestazione = f'<header>{grado}<h2 id="l{i}">{e(livello["titolo"])}</h2></header>'
        livelli.append(f'<section class="livello" aria-labelledby="l{i}">{intestazione}'
                       f'{"".join(gruppi)}</section>')  # fmt: skip
    guida = "".join(f"<dt>{e(t)}</dt><dd>{e(d)}</dd>" for t, d in config.get("guida", GUIDA))
    # il piede è HTML scritto nella configurazione (fidata), non dati dei gestionali
    piede = "".join(f"<p>{riga}</p>" for riga in config.get("piede", []))
    stemma = config.get("stemma")
    alt = e(config.get("stemma_alt", ""))
    img = f'<img class="stemma" src="{e(Path(stemma).name)}" alt="{alt}">' if stemma else ""
    favicon = config.get("favicon")
    icona_pag = f'<link rel="icon" href="{e(Path(favicon).name)}">' if favicon else ""
    aggiornata = datetime.now().strftime("%d/%m/%Y %H:%M")
    return f"""<!doctype html>
<!-- Generata da scripts/portale/genera_portale.py (Gestione Associazione, CC0 1.0) -->
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(config.get("titolo", "Servizi"))}</title>
<meta name="description" content="{e(config.get("descrizione", ""))}">
<meta name="color-scheme" content="light dark">
{icona_pag}<link rel="stylesheet" href="colori.css">
<link rel="stylesheet" href="stile.css">
</head>
<body>
{ICONE}
<header class="testata">
  {'<div class="tricolore" role="presentation"></div>' if config.get("tricolore", True) else ""}
  <div class="contenuto">
    {img}
    <p class="ente">{e(config.get("ente", ""))}</p>
    {f'<p class="motto">{e(config["motto"])}</p>' if config.get("motto") else ""}
    <hr class="filetto">
    <h1>{e(config.get("intestazione", ""))}</h1>
    {f'<p class="sottotitolo">{e(config["sottotitolo"])}</p>' if config.get("sottotitolo") else ""}
  </div>
</header>
<main>
{"".join(livelli)}
<aside class="guida" aria-labelledby="t-guida"><h2 id="t-guida">Guida ai servizi</h2><dl>{guida}</dl></aside>
</main>
<footer>{piede}<p class="aggiornata">Pagina aggiornata il {aggiornata} con i dati dei gestionali.</p></footer>
</body>
</html>
"""  # noqa: E501


def main():
    parser = argparse.ArgumentParser(description="Genera il portale dei servizi.")
    parser.add_argument("configurazione", type=Path)
    parser.add_argument("--uscita", type=Path, required=True, help="Cartella pubblicata")
    argomenti = parser.parse_args()
    config = tomllib.loads(argomenti.configurazione.read_text(encoding="utf-8"))
    base = argomenti.configurazione.parent
    uscita = argomenti.uscita
    uscita.mkdir(parents=True, exist_ok=True)
    voci = [v for liv in config.get("livelli", []) for g in liv.get("gruppi", [])
            for v in g.get("voci", [])]  # fmt: skip
    installazioni = [v["gestionale"] for v in voci if v.get("gestionale")]
    lette, problemi = schede(installazioni, base / "cache.json")
    for nome in ("stemma", "sfondo", "favicon"):
        if config.get(nome):
            shutil.copyfile(base / config[nome], uscita / Path(config[nome]).name)
    shutil.copyfile(Path(__file__).with_name("stile.css"), uscita / "stile.css")
    (uscita / "colori.css").write_text(colori_css(config), encoding="utf-8")
    temporaneo = uscita / ".index.html"
    temporaneo.write_text(pagina(config, lette), encoding="utf-8")
    temporaneo.replace(uscita / "index.html")
    for p in problemi:
        print(f"non raggiungibile (dati dell'ultima lettura): {p}", file=sys.stderr)
    print(f"portale generato: {len(installazioni)} installazioni, {len(problemi)} non raggiunte")


if __name__ == "__main__":
    main()
