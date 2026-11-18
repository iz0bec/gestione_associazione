# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Legge i flussi delle controparti (federazione e sezioni) e mette i documenti
# *              nella coda dei documenti in arrivo (rieseguibile)
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.core.management.base import BaseCommand

from apps.collegamenti import sincronizza


class Command(BaseCommand):
    help = "Legge i flussi delle controparti collegate come federazione o sezione."

    def handle(self, *args, **opzioni):
        for nome, ricevuti in sincronizza.sincronizza_tutti().items():
            if ricevuti:
                self.stdout.write(f"{nome}: {ricevuti} documenti ricevuti")
