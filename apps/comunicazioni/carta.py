# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Comunicazioni su carta per chi non ha l'email: elenco in CSV, buste DL in
# *              Word (le stesse del protocollo) e lettere in PDF con i segnaposto risolti.
# *              Vale il consenso come per le email: niente consenso, niente lettera.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.utils import timezone

from apps.core.audit import Azione, registra
from apps.core.models import Organizzazione
from apps.protocollo import buste

from .models import Destinatario, Finalita
from .servizi import componi, consensi_prestati, contesto_destinatario

SENZA_EMAIL = "senza email"


def destinatari_su_carta(invio):
    """Esclusi solo perché senza email (schede attive, persone in vita) che possono ricevere
    la comunicazione: per le finalità diverse da quella istituzionale serve il consenso."""
    esclusi = list(
        invio.destinatari.filter(
            stato=Destinatario.Stato.ESCLUSO, motivo=SENZA_EMAIL, soggetto__isnull=False
        ).select_related("soggetto")
    )
    if invio.finalita != Finalita.ISTITUZIONALE:
        con_consenso = consensi_prestati([d.soggetto for d in esclusi], invio.finalita)
        esclusi = [d for d in esclusi if d.soggetto_id in con_consenso]
    return sorted(esclusi, key=lambda d: d.nome)


def senza_consenso(invio):
    """Quanti, senza email, non possono ricevere nemmeno la lettera (consenso mancante)."""
    if invio.finalita == Finalita.ISTITUZIONALE:
        return 0
    tutti = invio.destinatari.filter(
        stato=Destinatario.Stato.ESCLUSO, motivo=SENZA_EMAIL, soggetto__isnull=False
    ).count()
    return tutti - len(destinatari_su_carta(invio))


def _riferimento(invio):
    return invio.protocollo.segnatura if invio.protocollo_id else ""


def righe(invio):
    """Righe delle buste dall'indirizzo attuale dell'anagrafica."""
    riferimento = _riferimento(invio)
    return [
        buste.riga_busta(
            s.intestazione, s.qualifica, s.indirizzo, s.cap, s.comune, s.provincia, riferimento
        )  # fmt: skip
        for d in destinatari_su_carta(invio)
        for s in [d.soggetto]
    ]


def _registra(invio, utente, cosa, n):
    registra(Azione.ESPORTAZIONE, invio, utente=utente,
             descrizione=f"{cosa} della comunicazione «{invio}»", righe=n)  # fmt: skip


def csv(invio, utente):
    r = righe(invio)
    _registra(invio, utente, "Destinatari su carta (CSV)", len(r))
    return buste.csv_da_righe(r), f"destinatari_carta_{invio.pk}.csv"


def docx(invio, utente, *, compilate=True):
    r = righe(invio) if compilate else None
    dati = buste.docx_da_righe(r, riferimento=_riferimento(invio))
    cosa = "Buste (Word)" if compilate else "Buste (Word, stampa unione)"
    _registra(invio, utente, cosa, len(r) if r is not None else 0)
    nome = f"buste_{invio.pk}.docx" if compilate else f"buste_stampa_unione_{invio.pk}.docx"
    return dati, nome


def etichette(invio, utente, formato, inizio):
    dati, n, scartate = buste.pdf_etichette(righe(invio), formato, inizio)
    _registra(invio, utente, "Etichette (PDF)", n)
    return dati, f"etichette_{invio.pk}.pdf"


def lettere(invio, utente):
    """Una lettera per destinatario su carta, con gli stessi segnaposto dell'email."""
    from apps.core.pdf import genera_pdf

    org = Organizzazione.corrente()
    elenco = []
    for d in destinatari_su_carta(invio):
        contesto = contesto_destinatario(invio, d)
        s = d.soggetto
        localita = " ".join(p for p in [s.cap, s.comune] if p)
        if s.provincia:
            localita = f"{localita} ({s.provincia})"
        elenco.append({
            "indirizzo": [r for r in [s.intestazione, s.qualifica, s.indirizzo, localita] if r],
            "oggetto": " ".join(componi(invio.oggetto, contesto).split()),
            "testo": componi(invio.corpo, contesto),
        })  # fmt: skip
    dati = genera_pdf("comunicazioni/pdf/lettere.html", {
        "organizzazione": org, "lettere": elenco, "invio": invio,
        "riferimento": _riferimento(invio), "oggi": timezone.localdate(),
    })  # fmt: skip
    _registra(invio, utente, "Lettere (PDF)", len(elenco))
    return dati, f"lettere_{invio.pk}.pdf"
