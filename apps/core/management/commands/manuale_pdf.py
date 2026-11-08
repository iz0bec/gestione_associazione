# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Genera il manuale operativo in PDF (con immagini) e, se richiesto, lo copia
# *              nel percorso indicato: manage.py manuale_pdf --uscita manuale-operativo.pdf
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import shutil

from django.core.management.base import BaseCommand

from apps.core import aiuto


class Command(BaseCommand):
    help = "Genera il manuale operativo in PDF, con le immagini esplicative."

    def add_arguments(self, parser):
        parser.add_argument("--uscita", help="Copia il PDF in questo percorso.")

    def handle(self, *args, **opzioni):
        percorso = aiuto.pdf_manuale()
        if opzioni.get("uscita"):
            shutil.copyfile(percorso, opzioni["uscita"])
            percorso = opzioni["uscita"]
        self.stdout.write(f"Manuale in PDF: {percorso}")
