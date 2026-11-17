# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Genera una chiave per i backup cifrati (CHIAVE_BACKUP).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.core.management.base import BaseCommand

from apps.core.cifratura_backup import nuova_chiave


class Command(BaseCommand):
    help = "Genera una chiave per i backup cifrati (CHIAVE_BACKUP): custodirla fuori dal server."

    def handle(self, *args, **options):
        self.stdout.write(nuova_chiave())
