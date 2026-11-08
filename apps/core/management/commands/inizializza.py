# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Inizializzazione: cancella TUTTI i dati e i file caricati e riporta
# *              l'applicazione allo stato di una nuova installazione (configurazione guidata
# *              al primo accesso). Chiede conferma e salva prima un backup completo.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import contextlib
import getpass
import os
import shutil
import sys
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Cancella tutti i dati (database e file caricati) e riporta l'applicazione a una nuova "
        "installazione. Prima salva un backup completo."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--conferma",
            metavar="NOME_DATABASE",
            help="Conferma senza domande: va indicato il nome del database da azzerare.",
        )
        parser.add_argument(
            "--senza-backup", action="store_true", help="Non salvare il backup (sconsigliato)."
        )
        parser.add_argument("--admin", default="admin", help="Utente amministratore da creare.")
        parser.add_argument("--email", default="", help="Email dell'amministratore.")
        parser.add_argument(
            "--senza-admin", action="store_true", help="Non creare l'amministratore."
        )

    # --- passi -------------------------------------------------------------------------------

    def _riepilogo(self):
        from apps.anagrafica.models import Soggetto
        from apps.protocollo.models import Protocollo
        from apps.soci.models import Socio
        from apps.tesoreria.models import Movimento

        db = settings.DATABASES["default"]
        self.stdout.write(self.style.WARNING("ATTENZIONE: verranno cancellati DEFINITIVAMENTE"))
        self.stdout.write(
            f"  database  {db['NAME']} su {db.get('HOST') or 'localhost'}:{db.get('PORT') or 5432}"
        )
        # database vuoto o parziale: il riepilogo è solo indicativo
        with contextlib.suppress(Exception):
            self.stdout.write(
                f"            {Soggetto.objects.count()} schede anagrafiche, "
                f"{Socio.objects.count()} soci, {Protocollo.objects.count()} protocolli, "
                f"{Movimento.objects.count()} movimenti di tesoreria"
            )
        self.stdout.write(f"  file      {settings.MEDIA_ROOT}")
        self.stdout.write("Fermare prima l'applicazione e il pianificatore (systemctl stop ...).")

    def _conferma(self, opzioni):
        nome = settings.DATABASES["default"]["NAME"]
        if opzioni["conferma"] is not None:
            if opzioni["conferma"] != nome:
                raise CommandError(f"--conferma deve essere il nome del database: {nome}")
            return
        if not sys.stdin.isatty():
            raise CommandError("Senza terminale serve --conferma NOME_DATABASE.")
        risposta = input(f"Per procedere scrivere il nome del database ({nome}): ").strip()
        if risposta != nome:
            raise CommandError("Inizializzazione annullata: nessuna modifica.")

    def _backup(self):
        from apps.core import backup

        try:
            p = backup.crea(motivo="prima dell'inizializzazione")
        except backup.BackupNonValido as e:
            raise CommandError(
                f"Backup non riuscito, nulla è stato cancellato: {' '.join(e.messages)}"
            ) from None
        self.stdout.write(f"Backup completo: {p}")

    def _azzera_database(self):
        from apps.core.backup import svuota_database

        n = svuota_database()
        self.stdout.write(f"Tabelle eliminate: {n}")
        call_command("migrate", interactive=False, verbosity=0)
        self.stdout.write(
            "Database ricreato con i dati iniziali (ruoli, tipologie, piano dei conti...)."
        )

    def _azzera_file(self):
        media = Path(settings.MEDIA_ROOT)
        if not media.is_dir():
            return
        for voce in media.iterdir():
            if voce.is_dir() and not voce.is_symlink():
                shutil.rmtree(voce)
            else:
                voce.unlink()
        self.stdout.write("File caricati eliminati.")

    def _amministratore(self, opzioni):
        password = os.environ.get("INIZIALIZZA_PASSWORD", "")
        if not password:
            if not sys.stdin.isatty():
                self.stdout.write(self.style.WARNING(
                    "Amministratore non creato (nessun terminale): usare manage.py createsuperuser."
                ))  # fmt: skip
                return
            while True:
                password = getpass.getpass(f"Password per «{opzioni['admin']}»: ")
                if password != getpass.getpass("Ripetere la password: "):
                    self.stderr.write("Le password non coincidono.")
                    continue
                try:
                    validate_password(password)
                    break
                except ValidationError as e:
                    self.stderr.write(" ".join(e.messages))
        get_user_model().objects.create_superuser(
            username=opzioni["admin"],
            email=opzioni["email"] or f"{opzioni['admin']}@localhost",
            password=password,
        )
        self.stdout.write(f"Amministratore «{opzioni['admin']}» creato.")

    def handle(self, *args, **opzioni):
        self._riepilogo()
        self._conferma(opzioni)
        if not opzioni["senza_backup"]:
            self._backup()
        self._azzera_database()
        self._azzera_file()
        if not opzioni["senza_admin"]:
            self._amministratore(opzioni)
        self.stdout.write(self.style.SUCCESS(
            "Inizializzazione completata. Al primo accesso parte la configurazione guidata."
        ))  # fmt: skip
