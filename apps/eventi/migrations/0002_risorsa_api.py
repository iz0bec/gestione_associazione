# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Evento esposto dall'API: uuid (popolato per le righe esistenti) e versione.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import uuid

from django.db import migrations, models


def popola(apps, schema_editor):
    Modello = apps.get_model("eventi", "evento")
    for riga in Modello.objects.filter(uuid__isnull=True).only("pk"):
        Modello.objects.filter(pk=riga.pk).update(uuid=uuid.uuid4(), versione=1)


class Migration(migrations.Migration):
    dependencies = [("eventi", "0001_iniziale")]

    operations = [
        migrations.AddField(
            model_name="evento",
            name="uuid",
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.AddField(
            model_name="evento",
            name="versione",
            field=models.PositiveIntegerField(default=0, editable=False),
        ),
        migrations.RunPython(popola, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="evento",
            name="uuid",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
