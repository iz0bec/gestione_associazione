# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: File caricati tenuti tra l'anteprima e la conferma di un'importazione:
# *              nome casuale, fuori dalle cartelle servite, eliminati dopo l'uso o dopo un giorno.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import secrets
import time
from pathlib import Path

from django.conf import settings

DURATA = 24 * 3600


def _cartella():
    cartella = Path(settings.MEDIA_ROOT) / "importazioni"
    cartella.mkdir(parents=True, exist_ok=True)
    return cartella


def _pulisci_vecchi(cartella):
    limite = time.time() - DURATA
    for f in cartella.glob("*.dat"):
        if f.stat().st_mtime < limite:
            f.unlink(missing_ok=True)


def salva_temporaneo(contenuto, nome_originale=""):
    cartella = _cartella()
    _pulisci_vecchi(cartella)
    nome = f"{secrets.token_hex(16)}.dat"
    (cartella / nome).write_bytes(contenuto)
    return nome


def _percorso(nome):
    if not nome or "/" in nome or "\\" in nome or not nome.endswith(".dat"):
        return None
    return _cartella() / nome


def leggi_temporaneo(nome):
    p = _percorso(nome)
    return p.read_bytes() if p and p.is_file() else None


def elimina_temporaneo(nome):
    if p := _percorso(nome):
        p.unlink(missing_ok=True)
