# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: «Rispondi con»: servizio di invio proposto per le risposte ai messaggi di una
# *              casella, compilato con il servizio dello stesso indirizzo (e tipo).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
import django.db.models.deletion
from django.db import migrations, models


def collega_per_indirizzo(apps, schema_editor):
    caselle = apps.get_model("protocollo", "CasellaPosta")
    servizi = apps.get_model("core", "ServizioInvio")
    for c in caselle.objects.filter(servizio_risposta__isnull=True):
        if "@" not in c.utente:
            continue
        servizio = servizi.objects.filter(
            tipo="pec" if c.pec else "email", indirizzo__iexact=c.utente
        ).first()
        if servizio is not None:
            c.servizio_risposta = servizio
            c.save(update_fields=["servizio_risposta"])


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0012_servizi_invio"),
        ("protocollo", "0012_casella_usata_dal_protocollo"),
    ]

    operations = [
        migrations.AddField(
            model_name="casellaposta",
            name="servizio_risposta",
            field=models.ForeignKey(
                blank=True,
                help_text="Servizio di invio proposto per rispondere ai messaggi arrivati qui. Vuoto: quello con lo stesso indirizzo della casella.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="caselle",
                to="core.servizioinvio",
                verbose_name="rispondi con",
            ),
        ),
        migrations.RunPython(collega_per_indirizzo, migrations.RunPython.noop),
    ]
