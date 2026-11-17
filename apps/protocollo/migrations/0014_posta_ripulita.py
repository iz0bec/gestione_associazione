# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Pulizia della posta scartata: data della pulizia e permesso dedicato.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('protocollo', '0013_rispondi_con'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='messaggioricevuto',
            options={'ordering': ['-data', '-id'], 'permissions': [('gestisci_posta', 'Può esaminare, protocollare e scartare la posta ricevuta'), ('ripulisci_posta', 'Può eliminare definitivamente il contenuto della posta scartata')], 'verbose_name': 'messaggio ricevuto', 'verbose_name_plural': 'messaggi ricevuti'},
        ),
        migrations.AddField(
            model_name='messaggioricevuto',
            name='ripulito_il',
            field=models.DateTimeField(blank=True, editable=False, help_text='Scartato e ripulito: testo, allegati e file originale eliminati.', null=True),
        ),
    ]
