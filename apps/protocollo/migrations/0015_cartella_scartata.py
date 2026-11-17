# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Cartella SCARTATA sul server e spostamenti dei messaggi in attesa (scartati già
# *              presenti compresi: vanno in SCARTATA al prossimo scaricamento).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
import django.core.validators
from django.db import migrations, models


def scartati_da_spostare(apps, schema_editor):
    messaggi = apps.get_model("protocollo", "MessaggioRicevuto")
    messaggi.objects.filter(
        stato="scartato", ripulito_il__isnull=True, casella__cartella_scartata__gt=""
    ).update(spostare_in="scartata")


class Migration(migrations.Migration):

    dependencies = [
        ('protocollo', '0014_posta_ripulita'),
    ]

    operations = [
        migrations.AddField(
            model_name='casellaposta',
            name='cartella_scartata',
            field=models.CharField(blank=True, default='SCARTATA', help_text='I messaggi scartati nel programma vengono spostati in questa cartella del server (creata se manca), al giro di scaricamento successivo. Vuota: restano dove sono.', max_length=100, validators=[django.core.validators.RegexValidator('^[A-Za-z0-9][A-Za-z0-9 _.\\-]*$', 'Solo lettere senza accenti, cifre, spazi, punti, trattini e trattini bassi.')], verbose_name='cartella dei messaggi scartati'),
        ),
        migrations.AddField(
            model_name='messaggioricevuto',
            name='cartella_server',
            field=models.CharField(blank=True, editable=False, max_length=10),
        ),
        migrations.AddField(
            model_name='messaggioricevuto',
            name='errore_server',
            field=models.CharField(blank=True, editable=False, max_length=300),
        ),
        migrations.AddField(
            model_name='messaggioricevuto',
            name='spostare_in',
            field=models.CharField(blank=True, db_index=True, editable=False, help_text='Spostamento sul server in attesa del prossimo scaricamento (processata, scartata, cestino).', max_length=10),
        ),
        migrations.RunPython(scartati_da_spostare, migrations.RunPython.noop),
    ]
