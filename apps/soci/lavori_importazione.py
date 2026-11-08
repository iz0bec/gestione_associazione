# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Importazioni in un processo separato: anteprima ed esecuzione non bloccano la
# *              pagina e scrivono l'avanzamento (riga N di M) in un file di stato, letto dalla
# *              finestra di avanzamento. Un lavoro appartiene all'utente che l'ha avviato.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import json
import re
import secrets
import subprocess  # noqa: S404 - avvio di manage.py con argomenti fissi, senza shell
import sys
import time
from dataclasses import asdict
from pathlib import Path

from django.conf import settings

from . import importazione, temporanei

ID_VALIDO = re.compile(r"^[0-9a-f]{32}$")


def _file(lavoro_id):
    if not ID_VALIDO.match(lavoro_id or ""):
        return None
    return temporanei._cartella() / f"lavoro_{lavoro_id}.json"


def leggi(lavoro_id, utente=None):
    """Stato del lavoro; None se non esiste o (con `utente`) se è di un altro utente."""
    p = _file(lavoro_id)
    if p is None or not p.is_file():
        return None
    try:
        dati = json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if utente is not None and dati.get("utente_id") != utente.pk:
        return None
    return dati


def scrivi(lavoro_id, **campi):
    p = _file(lavoro_id)
    dati = {**(leggi(lavoro_id) or {}), **campi}
    temporaneo = p.with_suffix(".tmp")
    temporaneo.write_text(json.dumps(dati, ensure_ascii=False, default=str))
    temporaneo.chmod(0o600)
    temporaneo.replace(p)  # chi legge non vede mai un file a metà
    return dati


def nuovo(utente, nome_file, contenuto, opzioni, colonne, ignorate, totale):
    lavoro_id = secrets.token_hex(16)
    scrivi(
        lavoro_id,
        id=lavoro_id, utente_id=utente.pk, utente=str(utente), nome_file=nome_file,
        file=temporanei.salva_temporaneo(contenuto, nome_file), opzioni=opzioni,
        colonne=colonne, ignorate=ignorate, totale=totale, fatte=0,
        fase="anteprima", stato="in_attesa", rapporto=None, errore="",
    )  # fmt: skip
    return lavoro_id


def avvia(lavoro_id, fase):
    """Avvia anteprima o esecuzione in un processo separato."""
    scrivi(lavoro_id, fase=fase, stato="in_corso", fatte=0, errore="", avviato=time.time())
    base = Path(settings.BASE_DIR)
    subprocess.Popen(  # noqa: S603
        [sys.executable, str(base / "manage.py"), "lavoro_importazione", lavoro_id],
        cwd=base, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, start_new_session=True,
    )  # fmt: skip


def opzioni_da_dict(d):
    from .models import Sezione, TipologiaSocio

    consentite = d.get("sezioni_consentite")
    return importazione.Opzioni(
        sezione=Sezione.objects.filter(pk=d.get("sezione")).first() if d.get("sezione") else None,
        tipologia=TipologiaSocio.objects.filter(pk=d.get("tipologia")).first(),
        crea_sezioni=d.get("crea_sezioni", False),
        allinea_sezione=d.get("allinea_sezione", False),
        tessere=d.get("tessere", True),
        crea_tessere=d.get("crea_tessere", True),
        anno_tessere=d.get("anno_tessere"),
        cessazioni=d.get("cessazioni", True),
        quote_pagate=d.get("quote_pagate", False),
        sezioni_consentite=set(consentite) if consentite is not None else None,
    )


def esegui(lavoro_id):
    """Corpo del processo separato (comando lavoro_importazione)."""
    from django.contrib.auth import get_user_model

    lavoro = leggi(lavoro_id)
    if lavoro is None:
        return
    esegui_davvero = lavoro["fase"] == "esecuzione"
    ultimo = [0.0]

    def avanzamento(fatte, totale):
        if time.monotonic() - ultimo[0] >= 0.5 or fatte == totale:
            scrivi(lavoro_id, fatte=fatte, totale=totale)
            ultimo[0] = time.monotonic()

    try:
        contenuto = temporanei.leggi_temporaneo(lavoro["file"])
        if contenuto is None:
            raise importazione.FileNonValido("Il file caricato non è più disponibile.")
        _, righe, _ = importazione.leggi(lavoro["nome_file"], contenuto)
        utente = get_user_model().objects.filter(pk=lavoro["utente_id"]).first()
        rapporto = importazione.elabora(
            righe, opzioni_da_dict(lavoro["opzioni"]), utente,
            esegui=esegui_davvero, avanzamento=avanzamento,
        )  # fmt: skip
        dati = asdict(rapporto)
        dati["riepilogo"] = rapporto.riepilogo
        scrivi(lavoro_id, stato="completato", rapporto=dati, fatte=len(righe))
        if esegui_davvero:
            temporanei.elimina_temporaneo(lavoro["file"])
    except Exception as e:  # noqa: BLE001 - l'errore va mostrato all'utente nella finestra
        messaggio = " ".join(getattr(e, "messages", [])) or str(e)
        scrivi(lavoro_id, stato="errore", errore=messaggio[:2000])
