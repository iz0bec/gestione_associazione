# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Consegna degli avvisi dei cambiamenti alle controparti (ripetizioni con attesa
# *              crescente; rieseguibile)
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.core.management.base import BaseCommand

from apps.collegamenti import client


class Command(BaseCommand):
    help = "Consegna le notifiche dei cambiamenti dovute alle controparti dell'API."

    def handle(self, *args, **opzioni):
        consegnate, fallite = client.invia_notifiche()
        if consegnate or fallite:
            self.stdout.write(f"notifiche consegnate: {consegnate}, non riuscite: {fallite}")
