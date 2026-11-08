# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Tessera digitale: PDF in formato carta con QR di verifica (da inviare per
# *              email; quella fisica resta la tessera prestampata) e verifica pubblica
# *              con il QR o con numero di tessera e cognome. Mostra solo l'essenziale.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import re
import secrets
from dataclasses import dataclass

from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from apps.core.audit import Azione, registra

from .models import Socio, Tessera


def token_di(tessera):
    """Codice di verifica (casuale, non ricavabile dal numero), creato alla prima occorrenza."""
    if tessera.token_verifica:
        return tessera.token_verifica
    for _ in range(3):
        try:
            with transaction.atomic():
                tessera.token_verifica = secrets.token_urlsafe(24)
                tessera.save(update_fields=["token_verifica"])
            return tessera.token_verifica
        except IntegrityError:  # coincidenza praticamente impossibile: si riprova
            continue
    raise RuntimeError("Codice di verifica non generato.")


def url_verifica(tessera, base_url):
    return base_url.rstrip("/") + reverse("verifica_tessera_codice", args=[token_di(tessera)])


@dataclass
class Esito:
    valida: bool
    motivo: str
    nome: str
    sezione: str
    anno: int
    codice: str


def esito(tessera):
    """Validità per un controllo esterno: tessera dell'anno in corso, non annullata, quota
    pagata (o esente) e socio attivo."""
    socio = tessera.socio
    anno = timezone.localdate().year
    if tessera.annullata:
        valida, motivo = False, "tessera annullata"
    elif socio.stato != Socio.Stato.ATTIVO:
        valida, motivo = False, "il titolare non risulta socio attivo"
    elif tessera.anno != anno:
        valida, motivo = False, f"tessera dell'anno {tessera.anno}"
    elif not tessera.pagata and tessera.importo > 0:
        valida, motivo = False, "quota dell'anno non ancora versata"
    else:
        valida, motivo = True, f"socio in regola per l'anno {anno}"
    s = socio.soggetto
    return Esito(
        valida,
        motivo,
        " ".join(p for p in (s.nome, s.cognome) if p),
        socio.sezione.nome if socio.sezione_id else "",
        tessera.anno,
        tessera.codice,
    )


def da_codice(codice):
    return (
        Tessera.objects.select_related("socio__soggetto", "socio__sezione", "carta")
        .filter(token_verifica=codice or "-")
        .first()
    )


def da_numero(numero, cognome):
    """La tessera più recente con quel numero (con o senza zeri iniziali) e quel cognome."""
    numero = re.sub(r"\s", "", numero or "")
    cognome = " ".join((cognome or "").split())
    if not numero or not cognome:
        return None
    qs = Tessera.objects.select_related("socio__soggetto", "socio__sezione", "carta").filter(
        socio__soggetto__cognome__iexact=cognome
    )
    trovate = [t for t in qs.filter(carta__isnull=False).order_by("-anno")
               if t.carta.codice.lstrip("0") == numero.lstrip("0")]  # fmt: skip
    return trovate[0] if trovate else None


def pdf(tessera, utente, base_url):
    """La tessera digitale in PDF (formato carta di credito, due facce)."""
    from apps.core.models import Organizzazione
    from apps.core.pdf import genera_pdf
    from apps.patrimonio.servizi import qr_svg

    indirizzo = url_verifica(tessera, base_url)
    contenuto = genera_pdf("soci/pdf/tessera_digitale.html", {
        "tessera": tessera, "organizzazione": Organizzazione.corrente(),
        "qr": qr_svg(indirizzo, scala=2), "url_verifica": indirizzo,
    })  # fmt: skip
    registra(Azione.ESPORTAZIONE, tessera, utente=utente, documento="tessera digitale")
    return contenuto


def nome_file(tessera):
    return f"tessera_{tessera.anno}_{tessera.socio.numero}.pdf"
