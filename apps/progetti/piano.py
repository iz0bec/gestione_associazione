# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Piano economico del progetto (P4): totali per categoria, spese generali,
# *              coperture (contributo, cofinanziamento in denaro, dei partner, in natura) e
# *              controlli dei limiti del bando collegato.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from .models import Categoria, FonteFinanziamento

ZERO = Decimal("0.00")
CENTESIMO = Decimal("0.01")


def _q(valore):
    return Decimal(valore).quantize(CENTESIMO, ROUND_HALF_UP)


def percentuale(parte, totale):
    return _q(parte * 100 / totale) if totale else ZERO


def euro(valore):
    return f"€ {valore:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _pc(valore):
    return f"{valore:.2f}".replace(".", ",").removesuffix(",00") + "%"


@dataclass
class Controllo:
    esito: str  # ok | errore | avviso
    testo: str


@dataclass
class Piano:
    categorie: list = field(default_factory=list)  # [(categoria, etichetta, voci, totale)]
    diretti: Decimal = ZERO  # costi in denaro
    spese_generali: Decimal = ZERO
    natura: Decimal = ZERO
    totale_costi: Decimal = ZERO
    contributo: Decimal = ZERO
    proprio: Decimal = ZERO
    partner: Decimal = ZERO
    altri: Decimal = ZERO
    fonti: list = field(default_factory=list)
    controlli: list = field(default_factory=list)

    @property
    def totale_fonti(self):
        return self.contributo + self.proprio + self.partner + self.altri + self.natura

    @property
    def cofinanziamento(self):
        return self.totale_costi - self.contributo

    @property
    def differenza(self):
        return self.totale_fonti - self.totale_costi

    @property
    def errori(self):
        return [c for c in self.controlli if c.esito == "errore"]


def calcola(progetto):
    p = Piano()
    voci = list(progetto.voci.all())
    for valore, etichetta in Categoria.choices:
        della = [v for v in voci if v.categoria == valore]
        if della:
            p.categorie.append((valore, etichetta, della, sum((v.importo for v in della), ZERO)))
    p.natura = sum((v.importo for v in voci if v.in_natura), ZERO)
    p.diretti = sum((v.importo for v in voci if not v.in_natura), ZERO)
    if progetto.spese_generali:
        p.spese_generali = _q(p.diretti * progetto.spese_generali / 100)
    p.totale_costi = p.diretti + p.spese_generali + p.natura
    p.fonti = list(progetto.fonti.all())
    for f in p.fonti:
        if f.tipo == FonteFinanziamento.Tipo.CONTRIBUTO:
            p.contributo += f.importo
        elif f.tipo == FonteFinanziamento.Tipo.PROPRIO:
            p.proprio += f.importo
        else:
            p.altri += f.importo
    p.partner = sum((x.cofinanziamento or ZERO for x in progetto.partner.all()), ZERO)
    p.controlli = controlli(progetto, p)
    return p


def controlli(progetto, p):
    if not p.totale_costi:
        return [Controllo("avviso", "Il piano non ha ancora voci di costo.")]
    c = []
    if p.differenza == 0:
        c.append(Controllo("ok", f"Costi e coperture si equivalgono ({euro(p.totale_costi)})."))
    elif p.differenza < 0:
        c.append(Controllo("errore", f"Mancano coperture per {euro(-p.differenza)}."))
    else:
        c.append(Controllo("errore", f"Le coperture superano i costi di {euro(p.differenza)}."))
    bando = progetto.bando
    if bando is None:
        c.append(Controllo("avviso", "Nessun bando collegato: controllati solo i totali."))
        return c
    if bando.importo_massimo is not None:
        massimo = euro(bando.importo_massimo)
        if p.contributo <= bando.importo_massimo:
            c.append(Controllo("ok", f"Contributo entro il massimo del bando ({massimo})."))
        else:
            c.append(Controllo("errore", f"Il contributo richiesto supera il massimo ({massimo})."))
    if bando.cofinanziamento is not None:
        quota = percentuale(p.cofinanziamento, p.totale_costi)
        esito = "ok" if quota >= bando.cofinanziamento else "errore"
        c.append(
            Controllo(
                esito,
                f"Cofinanziamento {_pc(quota)} del totale "
                f"(il bando chiede almeno {_pc(bando.cofinanziamento)}).",
            )
        )
    if progetto.spese_generali:
        massimo = bando.spese_generali_massime
        if massimo is None:
            c.append(Controllo("avviso", "Il bando non indica le spese generali ammesse."))
        else:
            esito = "ok" if progetto.spese_generali <= massimo else "errore"
            c.append(
                Controllo(
                    esito,
                    f"Spese generali {_pc(progetto.spese_generali)} (massimo {_pc(massimo)}).",
                )
            )
    totali = {cat: tot for cat, _, _, tot in p.categorie}
    for limite in bando.limiti.all():
        quota = percentuale(totali.get(limite.categoria, ZERO), p.totale_costi)
        esito = "ok" if quota <= limite.percentuale_massima else "errore"
        c.append(
            Controllo(
                esito,
                f"{limite.get_categoria_display()}: {_pc(quota)} del totale "
                f"(massimo {_pc(limite.percentuale_massima)}).",
            )
        )
    if bando.natura_massima is not None and p.natura:
        quota = percentuale(p.natura, p.cofinanziamento)
        esito = "ok" if quota <= bando.natura_massima else "errore"
        c.append(
            Controllo(
                esito,
                f"In natura {_pc(quota)} del cofinanziamento "
                f"(massimo {_pc(bando.natura_massima)}).",
            )
        )
    return c
