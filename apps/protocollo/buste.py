# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Spedizioni postali dei protocolli in uscita (e delle comunicazioni a chi non
# *              ha l'email): elenco dei destinatari in CSV e buste formato DL in Word
# *              (stampa unione o già compilate).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import csv
import io
import re
import zipfile
from xml.sax.saxutils import escape

from apps.anagrafica.servizi import cella_sicura
from apps.core.audit import Azione, registra
from apps.core.models import Organizzazione

from .models import Protocollo

MEZZI_POSTALI = {
    Protocollo.Mezzo.POSTA,
    Protocollo.Mezzo.RACCOMANDATA,
    Protocollo.Mezzo.MANO,
}
RIGHE = 4  # righe dell'indirizzo sulla busta (vuote in fondo)
COLONNE = [
    "Protocollo", "Nominativo", "Qualifica", "Indirizzo", "CAP", "Comune", "Provincia",
    *(f"Riga{i}" for i in range(1, RIGHE + 1)), "Avviso",
]  # fmt: skip

_LOCALITA = re.compile(r"^(?:(?P<cap>\d{5})\s*)?(?P<comune>.*?)\s*(?:\((?P<prov>[A-Za-z]{2})\))?$")


def destinatari_su_carta(protocollo):
    """Destinatari a cui la comunicazione arriva su carta.

    Con posta, raccomandata o consegna a mano sono tutti; con email, PEC o messaggistica solo
    quelli registrati senza un indirizzo email (es. componenti di una lista senza email).
    """
    if protocollo.direzione == Protocollo.Direzione.ENTRATA:
        return []
    if protocollo.mezzo in MEZZI_POSTALI:
        return protocollo.destinatari
    return [c for c in protocollo.destinatari if "@" not in c.indirizzo]


def con_buste(protocollo):
    return bool(destinatari_su_carta(protocollo))


def solo_senza_email(protocollo):
    """Le buste riguardano solo una parte dei destinatari (quelli senza email)."""
    return protocollo.mezzo not in MEZZI_POSTALI


def scomponi_indirizzo(testo):
    """«Via Roma 1, 85100 Potenza (PZ)» → (via, cap, comune, provincia).

    Legge l'indirizzo conservato nella registrazione (non quello attuale dell'anagrafica): la
    busta corrisponde a ciò che è stato protocollato. Un indirizzo email non è postale.
    """
    testo = " ".join((testo or "").split())
    if not testo or "@" in testo:
        return "", "", "", ""
    via, _, localita = testo.rpartition(",")
    if not via:
        if not re.match(r"^\d{5}\b", testo) and not re.search(r"\([A-Za-z]{2}\)$", testo):
            return testo, "", "", ""
        localita = testo
    m = _LOCALITA.match(localita.strip())
    if m is None:  # non succede: l'espressione accetta qualsiasi testo
        return via.strip(), "", localita.strip(), ""
    return via.strip(), m["cap"] or "", m["comune"], (m["prov"] or "").upper()


def riga_busta(nominativo, qualifica, via, cap, comune, prov, riferimento=""):
    """Una riga dell'elenco: colonne del CSV e righe già composte della busta."""
    localita = " ".join(p for p in [cap, comune] if p)
    if prov:
        localita = f"{localita} ({prov})"
    busta = [r for r in [nominativo, qualifica, via, localita] if r]
    busta += [""] * (RIGHE - len(busta))
    avviso = "" if (via and comune) else "indirizzo postale mancante o incompleto"
    return {
        "Protocollo": riferimento, "Nominativo": nominativo, "Qualifica": qualifica,
        "Indirizzo": via, "CAP": cap, "Comune": comune, "Provincia": prov,
        **{f"Riga{i}": r for i, r in enumerate(busta[:RIGHE], 1)}, "Avviso": avviso,
    }  # fmt: skip


def righe_destinatari(protocollo):
    righe = []
    for c in destinatari_su_carta(protocollo):
        via, cap, comune, prov = scomponi_indirizzo(c.indirizzo)
        qualifica = c.soggetto.qualifica if c.soggetto_id else ""
        righe.append(riga_busta(c.descrizione, qualifica, via, cap, comune, prov,
                                protocollo.segnatura))  # fmt: skip
    return righe


def _nome(protocollo, estensione):
    return f"destinatari_{protocollo.anno}_{protocollo.numero:05d}.{estensione}"


def csv_da_righe(righe):
    """CSV per Word, LibreOffice o Excel: separatore «;» e BOM UTF-8 (lettere accentate)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(COLONNE)
    for r in righe:
        writer.writerow([cella_sicura(r[c]) for c in COLONNE])
    return ("\ufeff" + buffer.getvalue()).encode("utf-8")


def csv_destinatari(protocollo, utente):
    righe = righe_destinatari(protocollo)
    registra(
        Azione.ESPORTAZIONE,
        protocollo,
        utente=utente,
        descrizione=f"Destinatari del protocollo {protocollo.segnatura} (CSV)",
        righe=len(righe),
    )
    return csv_da_righe(righe), _nome(protocollo, "csv")


# --- buste DL (220 × 110 mm) in Word -----------------------------------------------------------

_MM = 56.7  # twip per millimetro
_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_PKG = "http://schemas.openxmlformats.org/package/2006"
_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_TIPO = "application/vnd.openxmlformats-officedocument.wordprocessingml"


def _run(testo, *, pt=None, grassetto=False):
    proprieta = ""
    if grassetto:
        proprieta += "<w:b/>"
    if pt:
        proprieta += f'<w:sz w:val="{int(pt * 2)}"/>'
    rpr = f"<w:rPr>{proprieta}</w:rPr>" if proprieta else ""
    return f'<w:r>{rpr}<w:t xml:space="preserve">{escape(testo)}</w:t></w:r>'


def _campo(nome):
    """Campo di stampa unione: Word lo riempie con la colonna del CSV scelto come origine."""
    return f'<w:fldSimple w:instr=" MERGEFIELD {nome} ">{_run(f"«{nome}»")}</w:fldSimple>'


def _paragrafo(contenuto, *, sinistra=0.0, prima=0.0, destra=False, pt=None):
    interlinea = int(pt * 22) if pt else 240
    ppr = (
        f'<w:spacing w:before="{int(prima)}" w:after="0" w:line="{interlinea}" w:lineRule="auto"/>'
    )
    if sinistra:
        ppr += f'<w:ind w:left="{int(sinistra)}"/>'
    if destra:
        ppr += '<w:jc w:val="right"/>'
    return f"<w:p><w:pPr>{ppr}</w:pPr>{contenuto}</w:p>"


def _busta(org, indirizzo, ultima, *, riferimento="", raccomandata=False):
    """Una busta: mittente in alto a sinistra, destinatario nella finestra a destra."""
    sede = " ".join(p for p in [org.cap, org.comune] if p)
    if org.provincia:
        sede = f"{sede} ({org.provincia})"
    mittente = [org.denominazione, org.indirizzo, sede]
    parti = [
        _paragrafo(_run(r, pt=9, grassetto=(i == 0)), pt=9) for i, r in enumerate(mittente) if r
    ]
    if riferimento:
        parti.append(_paragrafo(_run(f"Prot. n. {riferimento}", pt=8), pt=8))
    if raccomandata:
        parti.append(_paragrafo(_run("RACCOMANDATA", pt=11, grassetto=True), destra=True))
    for i, riga in enumerate(indirizzo):
        parti.append(_paragrafo(riga, sinistra=100 * _MM, prima=(18 * _MM if i == 0 else 0)))
    if not ultima:
        parti.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')
    return "".join(parti)


def _documento(corpo):
    sezione = (
        f'<w:sectPr><w:pgSz w:w="{int(220 * _MM)}" w:h="{int(110 * _MM)}" w:orient="landscape"/>'
        f'<w:pgMar w:top="{int(10 * _MM)}" w:right="{int(10 * _MM)}" w:bottom="{int(8 * _MM)}"'
        f' w:left="{int(12 * _MM)}" w:header="0" w:footer="0" w:gutter="0"/></w:sectPr>'
    )
    documento = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{_W}"><w:body>{corpo}{sezione}</w:body></w:document>'
    )
    stili = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:styles xmlns:w="{_W}"><w:docDefaults><w:rPrDefault><w:rPr>'
        '<w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial" w:eastAsia="Arial"/>'
        '<w:sz w:val="24"/><w:lang w:val="it-IT"/></w:rPr></w:rPrDefault>'
        '<w:pPrDefault><w:pPr><w:spacing w:after="0"/></w:pPr></w:pPrDefault></w:docDefaults>'
        "</w:styles>"
    )
    tipi = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Types xmlns="{_PKG}/content-types">'
        '<Default Extension="rels" '
        'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        f'<Override PartName="/word/document.xml" ContentType="{_TIPO}.document.main+xml"/>'
        f'<Override PartName="/word/styles.xml" ContentType="{_TIPO}.styles+xml"/>'
        "</Types>"
    )
    relazioni = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{_PKG}/relationships">'
        f'<Relationship Id="rId1" Type="{_REL}/officeDocument" Target="word/document.xml"/>'
        "</Relationships>"
    )
    relazioni_doc = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{_PKG}/relationships">'
        f'<Relationship Id="rId1" Type="{_REL}/styles" Target="styles.xml"/>'
        "</Relationships>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", tipi)
        z.writestr("_rels/.rels", relazioni)
        z.writestr("word/_rels/document.xml.rels", relazioni_doc)
        z.writestr("word/document.xml", documento)
        z.writestr("word/styles.xml", stili)
    return buffer.getvalue()


def docx_buste(protocollo, utente, *, compilate=False):
    """Buste DL in Word.

    `compilate=False`: documento principale di **stampa unione** con i campi Riga1…Riga4, da
    abbinare al CSV dei destinatari. `compilate=True`: una busta per destinatario, già pronta.
    """
    righe = righe_destinatari(protocollo) if compilate else None
    raccomandata = protocollo.mezzo == Protocollo.Mezzo.RACCOMANDATA
    dati = docx_da_righe(righe, riferimento=protocollo.segnatura, raccomandata=raccomandata)
    if compilate:
        nome = f"buste_{protocollo.anno}_{protocollo.numero:05d}.docx"
    else:
        nome = f"buste_stampa_unione_{protocollo.anno}_{protocollo.numero:05d}.docx"
    registra(
        Azione.ESPORTAZIONE,
        protocollo,
        utente=utente,
        descrizione=f"Buste del protocollo {protocollo.segnatura} (Word"
        + (")" if compilate else ", stampa unione)"),
    )
    return dati, nome


def docx_da_righe(righe=None, *, riferimento="", raccomandata=False):
    """Buste DL in Word: con `righe` una busta compilata per riga; senza, il documento di
    stampa unione con i campi Riga1…Riga4 da abbinare al CSV."""
    org = Organizzazione.corrente()
    opzioni = {"riferimento": riferimento, "raccomandata": raccomandata}
    if righe is None:
        campi = [_campo(f"Riga{i}") for i in range(1, RIGHE + 1)]
        return _documento(_busta(org, campi, ultima=True, **opzioni))
    corpo = "".join(
        _busta(org, [_run(r[f"Riga{i}"]) for i in range(1, RIGHE + 1)],
               ultima=(n == len(righe) - 1), **opzioni)
        for n, r in enumerate(righe)
    )  # fmt: skip
    return _documento(corpo)


# --- etichette adesive in PDF (fogli A4) ---------------------------------------------------------

# misure in mm: colonne, righe, larghezza e altezza dell'etichetta, margini sinistro e superiore,
# passo orizzontale e verticale (etichetta + spazio fra le etichette)
FORMATI_ETICHETTE = {
    "70x37": {"nome": "70 × 37 mm, 24 per foglio (3 × 8)", "colonne": 3, "righe": 8,
              "larghezza": 70, "altezza": 37, "sinistra": 0, "sopra": 0.5,
              "passo_x": 70, "passo_y": 37},
    "70x36": {"nome": "70 × 36 mm, 24 per foglio (3 × 8, con margini)", "colonne": 3,
              "righe": 8, "larghezza": 70, "altezza": 36, "sinistra": 0, "sopra": 4.5,
              "passo_x": 70, "passo_y": 36},
    "63x38": {"nome": "63,5 × 38,1 mm, 21 per foglio (3 × 7, tipo L7160)", "colonne": 3,
              "righe": 7, "larghezza": 63.5, "altezza": 38.1, "sinistra": 7.2, "sopra": 15.1,
              "passo_x": 66, "passo_y": 38.1},
    "99x38": {"nome": "99,1 × 38,1 mm, 14 per foglio (2 × 7, tipo L7163)", "colonne": 2,
              "righe": 7, "larghezza": 99.1, "altezza": 38.1, "sinistra": 4.7, "sopra": 15.1,
              "passo_x": 101.6, "passo_y": 38.1},
}  # fmt: skip
FORMATO_ETICHETTE = "70x37"


def formato_etichette(valore):
    return valore if valore in FORMATI_ETICHETTE else FORMATO_ETICHETTE


def posizione_iniziale(valore, formato):
    """Prima etichetta libera (1 = in alto a sinistra), per riusare un foglio già iniziato."""
    f = FORMATI_ETICHETTE[formato]
    try:
        n = int(valore)
    except (TypeError, ValueError):
        return 1
    return min(max(n, 1), f["colonne"] * f["righe"])


def pdf_etichette(righe, formato=FORMATO_ETICHETTE, inizio=1):
    """Un'etichetta per riga (le righe di riga_busta), solo con indirizzo postale completo.

    Restituisce (pdf, quante etichette, quante righe scartate perché senza indirizzo).
    """
    from apps.core.pdf import genera_pdf

    f = FORMATI_ETICHETTE[formato]
    per_foglio = f["colonne"] * f["righe"]
    valide = [r for r in righe if not r["Avviso"]]
    testi = [[r[f"Riga{i}"] for i in range(1, RIGHE + 1) if r[f"Riga{i}"]] for r in valide]
    posti = [None] * (inizio - 1) + testi
    fogli = []
    for p in range(0, max(len(posti), 1), per_foglio):
        fogli.append([
            {"righe": t, "x": f["sinistra"] + (i % f["colonne"]) * f["passo_x"],
             "y": f["sopra"] + (i // f["colonne"]) * f["passo_y"]}
            for i, t in enumerate(posti[p:p + per_foglio]) if t is not None
        ])  # fmt: skip
    dati = genera_pdf("protocollo/pdf/etichette.html", {"fogli": fogli, "formato": f})
    return dati, len(testi), len(righe) - len(valide)


def etichette_protocollo(protocollo, utente, formato, inizio):
    righe = righe_destinatari(protocollo)
    dati, n, scartate = pdf_etichette(righe, formato, inizio)
    registra(Azione.ESPORTAZIONE, protocollo, utente=utente,
             descrizione=f"Etichette dei destinatari del protocollo {protocollo.segnatura}",
             etichette=n, senza_indirizzo=scartate, formato=formato)  # fmt: skip
    return dati, _nome(protocollo, "pdf").replace("destinatari_", "etichette_")
