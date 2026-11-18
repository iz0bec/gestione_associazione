# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Sezione esposto dall'API: uuid (popolato per le righe esistenti) e versione.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import uuid

import django.utils.timezone
from django.db import migrations, models


def popola(apps, schema_editor):
    Modello = apps.get_model("soci", "sezione")
    for riga in Modello.objects.filter(uuid__isnull=True).only("pk"):
        Modello.objects.filter(pk=riga.pk).update(uuid=uuid.uuid4(), versione=1)


class Migration(migrations.Migration):
    dependencies = [("soci", "0012_domanda_modulo_protocollo")]

    operations = [
        migrations.AddField(
            model_name="sezione",
            name="uuid",
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.AddField(
            model_name="sezione",
            name="versione",
            field=models.PositiveIntegerField(default=0, editable=False),
        ),
        migrations.AddField(
            model_name="sezione",
            name="modificato_il",
            field=models.DateTimeField(
                auto_now=True, default=django.utils.timezone.now, verbose_name="modificato il"
            ),
            preserve_default=False,
        ),
        migrations.RunPython(popola, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="sezione",
            name="uuid",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
