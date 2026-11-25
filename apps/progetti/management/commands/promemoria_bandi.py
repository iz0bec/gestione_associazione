# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Avvisa delle domande dei bandi in scadenza (rieseguibile: una volta per soglia)
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.core.management.base import BaseCommand

from apps.progetti import servizi


class Command(BaseCommand):
    help = "Avvisa delle domande dei bandi in scadenza (7 e 2 giorni prima)."

    def handle(self, *args, **opzioni):
        n = servizi.promemoria_bandi()
        self.stdout.write(f"Bandi in scadenza avvisati: {n}.")
