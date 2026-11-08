# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Termini di conservazione: con l'anonimizzazione automatica attiva anonimizza le
# *              persone oltre il termine; altrimenti (o con --elenco) le elenca soltanto.
# *              Rieseguibile.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.core.management.base import BaseCommand

from apps.anagrafica import gdpr
from apps.core.models import Organizzazione


class Command(BaseCommand):
    help = "Anonimizza (se attivo) le persone oltre il termine di conservazione dei dati."

    def add_arguments(self, parser):
        parser.add_argument(
            "--elenco", action="store_true", help="Solo l'elenco, nessuna modifica."
        )

    def handle(self, *args, **opzioni):
        elenco = gdpr.scaduti()
        if opzioni["elenco"] or not Organizzazione.corrente().anonimizzazione_automatica:
            self.stdout.write(f"Persone oltre il termine di conservazione: {len(elenco)}")
            return
        if elenco:
            fatti, saltati = gdpr.anonimizza_scaduti(None)
            self.stdout.write(f"Anonimizzate {fatti} persone oltre il termine ({saltati} saltate)")
