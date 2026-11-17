# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Consenso a ricevere messaggi su WhatsApp.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('anagrafica', '0008_telegram'),
    ]

    operations = [
        migrations.AddField(
            model_name='soggetto',
            name='whatsapp_consenso_il',
            field=models.DateTimeField(blank=True, editable=False, null=True, verbose_name='consenso WhatsApp'),
        ),
    ]
