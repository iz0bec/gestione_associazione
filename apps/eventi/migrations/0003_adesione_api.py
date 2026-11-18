# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Adesioni ricevute via API: uuid, versione, controparte e riferimento esterno.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import uuid

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models

def popola(apps, schema_editor):
    Modello = apps.get_model("eventi", "adesione")
    for riga in Modello.objects.filter(uuid__isnull=True).only("pk"):
        Modello.objects.filter(pk=riga.pk).update(uuid=uuid.uuid4())


class Migration(migrations.Migration):
    dependencies = [("eventi", "0002_risorsa_api"), ("api", "0004_idempotenza")]

    operations = [
        migrations.AddField("adesione", "uuid", models.UUIDField(editable=False, null=True)),
        migrations.AddField(
            "adesione", "versione", models.PositiveIntegerField(default=1, editable=False)
        ),
        migrations.AddField(
            "adesione",
            "modificata_il",
            models.DateTimeField(auto_now=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            "adesione",
            "cliente_api",
            models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="adesioni",
                to="api.clienteapi",
                verbose_name="inviata da",
            ),
        ),
        migrations.AddField(
            "adesione",
            "riferimento_esterno",
            models.CharField(blank=True, editable=False, max_length=100),
        ),
        migrations.AlterField(
            "adesione",
            "origine",
            models.CharField(
                choices=[
                    ("segreteria", "Segreteria"),
                    ("pubblico", "Modulo pubblico"),
                    ("area", "Area del socio"),
                    ("integrazione", "Integrazione (API)"),
                ],
                max_length=12,
            ),
        ),
        migrations.RunPython(popola, migrations.RunPython.noop),
        migrations.AlterField(
            "adesione",
            "uuid",
            models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
