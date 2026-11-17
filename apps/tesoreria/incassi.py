# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Incassi diversi dalle quote (ricevuta nella numerazione delle quote e prima
# *              nota), note di storno e rimborsi di quote e incassi, registro degli incassi
# *              con i totali per metodo e per conto (quadratura con cassa ed estratto conto).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import io
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal

from django.db import transaction

from apps.anagrafica.servizi import cella_sicura
from apps.core.audit import Azione, registra
from apps.core.numerazione import prossimo_numero

from .models import METODI, Incasso, Movimento, Storno, Voce
from .servizi import OperazioneNonValida, annulla_movimento, conto_per_metodo, registra_movimento

SEQ_RICEVUTA = "ricevuta_quota"  # la stessa delle quote: un solo registro delle ricevute
SEQ_STORNO = "nota_storno"  # annuale
VOCE_RIMBORSI = "U.A.5"  # Uscite diverse di gestione
NOMI_METODI = dict(METODI)


@transaction.atomic
def registra_incasso(dati, utente):
    """Ricevuta numerata e movimento in prima nota. `dati`: data, tipo, soggetto, nominativo,
    codice_fiscale, importo, metodo, riferimento, causale, voce (facoltativa)."""
    dati = dict(dati)
    if not dati.get("importo") or dati["importo"] <= 0:
        raise OperazioneNonValida("L'importo deve essere maggiore di zero.")
    soggetto = dati.get("soggetto")
    if soggetto is not None:
        dati["nominativo"] = dati.get("nominativo") or soggetto.nome_completo
        dati["codice_fiscale"] = dati.get("codice_fiscale") or (soggetto.codice_fiscale or "")
    if not (dati.get("nominativo") or "").strip():
        raise OperazioneNonValida("Indicare chi ha versato.")
    voce = dati.get("voce") or Voce.objects.filter(codice=Incasso.VOCI[dati["tipo"]]).first()
    conto = conto_per_metodo(dati["metodo"])
    if conto is None:
        raise OperazioneNonValida("Nessun conto impostato per questo metodo (Tesoreria → Conti).")
    incasso = Incasso(
        **{**dati, "voce": voce},
        ricevuta_anno=dati["data"].year,
        ricevuta_numero=prossimo_numero(SEQ_RICEVUTA, dati["data"].year),
        creato_da=utente,
        modificato_da=utente,
    )
    incasso.movimento = registra_movimento({
        "data": incasso.data, "tipo": Movimento.Tipo.ENTRATA, "conto": conto,
        "importo": incasso.importo, "voce": voce,
        "descrizione": f"{incasso.get_tipo_display().split(' (')[0]}: {incasso.causale}"[:255],
        "controparte": soggetto, "controparte_testo": incasso.nominativo[:200],
        "documento": f"ricevuta n. {incasso.codice_ricevuta}",
    }, utente)  # fmt: skip
    incasso.save()
    registra(Azione.CREAZIONE, incasso, utente=utente, importo=str(incasso.importo),
             ricevuta=incasso.codice_ricevuta)  # fmt: skip
    return incasso


def _movimento_originale(documento):
    if isinstance(documento, Incasso):
        return documento.movimento
    return Movimento.objects.filter(tessera=documento, annullato=False).first()


@transaction.atomic
def storna(documento, utente, *, data, motivo, rimborso, metodo="", annulla_tessera=False):
    """Nota di storno di una ricevuta (Incasso o Tessera pagata).

    rimborso=True: il denaro è stato restituito, uscita in prima nota con lo stesso metodo (o
    quello indicato). rimborso=False: incasso registrato per errore, si annulla il movimento
    (serve l'esercizio aperto). Per una quota, `annulla_tessera` annulla anche il tesseramento.
    """
    from apps.soci.models import Tessera

    motivo = (motivo or "").strip()
    if not motivo:
        raise OperazioneNonValida("Indicare il motivo dello storno.")
    tessera = documento if isinstance(documento, Tessera) else None
    if tessera is not None:
        if not tessera.pagata or tessera.ricevuta_numero is None:
            raise OperazioneNonValida("La quota non risulta incassata con ricevuta.")
        if tessera.incasso_esterno:
            raise OperazioneNonValida("Quota incassata fuori dall'applicazione: nulla da stornare.")
    if documento.storni.exists():
        raise OperazioneNonValida("La ricevuta è già stata stornata.")
    importo = documento.importo
    originale = _movimento_originale(documento)
    movimento = None
    if rimborso:
        metodo = metodo or (documento.metodo if tessera is None else documento.metodo_pagamento)
        conto = conto_per_metodo(metodo)
        if conto is None:
            raise OperazioneNonValida("Nessun conto impostato per il metodo del rimborso.")
        movimento = registra_movimento({
            "data": data, "tipo": Movimento.Tipo.USCITA, "conto": conto, "importo": importo,
            "voce": Voce.objects.get(codice=VOCE_RIMBORSI),
            "descrizione": f"Rimborso ricevuta n. {documento.codice_ricevuta}: {motivo}"[:255],
            "controparte": originale.controparte if originale else None,
            "controparte_testo": (originale.controparte_testo if originale else "")[:200],
            "documento": "nota di storno",
        }, utente)  # fmt: skip
    elif originale is not None:
        annulla_movimento(originale, utente, f"Storno della ricevuta n. "
                                             f"{documento.codice_ricevuta}: {motivo}")  # fmt: skip
    storno = Storno.objects.create(
        anno=data.year, numero=prossimo_numero(SEQ_STORNO, data.year), data=data,
        tessera=tessera, incasso=None if tessera else documento, importo=importo,
        motivo=motivo[:255], rimborso=rimborso, metodo=metodo if rimborso else "",
        movimento=movimento, creato_da=utente, modificato_da=utente,
    )  # fmt: skip
    if movimento is not None:
        movimento.documento = f"nota di storno n. {storno.codice}"
        movimento.save(update_fields=["documento"])
    if tessera is not None and annulla_tessera and not tessera.annullata:
        from apps.soci import servizi as soci

        soci.annulla_tessera(tessera, utente, f"Storno della quota: {motivo}")
    registra(Azione.ANNULLAMENTO, storno, utente=utente, ricevuta=documento.codice_ricevuta,
             importo=str(importo), rimborso=rimborso, motivo=motivo)  # fmt: skip
    return storno


# --- registro degli incassi ----------------------------------------------------------------


@dataclass
class Riga:
    data: object
    documento: str
    tipo: str
    nominativo: str
    metodo: str
    conto: str
    importo: Decimal
    percorso: str = ""


@dataclass
class Registro:
    dal: object
    al: object
    righe: list = field(default_factory=list)
    per_metodo: dict = field(default_factory=dict)
    per_conto: dict = field(default_factory=dict)
    totale: Decimal = Decimal("0")
    ricevute: int = 0
    storni: int = 0


def registro(dal, al):
    """Ricevute (quote e altri incassi) e note di storno del periodo, con i totali."""
    from apps.soci.models import Tessera

    righe = []
    quote = (
        Tessera.objects.filter(pagata_il__range=(dal, al), ricevuta_numero__isnull=False)
        .exclude(incasso_esterno=True)
        .select_related("socio__soggetto")
    )
    for t in quote:
        conto = conto_per_metodo(t.metodo_pagamento)
        righe.append(Riga(t.pagata_il, f"Ricevuta {t.codice_ricevuta}", f"Quota {t.anno}",
                          t.socio.soggetto.nome_completo,
                          t.get_metodo_pagamento_display() or "—", str(conto or "—"),
                          t.importo, t.socio.get_absolute_url()))  # fmt: skip
    for i in Incasso.objects.filter(data__range=(dal, al)).select_related("movimento__conto"):
        conto = i.movimento.conto if i.movimento else conto_per_metodo(i.metodo)
        righe.append(Riga(i.data, f"Ricevuta {i.codice_ricevuta}", i.get_tipo_display(),
                          i.nominativo, i.get_metodo_display(), str(conto or "—"), i.importo,
                          i.get_absolute_url()))  # fmt: skip
    storni = Storno.objects.filter(data__range=(dal, al)).select_related(
        "tessera__socio__soggetto", "incasso", "movimento__conto"
    )
    for s in storni:
        doc = s.tessera or s.incasso
        nominativo = s.tessera.socio.soggetto.nome_completo if s.tessera else doc.nominativo
        if s.rimborso:
            metodo = NOMI_METODI.get(s.metodo, "—")
        else:
            metodo = doc.get_metodo_pagamento_display() if s.tessera else doc.get_metodo_display()
        if s.movimento:
            conto = s.movimento.conto
        else:
            conto = conto_per_metodo(doc.metodo_pagamento if s.tessera else doc.metodo)
        tipo = "Rimborso" if s.rimborso else "Storno (incasso annullato)"
        righe.append(Riga(s.data, f"Storno {s.codice} (ric. {s.ricevuta})", tipo, nominativo,
                          metodo, str(conto or "—"), -s.importo))  # fmt: skip
    righe.sort(key=lambda r: (r.data, r.documento))
    r = Registro(dal, al, righe)
    metodi, conti = defaultdict(Decimal), defaultdict(Decimal)
    for riga in righe:
        metodi[riga.metodo] += riga.importo
        conti[riga.conto] += riga.importo
        r.totale += riga.importo
    r.per_metodo, r.per_conto = dict(sorted(metodi.items())), dict(sorted(conti.items()))
    r.ricevute = sum(1 for x in righe if x.importo > 0)
    r.storni = sum(1 for x in righe if x.importo < 0)
    return r


def registro_xlsx(r):
    from openpyxl import Workbook
    from openpyxl.styles import Font

    wb = Workbook()
    ws = wb.active
    ws.title = "Registro incassi"
    ws.append([f"Registro degli incassi dal {r.dal:%d/%m/%Y} al {r.al:%d/%m/%Y}"])
    ws.append(["Data", "Documento", "Tipo", "Nominativo", "Metodo", "Conto", "Importo"])
    ws["A2"].font = ws["B2"].font = Font(bold=True)
    for riga in r.righe:
        ws.append([riga.data, cella_sicura(riga.documento), cella_sicura(riga.tipo),
                   cella_sicura(riga.nominativo), riga.metodo, riga.conto,
                   float(riga.importo)])  # fmt: skip
    ws.append([])
    for titolo, gruppo in (("Per metodo", r.per_metodo), ("Per conto", r.per_conto)):
        ws.append([titolo])
        for nome, valore in gruppo.items():
            ws.append(["", nome, "", "", "", "", float(valore)])
    ws.append(["Totale", "", "", "", "", "", float(r.totale)])
    for col, larghezza in zip("ABCDEFG", (12, 30, 28, 34, 14, 22, 12), strict=True):
        ws.column_dimensions[col].width = larghezza
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
