# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Comunicazioni senza email: solo SMS, WhatsApp o Telegram.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('comunicazioni', '0008_sms_whatsapp'),
    ]

    operations = [
        migrations.AddField(
            model_name='invio',
            name='email',
            field=models.BooleanField(default=True, help_text='Tolto: solo SMS, WhatsApp o Telegram.', verbose_name='per email'),
        ),
    ]
