# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Domande di iscrizione ricevute via API: uuid, origine «integrazione» e controparte.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import uuid

import django.db.models.deletion
from django.db import migrations, models

def popola(apps, schema_editor):
    Modello = apps.get_model("soci", "domandaiscrizione")
    for riga in Modello.objects.filter(uuid__isnull=True).only("pk"):
        Modello.objects.filter(pk=riga.pk).update(uuid=uuid.uuid4())


class Migration(migrations.Migration):
    dependencies = [("soci", "0013_sezione_risorsa_api"), ("api", "0004_idempotenza")]

    operations = [
        migrations.AddField(
            "domandaiscrizione", "uuid", models.UUIDField(editable=False, null=True)
        ),
        migrations.AddField(
            "domandaiscrizione",
            "cliente_api",
            models.ForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="domande",
                to="api.clienteapi",
                verbose_name="inviata da",
            ),
        ),
        migrations.AlterField(
            "domandaiscrizione",
            "origine",
            models.CharField(
                choices=[
                    ("pubblica", "Modulo online"),
                    ("segreteria", "Segreteria"),
                    ("email", "Email"),
                    ("integrazione", "Integrazione (API)"),
                ],
                default="segreteria",
                max_length=12,
            ),
        ),
        migrations.RunPython(popola, migrations.RunPython.noop),
        migrations.AlterField(
            "domandaiscrizione",
            "uuid",
            models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
