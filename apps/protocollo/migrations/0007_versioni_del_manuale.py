# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Storico delle versioni adottate del manuale di gestione (ricostruito dai
# *              protocolli di adozione) e collegamento alla pubblicazione.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
import django.db.models.deletion
from django.conf import settings
import re

from django.db import migrations, models

_OGGETTO = re.compile(r"^Adozione del manuale di gestione documentale \(versione (\d+)\)$")


def versioni_gia_adottate(apps, schema_editor):
    """Ricostruisce lo storico dai protocolli di adozione già registrati."""
    Protocollo = apps.get_model("protocollo", "Protocollo")
    Allegato = apps.get_model("protocollo", "Allegato")
    Versione = apps.get_model("protocollo", "VersioneManuale")
    adozioni = Protocollo.objects.filter(
        oggetto__startswith="Adozione del manuale di gestione documentale", annullato=False
    )
    for p in adozioni.order_by("registrato_il"):
        m = _OGGETTO.match(p.oggetto)
        allegato = Allegato.objects.filter(protocollo=p, principale=True).first()
        if m and allegato:
            Versione.objects.get_or_create(
                versione=int(m[1]),
                defaults={"adottata_il": p.data_documento or p.registrato_il.date(),
                          "atto_adozione": (p.testo or "")[:200], "protocollo": p,
                          "allegato": allegato, "adottata_da": p.creato_da},
            )  # fmt: skip


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_firme_e_timbri_generici'),
        ('protocollo', '0006_manuale_di_gestione'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='manualegestione',
            name='documento_pubblico',
            field=models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='core.documentopubblico'),
        ),
        migrations.CreateModel(
            name='VersioneManuale',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('versione', models.PositiveIntegerField(unique=True)),
                ('adottata_il', models.DateField()),
                ('atto_adozione', models.CharField(blank=True, max_length=200, verbose_name='atto di adozione')),
                ('pubblicata', models.BooleanField(default=False, verbose_name='pubblicata fra i documenti pubblici')),
                ('adottata_da', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('allegato', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to='protocollo.allegato')),
                ('protocollo', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to='protocollo.protocollo')),
            ],
            options={
                'verbose_name': 'versione del manuale di gestione',
                'verbose_name_plural': 'versioni del manuale di gestione',
                'ordering': ['-versione'],
            },
        ),
        migrations.RunPython(versioni_gia_adottate, migrations.RunPython.noop),
    ]
