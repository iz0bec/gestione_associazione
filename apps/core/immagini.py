# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Immagini caricate dagli utenti: verificate con Pillow, ridimensionate e
# *              ricodificate senza metadati (EXIF: posizione GPS, dispositivo, data).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import io
import mimetypes
import secrets

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.http import FileResponse, Http404

MAX_MB = 15
# lato più lungo di firma o timbro, dopo il ritaglio: una firma larga 5 cm scansionata a 300 dpi
# misura circa 600 pixel; sotto i 300 la stampa (56 mm) è a meno di 140 dpi e si vede sgranata
LATO_MINIMO = 300


class ImmagineNonValida(ValidationError):
    pass


def ripulisci(file, *, lato=1600, formato="JPEG"):
    """Restituisce un ContentFile JPEG (o PNG, che conserva la trasparenza) senza metadati."""
    from PIL import Image, ImageOps, UnidentifiedImageError

    if file.size > MAX_MB * 1024 * 1024:
        raise ImmagineNonValida(f"L'immagine supera {MAX_MB} MB.")
    try:
        img = Image.open(file)
        img = ImageOps.exif_transpose(img)
        img.thumbnail((lato, lato))
        if formato == "PNG":
            if img.mode not in ("RGB", "RGBA", "L", "LA"):
                img = img.convert("RGBA")
        elif img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ImmagineNonValida("Il file non è un'immagine valida.") from None
    uscita = io.BytesIO()
    if formato == "PNG":
        img.save(uscita, "PNG", optimize=True)
        return ContentFile(uscita.getvalue(), name="immagine.png")
    img.save(uscita, "JPEG", quality=85, optimize=True)
    return ContentFile(uscita.getvalue(), name="immagine.jpg")


def nome_casuale(cartella, estensione="jpg"):
    """Nome non indovinabile: le foto non sono mai raggiungibili per indirizzo diretto."""
    return f"{cartella}/{secrets.token_urlsafe(12)}.{estensione}"


def risposta_immagine(campo, *, privata=True):
    """Serve un'immagine salvata (il permesso lo controlla la vista)."""
    if not campo:
        raise Http404
    try:
        f = campo.open("rb")
    except FileNotFoundError:
        raise Http404 from None
    tipo = mimetypes.guess_type(campo.name)[0] or "application/octet-stream"
    risposta = FileResponse(f, content_type=tipo)
    risposta["Cache-Control"] = "private, max-age=3600" if privata else "public, max-age=86400"
    risposta["X-Content-Type-Options"] = "nosniff"
    return risposta


def ripulisci_contrassegno(file, *, sfondo_trasparente=True, lato=1200):
    """Firma o timbro per le stampe: PNG senza metadati, ritagliato sul disegno.

    Con `sfondo_trasparente` il bianco del foglio (scansione o foto) diventa trasparente con un
    passaggio graduale, così l'inchiostro resta morbido sui bordi; la trasparenza già presente
    in un PNG si conserva comunque.
    """
    from PIL import Image, ImageChops, ImageOps, UnidentifiedImageError

    if file.size > MAX_MB * 1024 * 1024:
        raise ImmagineNonValida(f"L'immagine supera {MAX_MB} MB.")
    try:
        img = ImageOps.exif_transpose(Image.open(file)).convert("RGBA")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ImmagineNonValida("Il file non è un'immagine valida.") from None
    if sfondo_trasparente:
        # luminosità ≥ 225 (carta, anche un po' grigia) → trasparente; ≤ 150 → inchiostro pieno
        chiaro, scuro = 225, 150
        luce = ImageOps.autocontrast(img.convert("L"), cutoff=1)
        maschera = luce.point(
            lambda v: (
                0 if v >= chiaro else 255 if v <= scuro else (chiaro - v) * 255 // (chiaro - scuro)
            )
        )
        img.putalpha(ImageChops.multiply(img.getchannel("A"), maschera))
    riquadro = img.getchannel("A").point(lambda v: 255 if v > 24 else 0).getbbox()
    if riquadro is None:
        raise ImmagineNonValida(
            "Nell'immagine non si vede né una firma né un timbro: controllare la scansione."
        )
    margine = max(4, (riquadro[2] - riquadro[0]) // 50)
    img = img.crop((
        max(0, riquadro[0] - margine), max(0, riquadro[1] - margine),
        min(img.width, riquadro[2] + margine), min(img.height, riquadro[3] + margine),
    ))  # fmt: skip
    if max(img.size) < LATO_MINIMO:
        raise ImmagineNonValida(
            f"La firma o il timbro misura solo {img.width} × {img.height} pixel: stampato sarebbe "
            "sgranato. Rifare la scansione a 300 dpi (vedi la guida «Firme e timbri»)."
        )
    img.thumbnail((lato, lato))
    uscita = io.BytesIO()
    img.save(uscita, "PNG", optimize=True)
    return ContentFile(uscita.getvalue(), name="contrassegno.png")
