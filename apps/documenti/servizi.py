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
TEMPLATE_BENEMERENZA = "documenti/pdf/benemerenza.html"
SEGNAPOSTO_STAMPA = {
    **SEGNAPOSTO,
    "luogo": "comune dell'associazione",
    "data_estesa": "data di oggi per esteso (8 novembre 2026)",
    "firmatario": "nome del firmatario",
    "sede": "indirizzo della sede (via, CAP, comune e provincia)",
    "codice_fiscale_ente": "codice fiscale dell'associazione",
    "email_ente": "email dell'associazione",
    "pec_ente": "PEC dell'associazione",
    "rappresentante_legale": "nome del rappresentante legale (titolare del trattamento)",
    "qualifica_rappresentante": "qualifica del rappresentante legale",
}
_RE_SEGNAPOSTO = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")


class OperazioneNonValida(ValidationError):
    """Stampa non possibile (messaggio per l'utente)."""


def segnaposto_sconosciuti(*testi):
    trovati = {m for t in testi for m in _RE_SEGNAPOSTO.findall(t or "")}
    return sorted(trovati - set(SEGNAPOSTO_STAMPA))


def in_carica(ruolo):
    """Nome («Mario Rossi», con il titolo) di chi ricopre oggi il ruolo, o stringa vuota."""
    from apps.organi.models import Carica

    oggi = timezone.localdate()
    carica = (
        Carica.objects.filter(ruolo=ruolo, dal__lte=oggi)
        .exclude(al__lte=oggi)
        .select_related("soggetto")
        .order_by("-dal")
        .first()
    )
    return carica.soggetto.intestazione if carica else ""


def firma_legale(modello):
    """Firma del rappresentante legale per i modelli che la richiedono, o None."""
    if not modello.firma_legale:
        return None
    from apps.organi.firme import QUALIFICHE, RAPPRESENTANTE, Firma, legale_rappresentante

    return legale_rappresentante() or Firma(QUALIFICHE[RAPPRESENTANTE])


def firmatario(modello):
    """Nome del firmatario: il rappresentante legale (se richiesto), quello del modello o il
    presidente in carica."""
    legale = firma_legale(modello)
    if legale is not None:
        return legale.nome
    return modello.firma_nome or in_carica("presidente")


def qualifica_firmatario(modello):
    legale = firma_legale(modello)
    return legale.qualifica if legale is not None else modello.firma_ruolo


def seconda_firma(modello):
    if not modello.seconda_firma:
        return None
    return {"ruolo": modello.get_seconda_firma_display(), "nome": in_carica(modello.seconda_firma)}


def stemmi(modello, org):
    """Immagini in testa all'attestato solenne: logo dell'ente e stemma del modello (o il logo
    del modulo di adesione, es. della presidenza nazionale). Percorsi relativi a MEDIA_ROOT."""
    elenco = [org.logo.name if org.logo else ""]
    secondo = modello.stemma or org.modulo_logo
    elenco.append(secondo.name if secondo else "")
    return [s for s in elenco if s]


def template_di(modello):
    return TEMPLATE_BENEMERENZA if modello.tipo == modello.Tipo.BENEMERENZA else TEMPLATE


def _contesto(soggetto, firma):
    org = Organizzazione.corrente()
    c = contesto_generale()
    c.update(
        luogo=org.comune,
        data_estesa=date_format(timezone.localdate(), "j F Y").lower(),
        firmatario=firma,
        sede=" ".join(
            p
            for p in (
                org.indirizzo + ("," if org.indirizzo else ""),
                org.cap,
                org.comune,
                f"({org.provincia})" if org.provincia else "",
            )
            if p
        ).strip(" ,"),  # fmt: skip
        codice_fiscale_ente=org.codice_fiscale,
        email_ente=org.email,
        pec_ente=org.pec,
    )
    from apps.organi.firme import legale_rappresentante

    rappresentante = legale_rappresentante()
    if rappresentante:
        c.update(
            rappresentante_legale=rappresentante.nome,
            qualifica_rappresentante=rappresentante.qualifica,
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
        "firma_ruolo": qualifica_firmatario(modello),
        "firma_nome": firma,
        "luogo_data": ", ".join(
            p for p in (org.comune, date_format(timezone.localdate(), "j F Y").lower()) if p
        ),
        "protocollo": protocollo,
        "seconda_firma": seconda_firma(modello),
        "stemmi": stemmi(modello, org),
    }


def nome_file(modello):
    return f"{slugify(modello.nome) or 'documento'}_{timezone.localdate():%Y%m%d}.pdf"


def anteprima(modello, soggetto=None):
    """PDF di prova (nessuna registrazione)."""
    return genera_pdf(template_di(modello), _contesto_pdf(modello, [soggetto] if soggetto else []))


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
    pdf = genera_pdf(template_di(modello), _contesto_pdf(modello, soggetti, protocollo))
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
