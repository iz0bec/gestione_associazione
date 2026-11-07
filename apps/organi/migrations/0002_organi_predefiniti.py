# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Organi predefiniti (regole da adattare allo statuto)
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.db import migrations

# nome, sigla, tipo, quorum prima, quorum seconda, deleghe, ordine
ORGANI = [
    ("Assemblea dei soci", "ASS", "assemblea", 50, 0, 3, 1),
    ("Consiglio direttivo", "CD", "consiglio", 50, 50, 0, 2),
    ("Collegio dei revisori", "REV", "controllo", 50, 50, 0, 3),
]


def crea(apps, schema_editor):
    Organo = apps.get_model("organi", "Organo")
    for nome, sigla, tipo, prima, seconda, deleghe, ordine in ORGANI:
        Organo.objects.get_or_create(
            nome=nome,
            defaults={
                "sigla": sigla, "tipo": tipo, "quorum_prima": prima, "quorum_seconda": seconda,
                "max_deleghe": deleghe, "ordine": ordine,
            },
        )  # fmt: skip


class Migration(migrations.Migration):
    dependencies = [("organi", "0001_initial")]
    operations = [migrations.RunPython(crea, migrations.RunPython.noop)]
