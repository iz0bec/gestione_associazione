# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Accessi all'area personale e richieste dei soci.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('anagrafica', '0009_sms_whatsapp'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AccessoArea',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('impronta', models.CharField(max_length=64, unique=True)),
                ('creato_il', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('usato_il', models.DateTimeField(blank=True, null=True)),
                ('indirizzo_ip', models.GenericIPAddressField(blank=True, null=True)),
                ('soggetto', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='accessi_area', to='anagrafica.soggetto')),
            ],
            options={
                'verbose_name': "accesso all'area personale",
                'verbose_name_plural': "accessi all'area personale",
            },
        ),
        migrations.CreateModel(
            name='RichiestaArea',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('testo', models.TextField()),
                ('creata_il', models.DateTimeField(auto_now_add=True)),
                ('gestita_il', models.DateTimeField(blank=True, null=True)),
                ('gestita_da', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('soggetto', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='richieste_area', to='anagrafica.soggetto')),
            ],
            options={
                'verbose_name': "richiesta dall'area personale",
                'verbose_name_plural': "richieste dall'area personale",
                'ordering': ['-creata_il'],
            },
        ),
    ]
