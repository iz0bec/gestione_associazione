# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Bot Telegram dell'organizzazione.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0012_servizi_invio'),
    ]

    operations = [
        migrations.CreateModel(
            name='CanaleTelegram',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token_cifrato', models.TextField(blank=True, editable=False)),
                ('nome_bot', models.CharField(blank=True, editable=False, help_text='Letto da Telegram.', max_length=64, verbose_name='nome del bot')),
                ('attivo', models.BooleanField(default=False)),
                ('ultimo_update', models.BigIntegerField(default=0, editable=False)),
                ('ultimo_controllo', models.DateTimeField(blank=True, editable=False, null=True)),
                ('ultimo_errore', models.CharField(blank=True, editable=False, max_length=300)),
            ],
            options={
                'verbose_name': 'canale Telegram',
                'verbose_name_plural': 'canale Telegram',
            },
        ),
    ]
