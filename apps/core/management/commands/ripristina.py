# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Ripristina un backup completo: verifica, salva lo stato attuale, sostituisce
# *              database e file. Usato anche dall'interfaccia (in un processo separato).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import os
import sys
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.core import backup


class Command(BaseCommand):
    help = "Ripristina un backup (file .tar creato dall'applicazione): sostituisce TUTTI i dati."

    def add_arguments(self, parser):
        parser.add_argument("file", help="Nome del backup in BACKUP_ROOT o percorso del file")
        parser.add_argument("--conferma", metavar="NOME_DATABASE")
        parser.add_argument("--senza-backup-sicurezza", action="store_true")
        parser.add_argument("--utente", default="", help="Chi ha chiesto il ripristino")
        parser.add_argument("--stato", action="store_true", help="Aggiorna lo stato per il web")

    def handle(self, *args, **o):
        p = Path(o["file"])
        if not p.is_file():
            p = Path(settings.BACKUP_ROOT) / o["file"]
        if not p.is_file():
            raise CommandError(f"Backup non trovato: {o['file']}")
        nome_db = settings.DATABASES["default"]["NAME"]
        if o["conferma"] != nome_db:
            if o["conferma"] is not None or not sys.stdin.isatty():
                raise CommandError(f"Per confermare: --conferma {nome_db}")
            if input(f"Tutti i dati saranno sostituiti. Scrivere {nome_db}: ").strip() != nome_db:
                raise CommandError("Ripristino annullato.")
        blocco = Path(settings.BACKUP_ROOT) / ".ripristino.lock"
        try:
            fd = os.open(blocco, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
        except FileExistsError:
            raise CommandError("Un altro ripristino è in corso.") from None

        def avanzamento(testo):
            self.stdout.write(testo)
            if o["stato"]:
                backup.scrivi_stato(fase=testo)

        try:
            if o["stato"]:
                backup.scrivi_stato(esito="in_corso", file=p.name, messaggio="",
                                    inizio=timezone.now().isoformat())  # fmt: skip
            manifesto, sicurezza = backup.ripristina(
                p, utente_descrizione=o["utente"],
                backup_sicurezza=not o["senza_backup_sicurezza"], avanzamento=avanzamento,
            )  # fmt: skip
        except Exception as e:
            if o["stato"]:
                backup.scrivi_stato(esito="errore", messaggio=str(e)[:2000])
            raise CommandError(f"Ripristino non riuscito: {e}") from None
        finally:
            blocco.unlink(missing_ok=True)
        messaggio = f"Ripristinato il backup del {manifesto.get('creato_il', '?')}." + (
            f" Lo stato precedente è nel backup {sicurezza.name}." if sicurezza else ""
        )
        if o["stato"]:
            backup.scrivi_stato(esito="ok", fase="Completato", messaggio=messaggio)
        self.stdout.write(self.style.SUCCESS(messaggio))
