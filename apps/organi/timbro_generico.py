# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Timbro tondo generico (SVG) per le stampe quando non è stato caricato un
# *              timbro: denominazione lungo il bordo, località o sezione al centro.
# *              Le lettere sono disposte una per una (WeasyPrint non disegna textPath).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import math
from xml.sax.saxutils import escape

COLORE = "#1d3b8f"
_R_TESTO = 78  # raggio della riga di testo (viewBox 200 × 200)
_LARGHEZZA = 0.68  # larghezza media di una maiuscola rispetto al corpo


def _testi(organizzazione, sezione):
    bordo = (organizzazione.denominazione or "").upper()
    if sezione is not None:
        centro = ["SEZIONE", sezione.nome.upper()]
    else:
        centro = [organizzazione.comune.upper()] if organizzazione.comune else []
    return " ".join(bordo.split()), centro


def svg(organizzazione, sezione=None):
    """Markup SVG del timbro (testo dell'utente sempre con escape)."""
    bordo, centro = _testi(organizzazione, sezione)
    testo = f"{bordo} ★ " if bordo else ""
    parti = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" class="timbro-generico">',
        f'<g fill="none" stroke="{COLORE}">',
        '<circle cx="100" cy="100" r="97" stroke-width="3.5"/>',
        '<circle cx="100" cy="100" r="62" stroke-width="1.6"/></g>',
        f'<g fill="{COLORE}" font-family="DejaVu Sans, Arial, sans-serif" font-weight="bold">',
    ]
    if testo:
        corpo = min(17.0, 2 * math.pi * _R_TESTO / (len(testo) * _LARGHEZZA))
        passo = 360 / len(testo)
        for i, lettera in enumerate(testo):
            if lettera == " ":
                continue
            parti.append(
                f'<text x="100" y="{100 - _R_TESTO + corpo / 2.6:.2f}" font-size="{corpo:.2f}" '
                f'text-anchor="middle" transform="rotate({i * passo:.2f} 100 100)">'
                f"{escape(lettera)}</text>"
            )
    for n, riga in enumerate(centro):
        corpo = min(17.0, 104 / (max(len(riga), 1) * _LARGHEZZA))
        y = 100 + corpo / 2.8 + (n - (len(centro) - 1) / 2) * corpo * 1.25
        parti.append(
            f'<text x="100" y="{y:.2f}" font-size="{corpo:.2f}" text-anchor="middle">'
            f"{escape(riga)}</text>"
        )
    parti.append("</g></svg>")
    return "".join(parti)
