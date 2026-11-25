# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Legge da federazione e sezioni collegate cariche, numeri del tesseramento ed
# *              eventi condivisi (F4, rieseguibile)
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.core.management.base import BaseCommand

from apps.collegamenti import condivisi


class Command(BaseCommand):
    help = "Aggiorna cariche, numeri ed eventi condivisi dalle installazioni collegate."

    def handle(self, *args, **opzioni):
        for nome, esito in condivisi.aggiorna_tutti().items():
            self.stdout.write(f"{nome}: {esito}")
