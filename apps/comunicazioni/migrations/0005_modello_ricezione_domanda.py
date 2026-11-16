# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Modello della conferma di ricezione delle domande di iscrizione.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
from django.db import migrations, models

MODELLO = {
    "nome": "Conferma di ricezione della domanda",
    "uso": "ricezione",
    "oggetto": "Abbiamo ricevuto la tua domanda di iscrizione",
    "corpo": (
        "{{ saluto }} {{ nome }},\n\n"
        "ti confermiamo che abbiamo ricevuto la domanda di iscrizione a {{ organizzazione }} "
        "di {{ richiedente }}, registrata con il protocollo n. {{ protocollo }} del "
        "{{ data_protocollo }}.\n\n"
        "La domanda sarà esaminata al più presto e l'esito ti sarà comunicato. Per qualsiasi "
        "chiarimento puoi rispondere a questo messaggio.\n\n"
        "Cordiali saluti\nLa segreteria"
    ),
}


def crea(apps, schema_editor):
    Modello = apps.get_model("comunicazioni", "Modello")
    Modello.objects.get_or_create(nome=MODELLO["nome"], defaults=MODELLO)


class Migration(migrations.Migration):

    dependencies = [
        ('comunicazioni', '0004_modello_tessera'),
    ]

    operations = [
        migrations.AlterField(
            model_name='modello',
            name='uso',
            field=models.CharField(choices=[('generico', 'Comunicazione generica'), ('convocazione', 'Convocazione'), ('ricevuta', 'Ricevuta della quota'), ('domanda', 'Esito della domanda di iscrizione'), ('ricezione', 'Conferma di ricezione della domanda'), ('compleanno', 'Auguri di compleanno'), ('onomastico', 'Auguri di onomastico'), ('anzianita', 'Anniversario di iscrizione'), ('ricorrenza', 'Ricorrenza'), ('rinnovo', 'Promemoria di rinnovo della quota'), ('tessera', 'Tessera digitale')], default='generico', max_length=15),
        ),
        migrations.RunPython(crea, migrations.RunPython.noop),
    ]
