# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Processo dei lavori periodici (posta del protocollo, registro giornaliero).
# *              Da avviare come servizio (systemd o container dedicato); un lavoro in errore
# *              non ferma gli altri. In alternativa usare i singoli comandi con cron/timer.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import logging
import signal
import time

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import close_old_connections
from django.utils import timezone

log = logging.getLogger("pianificatore")


class Command(BaseCommand):
    help = "Lavori periodici: scarica_posta (ogni N minuti) e registro_giornaliero (di notte)."

    def add_arguments(self, parser):
        parser.add_argument("--minuti-posta", type=int, default=15)
        parser.add_argument("--ora-registro", type=int, default=1, help="Ora del registro")
        parser.add_argument("--una-volta", action="store_true", help="Esegue tutto ed esce")

    def handle(self, *args, **opzioni):
        self.attivo = True
        signal.signal(signal.SIGTERM, self._ferma)
        signal.signal(signal.SIGINT, self._ferma)
        ultima_posta = 0.0
        ultimo_registro = None
        log.info("Pianificatore avviato")
        while self.attivo:
            adesso = timezone.localtime()
            intervallo = opzioni["minuti_posta"] * 60
            if opzioni["una_volta"] or time.monotonic() - ultima_posta >= intervallo:
                self._esegui("scarica_posta")
                ultima_posta = time.monotonic()
            if opzioni["una_volta"] or (
                adesso.hour >= opzioni["ora_registro"] and ultimo_registro != adesso.date()
            ):
                self._esegui("registro_giornaliero")
                ultimo_registro = adesso.date()
            if opzioni["una_volta"]:
                return
            for _ in range(30):  # risveglio ogni secondo per fermarsi subito
                if not self.attivo:
                    break
                time.sleep(1)
        log.info("Pianificatore fermato")

    def _esegui(self, comando):
        close_old_connections()
        try:
            call_command(comando, stdout=self.stdout, stderr=self.stderr)
        except Exception:  # noqa: BLE001 - un lavoro in errore non ferma il pianificatore
            log.exception("Lavoro %s non riuscito", comando)
        finally:
            close_old_connections()

    def _ferma(self, *_):
        self.attivo = False
