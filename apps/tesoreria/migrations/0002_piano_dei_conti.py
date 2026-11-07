# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Voci del rendiconto per cassa degli ETS (Modello D, D.M. 5 marzo 2020)
# *              e conti di partenza (Cassa e Banca).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.db import migrations

GESTIONE_USCITE = [
    "Materie prime, sussidiarie, di consumo e di merci", "Servizi", "Godimento beni di terzi",
    "Personale", "Uscite diverse di gestione",
]  # fmt: skip

VOCI = {
    ("uscita", "A"): GESTIONE_USCITE,
    ("entrata", "A"): [
        "Entrate da quote associative e apporti dei fondatori",
        "Entrate dagli associati per attività mutuali",
        "Entrate per prestazioni e cessioni ad associati e fondatori",
        "Erogazioni liberali", "Entrate del 5 per mille", "Contributi da soggetti privati",
        "Entrate per prestazioni e cessioni a terzi", "Contributi da enti pubblici",
        "Entrate da contratti con enti pubblici", "Altre entrate",
    ],
    ("uscita", "B"): GESTIONE_USCITE,
    ("entrata", "B"): [
        "Entrate per prestazioni e cessioni ad associati e fondatori",
        "Contributi da soggetti privati", "Entrate per prestazioni e cessioni a terzi",
        "Contributi da enti pubblici", "Entrate da contratti con enti pubblici", "Altre entrate",
    ],
    ("uscita", "C"): [
        "Uscite per raccolte fondi abituali", "Uscite per raccolte fondi occasionali", "Altre uscite",
    ],
    ("entrata", "C"): [
        "Entrate da raccolte fondi abituali", "Entrate da raccolte fondi occasionali", "Altre entrate",
    ],
    ("uscita", "D"): [
        "Su rapporti bancari", "Su investimenti finanziari", "Su patrimonio edilizio",
        "Su altri beni patrimoniali", "Altre uscite",
    ],
    ("entrata", "D"): [
        "Da rapporti bancari", "Da altri investimenti finanziari", "Da patrimonio edilizio",
        "Da altri beni patrimoniali", "Altre entrate",
    ],
    ("uscita", "E"): [
        "Materie prime, sussidiarie, di consumo e di merci", "Servizi",
        "Godimento beni di terzi", "Personale", "Altre uscite",
    ],
    ("entrata", "E"): ["Entrate da distacco del personale", "Altre entrate di supporto generale"],
    ("uscita", "INV"): [
        "Investimenti in immobilizzazioni inerenti alle attività di interesse generale",
        "Investimenti in immobilizzazioni inerenti alle attività diverse",
        "Investimenti in attività finanziarie e patrimoniali",
        "Rimborso di finanziamenti per quota capitale e di prestiti",
    ],
    ("entrata", "INV"): [
        "Disinvestimenti di immobilizzazioni inerenti alle attività di interesse generale",
        "Disinvestimenti di immobilizzazioni inerenti alle attività diverse",
        "Disinvestimenti di attività finanziarie e patrimoniali",
        "Ricevimento di finanziamenti e di prestiti",
    ],
    ("uscita", "IMP"): ["Imposte"],
}  # fmt: skip

# sottovoci di dettaglio proposte per una sezione combattentistica (modificabili)
SOTTOVOCI = [
    ("U.A.2", "Corone, onoranze e cerimonie"),
    ("U.A.1", "Tessere e bollini della sede centrale"),
    ("U.E.2", "Spese postali e telefoniche"),
    ("U.E.1", "Cancelleria e materiale d'ufficio"),
    ("U.D.1", "Spese e commissioni bancarie"),
    ("E.A.4", "Offerte e donazioni"),
]


def crea(apps, schema_editor):
    Voce = apps.get_model("tesoreria", "Voce")
    Conto = apps.get_model("tesoreria", "Conto")
    for (tipo, sezione), descrizioni in VOCI.items():
        for numero, descrizione in enumerate(descrizioni, start=1):
            codice = f"{'E' if tipo == 'entrata' else 'U'}.{sezione}.{numero}"
            Voce.objects.get_or_create(
                codice=codice,
                defaults={"tipo": tipo, "sezione": sezione, "numero": numero, "descrizione": descrizione},
            )
    for i, (codice_padre, descrizione) in enumerate(SOTTOVOCI, start=1):
        padre = Voce.objects.get(codice=codice_padre)
        Voce.objects.get_or_create(
            codice=f"{codice_padre}.{i}",
            defaults={"tipo": padre.tipo, "sezione": padre.sezione, "numero": padre.numero,
                      "descrizione": descrizione, "padre": padre},
        )  # fmt: skip
    if not Conto.objects.exists():
        Conto.objects.create(nome="Cassa", tipo="cassa", per_contanti=True, ordine=1)
        Conto.objects.create(nome="Banca", tipo="banca", per_pagamenti_elettronici=True, ordine=2)


class Migration(migrations.Migration):
    dependencies = [("tesoreria", "0001_initial")]
    operations = [migrations.RunPython(crea, migrations.RunPython.noop)]
