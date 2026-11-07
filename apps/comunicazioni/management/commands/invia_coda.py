# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Spedisce i messaggi in coda e prepara gli auguri automatici del giorno
# *              (da pianificare ogni minuto; rieseguibile senza doppioni).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.core.management.base import BaseCommand

from apps.comunicazioni.servizi import auguri_del_giorno, elabora_coda


class Command(BaseCommand):
    help = "Prepara gli auguri del giorno e spedisce i messaggi in coda."

    def handle(self, *args, **options):
        auguri = auguri_del_giorno()
        inviati, errori = elabora_coda()
        if auguri or inviati or errori:
            self.stdout.write(
                f"Auguri preparati: {len(auguri)}; inviati {inviati}, errori {errori}"
            )
