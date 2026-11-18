# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Ricevute degli incassi esposte dall'API (uuid, versione).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import uuid

from django.db import migrations, models


def popola(apps, schema_editor):
    for nome in ("incasso",):
        Modello = apps.get_model("tesoreria", nome)
        for riga in Modello.objects.filter(uuid__isnull=True).only("pk"):
            Modello.objects.filter(pk=riga.pk).update(uuid=uuid.uuid4(), versione=1)


class Migration(migrations.Migration):
    dependencies = [("tesoreria", "0004_ciclo_tessere")]

    operations = [
        migrations.AddField("incasso", "uuid", models.UUIDField(editable=False, null=True)),
        migrations.AddField(
            "incasso", "versione", models.PositiveIntegerField(default=0, editable=False)
        ),
        migrations.RunPython(popola, migrations.RunPython.noop),
        migrations.AlterField(
            "incasso", "uuid", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
        ),
    ]
