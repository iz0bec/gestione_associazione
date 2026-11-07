# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Categorie di beni predefinite per una sezione combattentistica (modificabili)
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.db import migrations

CATEGORIE = [
    "Bandiere, labari e gagliardetti", "Cimeli e reperti storici", "Medaglie e decorazioni",
    "Documenti, fotografie e archivio", "Libri e pubblicazioni", "Targhe, lapidi e monumenti",
    "Arredi", "Attrezzature informatiche ed elettroniche", "Altro",
]  # fmt: skip


def crea(apps, schema_editor):
    CategoriaBene = apps.get_model("patrimonio", "CategoriaBene")
    for i, nome in enumerate(CATEGORIE, start=1):
        CategoriaBene.objects.get_or_create(nome=nome, defaults={"ordine": i})


class Migration(migrations.Migration):
    dependencies = [("patrimonio", "0001_initial")]
    operations = [migrations.RunPython(crea, migrations.RunPython.noop)]
