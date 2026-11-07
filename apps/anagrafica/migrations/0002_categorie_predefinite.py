# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Categorie predefinite dell'anagrafica (dalle rubriche dei progetti di origine)
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.db import migrations

CATEGORIE = [
    ("Socio", "Iscritto all'associazione", "primary"),
    ("Autorità", "Rappresentanti istituzionali, civili, militari e religiosi", "red"),
    ("Amico della sezione", "Sostenitori e simpatizzanti", "green"),
    ("Altra associazione", "Associazioni e organizzazioni partner", "purple"),
    ("Sezione consorella", "Altre sezioni della stessa associazione", "cyan"),
    ("Ente pubblico", "Comuni, prefetture, scuole e altri enti", "orange"),
    ("Fornitore", "Fornitori di beni e servizi", "yellow"),
]


def crea(apps, schema_editor):
    Categoria = apps.get_model("anagrafica", "Categoria")
    for nome, descrizione, colore in CATEGORIE:
        Categoria.objects.get_or_create(
            nome=nome, defaults={"descrizione": descrizione, "colore": colore}
        )


class Migration(migrations.Migration):
    dependencies = [("anagrafica", "0001_initial")]
    operations = [migrations.RunPython(crea, migrations.RunPython.noop)]
