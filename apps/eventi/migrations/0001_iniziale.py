# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Eventi e adesioni.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
import apps.eventi.models
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
            name='Evento',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('creato_il', models.DateTimeField(auto_now_add=True, verbose_name='creato il')),
                ('modificato_il', models.DateTimeField(auto_now=True, verbose_name='modificato il')),
                ('titolo', models.CharField(max_length=200)),
                ('tipo', models.CharField(choices=[('cerimonia', 'Cerimonia o commemorazione'), ('incontro', 'Incontro o conferenza'), ('gita', 'Gita o viaggio'), ('conviviale', 'Pranzo o cena'), ('altro', 'Altro')], default='cerimonia', max_length=12)),
                ('inizio', models.DateTimeField()),
                ('fine', models.DateTimeField(blank=True, null=True)),
                ('luogo', models.CharField(blank=True, max_length=200)),
                ('descrizione', models.TextField(blank=True, help_text='Programma, appuntamento, indicazioni.')),
                ('quota', models.CharField(blank=True, help_text='Solo indicativa (es. «25 € a persona»); gli incassi si registrano in Tesoreria.', max_length=100, verbose_name='quota di partecipazione')),
                ('posti', models.PositiveIntegerField(blank=True, help_text='Vuoto: senza limite.', null=True, verbose_name='posti disponibili')),
                ('accompagnatori', models.PositiveSmallIntegerField(default=0, help_text='Quanti accompagnatori può indicare.', verbose_name='accompagnatori per adesione')),
                ('adesioni_aperte', models.BooleanField(default=True)),
                ('chiusura_adesioni', models.DateTimeField(blank=True, help_text="Vuoto: fino all'inizio.", null=True, verbose_name='adesioni fino al')),
                ('pubblico', models.BooleanField(default=False, help_text='Chiunque abbia il collegamento può aderire (anche i non soci).', verbose_name='modulo pubblico di adesione')),
                ('token', models.CharField(default=apps.eventi.models._token, editable=False, max_length=32, unique=True)),
                ('annullato', models.BooleanField(default=False)),
                ('creato_da', models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='creato da')),
                ('modificato_da', models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='modificato da')),
            ],
            options={
                'verbose_name': 'evento',
                'verbose_name_plural': 'eventi',
                'ordering': ['-inizio'],
            },
        ),
        migrations.CreateModel(
            name='Adesione',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cognome', models.CharField(max_length=100)),
                ('nome', models.CharField(blank=True, max_length=100)),
                ('email', models.EmailField(blank=True, max_length=254)),
                ('telefono', models.CharField(blank=True, max_length=30)),
                ('accompagnatori', models.PositiveSmallIntegerField(default=0)),
                ('note', models.CharField(blank=True, max_length=255)),
                ('origine', models.CharField(choices=[('segreteria', 'Segreteria'), ('pubblico', 'Modulo pubblico'), ('area', 'Area del socio')], max_length=10)),
                ('annullata', models.BooleanField(default=False)),
                ('creata_il', models.DateTimeField(auto_now_add=True)),
                ('indirizzo_ip', models.GenericIPAddressField(blank=True, editable=False, null=True)),
                ('soggetto', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='adesioni', to='anagrafica.soggetto')),
                ('evento', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='adesioni', to='eventi.evento')),
            ],
            options={
                'verbose_name': 'adesione',
                'verbose_name_plural': 'adesioni',
                'ordering': ['cognome', 'nome'],
                'constraints': [models.UniqueConstraint(condition=models.Q(('annullata', False), ('soggetto__isnull', False)), fields=('evento', 'soggetto'), name='una_adesione_per_persona')],
            },
        ),
    ]
