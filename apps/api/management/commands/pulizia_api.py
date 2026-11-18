# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Pulizia periodica dell'API: nonce, registro delle chiamate, chiavi
# *              ritirate, controparti scadute
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.core.management.base import BaseCommand

from apps.api import servizi


class Command(BaseCommand):
    help = "Pulizia periodica dell'API di interoperabilità (rieseguibile)."

    def handle(self, *args, **opzioni):
        esito = servizi.pulizia()
        self.stdout.write(", ".join(f"{k}: {v}" for k, v in esito.items()))
