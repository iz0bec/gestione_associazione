# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Durata del mandato degli organi e preavviso della scadenza.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('organi', '0007_permesso_timbri'),
    ]

    operations = [
        migrations.AddField(
            model_name='organo',
            name='durata_mandato',
            field=models.PositiveSmallIntegerField(blank=True, help_text='Secondo lo statuto (es. 4). Vuoto: nessuna scadenza calcolata.', null=True, verbose_name='durata del mandato (anni)'),
        ),
        migrations.AddField(
            model_name='organo',
            name='preavviso_mandato',
            field=models.PositiveSmallIntegerField(default=90, help_text='Da quanti giorni prima la scadenza compare nel cruscotto.', verbose_name='preavviso (giorni)'),
        ),
    ]
