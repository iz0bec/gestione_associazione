# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Avvisi della posta da protocollare scelti dall'utente (Telegram, SMS, WhatsApp).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_flag_cambio_password'),
    ]

    operations = [
        migrations.AddField(
            model_name='utente',
            name='avvisi_posta',
            field=models.CharField(blank=True, choices=[('', 'Nessuno'), ('telegram', 'Telegram'), ('sms', 'SMS'), ('whatsapp', 'WhatsApp')], help_text="Scelto dall'utente: un avviso quando arrivano messaggi nuovi da protocollare.", max_length=10, verbose_name='avvisi della posta da protocollare'),
        ),
    ]
