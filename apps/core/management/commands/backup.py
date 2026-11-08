# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Crea un backup completo (database e file); con --automatico tiene solo gli
# *              ultimi BACKUP_CONSERVA backup automatici. Elenca i backup con --elenco.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.core import backup


class Command(BaseCommand):
    help = "Crea un backup completo (database e file caricati) nella cartella BACKUP_ROOT."

    def add_arguments(self, parser):
        parser.add_argument("--automatico", action="store_true", help="Backup pianificato")
        parser.add_argument("--elenco", action="store_true", help="Elenca i backup e esce")
        parser.add_argument("--motivo", default="manuale", help="Es. «prima dell'aggiornamento»")

    def handle(self, *args, **opzioni):
        if opzioni["elenco"]:
            for b in backup.elenco():
                self.stdout.write(
                    f"{b.nome}  {backup.formato_dimensione(b.dimensione):>9}  "
                    f"{b.manifesto.get('versione', '?')}  {b.motivo}"
                )
            return
        try:
            p = backup.crea(motivo="automatico" if opzioni["automatico"] else opzioni["motivo"])
        except backup.BackupNonValido as e:
            raise CommandError(" ".join(e.messages)) from None
        self.stdout.write(self.style.SUCCESS(f"Backup creato: {p}"))
        if opzioni["automatico"]:
            tolti = backup.pulisci_automatici(settings.BACKUP_CONSERVA)
            if tolti:
                self.stdout.write(f"Backup automatici più vecchi eliminati: {tolti}")
