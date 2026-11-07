# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Dati iniziali delle comunicazioni: modelli di testo, auguri automatici
# *              (disattivati), ricorrenze nazionali e calendario degli onomastici.
# *              Tutto è modificabile dall'interfaccia.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.db import migrations

MODELLI = [
    ("Comunicazione generica", "generico", "{{ organizzazione }}: comunicazione",
     "{{ saluto }} {{ nome }},\n\n\n\nCordiali saluti\nLa segreteria"),
    ("Convocazione", "convocazione", "Convocazione {{ riunione }}",
     "{{ saluto }} {{ nome }},\n\nsei convocato/a alla riunione {{ riunione }} che si terrà il "
     "{{ data_riunione }} presso {{ luogo_riunione }}, con il seguente ordine del giorno:\n\n"
     "{{ ordine_del_giorno }}\n\nIn allegato la lettera di convocazione.\n\nCordiali saluti\nIl Presidente"),
    ("Ricevuta della quota", "ricevuta", "Ricevuta della quota associativa {{ anno_quota }}",
     "{{ saluto }} {{ nome }},\n\nti ringraziamo per il versamento della quota associativa "
     "{{ anno_quota }} di {{ importo }} euro. In allegato la ricevuta n. {{ ricevuta }}.\n\n"
     "Cordiali saluti\nIl Tesoriere"),
    ("Esito della domanda di iscrizione", "domanda", "La tua domanda di iscrizione",
     "{{ saluto }} {{ nome }},\n\nti comunichiamo che la tua domanda di iscrizione a {{ organizzazione }} "
     "è stata {{ esito }}.\n\nCordiali saluti\nLa segreteria"),
    ("Auguri di compleanno", "compleanno", "Buon compleanno, {{ nome }}!",
     "{{ saluto }} {{ nome }},\n\ntutta {{ organizzazione }} ti augura un felice compleanno!\n\n"
     "Con affetto\nIl Presidente e il Consiglio direttivo"),
    ("Auguri di onomastico", "onomastico", "Buon onomastico, {{ nome }}!",
     "{{ saluto }} {{ nome }},\n\nnel giorno del tuo onomastico ti giungano i più sinceri auguri da "
     "tutta {{ organizzazione }}.\n\nIl Presidente e il Consiglio direttivo"),
    ("Anniversario di iscrizione", "anzianita", "{{ anni }} anni insieme a {{ organizzazione }}",
     "{{ saluto }} {{ nome }},\n\noggi ricorrono {{ anni }} anni dalla tua iscrizione alla nostra "
     "associazione (socio n. {{ numero_socio }}). Grazie per la fedeltà e l'impegno di tutti questi "
     "anni.\n\nIl Presidente e il Consiglio direttivo"),
    ("Ricorrenza", "ricorrenza", "{{ ricorrenza }}",
     "{{ saluto }} {{ nome }},\n\nin occasione della ricorrenza «{{ ricorrenza }}» {{ organizzazione }} "
     "rinnova a tutti i soci il ricordo e l'impegno.\n\nIl Presidente"),
]  # fmt: skip

RICORRENZE = [
    ("Giorno della Memoria", 27, 1, 1945),
    ("Giorno del Ricordo", 10, 2, 1947),
    ("Festa della Liberazione", 25, 4, 1945),
    ("Anniversario dell'entrata dell'Italia nella Grande Guerra", 24, 5, 1915),
    ("Festa della Repubblica", 2, 6, 1946),
    ("Commemorazione dei defunti", 2, 11, None),
    ("Giorno dell'Unità Nazionale e Giornata delle Forze Armate", 4, 11, 1918),
    ("Giornata del ricordo dei Caduti nelle missioni internazionali", 12, 11, 2003),
]

# nome normalizzato, giorno, mese, santo (data più diffusa nei calendari italiani)
ONOMASTICI = [
    ("addolorata", 15, 9, "Beata Vergine Maria Addolorata"), ("agnese", 21, 1, "Sant'Agnese"),
    ("agostino", 28, 8, "Sant'Agostino"), ("alberto", 15, 11, "Sant'Alberto Magno"),
    ("alessandro", 26, 8, "Sant'Alessandro"), ("andrea", 30, 11, "Sant'Andrea apostolo"),
    ("angela", 27, 1, "Sant'Angela Merici"), ("angelo", 5, 5, "Sant'Angelo martire"),
    ("anna", 26, 7, "Sant'Anna"), ("annunziata", 25, 3, "Annunciazione del Signore"),
    ("antonio", 13, 6, "Sant'Antonio di Padova"), ("assunta", 15, 8, "Assunzione di Maria"),
    ("barbara", 4, 12, "Santa Barbara"), ("bartolomeo", 24, 8, "San Bartolomeo apostolo"),
    ("beatrice", 29, 7, "Santa Beatrice"), ("benedetto", 11, 7, "San Benedetto da Norcia"),
    ("bernardo", 20, 8, "San Bernardo di Chiaravalle"), ("biagio", 3, 2, "San Biagio"),
    ("bruno", 6, 10, "San Bruno"), ("camillo", 14, 7, "San Camillo de Lellis"),
    ("carla", 4, 11, "San Carlo Borromeo"), ("carlo", 4, 11, "San Carlo Borromeo"),
    ("carmela", 16, 7, "Beata Vergine del Carmelo"), ("carmine", 16, 7, "Beata Vergine del Carmelo"),
    ("caterina", 29, 4, "Santa Caterina da Siena"), ("cecilia", 22, 11, "Santa Cecilia"),
    ("chiara", 11, 8, "Santa Chiara d'Assisi"), ("concetta", 8, 12, "Immacolata Concezione"),
    ("cosimo", 26, 9, "Santi Cosma e Damiano"), ("cristina", 24, 7, "Santa Cristina"),
    ("cristoforo", 25, 7, "San Cristoforo"), ("damiano", 26, 9, "Santi Cosma e Damiano"),
    ("daniele", 21, 7, "San Daniele profeta"), ("davide", 29, 12, "San Davide re"),
    ("domenico", 8, 8, "San Domenico di Guzmán"), ("donato", 7, 8, "San Donato"),
    ("edoardo", 13, 10, "Sant'Edoardo"), ("elena", 18, 8, "Sant'Elena"),
    ("elia", 20, 7, "Sant'Elia profeta"), ("elisabetta", 17, 11, "Santa Elisabetta d'Ungheria"),
    ("enrico", 13, 7, "Sant'Enrico"), ("fabio", 31, 7, "San Fabio"),
    ("federico", 18, 7, "San Federico"), ("ferdinando", 30, 5, "San Ferdinando"),
    ("filippo", 26, 5, "San Filippo Neri"), ("francesca", 9, 3, "Santa Francesca Romana"),
    ("francesco", 4, 10, "San Francesco d'Assisi"), ("franco", 4, 10, "San Francesco d'Assisi"),
    ("gabriele", 29, 9, "San Gabriele arcangelo"), ("gaetano", 7, 8, "San Gaetano"),
    ("gennaro", 19, 9, "San Gennaro"), ("gerardo", 16, 10, "San Gerardo Maiella"),
    ("giacinto", 17, 8, "San Giacinto"), ("giacomo", 25, 7, "San Giacomo apostolo"),
    ("gianni", 24, 6, "Natività di San Giovanni Battista"), ("giorgio", 23, 4, "San Giorgio"),
    ("giovanna", 30, 5, "Santa Giovanna d'Arco"), ("giovanni", 24, 6, "Natività di San Giovanni Battista"),
    ("giulia", 22, 5, "Santa Giulia"), ("giuseppe", 19, 3, "San Giuseppe"),
    ("giuseppina", 19, 3, "San Giuseppe"), ("gregorio", 3, 9, "San Gregorio Magno"),
    ("ignazio", 31, 7, "Sant'Ignazio di Loyola"), ("immacolata", 8, 12, "Immacolata Concezione"),
    ("leonardo", 6, 11, "San Leonardo"), ("lino", 23, 9, "San Lino papa"),
    ("lorenzo", 10, 8, "San Lorenzo"), ("luca", 18, 10, "San Luca evangelista"),
    ("lucia", 13, 12, "Santa Lucia"), ("luigi", 21, 6, "San Luigi Gonzaga"),
    ("luisa", 15, 3, "Santa Luisa de Marillac"), ("marco", 25, 4, "San Marco evangelista"),
    ("maria", 12, 9, "Santissimo Nome di Maria"), ("mario", 19, 1, "San Mario"),
    ("marta", 29, 7, "Santa Marta"), ("martino", 11, 11, "San Martino di Tours"),
    ("matteo", 21, 9, "San Matteo apostolo"), ("mauro", 15, 1, "San Mauro"),
    ("michele", 29, 9, "San Michele arcangelo"), ("monica", 27, 8, "Santa Monica"),
    ("nicola", 6, 12, "San Nicola di Bari"), ("nicolo", 6, 12, "San Nicola di Bari"),
    ("nunzia", 25, 3, "Annunciazione del Signore"), ("nunzio", 25, 3, "Annunciazione del Signore"),
    ("paola", 26, 1, "Santa Paola"), ("paolo", 29, 6, "Santi Pietro e Paolo"),
    ("pasquale", 17, 5, "San Pasquale Baylon"), ("pietro", 29, 6, "Santi Pietro e Paolo"),
    ("pio", 23, 9, "San Pio da Pietrelcina"), ("raffaele", 29, 9, "San Raffaele arcangelo"),
    ("rita", 22, 5, "Santa Rita da Cascia"), ("rocco", 16, 8, "San Rocco"),
    ("rosa", 23, 8, "Santa Rosa da Lima"), ("rosalia", 4, 9, "Santa Rosalia"),
    ("rosaria", 7, 10, "Beata Vergine del Rosario"), ("rosario", 7, 10, "Beata Vergine del Rosario"),
    ("sebastiano", 20, 1, "San Sebastiano"), ("silvia", 3, 11, "Santa Silvia"),
    ("simone", 28, 10, "Santi Simone e Giuda"), ("stefano", 26, 12, "Santo Stefano"),
    ("teresa", 15, 10, "Santa Teresa d'Avila"), ("tommaso", 3, 7, "San Tommaso apostolo"),
    ("valentino", 14, 2, "San Valentino"), ("vincenzo", 22, 1, "San Vincenzo diacono"),
    ("vito", 15, 6, "San Vito"),
]  # fmt: skip


def crea(apps, schema_editor):
    Modello = apps.get_model("comunicazioni", "Modello")
    Automazione = apps.get_model("comunicazioni", "Automazione")
    Ricorrenza = apps.get_model("comunicazioni", "Ricorrenza")
    Onomastico = apps.get_model("comunicazioni", "Onomastico")
    for nome, uso, oggetto, corpo in MODELLI:
        Modello.objects.get_or_create(nome=nome, defaults={"uso": uso, "oggetto": oggetto, "corpo": corpo})
    for tipo in ("compleanno", "onomastico", "anzianita"):
        Automazione.objects.get_or_create(tipo=tipo)
    for nome, giorno, mese, anno in RICORRENZE:
        Ricorrenza.objects.get_or_create(
            nome=nome, defaults={"giorno": giorno, "mese": mese, "anno_inizio": anno}
        )
    for nome, giorno, mese, santo in ONOMASTICI:
        Onomastico.objects.get_or_create(nome=nome, defaults={"giorno": giorno, "mese": mese, "santo": santo})


class Migration(migrations.Migration):
    dependencies = [("comunicazioni", "0001_initial")]
    operations = [migrations.RunPython(crea, migrations.RunPython.noop)]
