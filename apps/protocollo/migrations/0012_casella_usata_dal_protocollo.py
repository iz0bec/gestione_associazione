# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: «attiva» della casella diventa «usata dal protocollo» (solo l'etichetta).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('protocollo', '0011_servizi_invio'),
    ]

    operations = [
        migrations.AlterField(
            model_name='casellaposta',
            name='attiva',
            field=models.BooleanField(default=True, help_text='Si abilita in Protocollo → Caselle: solo le caselle usate vengono lette.', verbose_name='usata dal protocollo'),
        ),
    ]
