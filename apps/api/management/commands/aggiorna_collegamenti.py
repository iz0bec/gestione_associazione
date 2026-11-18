# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Rilegge chiavi e impronte TLS delle installazioni collegate dalla loro
# *              /.well-known firmata (rotazione delle chiavi, rinnovo dei certificati)
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.core.management.base import BaseCommand

from apps.api.models import ClienteApi
from apps.collegamenti import client


class Command(BaseCommand):
    help = "Aggiorna chiavi e impronte TLS delle installazioni collegate (rieseguibile)."

    def handle(self, *args, **opzioni):
        controparti = ClienteApi.objects.filter(
            tipo=ClienteApi.Tipo.INSTALLAZIONE,
            stato__in=[ClienteApi.Stato.ATTIVA, ClienteApi.Stato.IN_PROVA],
            istanza__isnull=False,
        )
        for cliente in controparti:
            if cliente.indirizzo_interno or cliente.indirizzo_pubblico:
                _, messaggio = client.aggiorna_identita(cliente)
                self.stdout.write(f"{cliente}: {messaggio}")
