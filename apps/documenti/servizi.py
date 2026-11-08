# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Stampa dei documenti dai modelli: composizione dei testi (segnaposto delle
# *              Comunicazioni, mai il motore dei template), PDF e protocollazione in uscita.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import re

import markdown
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.html import escape
from django.utils.text import slugify

from apps.comunicazioni.servizi import (
    SEGNAPOSTO,
    componi,
    contesto_generale,
    contesto_soggetto,
)
from apps.core.audit import Azione, registra
from apps.core.models import Organizzazione
from apps.core.pdf import genera_pdf

TEMPLATE = "documenti/pdf/documento.html"
SEGNAPOSTO_STAMPA = {
    **SEGNAPOSTO,
    "luogo": "comune dell'associazione",
    "data_estesa": "data di oggi per esteso (8 novembre 2026)",
    "firmatario": "nome del firmatario",
}
_RE_SEGNAPOSTO = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")


class OperazioneNonValida(ValidationError):
    """Stampa non possibile (messaggio per l'utente)."""


def segnaposto_sconosciuti(*testi):
    trovati = {m for t in testi for m in _RE_SEGNAPOSTO.findall(t or "")}
    return sorted(trovati - set(SEGNAPOSTO_STAMPA))


def firmatario(modello):
    """Nome del firmatario: quello del modello o il presidente in carica."""
    if modello.firma_nome:
        return modello.firma_nome
    from apps.organi.models import Carica

    oggi = timezone.localdate()
    carica = (
        Carica.objects.filter(ruolo=Carica.Ruolo.PRESIDENTE, dal__lte=oggi)
        .exclude(al__lt=oggi)
        .select_related("soggetto")
        .order_by("-dal")
        .first()
    )
    return carica.soggetto.nome_completo if carica else ""


def _contesto(soggetto, firma):
    org = Organizzazione.corrente()
    c = contesto_generale()
    c.update(
        luogo=org.comune,
        data_estesa=date_format(timezone.localdate(), "j F Y").lower(),
        firmatario=firma,
    )
    if soggetto is not None:
        c.update(contesto_soggetto(soggetto))
    return c


def testo_html(testo, contesto):
    """Segnaposto sostituiti, poi il poco Markdown ammesso. L'HTML scritto dall'utente (e
    quello nei dati dei soggetti) viene neutralizzato prima della conversione."""
    composto = escape(componi(testo, contesto))
    return markdown.markdown(composto, extensions=["sane_lists"])


def pagine(modello, soggetti):
    firma = firmatario(modello)
    risultato = []
    for s in soggetti or [None]:
        c = _contesto(s, firma)
        risultato.append(
            {
                "destinatario": s,
                "titolo": componi(modello.titolo, c),
                "html": testo_html(modello.corpo, c),
            }
        )
    return risultato, firma


def destinatari_validi(soggetti):
    """Esclude schede archiviate e persone decedute; restituisce (validi, esclusi)."""
    validi, esclusi = [], []
    for s in soggetti:
        (esclusi if (not s.attivo or s.deceduto) else validi).append(s)
    return validi, esclusi


def _contesto_pdf(modello, soggetti, protocollo=None):
    elenco, firma = pagine(modello, soggetti)
    org = Organizzazione.corrente()
    return {
        "organizzazione": org,
        "modello": modello,
        "pagine": elenco,
        "firma_ruolo": modello.firma_ruolo,
        "firma_nome": firma,
        "luogo_data": ", ".join(
            p for p in (org.comune, date_format(timezone.localdate(), "j F Y").lower()) if p
        ),
        "protocollo": protocollo,
    }


def nome_file(modello):
    return f"{slugify(modello.nome) or 'documento'}_{timezone.localdate():%Y%m%d}.pdf"


def anteprima(modello, soggetto=None):
    """PDF di prova (nessuna registrazione)."""
    return genera_pdf(TEMPLATE, _contesto_pdf(modello, [soggetto] if soggetto else []))


@transaction.atomic
def stampa(modello, soggetti, utente, *, protocolla=False, mezzo="posta"):
    """PDF con una pagina per destinatario. Con `protocolla` registra un protocollo in uscita
    (numero stampato sul documento) e vi allega il PDF. Restituisce (pdf, protocollo)."""
    if not modello.attivo:
        raise OperazioneNonValida(f"Il modello «{modello}» non è attivo.")
    soggetti = list(soggetti)
    if not soggetti and modello.tipo == modello.Tipo.LETTERA:
        raise OperazioneNonValida("Una lettera richiede almeno un destinatario.")
    from apps.protocollo import servizi as prot
    from apps.protocollo.models import Corrispondente, Protocollo

    protocollo = None
    if protocolla:
        oggetto = componi(modello.titolo, _contesto(None, "")) or modello.nome
        corrispondenti = [prot.corrispondente_da_soggetto(s, "destinatario") for s in soggetti]
        direzione = Protocollo.Direzione.USCITA if soggetti else Protocollo.Direzione.INTERNO
        if not soggetti:
            org = Organizzazione.corrente()
            corrispondenti = [{"ruolo": Corrispondente.Ruolo.MITTENTE,
                               "descrizione": org.denominazione}]  # fmt: skip
        protocollo = prot.registra_protocollo(
            {"direzione": direzione, "mezzo": mezzo, "oggetto": oggetto[:500]},
            corrispondenti,
            utente,
        )
    pdf = genera_pdf(TEMPLATE, _contesto_pdf(modello, soggetti, protocollo))
    if protocollo:
        prot.aggiungi_allegato(
            protocollo, ContentFile(pdf, name=nome_file(modello)), utente, principale=True,
            controlla=False,
        )  # fmt: skip
    registra(
        Azione.ESPORTAZIONE,
        modello,
        utente=utente,
        destinatari=len(soggetti),
        protocollo=protocollo.segnatura if protocollo else None,
    )
    return pdf, protocollo
