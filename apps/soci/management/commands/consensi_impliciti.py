# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Registra in blocco i consensi impliciti dei soci attivi e sospesi (finalità
# *              senza registrazioni; mai sopra un diniego). Senza --esegui conta soltanto.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.core.management.base import BaseCommand, CommandError

from apps.soci import servizi


class Command(BaseCommand):
    help = "Registra i consensi impliciti dei soci (senza --esegui: solo il conteggio)."

    def add_arguments(self, parser):
        parser.add_argument("--esegui", action="store_true", help="Registra davvero.")

    def handle(self, *args, **opzioni):
        try:
            conteggi = servizi.registra_consensi_impliciti(esegui=opzioni["esegui"])
        except servizi.OperazioneNonValida as e:
            raise CommandError(e.message) from e
        totale = sum(conteggi.values())
        verbo = "Registrati" if opzioni["esegui"] else "Da registrare"
        dettagli = ", ".join(f"{f}: {n}" for f, n in conteggi.items())
        self.stdout.write(f"{verbo}: {totale} ({dettagli})")
