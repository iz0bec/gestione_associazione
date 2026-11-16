# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Testo del protocollo (corpo di email, PEC, messaggi o trascrizione).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('protocollo', '0002_titolario_predefinito'),
    ]

    operations = [
        migrations.AddField(
            model_name='protocollo',
            name='testo',
            field=models.TextField(blank=True, help_text='Corpo del messaggio (email, PEC, messaggistica) o trascrizione del documento.'),
        ),
    ]
