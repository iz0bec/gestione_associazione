# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Stampa una nuova chiave per CHIAVE_CIFRATURA (da copiare nel file .env)
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.core.management.base import BaseCommand

from apps.core.cifratura import nuova_chiave


class Command(BaseCommand):
    help = "Genera una chiave di cifratura per i segreti salvati nel database (CHIAVE_CIFRATURA)."

    def handle(self, *args, **options):
        self.stdout.write(nuova_chiave())
