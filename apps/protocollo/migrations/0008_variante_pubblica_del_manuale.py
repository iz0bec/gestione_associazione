# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Variante pubblica di ogni versione adottata del manuale di gestione.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('protocollo', '0007_versioni_del_manuale'),
    ]

    operations = [
        migrations.AddField(
            model_name='versionemanuale',
            name='allegato_pubblico',
            field=models.ForeignKey(blank=True, help_text="Variante per la pubblicazione (senza utenti né account), prodotta all'adozione.", null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='protocollo.allegato'),
        ),
    ]
