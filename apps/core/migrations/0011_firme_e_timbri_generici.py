# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Firma e timbro generici nelle stampe (interruttori dell'organizzazione).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_conservazione'),
    ]

    operations = [
        migrations.AddField(
            model_name='organizzazione',
            name='firma_generica',
            field=models.BooleanField(default=True, help_text="Se manca l'immagine della firma, il nome di chi firma in corsivo sopra la riga.", verbose_name='firma generica'),
        ),
        migrations.AddField(
            model_name='organizzazione',
            name='timbro_generico',
            field=models.BooleanField(default=True, help_text="Se manca l'immagine del timbro, un timbro tondo con la denominazione dell'ente.", verbose_name='timbro generico'),
        ),
    ]
