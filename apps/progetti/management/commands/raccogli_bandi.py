# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Raccoglie le novità dalle fonti dei bandi attive (rieseguibile: niente doppioni)
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.core.management.base import BaseCommand

from apps.progetti import raccolta


class Command(BaseCommand):
    help = "Raccoglie i bandi dalle fonti attive (feed e pagine) e li propone da vagliare."

    def handle(self, *args, **opzioni):
        n = raccolta.raccogli_tutte()
        self.stdout.write(f"Bandi proposti: {n}.")
