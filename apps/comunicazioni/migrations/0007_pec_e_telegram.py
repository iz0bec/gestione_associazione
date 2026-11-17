# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Comunicazioni via PEC (servizio di invio, canale, ricevute) e anche su Telegram.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('comunicazioni', '0006_lista_sezioni'),
        ('core', '0013_canale_telegram'),
    ]

    operations = [
        migrations.AddField(
            model_name='destinatario',
            name='canale',
            field=models.CharField(choices=[('email', 'Email'), ('pec', 'PEC')], default='email', max_length=5),
        ),
        migrations.AddField(
            model_name='destinatario',
            name='esito_pec',
            field=models.CharField(blank=True, help_text='Ultima ricevuta PEC (accettazione, consegna...).', max_length=30),
        ),
        migrations.AddField(
            model_name='destinatario',
            name='message_id',
            field=models.CharField(blank=True, db_index=True, max_length=255),
        ),
        migrations.AddField(
            model_name='destinatario',
            name='telegram_errore',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='destinatario',
            name='telegram_stato',
            field=models.CharField(blank=True, help_text='Vuoto: non su Telegram; in_attesa, inviato, errore.', max_length=10),
        ),
        migrations.AddField(
            model_name='invio',
            name='servizio',
            field=models.ForeignKey(blank=True, help_text='Vuoto: il server generale. Con un servizio PEC chi ha la PEC la riceve per PEC, gli altri per email dal server generale.', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='invii', to='core.servizioinvio', verbose_name='spedisci da'),
        ),
        migrations.AddField(
            model_name='invio',
            name='telegram',
            field=models.BooleanField(default=False, help_text='A chi ha collegato Telegram.', verbose_name='anche su Telegram'),
        ),
        migrations.AlterField(
            model_name='destinatario',
            name='email',
            field=models.EmailField(blank=True, help_text='Indirizzo email o PEC, secondo il canale.', max_length=254),
        ),
    ]
