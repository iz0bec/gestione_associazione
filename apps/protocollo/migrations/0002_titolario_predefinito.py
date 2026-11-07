# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Titolario di classificazione di base per un'associazione (modificabile)
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.db import migrations

TITOLARIO = [
    ("01", "Organizzazione e statuto"),
    ("02", "Soci e tesseramento"),
    ("03", "Organi sociali (assemblee, consiglio direttivo)"),
    ("04", "Amministrazione e contabilità"),
    ("05", "Patrimonio e beni"),
    ("06", "Attività, eventi e cerimonie"),
    ("07", "Rapporti con enti e istituzioni"),
    ("08", "Rapporti con l'associazione nazionale e le sezioni"),
    ("09", "Comunicazione e stampa"),
    ("10", "Privacy, sicurezza e adempimenti"),
    ("99", "Varie"),
]


def crea(apps, schema_editor):
    Classificazione = apps.get_model("protocollo", "Classificazione")
    for codice, descrizione in TITOLARIO:
        Classificazione.objects.get_or_create(codice=codice, defaults={"descrizione": descrizione})


class Migration(migrations.Migration):
    dependencies = [("protocollo", "0001_initial")]
    operations = [migrations.RunPython(crea, migrations.RunPython.noop)]
