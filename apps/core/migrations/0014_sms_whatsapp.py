# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Servizi di messaggistica (SMS e WhatsApp Business).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0013_canale_telegram'),
    ]

    operations = [
        migrations.CreateModel(
            name='ServizioMessaggi',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=100)),
                ('tipo', models.CharField(choices=[('skebby', 'SMS - Skebby'), ('aruba', 'SMS - Aruba'), ('twilio', 'SMS - Twilio'), ('whatsapp', 'WhatsApp Business (API Cloud di Meta)')], max_length=10)),
                ('account', models.CharField(help_text='Skebby e Aruba: nome utente; Twilio: Account SID; WhatsApp: ID del numero di telefono (Phone number ID).', max_length=200)),
                ('segreto_cifrato', models.TextField(blank=True, editable=False)),
                ('mittente', models.CharField(blank=True, help_text='SMS: mittente alfanumerico (max 11 caratteri, es. ANCR) o numero; Twilio: numero (+39...) o Messaging Service SID (MG...). Non serve per WhatsApp.', max_length=40)),
                ('modello', models.CharField(blank=True, help_text='Nome del modello di messaggio approvato da Meta, con un solo parametro {{1}} nel corpo: lì va il testo breve della comunicazione.', max_length=100, verbose_name='modello WhatsApp')),
                ('lingua', models.CharField(blank=True, default='it', max_length=10, verbose_name='lingua del modello')),
                ('tipo_messaggio', models.CharField(blank=True, help_text='Skebby e Aruba: tipo di messaggio del listino (es. GP alta qualità, N notifica). Vuoto: GP.', max_length=10, verbose_name='qualità SMS')),
                ('url_base', models.URLField(blank=True, help_text='Vuoto: quello predefinito del fornitore. Da cambiare solo se lo indica il fornitore.', verbose_name="indirizzo dell'API")),
                ('attivo', models.BooleanField(default=False)),
                ('ultimo_errore', models.CharField(blank=True, editable=False, max_length=300)),
            ],
            options={
                'verbose_name': 'servizio di messaggistica',
                'verbose_name_plural': 'servizi di messaggistica',
                'ordering': ['tipo', 'nome'],
            },
        ),
    ]
