# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Dati organizzativi del manuale di gestione documentale.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('anagrafica', '0007_conservazione'),
        ('protocollo', '0005_modelli_predefiniti'),
    ]

    operations = [
        migrations.CreateModel(
            name='ManualeGestione',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('conservatore', models.CharField(blank=True, help_text='Chi conserva registri e documenti nel lungo periodo, es. «conservatore qualificato X, contratto del ...» oppure «copie periodiche su supporto esterno».', max_length=255, verbose_name='conservazione dei documenti')),
                ('atto_adozione', models.CharField(blank=True, help_text='Es. «delibera del Consiglio direttivo n. 5 del 20/11/2026».', max_length=200, verbose_name='atto di adozione')),
                ('integrazioni', models.TextField(blank=True, help_text="Regole organizzative proprie dell'ente (orari, uffici, casi particolari), riportate in un capitolo del manuale. Ammessi grassetto, elenchi e titoli Markdown.", verbose_name='disposizioni aggiuntive')),
                ('versione', models.PositiveIntegerField(default=0, editable=False)),
                ('adottato_il', models.DateField(blank=True, editable=False, null=True)),
                ('protocollo', models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='protocollo.protocollo', verbose_name="protocollo dell'ultima adozione")),
                ('responsabile', models.ForeignKey(blank=True, limit_choices_to={'tipo': 'persona'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='anagrafica.soggetto', verbose_name='responsabile della gestione documentale')),
                ('responsabile_conservazione', models.ForeignKey(blank=True, limit_choices_to={'tipo': 'persona'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='anagrafica.soggetto', verbose_name='responsabile della conservazione')),
                ('vicario', models.ForeignKey(blank=True, limit_choices_to={'tipo': 'persona'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='anagrafica.soggetto', verbose_name='vicario del responsabile')),
            ],
            options={
                'verbose_name': 'manuale di gestione',
                'verbose_name_plural': 'manuale di gestione',
                'permissions': [('gestisci_manuale', 'Può preparare e adottare il manuale di gestione documentale')],
            },
        ),
    ]
