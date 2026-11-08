# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Importazione dai gestionali precedenti (anteprima predefinita, --esegui applica)
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.soci.models import Sezione, TipologiaSocio
from apps.tesoreria.models import Conto


class Command(BaseCommand):
    help = (
        "Importa i dati di un gestionale precedente. Senza --esegui mostra solo l'anteprima "
        "(nessuna modifica). Rieseguibile: i record già importati vengono saltati."
    )

    def add_arguments(self, parser):
        sotto = parser.add_subparsers(dest="fonte", required=True)
        gs = sotto.add_parser("gestione-soci", help="Gestione Soci (database SQLite)")
        gs.add_argument("database", help="File .db di Gestione Soci (es. instance/gest_2025.db)")
        gs.add_argument("--tipologia", default="Ordinario", help="Tipologia dei soci nuovi")
        gs.add_argument("--sezione", help="Codice della sezione per i soci senza sezione")
        gs.add_argument("--abbina", choices=["comune", "nome", "codice"], default="comune")
        gs.add_argument("--crea-sezioni", action="store_true", help="Crea le sezioni mancanti")
        gs.add_argument("--conto", help="Conto della cassa importata (predefinito: contanti)")
        gs.add_argument("--senza-tesoreria", action="store_true")
        gs.add_argument("--senza-beni", action="store_true")
        for p in (gs,):
            p.add_argument("--utente", help="Username registrato come autore (audit)")
            p.add_argument("--esegui", action="store_true", help="Applica (senza: anteprima)")
            p.add_argument("--dettagli", action="store_true", help="Mostra ogni record")

    def handle(self, *args, **o):
        utente = None
        if o.get("utente"):
            utente = get_user_model().objects.filter(username=o["utente"]).first()
            if utente is None:
                raise CommandError(f"Utente {o['utente']} inesistente.")
        try:
            rapporto = getattr(self, "_" + o["fonte"].replace("-", "_"))(o, utente)
        except ValidationError as e:
            raise CommandError(" ".join(e.messages)) from e
        self.stdout.write(rapporto.testo(dettagli=o["dettagli"]))
        if not o["esegui"]:
            avviso = "\nAnteprima: nulla è stato modificato. Ripetere con --esegui per applicare."
            self.stdout.write(self.style.WARNING(avviso))

    def _gestione_soci(self, o, utente):
        from apps.migrazione import gestione_soci

        tipologia = TipologiaSocio.objects.filter(nome__iexact=o["tipologia"]).first()
        if tipologia is None:
            raise CommandError(f"Tipologia {o['tipologia']} inesistente.")
        sezione = None
        if o["sezione"]:
            sezione = Sezione.objects.filter(codice=o["sezione"]).first()
            if sezione is None:
                raise CommandError(f"Sezione {o['sezione']} inesistente.")
        conto = None
        if o["conto"]:
            conto = Conto.objects.filter(nome__iexact=o["conto"]).first()
            if conto is None:
                raise CommandError(f"Conto {o['conto']} inesistente.")
        opzioni = gestione_soci.Opzioni(
            tipologia=tipologia, sezione=sezione, abbina=o["abbina"], conto=conto,
            crea_sezioni=o["crea_sezioni"], tesoreria=not o["senza_tesoreria"],
            beni=not o["senza_beni"],
        )  # fmt: skip
        return gestione_soci.importa(o["database"], opzioni, utente, esegui=o["esegui"])
