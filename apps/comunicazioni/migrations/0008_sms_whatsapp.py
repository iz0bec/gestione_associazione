# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Comunicazioni anche per SMS e WhatsApp: testo breve e consegne per canale.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('comunicazioni', '0007_pec_e_telegram'),
    ]

    operations = [
        migrations.AddField(
            model_name='invio',
            name='sms',
            field=models.BooleanField(default=False, verbose_name='anche per SMS'),
        ),
        migrations.AddField(
            model_name='invio',
            name='testo_breve',
            field=models.CharField(blank=True, help_text="Con i segnaposto. Vuoto: l'oggetto della comunicazione.", max_length=320, verbose_name='testo breve (SMS e WhatsApp)'),
        ),
        migrations.AddField(
            model_name='invio',
            name='whatsapp',
            field=models.BooleanField(default=False, verbose_name='anche su WhatsApp'),
        ),
        migrations.CreateModel(
            name='ConsegnaMessaggio',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('canale', models.CharField(choices=[('sms', 'SMS'), ('whatsapp', 'WhatsApp')], max_length=10)),
                ('numero', models.CharField(max_length=20)),
                ('stato', models.CharField(choices=[('in_attesa', 'In attesa'), ('inviato', 'Inviato'), ('errore', 'Errore')], db_index=True, default='in_attesa', max_length=10)),
                ('errore', models.CharField(blank=True, max_length=255)),
                ('tentativi', models.PositiveSmallIntegerField(default=0)),
                ('riferimento', models.CharField(blank=True, help_text='Id del fornitore.', max_length=100)),
                ('inviato_il', models.DateTimeField(blank=True, null=True)),
                ('destinatario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='consegne', to='comunicazioni.destinatario')),
            ],
            options={
                'verbose_name': 'consegna di messaggio',
                'verbose_name_plural': 'consegne di messaggi',
                'constraints': [models.UniqueConstraint(fields=('destinatario', 'canale'), name='una_consegna_per_canale')],
            },
        ),
    ]
