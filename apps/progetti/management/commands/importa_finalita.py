# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Carica le finalità statutarie da un file di testo, una per riga
# *              («a) Il culto della Patria;»), ad esempio dall'articolo dello statuto
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import sys

from django.core.management.base import BaseCommand, CommandError

from apps.progetti import servizi


class Command(BaseCommand):
    help = "Carica le finalità statutarie da un file (una per riga: «a) testo»; «-» = stdin)."

    def add_arguments(self, parser):
        parser.add_argument("file", help="File di testo, o - per leggere dallo standard input")
        parser.add_argument(
            "--sostituisci",
            action="store_true",
            help="Toglie prima le finalità non ancora usate da idee o progetti",
        )

    def handle(self, *args, **o):
        if o["file"] == "-":
            testo = sys.stdin.read()
        else:
            with open(o["file"], encoding="utf-8") as f:
                testo = f.read()
        try:
            n = servizi.carica_finalita(testo, sostituisci=o["sostituisci"])
        except servizi.OperazioneNonValida as e:
            raise CommandError(str(e)) from e
        self.stdout.write(f"Finalità caricate: {n} nuove.")
