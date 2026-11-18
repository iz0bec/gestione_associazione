# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Identità dell'istanza creata alla prima migrazione (le chiavi nascono al primo uso,
# *              quando c'è CHIAVE_CIFRATURA).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.db import migrations


def crea_istanza(apps, schema_editor):
    Istanza = apps.get_model("api", "Istanza")
    if not Istanza.objects.exists():
        Istanza.objects.create()


class Migration(migrations.Migration):
    dependencies = [("api", "0001_iniziale")]

    operations = [migrations.RunPython(crea_istanza, migrations.RunPython.noop)]
