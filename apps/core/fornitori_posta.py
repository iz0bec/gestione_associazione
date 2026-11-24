# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Preimpostazioni dei fornitori di posta: server, porta e cifratura per le caselle
# *              (IMAP) e i servizi di invio (SMTP). Quelli del programma stanno in
# *              dati/fornitori_posta.json; gli amministratori aggiungono i propri (FornitorePosta).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import json
import logging
from functools import cache
from pathlib import Path

log = logging.getLogger(__name__)
FILE_PREDEFINITO = Path(__file__).parent / "dati" / "fornitori_posta.json"
RUOLI = ("imap", "smtp")


def _leggi(percorso):
    try:
        dati = json.loads(Path(percorso).read_text(encoding="utf-8"))
        return [f for f in dati.get("fornitori", []) if f.get("id") and f.get("nome")]
    except (OSError, ValueError, AttributeError) as e:
        log.warning("Fornitori di posta: file %s non leggibile (%s)", percorso, e)
        return []


@cache
def predefiniti():
    """Fornitori del programma (file di dati)."""
    return _leggi(FILE_PREDEFINITO)


def personalizzati():
    """Fornitori aggiunti dagli amministratori, con lo stesso formato (id «p<pk>»)."""
    from .models import FornitorePosta

    return [f.come_voce() for f in FornitorePosta.objects.filter(attivo=True)]


def fornitori():
    """Prima quelli personalizzati (di solito i fornitori dell'associazione), poi i predefiniti."""
    return [*personalizzati(), *predefiniti()]


def per_ruolo(ruolo):
    """Fornitori che hanno i parametri per «imap» o «smtp»."""
    return [f for f in fornitori() if isinstance(f.get(ruolo), dict) and f[ruolo].get("server")]


def scelte(ruolo):
    return [("", "Altro (valori a mano)")] + [(f["id"], f["nome"]) for f in per_ruolo(ruolo)]


def trova(ruolo, identificativo):
    return next((f for f in per_ruolo(ruolo) if f["id"] == identificativo), None)


def per_il_modulo(ruolo):
    """Dati per app.js (attributo data-fornitore-posta): {id: {server, porta, ssl, pec, nota}}."""
    return json.dumps({
        f["id"]: {**{k: f[ruolo][k] for k in ("server", "porta", "ssl") if k in f[ruolo]},
                  "pec": bool(f.get("pec")), "nota": f.get("nota", "")}
        for f in per_ruolo(ruolo)
    }, ensure_ascii=False)  # fmt: skip
