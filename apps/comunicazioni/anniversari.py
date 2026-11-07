# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Calcolo degli anniversari in un periodo: compleanni, onomastici,
# *              anniversari di iscrizione, ricorrenze dell'associazione e anniversari
# *              di scomparsa (solo promemoria).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import unicodedata
from dataclasses import dataclass, field
from datetime import date, timedelta

from apps.anagrafica.models import Soggetto

from .models import Onomastico, Ricorrenza

TIPI = {
    "compleanno": ("Compleanno", "cake", "pink"),
    "onomastico": ("Onomastico", "flower", "purple"),
    "anzianita": ("Anniversario di iscrizione", "id-badge-2", "blue"),
    "ricorrenza": ("Ricorrenza", "flag", "green"),
    "scomparsa": ("Anniversario di scomparsa", "candle", "secondary"),
}


@dataclass
class Evento:
    tipo: str
    data: date
    titolo: str
    anni: int | None = None
    soggetto: Soggetto | None = None
    ricorrenza: Ricorrenza | None = None
    dettaglio: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def etichetta(self):
        return TIPI[self.tipo][0]

    @property
    def icona(self):
        return TIPI[self.tipo][1]

    @property
    def colore(self):
        return TIPI[self.tipo][2]

    @property
    def tondo(self):
        return bool(self.anni) and (self.anni % 10 == 0 or self.anni in (1, 5, 25, 75))


def normalizza_nome(nome):
    testo = unicodedata.normalize("NFKD", nome or "").encode("ascii", "ignore").decode()
    return " ".join(testo.lower().split())


def nomi_candidati(nome):
    """Per «Maria Teresa» cerca «maria teresa», poi «maria»."""
    n = normalizza_nome(nome)
    return [n, n.split(" ")[0]] if " " in n else [n]


def _in_anno(giorno, mese, anno):
    try:
        return date(anno, mese, giorno)
    except ValueError:  # 29 febbraio negli anni non bisestili
        return date(anno, 3, 1)


def _date_nel_periodo(giorno, mese, dal, al):
    for anno in range(dal.year, al.year + 1):
        d = _in_anno(giorno, mese, anno)
        if dal <= d <= al:
            yield d


def persone_vive():
    return Soggetto.objects.attivi().filter(tipo=Soggetto.Tipo.PERSONA, data_decesso__isnull=True)


def compleanni(dal, al):
    for p in persone_vive().filter(data_nascita__isnull=False):
        for d in _date_nel_periodo(p.data_nascita.day, p.data_nascita.month, dal, al):
            yield Evento("compleanno", d, p.nome_completo, d.year - p.data_nascita.year, p)


def onomastici(dal, al):
    calendario = {o.nome: o for o in Onomastico.objects.all()}
    for p in persone_vive().exclude(nome=""):
        o = next((calendario[n] for n in nomi_candidati(p.nome) if n in calendario), None)
        if o is None:
            continue
        for d in _date_nel_periodo(o.giorno, o.mese, dal, al):
            yield Evento("onomastico", d, p.nome_completo, soggetto=p, dettaglio=o.santo)


def anzianita(dal, al, anni_scelti=None):
    from apps.soci.models import Socio

    for s in Socio.objects.attivi().select_related("soggetto"):
        a = s.data_ammissione
        for d in _date_nel_periodo(a.day, a.month, dal, al):
            anni = d.year - a.year
            if anni >= 1 and (anni_scelti is None or anni in anni_scelti):
                yield Evento(
                    "anzianita", d, s.soggetto.nome_completo, anni, s.soggetto,
                    dettaglio=f"socio n. {s.numero} dal {a:%d/%m/%Y}",
                )  # fmt: skip


def ricorrenze(dal, al):
    for r in Ricorrenza.objects.filter(attiva=True):
        for d in _date_nel_periodo(r.giorno, r.mese, dal, al):
            anni = d.year - r.anno_inizio if r.anno_inizio else None
            yield Evento("ricorrenza", d, r.nome, anni, ricorrenza=r, dettaglio=r.descrizione)


def scomparse(dal, al):
    morti = Soggetto.objects.filter(tipo=Soggetto.Tipo.PERSONA, data_decesso__isnull=False)
    for p in morti:
        for d in _date_nel_periodo(p.data_decesso.day, p.data_decesso.month, dal, al):
            if d.year > p.data_decesso.year:
                yield Evento("scomparsa", d, p.nome_completo, d.year - p.data_decesso.year, p)


def eventi(dal=None, giorni=30, tipi=None):
    dal = dal or date.today()
    al = dal + timedelta(days=giorni)
    tipi = tipi or list(TIPI)
    calcoli = {
        "compleanno": compleanni, "onomastico": onomastici, "anzianita": anzianita,
        "ricorrenza": ricorrenze, "scomparsa": scomparse,
    }  # fmt: skip
    risultato = [e for t in tipi for e in calcoli[t](dal, al)]
    return sorted(risultato, key=lambda e: (e.data, list(TIPI).index(e.tipo), e.titolo))
