# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: L'interruttore «invio dei messaggi» vale per tutti i canali (solo etichetta).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0014_sms_whatsapp'),
    ]

    operations = [
        migrations.AlterField(
            model_name='organizzazione',
            name='invio_email',
            field=models.BooleanField(default=True, help_text='Spento: non parte nulla, né email e PEC né Telegram, SMS e WhatsApp (comunicazioni, protocolli, auguri, promemoria, recupero password); i messaggi già confermati restano in coda.', verbose_name='invio dei messaggi'),
        ),
    ]
