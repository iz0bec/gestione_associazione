# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Genera gli ornamenti SVG dell'attestato solenne (angolo, fregio, alloro,
# *              coccarda tricolore) in static/img/attestato. Uso:
# *              uv run python scripts/ornamenti_attestato.py static/img/attestato
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

# ruff: noqa: E501  (stringhe SVG con la geometria degli ornamenti)
"""Genera gli ornamenti SVG dell'attestato solenne (geometria calcolata, nessuna fonte esterna)."""

import math
import sys
from pathlib import Path

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
ORO, ORO_SCURO, ORO_CHIARO = "#b08a3e", "#7d5f22", "#d9bf7f"
TESTA = (
    "<!-- Gestione Associazione - Autore: Bartolomeo Santoro aka IZ0BEC <info@iz0bec.info> - "
    "{d} - Licenza: CC0 1.0 Universal (pubblico dominio) - SPDX-License-Identifier: CC0-1.0 -->\n"
)


def svg(nome, descr, vb, corpo):
    (OUT / nome).write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        + TESTA.format(d=descr)
        + f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}">\n{corpo}\n</svg>\n',
        encoding="utf-8",
    )


def f(x):
    return f"{x:.2f}".rstrip("0").rstrip(".")


def foglia(cx, cy, ang, lung, larg, colore):
    """Foglia a mandorla con nervatura, orientata di ang gradi."""
    a = math.radians(ang)
    dx, dy = math.cos(a), math.sin(a)
    px, py = -dy, dx
    tx, ty = cx + dx * lung, cy + dy * lung
    c1 = (cx + dx * lung * 0.5 + px * larg, cy + dy * lung * 0.5 + py * larg)
    c2 = (cx + dx * lung * 0.5 - px * larg, cy + dy * lung * 0.5 - py * larg)
    return (
        f'<path d="M{f(cx)},{f(cy)} Q{f(c1[0])},{f(c1[1])} {f(tx)},{f(ty)} '
        f'Q{f(c2[0])},{f(c2[1])} {f(cx)},{f(cy)}Z" fill="{colore}"/>'
        f'<path d="M{f(cx)},{f(cy)} L{f(cx + dx * lung * 0.85)},{f(cy + dy * lung * 0.85)}" '
        f'stroke="{ORO_SCURO}" stroke-width=".35" opacity=".6"/>'
    )


# --- ramo d'alloro (coppia di rami che si incontrano in basso, aperti verso l'alto) ---------
def ramo(verso):
    parti = []
    # stelo: arco da (100,52) verso l'esterno e l'alto
    pts = []
    for i in range(41):
        t = i / 40
        x = 100 + verso * (t * 88)
        y = 52 - math.sin(t * math.pi * 0.55) * 30 - t * 4
        pts.append((x, y))
    d = "M" + " L".join(f"{f(x)},{f(y)}" for x, y in pts)
    parti.append(
        f'<path d="{d}" fill="none" stroke="{ORO_SCURO}" stroke-width="1.1" stroke-linecap="round"/>'
    )
    for k, i in enumerate(range(3, 40, 4)):
        x, y = pts[i]
        x2, y2 = pts[i + 1]
        tang = math.degrees(math.atan2(y2 - y, x2 - x))
        lung = 11 - k * 0.55
        colore = ORO if k % 2 == 0 else ORO_CHIARO
        parti.append(foglia(x, y, tang - 48, lung, 3.3, colore))
        parti.append(foglia(x, y, tang + 42, lung * 0.92, 3.1, ORO if k % 2 else ORO_CHIARO))
    x, y = pts[-1]
    parti.append(
        foglia(
            x,
            y,
            math.degrees(math.atan2(pts[-1][1] - pts[-2][1], pts[-1][0] - pts[-2][0])),
            9,
            3,
            ORO,
        )
    )
    # bacche
    for i in (9, 21, 33):
        x, y = pts[i]
        parti.append(f'<circle cx="{f(x)}" cy="{f(y + 4.5)}" r="1.5" fill="{ORO_SCURO}"/>')
    return "\n".join(parti)


nastro = (
    f'<path d="M92,50 Q100,58 108,50 L110,56 Q100,63 90,56Z" fill="{ORO_SCURO}"/>'
    f'<path d="M93,56 L88,64 L92,63 L94,67 L97,58Z M107,56 L112,64 L108,63 L106,67 L103,58Z" fill="{ORO}"/>'
)
svg(
    "alloro.svg",
    "Rami d'alloro con nastro",
    "0 0 200 70",
    ramo(-1) + "\n" + ramo(1) + "\n" + nastro,
)


# --- angolo ornato (in alto a sinistra; ruotato per gli altri) -------------------------------
def spirale(cx, cy, r0, giri, verso, ang0=0):
    pts = []
    n = int(giri * 36)
    for i in range(n + 1):
        t = i / n
        a = math.radians(ang0) + verso * t * giri * 2 * math.pi
        r = r0 * (1 - t * 0.82)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return "M" + " L".join(f"{f(x)},{f(y)}" for x, y in pts)


angolo = [
    # volute che partono dall'angolo lungo i due lati
    f'<path d="M24,21 C38,18 50,32 59.42,23.61" fill="none" stroke="{ORO_SCURO}" stroke-width="1.3" stroke-linecap="round"/>',
    f'<path d="M21,24 C18,38 32,50 23.61,59.42" fill="none" stroke="{ORO_SCURO}" stroke-width="1.3" stroke-linecap="round"/>',
    f'<path d="{spirale(66, 26, 7, 1.4, 1, 200)}" fill="none" stroke="{ORO}" stroke-width="1.1" stroke-linecap="round"/>',
    f'<path d="{spirale(26, 66, 7, 1.4, -1, 250)}" fill="none" stroke="{ORO}" stroke-width="1.1" stroke-linecap="round"/>',
    f'<path d="M73,26 C82,31 92,22 106,22" fill="none" stroke="{ORO}" stroke-width=".9"/>',
    f'<path d="M26,73 C31,82 22,92 22,106" fill="none" stroke="{ORO}" stroke-width=".9"/>',
    foglia(78, 27, -15, 10, 3, ORO_CHIARO),
    foglia(90, 24, 10, 9, 2.6, ORO),
    foglia(27, 78, 105, 10, 3, ORO_CHIARO),
    foglia(24, 90, 80, 9, 2.6, ORO),
    # rosetta a quattro petali nell'angolo
    *[foglia(20, 20, a, 9, 3.6, ORO if a % 90 == 45 else ORO_CHIARO) for a in (45, 135, 225, 315)],
    f'<circle cx="20" cy="20" r="2.6" fill="{ORO_SCURO}"/>',
    f'<circle cx="20" cy="20" r="1.1" fill="{ORO_CHIARO}"/>',
]
svg("angolo.svg", "Angolo ornato della cornice", "0 0 120 120", "\n".join(angolo))

# --- fregio centrale (in alto e in basso nella cornice) -------------------------------------
fregio = [
    f'<path d="M4,10 L72,10 M128,10 L196,10" stroke="{ORO}" stroke-width=".8"/>',
    f'<path d="M100,2 L108,10 L100,18 L92,10Z" fill="{ORO}" stroke="{ORO_SCURO}" stroke-width=".6"/>',
    f'<circle cx="100" cy="10" r="2" fill="{ORO_CHIARO}"/>',
    f'<path d="M90,10 C84,2 76,4 76,10 C76,16 84,18 90,10Z" fill="none" stroke="{ORO_SCURO}" stroke-width=".9"/>',
    f'<path d="M110,10 C116,2 124,4 124,10 C124,16 116,18 110,10Z" fill="none" stroke="{ORO_SCURO}" stroke-width=".9"/>',
    f'<circle cx="72" cy="10" r="1.4" fill="{ORO}"/><circle cx="128" cy="10" r="1.4" fill="{ORO}"/>',
]
svg("fregio.svg", "Fregio centrale della cornice", "0 0 200 20", "\n".join(fregio))

# --- coccarda tricolore: anelli plissettati verde, bianco e rosso, nastri tricolori --------
VERDE, BIANCO, ROSSO = "#009246", "#ffffff", "#ce2b37"
cx, cy = 60, 54


def plissettato(r_est, r_int, n, colore, bordo):
    punte = []
    for i in range(n * 2):
        r = r_est if i % 2 == 0 else r_int
        a = math.radians(i * 180 / n)
        punte.append(f"{f(cx + r * math.cos(a))},{f(cy + r * math.sin(a))}")
    pieghe = []
    for i in range(n):
        a = math.radians(i * 360 / n + 180 / n)
        pieghe.append(
            f"M{f(cx + r_int * 0.55 * math.cos(a))},{f(cy + r_int * 0.55 * math.sin(a))} "
            f"L{f(cx + r_int * math.cos(a))},{f(cy + r_int * math.sin(a))}"
        )
    return (
        f'<polygon points="{" ".join(punte)}" fill="{colore}" stroke="{bordo}" stroke-width=".6"/>'
        f'<path d="{" ".join(pieghe)}" stroke="{bordo}" stroke-width=".45" opacity=".55"/>'
    )


def nastro_tricolore(verso):
    """Coda di nastro con le tre bande (verde, bianco, rosso) nel senso della lunghezza e taglio a
    coda di rondine; inclinata verso l'esterno."""
    ang = math.radians(-verso * 24)
    ox, oy = 60 + verso * 15, 82

    def punto(x, y):
        return (
            f"{f(ox + x * math.cos(ang) - y * math.sin(ang))},"
            f"{f(oy + x * math.sin(ang) + y * math.cos(ang))}"
        )

    def fondo(x):
        return 40 + abs(x) * 8 / 7.5

    parti = []
    for a, b, colore in ((-7.5, -2.5, VERDE), (-2.5, 2.5, BIANCO), (2.5, 7.5, ROSSO)):
        vertici = [punto(a, 0), punto(b, 0), punto(b, fondo(b))]
        if a < 0 < b:
            vertici.append(punto(0, fondo(0)))
        vertici.append(punto(a, fondo(a)))
        parti.append(f'<polygon points="{" ".join(vertici)}" fill="{colore}"/>')
    contorno = [
        punto(-7.5, 0),
        punto(7.5, 0),
        punto(7.5, fondo(7.5)),
        punto(0, fondo(0)),
        punto(-7.5, fondo(-7.5)),
    ]
    parti.append(
        f'<polygon points="{" ".join(contorno)}" fill="none" stroke="#8a8a8a" stroke-width=".5"/>'
    )
    return "\n".join(parti)


coccarda = [
    nastro_tricolore(-1),
    nastro_tricolore(1),
    plissettato(47, 42.5, 40, VERDE, "#00692f"),
    f'<circle cx="{cx}" cy="{cy}" r="38.5" fill="none" stroke="{ORO}" stroke-width="1.4"/>',
    plissettato(37.5, 34, 34, BIANCO, "#b9b9b9"),
    f'<circle cx="{cx}" cy="{cy}" r="27" fill="none" stroke="{ORO}" stroke-width="1.2"/>',
    plissettato(26.5, 23.5, 26, ROSSO, "#8f1d26"),
    f'<circle cx="{cx}" cy="{cy}" r="9" fill="{ORO}" stroke="{ORO_SCURO}" stroke-width=".8"/>',
    f'<circle cx="{cx}" cy="{cy}" r="6" fill="none" stroke="{ORO_CHIARO}" stroke-width=".7"/>',
    f'<circle cx="{cx}" cy="{cy}" r="2.2" fill="{ORO_CHIARO}"/>',
]
svg("sigillo.svg", "Coccarda tricolore con nastri", "0 0 120 136", "\n".join(coccarda))
print("ok", sorted(p.name for p in OUT.iterdir()))
