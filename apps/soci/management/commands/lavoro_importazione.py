# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Esegue un lavoro di importazione avviato dall'interfaccia (uso interno).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.core.management.base import BaseCommand

from apps.soci import lavori_importazione


class Command(BaseCommand):
    help = "Uso interno: anteprima o esecuzione di un'importazione avviata dall'interfaccia."

    def add_arguments(self, parser):
        parser.add_argument("lavoro")

    def handle(self, *args, **opzioni):
        lavori_importazione.esegui(opzioni["lavoro"])
