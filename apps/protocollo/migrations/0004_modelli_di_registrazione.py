# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Modelli di registrazione del protocollo («Parti da un modello»).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('comunicazioni', '0004_modello_tessera'),
        ('protocollo', '0003_testo_del_protocollo'),
    ]

    operations = [
        migrations.CreateModel(
            name='ModelloProtocollo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=120, unique=True)),
                ('direzione', models.CharField(choices=[('entrata', 'In entrata'), ('uscita', 'In uscita'), ('interno', 'Interno')], default='uscita', max_length=8)),
                ('mezzo', models.CharField(choices=[('email', 'Email'), ('pec', 'PEC'), ('posta', 'Posta ordinaria'), ('raccomandata', 'Raccomandata'), ('mano', 'Consegna a mano'), ('messaggistica', 'Messaggistica'), ('altro', 'Altro')], default='email', max_length=15)),
                ('oggetto', models.CharField(help_text='{{ anno }}, {{ anno_precedente }}, {{ data }} e {{ organizzazione }} diventano i valori del giorno; i puntini (...) ricordano cosa completare.', max_length=500)),
                ('testo', models.TextField(blank=True, help_text='Corpo del messaggio, con gli stessi segnaposto.')),
                ('riservato', models.BooleanField(default=False)),
                ('ordine', models.PositiveSmallIntegerField(default=0)),
                ('attivo', models.BooleanField(default=True)),
                ('classificazione', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='protocollo.classificazione')),
                ('liste', models.ManyToManyField(blank=True, help_text='Destinatari proposti (solo per uscita e interno).', related_name='+', to='comunicazioni.lista', verbose_name='liste di distribuzione')),
            ],
            options={
                'verbose_name': 'modello di registrazione',
                'verbose_name_plural': 'modelli di registrazione',
                'ordering': ['ordine', 'nome'],
            },
        ),
    ]
