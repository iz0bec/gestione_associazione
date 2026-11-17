# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Interruttore dell'area personale dei soci.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0015_interruttore_invio'),
    ]

    operations = [
        migrations.AddField(
            model_name='organizzazione',
            name='area_soci',
            field=models.BooleanField(default=False, help_text="I soci entrano all'indirizzo /area/ con un collegamento inviato alla propria email e vedono dati, tessere, quote, ricevute ed eventi.", verbose_name='area personale dei soci'),
        ),
    ]
