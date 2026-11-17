# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Ultima attività dell'utente (utenti connessi).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_avvisi_posta'),
    ]

    operations = [
        migrations.AddField(
            model_name='utente',
            name='ultima_attivita',
            field=models.DateTimeField(blank=True, db_index=True, editable=False, null=True, verbose_name='ultima attività'),
        ),
    ]
