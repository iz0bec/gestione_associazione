# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Modulo di richiesta di adesione e consenso (Allegato A) in PDF: compilato da
# *              una domanda, dai dati di un socio (da far firmare) o in bianco.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import re

from django.utils import timezone

from apps.anagrafica.models import Consenso
from apps.comunicazioni.servizi import consensi_prestati
from apps.core.models import Organizzazione
from apps.core.pdf import genera_pdf

from .forms import TESTO_IMMAGINI, TESTO_PARTICOLARI, TESTO_TRATTAMENTO


def _luogo_nascita(luogo, provincia=""):
    return f"{luogo} ({provincia})" if provincia and "(" not in luogo else luogo


def dati_domanda(d):
    return {
        "nominativo": f"{d.cognome} {d.nome}".upper(),
        "luogo_nascita": d.luogo_nascita,
        "data_nascita": d.data_nascita,
        "indirizzo": d.indirizzo,
        "cap": d.cap,
        "comune": d.comune,
        "provincia": d.provincia,
        "telefono": d.telefono,
        "cellulare": d.cellulare,
        "email": d.email,
        "codice_fiscale": d.codice_fiscale,
        "sezione": d.sezione.nome if d.sezione else "",
        "luogo": d.sezione.comune or d.sezione.nome if d.sezione else "",
        "data": timezone.localtime(d.ricevuta_il).date(),
        "dichiarazione": d.dichiarazione,
        "consensi": {
            "trattamento": d.consenso_trattamento,
            "particolari": d.consenso_particolari,
            "immagini": d.consenso_immagini,
        },
    }


def dati_socio(socio):
    """Dati del socio per stampare il modulo da far firmare (consensi come registrati)."""
    p = socio.soggetto

    def prestato(finalita):
        return p.pk in consensi_prestati([p], finalita)

    return {
        "nominativo": f"{p.cognome} {p.nome}".upper(),
        "luogo_nascita": p.luogo_nascita,
        "data_nascita": p.data_nascita,
        "indirizzo": p.indirizzo,
        "cap": p.cap,
        "comune": p.comune,
        "provincia": p.provincia,
        "telefono": p.telefono,
        "cellulare": p.cellulare,
        "email": p.email,
        "codice_fiscale": p.codice_fiscale,
        "sezione": socio.sezione.nome,
        "luogo": socio.sezione.comune or socio.sezione.nome,
        "data": None,  # la data la scrive chi firma
        "dichiarazione": socio.dichiarazione,
        "consensi": {
            "trattamento": prestato(Consenso.Finalita.TRATTAMENTO),
            "particolari": prestato(Consenso.Finalita.PARTICOLARI),
            "immagini": prestato(Consenso.Finalita.IMMAGINI),
        },
    }


TITOLETTO = re.compile(r"^([A-ZÀ-Ú][^.,;:]{2,60}\.)\s+(.*)$")


def paragrafi_informativa(testo):
    """Righe dell'informativa con l'eventuale titoletto iniziale («Diritti dell'interessato.»)
    separato, per stamparlo in grassetto come nel modulo originale."""
    righe = []
    for riga in (testo or "").splitlines():
        m = TITOLETTO.match(riga.strip())
        if m and len(m.group(1).split()) <= 6:
            righe.append((m.group(1), m.group(2)))
        elif riga.strip():
            righe.append(("", riga.strip()))
    return righe


def pdf(dati=None):
    org = Organizzazione.corrente()
    return genera_pdf(
        "soci/pdf/allegato_a.html",
        {
            "m": dati or {"consensi": {}},
            "org": org,
            "informativa": paragrafi_informativa(org.informativa_privacy),
            "testi": {
                "trattamento": TESTO_TRATTAMENTO,
                "particolari": TESTO_PARTICOLARI,
                "immagini": TESTO_IMMAGINI,
            },
        },
    )
