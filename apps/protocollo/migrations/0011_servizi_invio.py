# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Spedizione dai servizi di invio di Sistema → Servizi di posta: le caselle
# *              «anche invio» diventano servizi (stesse credenziali), le caselle solo lettura.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
import django.db.models.deletion
from django.db import migrations, models


def caselle_in_servizi(apps, schema_editor):
    caselle = apps.get_model("protocollo", "CasellaPosta")
    spedizioni = apps.get_model("protocollo", "Spedizione")
    servizi = apps.get_model("core", "ServizioInvio")
    for c in caselle.objects.filter(invio=True).exclude(smtp_server=""):
        indirizzo = c.indirizzo or (c.utente if "@" in c.utente else "")
        if not indirizzo:
            continue
        tipo = "pec" if c.pec else "email"
        # stesso indirizzo del server generale (dal .env) o di un'altra casella: niente doppioni
        servizio = servizi.objects.filter(tipo=tipo, indirizzo__iexact=indirizzo).first()
        servizio = servizio or servizi.objects.create(
            nome=c.nome,
            tipo=tipo,
            indirizzo=indirizzo,
            server=c.smtp_server,
            porta=c.smtp_porta or 465,
            ssl=c.smtp_ssl,
            utente="" if c.utente == indirizzo else c.utente,
            password_cifrata=c.password_cifrata,
        )
        spedizioni.objects.filter(casella=c).update(servizio=servizio)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0012_servizi_invio"),
        ("protocollo", "0010_cartella_processata"),
    ]

    operations = [
        migrations.AddField(
            model_name="spedizione",
            name="servizio",
            field=models.ForeignKey(
                blank=True,
                help_text="Server di invio (Sistema → Servizi di posta). Vuoto: server generale.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="spedizioni",
                to="core.servizioinvio",
            ),
        ),
        migrations.RunPython(caselle_in_servizi, migrations.RunPython.noop),
        migrations.RemoveField(model_name="spedizione", name="casella"),
        migrations.RemoveField(model_name="casellaposta", name="indirizzo"),
        migrations.RemoveField(model_name="casellaposta", name="invio"),
        migrations.RemoveField(model_name="casellaposta", name="smtp_porta"),
        migrations.RemoveField(model_name="casellaposta", name="smtp_server"),
        migrations.RemoveField(model_name="casellaposta", name="smtp_ssl"),
    ]
