# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Incassi diversi dalle quote (ricevuta numerata) e note di storno.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
import django.core.validators
import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('anagrafica', '0009_sms_whatsapp'),
        ('soci', '0012_domanda_modulo_protocollo'),
        ('tesoreria', '0002_piano_dei_conti'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Incasso',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('creato_il', models.DateTimeField(auto_now_add=True, verbose_name='creato il')),
                ('modificato_il', models.DateTimeField(auto_now=True, verbose_name='modificato il')),
                ('data', models.DateField()),
                ('tipo', models.CharField(choices=[('donazione', 'Donazione o offerta'), ('contributo', 'Contributo'), ('partecipazione', 'Quota di partecipazione (eventi, gite, pranzi)'), ('altro', 'Altro')], max_length=15)),
                ('nominativo', models.CharField(help_text='Come appare sulla ricevuta.', max_length=200)),
                ('codice_fiscale', models.CharField(blank=True, max_length=16, verbose_name='codice fiscale')),
                ('importo', models.DecimalField(decimal_places=2, max_digits=10, validators=[django.core.validators.MinValueValidator(Decimal('0.01'))])),
                ('metodo', models.CharField(choices=[('contanti', 'Contanti'), ('bonifico', 'Bonifico'), ('pos', 'Carta / POS'), ('altro', 'Altro')], max_length=10, verbose_name='metodo di pagamento')),
                ('riferimento', models.CharField(blank=True, help_text='Es. CRO del bonifico.', max_length=100)),
                ('causale', models.CharField(max_length=255)),
                ('ricevuta_anno', models.PositiveIntegerField(editable=False)),
                ('ricevuta_numero', models.PositiveIntegerField(editable=False)),
                ('creato_da', models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='creato da')),
                ('modificato_da', models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='modificato da')),
                ('movimento', models.OneToOneField(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='incasso', to='tesoreria.movimento')),
                ('soggetto', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='incassi', to='anagrafica.soggetto')),
                ('voce', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to='tesoreria.voce')),
            ],
            options={
                'verbose_name': 'incasso',
                'verbose_name_plural': 'incassi',
                'ordering': ['-data', '-ricevuta_numero'],
                'permissions': [('registra_incasso', 'Può registrare incassi ed emettere ricevute')],
            },
        ),
        migrations.CreateModel(
            name='Storno',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('creato_il', models.DateTimeField(auto_now_add=True, verbose_name='creato il')),
                ('modificato_il', models.DateTimeField(auto_now=True, verbose_name='modificato il')),
                ('anno', models.PositiveIntegerField(editable=False)),
                ('numero', models.PositiveIntegerField(editable=False)),
                ('data', models.DateField()),
                ('importo', models.DecimalField(decimal_places=2, max_digits=10)),
                ('motivo', models.CharField(max_length=255)),
                ('rimborso', models.BooleanField(default=False, help_text='Sì: il denaro è stato restituito (uscita in prima nota). No: incasso registrato per errore (il movimento viene annullato).', verbose_name='somma restituita')),
                ('metodo', models.CharField(blank=True, choices=[('contanti', 'Contanti'), ('bonifico', 'Bonifico'), ('pos', 'Carta / POS'), ('altro', 'Altro')], max_length=10, verbose_name='metodo del rimborso')),
                ('creato_da', models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='creato da')),
                ('incasso', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='storni', to='tesoreria.incasso')),
                ('modificato_da', models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='modificato da')),
                ('movimento', models.OneToOneField(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='storno', to='tesoreria.movimento')),
                ('tessera', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='storni', to='soci.tessera')),
            ],
            options={
                'verbose_name': 'nota di storno',
                'verbose_name_plural': 'note di storno',
                'ordering': ['-data', '-numero'],
                'permissions': [('storna', 'Può stornare quote e incassi')],
                'constraints': [models.UniqueConstraint(fields=('anno', 'numero'), name='storno_numero_unico'), models.UniqueConstraint(condition=models.Q(('tessera__isnull', False)), fields=('tessera',), name='uno_storno_per_quota'), models.UniqueConstraint(condition=models.Q(('incasso__isnull', False)), fields=('incasso',), name='uno_storno_per_incasso'), models.CheckConstraint(condition=models.Q(('tessera__isnull', True), ('incasso__isnull', True), _connector='XOR'), name='storno_di_un_solo_documento')],
            },
        ),
    ]
