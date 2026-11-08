# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Documenti pubblici (statuto, regolamento): caricamento dei PDF da parte del
# *              gestore e consultazione libera, solo per i documenti pubblicati.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.core.exceptions import ValidationError
from django.db import transaction

from .audit import Azione, campi_modificati, registra
from .models import DocumentoPubblico

MAX_MB = 30


class FileNonValido(ValidationError):
    pass


def controlla_pdf(file):
    if file.size > MAX_MB * 1024 * 1024:
        raise FileNonValido(f"Il file supera {MAX_MB} MB.")
    inizio = file.read(1024)
    file.seek(0)
    if b"%PDF-" not in inizio:
        raise FileNonValido("Il file non è un PDF.")


def pubblicati():
    return DocumentoPubblico.objects.filter(pubblicato=True)


@transaction.atomic
def salva(form, utente, file=None):
    """Salva i dati del documento e, se indicato, il nuovo PDF (sostituisce il precedente)."""
    nuovo = form.instance.pk is None
    dettagli = {} if nuovo else campi_modificati(form)
    doc = form.save(commit=False)
    if nuovo and file is None:
        raise FileNonValido("Caricare il file PDF.")
    vecchio = doc.file.name if (file is not None and not nuovo) else None
    if file is not None:
        controlla_pdf(file)
        doc.nome_file = file.name[:200]
        doc.dimensione = file.size
        doc.file.save("documento.pdf", file, save=False)
    if nuovo:
        doc.creato_da = utente
    doc.modificato_da = utente
    doc.save()
    if vecchio:
        doc.file.storage.delete(vecchio)
    if nuovo:
        registra(Azione.CREAZIONE, doc, utente=utente, file=doc.nome_file)
    elif dettagli.get("campi") or file is not None:
        registra(Azione.MODIFICA, doc, utente=utente,
                 nuovo_file=doc.nome_file if file is not None else None, **dettagli)  # fmt: skip
    return doc
