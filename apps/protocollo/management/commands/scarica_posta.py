# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Scarica la posta dalle caselle attive (da pianificare, es. ogni 15 minuti)
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.core.management.base import BaseCommand

from apps.protocollo.posta import scarica_tutte


class Command(BaseCommand):
    help = "Scarica i nuovi messaggi dalle caselle di posta del protocollo."

    def handle(self, *args, **options):
        for casella, esito in scarica_tutte().items():
            if isinstance(esito, int):
                self.stdout.write(f"{casella}: {esito} nuovi messaggi")
            else:
                self.stderr.write(f"{casella}: ERRORE {esito}")
