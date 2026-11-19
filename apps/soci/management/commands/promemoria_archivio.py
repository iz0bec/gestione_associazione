# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Riepilogo giornaliero per email dei soci da riportare nell'archivio centrale
# *              (nuovi e rettifiche non ancora segnalati). Rieseguibile.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.core.management.base import BaseCommand

from apps.soci import promemoria


class Command(BaseCommand):
    help = "Invia a chi gestisce i soci il riepilogo dei promemoria per l'archivio centrale."

    def handle(self, *args, **opzioni):
        self.stdout.write(f"Riepiloghi inviati: {promemoria.invia_riepilogo()}")
