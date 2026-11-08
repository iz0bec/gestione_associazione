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
