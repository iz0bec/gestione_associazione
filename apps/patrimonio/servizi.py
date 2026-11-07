# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Operazioni del patrimonio: inventario numerato, foto ripulite, valutazioni,
# *              prestiti e uscite, passaggi di consegne con PDF e impronta, codici QR.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import csv
import hashlib
import io
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from apps.anagrafica.servizi import cella_sicura
from apps.core.audit import Azione, campi_modificati, registra
from apps.core.models import Organizzazione
from apps.core.numerazione import prossimo_numero

from .models import SEQ_INVENTARIO, Bene, PassaggioConsegne, Uscita, Valutazione

FOTO_MAX_MB = 15
FOTO_LATO = 1600


class OperazioneNonValida(ValidationError):
    """Operazione rifiutata per una regola del patrimonio (messaggio per l'utente)."""


def foto_ripulita(file):
    """JPEG ridimensionato e senza metadati (EXIF: posizione GPS, dispositivo, data)."""
    from PIL import Image, ImageOps, UnidentifiedImageError

    if file.size > FOTO_MAX_MB * 1024 * 1024:
        raise OperazioneNonValida(f"La foto supera {FOTO_MAX_MB} MB.")
    try:
        img = Image.open(file)
        img = ImageOps.exif_transpose(img)
        img.thumbnail((FOTO_LATO, FOTO_LATO))
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise OperazioneNonValida("Il file non è un'immagine valida.") from None
    uscita = io.BytesIO()
    img.save(uscita, "JPEG", quality=85, optimize=True)
    return ContentFile(uscita.getvalue(), name="foto.jpg")


@transaction.atomic
def salva_bene(form, utente, *, foto=None, togli_foto=False):
    nuovo = form.instance.pk is None
    dettagli = {} if nuovo else campi_modificati(form)
    bene = form.save(commit=False)
    if nuovo:
        bene.numero = prossimo_numero(SEQ_INVENTARIO)
        bene.creato_da = utente
        bene.valore = bene.valore or bene.valore_acquisizione
    if foto:
        nuova = foto_ripulita(foto)
        if bene.foto:
            bene.foto.delete(save=False)
        bene.foto.save("foto.jpg", nuova, save=False)
    elif togli_foto and bene.foto:
        bene.foto.delete(save=False)
    bene.modificato_da = utente
    bene.save()
    if nuovo:
        registra(Azione.CREAZIONE, bene, utente=utente, numero=bene.numero)
    elif dettagli.get("campi") or foto or togli_foto:
        registra(Azione.MODIFICA, bene, utente=utente, foto=bool(foto), **dettagli)
    return bene


@transaction.atomic
def valuta(bene, utente, *, data, valore, metodo, note=""):
    v = Valutazione.objects.create(
        bene=bene, data=data, valore=valore, metodo=metodo, note=note, registrata_da=utente
    )
    ultima = bene.valutazioni.order_by("-data", "-registrata_il").first()
    bene.valore = ultima.valore
    bene.modificato_da = utente
    bene.save(update_fields=["valore", "modificato_da", "modificato_il"])
    registra(Azione.MODIFICA, bene, utente=utente, valutazione=str(valore), metodo=metodo)
    return v


@transaction.atomic
def registra_uscita(bene, utente, *, tipo, data, motivo, controparte=None, controparte_testo="",
                    condizioni="", restituzione_prevista=None, importo=Decimal("0")):  # fmt: skip
    bene = Bene.objects.select_for_update().get(pk=bene.pk)
    if not bene.in_patrimonio:
        raise OperazioneNonValida("Il bene non è più nel patrimonio.")
    if not (motivo or "").strip():
        raise OperazioneNonValida("Indicare il motivo.")
    if tipo == Uscita.Tipo.PRESTITO:
        if bene.stato == Bene.Stato.IN_PRESTITO:
            raise OperazioneNonValida("Il bene è già in prestito.")
        if not (controparte or controparte_testo):
            raise OperazioneNonValida("Indicare a chi viene prestato.")
        if restituzione_prevista and restituzione_prevista < data:
            raise OperazioneNonValida("La restituzione non può precedere il prestito.")
    elif bene.stato == Bene.Stato.IN_PRESTITO and tipo != Uscita.Tipo.SMARRIMENTO:
        raise OperazioneNonValida("Il bene è in prestito: registrare prima la restituzione.")
    if controparte and not controparte_testo:
        controparte_testo = controparte.nome_completo
    u = Uscita.objects.create(
        bene=bene, tipo=tipo, data=data, motivo=motivo.strip(), controparte=controparte,
        controparte_testo=controparte_testo, condizioni=condizioni,
        restituzione_prevista=restituzione_prevista if tipo == Uscita.Tipo.PRESTITO else None,
        importo=importo or Decimal("0"), creato_da=utente, modificato_da=utente,
    )  # fmt: skip
    bene.stato = Bene.Stato.IN_PRESTITO if tipo == Uscita.Tipo.PRESTITO else Bene.Stato.USCITO
    bene.modificato_da = utente
    bene.save(update_fields=["stato", "modificato_da", "modificato_il"])
    azione = Azione.MODIFICA if tipo == Uscita.Tipo.PRESTITO else Azione.ARCHIVIAZIONE
    registra(
        azione, bene, utente=utente, uscita=u.get_tipo_display(), a=controparte_testo, motivo=motivo
    )
    return u


@transaction.atomic
def restituzione(uscita, utente, *, data, rientro, note=""):
    uscita = Uscita.objects.select_for_update().select_related("bene").get(pk=uscita.pk)
    if not uscita.in_corso:
        raise OperazioneNonValida("Non è un prestito in corso.")
    if data < uscita.data:
        raise OperazioneNonValida("La restituzione non può precedere il prestito.")
    uscita.restituito_il = data
    uscita.rientro = rientro
    uscita.note_rientro = note
    uscita.modificato_da = utente
    uscita.save()
    bene = uscita.bene
    bene.stato = Bene.Stato.IN_DOTAZIONE
    bene.modificato_da = utente
    bene.save(update_fields=["stato", "modificato_da", "modificato_il"])
    registra(Azione.MODIFICA, bene, utente=utente, restituito=str(data), rientro=rientro, note=note)
    return uscita


def prestiti_scaduti(oggi=None):
    oggi = oggi or timezone.localdate()
    return Uscita.objects.filter(
        tipo=Uscita.Tipo.PRESTITO, restituito_il__isnull=True, restituzione_prevista__lt=oggi
    ).select_related("bene")


def in_patrimonio():
    return Bene.objects.exclude(stato=Bene.Stato.USCITO).select_related("categoria")


def totali():
    beni = in_patrimonio()
    valore = sum((b.valore_totale for b in beni), Decimal("0"))
    per_categoria = {}
    for b in beni:
        voce = per_categoria.setdefault(b.categoria.nome, {"beni": 0, "valore": Decimal("0")})
        voce["beni"] += 1
        voce["valore"] += b.valore_totale
    return {
        "beni": beni.count(),
        "valore": valore,
        "in_prestito": beni.filter(stato=Bene.Stato.IN_PRESTITO).count(),
        "per_categoria": sorted(per_categoria.items()),
    }


# --- passaggio di consegne ---------------------------------------------------------------------


def fotografia():
    return [
        {
            "codice": b.codice,
            "nome": b.nome,
            "categoria": b.categoria.nome,
            "quantita": b.quantita,
            "ubicazione": b.ubicazione,
            "conservazione": b.get_conservazione_display(),
            "stato": b.get_stato_display(),
            "valore": str(b.valore_totale),
        }  # fmt: skip
        for b in in_patrimonio().order_by("categoria__ordine", "categoria__nome", "numero")
    ]


@transaction.atomic
def crea_passaggio(utente, *, data, consegnante, consegnante_ruolo, ricevente, ricevente_ruolo,
                   note="", protocolla=False):  # fmt: skip
    from apps.core.pdf import genera_pdf

    beni = fotografia()
    if not beni:
        raise OperazioneNonValida("L'inventario è vuoto.")
    valore = sum((Decimal(b["valore"]) for b in beni), Decimal("0"))
    p = PassaggioConsegne(
        data=data, consegnante=consegnante, consegnante_ruolo=consegnante_ruolo,
        ricevente=ricevente, ricevente_ruolo=ricevente_ruolo, note=note, beni=beni,
        numero_beni=len(beni),
        valore_totale=valore, creato_da=utente,
    )  # fmt: skip
    pdf = genera_pdf(
        "patrimonio/pdf/passaggio.html", {"p": p, "organizzazione": Organizzazione.corrente()}
    )
    p.impronta = hashlib.sha256(pdf).hexdigest()
    p.file.save(f"passaggio_consegne_{data:%Y%m%d}.pdf", ContentFile(pdf), save=False)
    if protocolla:
        p.protocollo = _protocolla(p, pdf, utente)
    p.save()
    registra(
        Azione.CREAZIONE, p, utente=utente, beni=len(beni), valore=str(valore), impronta=p.impronta
    )
    return p


def _protocolla(passaggio, pdf, utente):
    from apps.protocollo import servizi as protocollo
    from apps.protocollo.models import Classificazione, Protocollo

    pr = protocollo.registra_protocollo(
        {
            "direzione": Protocollo.Direzione.INTERNO,
            "mezzo": Protocollo.Mezzo.MANO,
            "oggetto": f"Passaggio di consegne del patrimonio del {passaggio.data:%d/%m/%Y}: "
            f"{passaggio.consegnante} a {passaggio.ricevente}",
            "classificazione": Classificazione.objects.filter(codice="05").first(),
        },
        [],
        utente,
    )
    protocollo.aggiungi_allegato(
        pr,
        ContentFile(pdf, name="passaggio_consegne.pdf"),
        utente,
        principale=True,
        controlla=False,
    )
    return pr


# --- QR ed esportazioni ------------------------------------------------------------------------


def qr_svg(testo, scala=4):
    """SVG del QR da inserire nella pagina: generato da segno (solo forme, nessun testo utente)."""
    import segno
    from django.utils.safestring import mark_safe

    return mark_safe(segno.make(testo, error="m").svg_inline(scale=scala, border=1))  # noqa: S308


def esporta_csv(queryset, destinazione, utente):
    w = csv.writer(destinazione, delimiter=";")
    w.writerow(["numero", "nome", "categoria", "quantita", "ubicazione", "conservazione",
                "acquisizione", "data_acquisizione", "provenienza", "valore_acquisizione",
                "valore_attuale", "stato"])  # fmt: skip
    n = 0
    for b in queryset.select_related("categoria"):
        riga = [
            b.codice, b.nome, b.categoria, b.quantita, b.ubicazione, b.get_conservazione_display(),
            b.get_acquisizione_display(), b.data_acquisizione or "", b.provenienza_testo,
            str(b.valore_acquisizione).replace(".", ","), str(b.valore).replace(".", ","),
            b.get_stato_display(),
        ]  # fmt: skip
        w.writerow([cella_sicura(v) for v in riga])
        n += 1
    registra(Azione.ESPORTAZIONE, utente=utente, descrizione=f"Inventario CSV ({n} righe)", righe=n)
    return n
