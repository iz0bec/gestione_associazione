# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Rimette in coda lo spostamento in SCARTATA degli scartati «non trovati» dalla
# *              1.0.25 (erano ancora nella posta in arrivo, ora li si cerca anche lì).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.db import migrations


def riprova(apps, schema_editor):
    messaggi = apps.get_model("protocollo", "MessaggioRicevuto")
    messaggi.objects.filter(
        stato="scartato",
        ripulito_il__isnull=True,
        cartella_server="",
        spostare_in="",
        errore_server__startswith="non trovato",
        casella__cartella_scartata__gt="",
    ).update(spostare_in="scartata", errore_server="")


class Migration(migrations.Migration):
    dependencies = [("protocollo", "0015_cartella_scartata")]

    operations = [migrations.RunPython(riprova, migrations.RunPython.noop)]
