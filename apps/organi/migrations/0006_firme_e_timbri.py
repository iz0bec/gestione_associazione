# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Firme grafiche (per persona) e timbri (per ente) per le stampe.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
import apps.organi.models
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('anagrafica', '0007_conservazione'),
        ('organi', '0005_modelli_convocazione'),
        ('soci', '0012_domanda_modulo_protocollo'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='FirmaGrafica',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('immagine', models.FileField(max_length=255, upload_to=apps.organi.models.percorso_contrassegno)),
                ('impronta', models.CharField(max_length=64, verbose_name='impronta SHA-256')),
                ('attiva', models.BooleanField(default=True, help_text="Spenta: l'immagine resta ma non si stampa.", verbose_name='usa nelle stampe')),
                ('caricata_il', models.DateTimeField(auto_now=True)),
                ('autorizzazione', models.CharField(blank=True, help_text="Come l'interessato ha autorizzato l'uso, es. «autorizzazione scritta del 12/11/2026, prot. 2026-00045».", max_length=200)),
                ('caricata_da', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('soggetto', models.OneToOneField(limit_choices_to={'tipo': 'persona'}, on_delete=django.db.models.deletion.CASCADE, related_name='firma_grafica', to='anagrafica.soggetto', verbose_name='persona')),
            ],
            options={
                'verbose_name': 'firma grafica',
                'verbose_name_plural': 'firme grafiche',
                'permissions': [('gestisci_firme', 'Può caricare le firme e i timbri per le stampe')],
            },
        ),
        migrations.CreateModel(
            name='Timbro',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('immagine', models.FileField(max_length=255, upload_to=apps.organi.models.percorso_contrassegno)),
                ('impronta', models.CharField(max_length=64, verbose_name='impronta SHA-256')),
                ('attiva', models.BooleanField(default=True, help_text="Spenta: l'immagine resta ma non si stampa.", verbose_name='usa nelle stampe')),
                ('caricata_il', models.DateTimeField(auto_now=True)),
                ('caricata_da', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('sezione', models.ForeignKey(blank=True, help_text="Vuota = l'associazione (federazione).", null=True, on_delete=django.db.models.deletion.CASCADE, related_name='timbri', to='soci.sezione')),
            ],
            options={
                'verbose_name': 'timbro',
                'verbose_name_plural': 'timbri',
                'constraints': [models.UniqueConstraint(fields=('sezione',), name='timbro_unico_per_ente', nulls_distinct=False)],
            },
        ),
    ]
