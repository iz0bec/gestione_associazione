# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Cartella del server in cui spostare i messaggi scaricati (PROCESSATA).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('protocollo', '0009_spedizioni'),
    ]

    operations = [
        migrations.AddField(
            model_name='casellaposta',
            name='cartella_processata',
            field=models.CharField(blank=True, default='PROCESSATA', help_text='Dopo lo scaricamento i messaggi vengono spostati in questa cartella del server (creata se manca). Vuota: restano dove sono.', max_length=100, validators=[django.core.validators.RegexValidator('^[A-Za-z0-9][A-Za-z0-9 _.\\-]*$', 'Solo lettere senza accenti, cifre, spazi, punti, trattini e trattini bassi.')], verbose_name='cartella dei messaggi scaricati'),
        ),
    ]
