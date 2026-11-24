# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Profili elettorali preimpostati: congresso sezionale e provinciale ANCR,
# *              assemblea elettiva generica (ETS).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.db import migrations


def crea(apps, schema_editor):
    from apps.elezioni.servizi import PROFILI

    Profilo = apps.get_model("elezioni", "ProfiloElettorale")
    for dati in PROFILI:
        Profilo.objects.get_or_create(nome=dati["nome"], defaults=dati)


class Migration(migrations.Migration):
    dependencies = [("elezioni", "0001_initial")]

    operations = [migrations.RunPython(crea, migrations.RunPython.noop)]
