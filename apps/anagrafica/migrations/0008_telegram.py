# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Collegamento Telegram della persona (chat, data, codice dell'invito).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('anagrafica', '0007_conservazione'),
    ]

    operations = [
        migrations.AddField(
            model_name='soggetto',
            name='telegram_chat_id',
            field=models.BigIntegerField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name='soggetto',
            name='telegram_codice',
            field=models.CharField(blank=True, db_index=True, editable=False, max_length=32),
        ),
        migrations.AddField(
            model_name='soggetto',
            name='telegram_collegato_il',
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
    ]
