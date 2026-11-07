# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Tipologie di socio predefinite (le quote si impostano dall'interfaccia)
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.db import migrations

TIPOLOGIE = [
    ("Ordinario", "Socio con diritto di voto in assemblea", 1),
    ("Sostenitore", "Socio che contribuisce con una quota maggiorata", 2),
    ("Onorario", "Nominato dall'assemblea per meriti particolari, esente dalla quota", 3),
]


def crea(apps, schema_editor):
    TipologiaSocio = apps.get_model("soci", "TipologiaSocio")
    for nome, descrizione, ordine in TIPOLOGIE:
        TipologiaSocio.objects.get_or_create(
            nome=nome, defaults={"descrizione": descrizione, "ordine": ordine}
        )


class Migration(migrations.Migration):
    dependencies = [("soci", "0001_initial")]
    operations = [migrations.RunPython(crea, migrations.RunPython.noop)]
