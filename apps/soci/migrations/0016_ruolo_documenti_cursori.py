# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Documenti del ciclo delle tessere esposti dall'API (uuid, versione) e collegamenti
# *              con le consegne e le richieste ricevute.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import uuid

import django.db.models.deletion
from django.db import migrations, models


def popola(apps, schema_editor):
    for nome in (
        "consegnatessere",
        "lottotessere",
        "richiestatessere",
    ):
        Modello = apps.get_model("soci", nome)
        for riga in Modello.objects.filter(uuid__isnull=True).only("pk"):
            Modello.objects.filter(pk=riga.pk).update(uuid=uuid.uuid4(), versione=1)


class Migration(migrations.Migration):
    dependencies = [("api", "0005_ruolo_documenti_cursori"), ("soci", "0015_ciclo_tessere")]

    operations = [
        migrations.AddField("consegnatessere", "uuid", models.UUIDField(editable=False, null=True)),
        migrations.AddField(
            "consegnatessere", "versione", models.PositiveIntegerField(default=0, editable=False)
        ),
        migrations.AddField("lottotessere", "uuid", models.UUIDField(editable=False, null=True)),
        migrations.AddField(
            "lottotessere", "versione", models.PositiveIntegerField(default=0, editable=False)
        ),
        migrations.AddField(
            "richiestatessere", "uuid", models.UUIDField(editable=False, null=True)
        ),
        migrations.AddField(
            "richiestatessere", "versione", models.PositiveIntegerField(default=0, editable=False)
        ),
        migrations.AddField(
            "lottotessere",
            "consegna_uuid",
            models.UUIDField(
                blank=True,
                editable=False,
                help_text="Consegna della federazione da cui viene il lotto (presa in carico via API).",
                null=True,
            ),
        ),
        migrations.AddField(
            "richiestatessere",
            "uuid_origine",
            models.UUIDField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            "richiestatessere",
            "cliente_api",
            models.ForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="api.clienteapi",
                verbose_name="ricevuta da",
            ),
        ),
        migrations.RunPython(popola, migrations.RunPython.noop),
        migrations.AlterField(
            "consegnatessere",
            "uuid",
            models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
        migrations.AlterField(
            "lottotessere",
            "uuid",
            models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
        migrations.AlterField(
            "richiestatessere",
            "uuid",
            models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
