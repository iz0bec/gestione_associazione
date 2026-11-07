# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Genera i registri giornalieri di protocollo mancanti fino a ieri
# *              (da pianificare ogni notte; rieseguibile senza effetti doppi).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.core.management.base import BaseCommand

from apps.protocollo.servizi import genera_registri_mancanti


class Command(BaseCommand):
    help = "Genera e conserva i PDF dei registri giornalieri di protocollo mancanti."

    def handle(self, *args, **options):
        creati = genera_registri_mancanti()
        for r in creati:
            self.stdout.write(
                f"{r.data:%d/%m/%Y}: {r.registrazioni} registrazioni, SHA-256 {r.impronta}"
            )
        if not creati:
            self.stdout.write("Nessun registro da generare.")
