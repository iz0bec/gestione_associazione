# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Criteri iniziali di valutazione delle idee (modificabili)
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.db import migrations

CRITERI = [
    ("Coerenza con le finalità", "Quanto risponde agli scopi statutari dell'associazione"),
    ("Fattibilità", "Si può realizzare con le capacità e i mezzi dell'associazione"),
    ("Urgenza", "Quanto è sentito e urgente il bisogno a cui risponde"),
    ("Risorse e persone", "Disponibilità di volontari, partner e fondi per realizzarla"),
]


def crea(apps, schema_editor):
    Criterio = apps.get_model("progetti", "CriterioValutazione")
    for i, (nome, descrizione) in enumerate(CRITERI, 1):
        Criterio.objects.get_or_create(nome=nome, defaults={"descrizione": descrizione,
                                                            "ordine": i})


class Migration(migrations.Migration):
    dependencies = [("progetti", "0001_iniziale")]
    operations = [migrations.RunPython(crea, migrations.RunPython.noop)]
