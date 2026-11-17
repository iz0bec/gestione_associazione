# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Crea un backup completo (database e file) e applica la conservazione a
# *              rotazione (BACKUP_GIORNALIERI/SETTIMANALI/MENSILI/ALTRI, BACKUP_SPAZIO_MASSIMO).
# *              Elenca i backup con --elenco (con il motivo per cui sono conservati),
# *              applica solo la conservazione con --pulisci;
# *              --conserva/--rilascia escludono un backup dalla rotazione o ve lo rimettono.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.core.management.base import BaseCommand, CommandError

from apps.core import backup


class Command(BaseCommand):
    help = "Crea un backup completo (database e file caricati) nella cartella BACKUP_ROOT."

    def add_arguments(self, parser):
        parser.add_argument("--automatico", action="store_true", help="Backup pianificato")
        parser.add_argument("--elenco", action="store_true", help="Elenca i backup e esce")
        parser.add_argument("--motivo", default="manuale", help="Es. «prima dell'aggiornamento»")
        parser.add_argument(
            "--pulisci", action="store_true", help="Applica solo la conservazione, senza backup"
        )
        parser.add_argument("--conserva", metavar="NOME", help="Esclude un backup dalla rotazione")
        parser.add_argument("--rilascia", metavar="NOME", help="Rimette un backup in rotazione")
        parser.add_argument("--nota", default="", help="Con --conserva: perché si conserva")
        parser.add_argument(
            "--prova", metavar="NOME", nargs="?", const="ultimo",
            help="Prova di ripristino (senza toccare i dati) del backup indicato o dell'ultimo",
        )  # fmt: skip
        parser.add_argument(
            "--estrai", nargs=2, metavar=("NOME", "CARTELLA"),
            help="Scrive nella cartella il dump del database e i file del backup, decifrati "
            "(per un ripristino a mano)",
        )  # fmt: skip

    def handle(self, *args, **opzioni):
        if opzioni["prova"]:
            elenco = backup.elenco()
            nome = elenco[0].nome if opzioni["prova"] == "ultimo" and elenco else opzioni["prova"]
            try:
                esito, dettaglio = backup.prova_ripristino(backup.percorso(nome))
            except backup.BackupNonValido as e:
                raise CommandError(" ".join(e.messages)) from None
            stile = self.style.SUCCESS if esito == "ok" else self.style.ERROR
            self.stdout.write(stile(f"{nome}: {esito} - {dettaglio}"))
            if esito != "ok":
                raise CommandError("Prova di ripristino non riuscita.")
            return
        if opzioni["estrai"]:
            nome, destinazione = opzioni["estrai"]
            try:
                backup.estrai(backup.percorso(nome), destinazione)
            except backup.BackupNonValido as e:
                raise CommandError(" ".join(e.messages)) from None
            self.stdout.write(self.style.SUCCESS(
                f"Estratti in {destinazione}: database.dump (per pg_restore) e la cartella media"
            ))  # fmt: skip
            return
        if opzioni["conserva"] or opzioni["rilascia"]:
            nome = opzioni["conserva"] or opzioni["rilascia"]
            try:
                backup.imposta_conservato(nome, bool(opzioni["conserva"]), nota=opzioni["nota"])
            except backup.BackupNonValido as e:
                raise CommandError(" ".join(e.messages)) from None
            stato = "escluso dalla rotazione" if opzioni["conserva"] else "rimesso in rotazione"
            self.stdout.write(self.style.SUCCESS(f"{nome}: {stato}"))
            return
        if opzioni["elenco"]:
            tenuti = backup.classifica()
            for b in backup.elenco():
                self.stdout.write(
                    f"{b.nome}  {backup.formato_dimensione(b.dimensione):>9}  "
                    f"{b.manifesto.get('versione', '?')}  {b.motivo}  "
                    f"[{tenuti.get(b.nome, 'da eliminare')}]"
                )
            o = backup.occupazione()
            self.stdout.write(f"Totale {backup.formato_dimensione(o['backup'])}, liberi sul disco "
                              f"{backup.formato_dimensione(o['libero'])}")  # fmt: skip
            return
        if opzioni["pulisci"]:
            tolti = backup.pulisci()
        else:
            motivo = "automatico" if opzioni["automatico"] else opzioni["motivo"]
            try:
                p, tolti = backup.crea_e_pulisci(motivo=motivo)
            except backup.BackupNonValido as e:
                raise CommandError(" ".join(e.messages)) from None
            self.stdout.write(self.style.SUCCESS(f"Backup creato: {p}"))
        if tolti:
            self.stdout.write(f"Backup eliminati dalla conservazione: {len(tolti)}")
