# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Allineamento automatico dei soci con federazione e sezioni (F4) e invio a spinta
# *              verso la federazione che non ci raggiunge (rieseguibile)
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.core.management.base import BaseCommand

from apps.collegamenti import soci


class Command(BaseCommand):
    help = "Allinea i soci con le controparti che hanno l'allineamento automatico acceso."

    def handle(self, *args, **opzioni):
        for nome, esito in soci.allinea_tutti().items():
            self.stdout.write(f"{nome}: {esito}")
