# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Azzera l'ambiente dimostrativo (solo con DEMO=true): cancella database e file
# *              e ricarica i dati di fantasia con gli utenti dei ruoli. Senza --conferma, nulla.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.core.management.base import BaseCommand, CommandError

from apps.core import demo


class Command(BaseCommand):
    help = "Azzera l'ambiente dimostrativo (DEMO=true): CANCELLA database e file, ricarica i dati."

    def add_arguments(self, parser):
        parser.add_argument("--conferma", action="store_true", help="Esegue davvero l'azzeramento")
        parser.add_argument(
            "--se-dovuto", action="store_true", help="Solo il 1° del mese, se non già fatto"
        )

    def handle(self, *args, **opzioni):
        if not demo.attiva():
            raise CommandError("Rifiutato: l'azzeramento funziona solo con DEMO=true nel .env.")
        if opzioni["se_dovuto"] and not demo.azzeramento_dovuto():
            return
        if not opzioni["conferma"] and not opzioni["se_dovuto"]:
            raise CommandError("Cancella database e file: aggiungere --conferma per procedere.")
        password = demo.azzera(stdout=self.stdout)
        self.stdout.write(f"\nUtenti dei ruoli: {', '.join(n for n, _, _ in demo.ACCOUNT)} "
                          f"(password pubblica nel .env, DEMO_PASSWORD).")  # fmt: skip
        if not opzioni["se_dovuto"]:
            self.stdout.write(f"Amministratore: {demo.ADMIN} / {password}")
