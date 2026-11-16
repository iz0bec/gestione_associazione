# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Spedizione per email o PEC dei protocolli in uscita: SMTP delle caselle,
# *              spedizioni ed esito per destinatario.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('protocollo', '0008_variante_pubblica_del_manuale'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='casellaposta',
            name='indirizzo',
            field=models.EmailField(blank=True, help_text='Lasciare vuoto se coincide con il nome utente.', max_length=254, verbose_name='indirizzo del mittente'),
        ),
        migrations.AddField(
            model_name='casellaposta',
            name='invio',
            field=models.BooleanField(default=False, help_text='I protocolli in uscita si possono spedire da questa casella (SMTP).', verbose_name='usata anche per spedire'),
        ),
        migrations.AddField(
            model_name='casellaposta',
            name='smtp_porta',
            field=models.PositiveIntegerField(default=465, verbose_name='porta SMTP'),
        ),
        migrations.AddField(
            model_name='casellaposta',
            name='smtp_server',
            field=models.CharField(blank=True, help_text='Es. smtps.pec.aruba.it', max_length=200, verbose_name='server SMTP'),
        ),
        migrations.AddField(
            model_name='casellaposta',
            name='smtp_ssl',
            field=models.BooleanField(default=True, help_text='Porta 465: SSL; porta 587: togliere la spunta (si usa STARTTLS).', verbose_name='SMTP con SSL implicito'),
        ),
        migrations.CreateModel(
            name='Spedizione',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('creato_il', models.DateTimeField(auto_now_add=True, verbose_name='creato il')),
                ('modificato_il', models.DateTimeField(auto_now=True, verbose_name='modificato il')),
                ('canale', models.CharField(choices=[('email', 'Email'), ('pec', 'PEC')], max_length=5)),
                ('mittente', models.CharField(max_length=254)),
                ('oggetto', models.CharField(max_length=600)),
                ('testo', models.TextField()),
                ('allegati', models.ManyToManyField(blank=True, related_name='spedizioni', to='protocollo.allegato')),
                ('casella', models.ForeignKey(blank=True, help_text='Vuota: server di invio generale.', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='spedizioni', to='protocollo.casellaposta')),
                ('creato_da', models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='creato da')),
                ('modificato_da', models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='modificato da')),
                ('protocollo', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='spedizioni', to='protocollo.protocollo')),
            ],
            options={
                'verbose_name': 'spedizione',
                'verbose_name_plural': 'spedizioni',
                'ordering': ['-creato_il', '-id'],
                'permissions': [('spedisci_protocollo', 'Può spedire per email o PEC i protocolli in uscita')],
            },
        ),
        migrations.CreateModel(
            name='DestinatarioSpedizione',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=300)),
                ('indirizzo', models.EmailField(max_length=254)),
                ('stato', models.CharField(choices=[('in_attesa', 'In coda'), ('inviato', 'Inviato'), ('accettato', 'Accettato dal gestore'), ('consegnato', 'Consegnato'), ('non_accettato', 'Non accettato'), ('non_consegnato', 'Non consegnato'), ('errore', 'Errore di invio')], db_index=True, default='in_attesa', max_length=15)),
                ('message_id', models.CharField(blank=True, db_index=True, max_length=300)),
                ('tentativi', models.PositiveSmallIntegerField(default=0)),
                ('dettaglio', models.CharField(blank=True, max_length=500)),
                ('inviato_il', models.DateTimeField(blank=True, null=True)),
                ('aggiornato_il', models.DateTimeField(blank=True, null=True)),
                ('corrispondente', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='protocollo.corrispondente')),
                ('spedizione', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='destinatari', to='protocollo.spedizione')),
            ],
            options={
                'verbose_name': 'destinatario della spedizione',
                'verbose_name_plural': 'destinatari della spedizione',
                'ordering': ['id'],
            },
        ),
    ]
