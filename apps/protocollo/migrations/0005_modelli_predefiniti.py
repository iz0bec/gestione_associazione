# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Modelli di registrazione di base (da adattare), creati solo se non ne esiste
# *              uno con lo stesso nome; la classificazione si cerca per codice del titolario.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.db import migrations

MODELLI = [
    {
        "nome": "Convocazione dell'assemblea dei soci",
        "direzione": "uscita", "mezzo": "posta", "codice": "03",
        "oggetto": "Convocazione dell'assemblea ordinaria dei soci - anno {{ anno }}",
        "testo": (
            "Si trasmette la convocazione dell'assemblea ordinaria dei soci, con l'ordine del "
            "giorno e le modalità di partecipazione e di delega."
        ),
    },
    {
        "nome": "Invito a una cerimonia o manifestazione",
        "direzione": "uscita", "mezzo": "email", "codice": "06",
        "oggetto": "Invito alla cerimonia del ...",
        "testo": (
            "Gentilissimi,\n{{ organizzazione }} ha il piacere di invitarvi alla cerimonia del ... "
            "che si terrà il giorno ... alle ore ... presso ....\nConfidando nella vostra "
            "partecipazione, porgiamo cordiali saluti."
        ),
    },
    {
        "nome": "Richiesta di patrocinio",
        "direzione": "uscita", "mezzo": "pec", "codice": "07",
        "oggetto": "Richiesta di patrocinio per ...",
        "testo": (
            "Con la presente {{ organizzazione }} chiede la concessione del patrocinio per "
            "l'iniziativa «...», che si svolgerà il ... presso .... Si allega il programma."
        ),
    },
    {
        "nome": "Comunicazione della composizione degli organi sociali",
        "direzione": "uscita", "mezzo": "pec", "codice": "03",
        "oggetto": "Comunicazione della composizione degli organi sociali",
        "testo": (
            "Si comunica che l'assemblea dei soci del ... ha eletto gli organi sociali, la cui "
            "composizione è riportata nel documento allegato."
        ),
    },
    {
        "nome": "Trasmissione del rendiconto",
        "direzione": "uscita", "mezzo": "pec", "codice": "04",
        "oggetto": "Trasmissione del rendiconto dell'esercizio {{ anno_precedente }}",
        "testo": (
            "Si trasmette il rendiconto dell'esercizio {{ anno_precedente }}, approvato "
            "dall'assemblea dei soci del ..., con la relazione dell'organo di controllo."
        ),
    },
    {
        "nome": "Richiesta di contributo",
        "direzione": "uscita", "mezzo": "pec", "codice": "04",
        "oggetto": "Richiesta di contributo per ...",
        "testo": (
            "{{ organizzazione }} chiede la concessione di un contributo per ..., come descritto "
            "nella relazione e nel preventivo allegati."
        ),
    },
    {
        "nome": "Domanda di iscrizione ricevuta",
        "direzione": "entrata", "mezzo": "mano", "codice": "02",
        "oggetto": "Domanda di iscrizione di ...",
        "testo": "",
    },
]  # fmt: skip


def crea(apps, schema_editor):
    Modello = apps.get_model("protocollo", "ModelloProtocollo")
    Classificazione = apps.get_model("protocollo", "Classificazione")
    for ordine, m in enumerate(MODELLI, 1):
        dati = dict(m)
        codice = dati.pop("codice")
        dati["classificazione"] = Classificazione.objects.filter(codice=codice).first()
        Modello.objects.get_or_create(nome=dati.pop("nome"), defaults={**dati, "ordine": ordine})


class Migration(migrations.Migration):
    dependencies = [("protocollo", "0004_modelli_di_registrazione")]
    operations = [migrations.RunPython(crea, migrations.RunPython.noop)]
