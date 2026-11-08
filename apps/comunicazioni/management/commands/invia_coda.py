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

from apps.comunicazioni.servizi import auguri_del_giorno, elabora_coda, promemoria_rinnovo


class Command(BaseCommand):
    help = "Prepara auguri e promemoria di rinnovo del giorno e spedisce i messaggi in coda."

    def handle(self, *args, **options):
        auguri = auguri_del_giorno()
        rinnovo = promemoria_rinnovo()
        if rinnovo:
            self.stdout.write(f"Promemoria di rinnovo: {rinnovo.destinatari.count()} soci")
        inviati, errori = elabora_coda()
        if auguri or inviati or errori:
            self.stdout.write(
                f"Auguri preparati: {len(auguri)}; inviati {inviati}, errori {errori}"
            )
