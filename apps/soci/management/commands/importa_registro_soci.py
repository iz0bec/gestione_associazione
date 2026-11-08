# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Importa i soci dall'estratto del registro nazionale (anteprima predefinita,
# *              --esegui per applicare). Stesse regole dell'importazione dall'interfaccia.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.soci import importazione
from apps.soci.models import Sezione, TipologiaSocio


class Command(BaseCommand):
    help = "Importa i soci da un file .xlsx o .csv del registro soci nazionale."

    def add_arguments(self, parser):
        parser.add_argument("file")
        parser.add_argument("--sezione", help="Codice della sezione per le righe senza sezione")
        parser.add_argument("--tipologia", default="Ordinario", help="Tipologia predefinita")
        parser.add_argument("--crea-sezioni", action="store_true")
        parser.add_argument("--allinea-sezione", action="store_true")
        parser.add_argument("--anno-tessere", type=int)
        parser.add_argument("--utente", help="Username registrato come autore (audit)")
        parser.add_argument("--esegui", action="store_true", help="Applica (senza: anteprima)")
        parser.add_argument("--dettagli", action="store_true", help="Mostra ogni riga")

    def handle(self, *args, **o):
        percorso = Path(o["file"])
        if not percorso.is_file():
            raise CommandError(f"File non trovato: {percorso}")
        sezione = None
        if o["sezione"]:
            sezione = Sezione.objects.filter(codice=o["sezione"]).first()
            if not sezione:
                raise CommandError(f"Sezione {o['sezione']} inesistente.")
        tipologia = TipologiaSocio.objects.filter(nome__iexact=o["tipologia"]).first()
        if not tipologia:
            raise CommandError(f"Tipologia {o['tipologia']} inesistente.")
        utente = None
        if o["utente"]:
            utente = get_user_model().objects.filter(username=o["utente"]).first()
        try:
            mappa, righe, ignorate = importazione.leggi(percorso.name, percorso.read_bytes())
        except importazione.FileNonValido as e:
            raise CommandError(" ".join(e.messages)) from None
        self.stdout.write(f"Colonne riconosciute: {', '.join(sorted(set(mappa.values())))}")
        if ignorate:
            self.stdout.write(f"Colonne ignorate: {', '.join(ignorate)}")
        opzioni = importazione.Opzioni(
            sezione=sezione, tipologia=tipologia, crea_sezioni=o["crea_sezioni"],
            allinea_sezione=o["allinea_sezione"], anno_tessere=o["anno_tessere"],
        )  # fmt: skip
        r = importazione.elabora(righe, opzioni, utente, esegui=o["esegui"])
        for e in r.esiti:
            if o["dettagli"] or e.stato == "errore":
                self.stdout.write(f"  riga {e.riga:>5} {e.stato:<10} {e.nome}: {'; '.join(e.note)}")
        if r.sezioni_nuove:
            self.stdout.write(f"Sezioni nuove: {', '.join(r.sezioni_nuove)}")
        if r.assenti:
            self.stdout.write(f"Soci attivi assenti dal file: {len(r.assenti)}")
        titolo = "Importazione eseguita" if r.eseguito else "ANTEPRIMA (nulla modificato)"
        self.stdout.write(self.style.SUCCESS(f"{titolo}: {r.riepilogo}"))
