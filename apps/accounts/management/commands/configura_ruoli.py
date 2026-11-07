# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Comando: allinea i gruppi/ruoli ai permessi definiti in ruoli.py
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.core.management.base import BaseCommand

from apps.accounts.ruoli import configura_ruoli


class Command(BaseCommand):
    help = "Crea o aggiorna i ruoli (gruppi) con i permessi previsti."

    def handle(self, *args, **options):
        configura_ruoli(verbose=True)
        self.stdout.write(self.style.SUCCESS("Ruoli allineati."))
