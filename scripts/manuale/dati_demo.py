# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Dati di fantasia per le schermate del manuale. Da eseguire SOLO su un database
# *              vuoto creato apposta (si rifiuta altrimenti):
# *              DATABASE_URL=.../gestione_demo uv run python manage.py shell < scripts/manuale/dati_demo.py
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
# ruff: noqa: E501, T201, S106, S311, E402  (dati di prova, password nota del solo utente dimostrativo)

import random
import sys
from datetime import date, time, timedelta
from decimal import Decimal
from email.message import EmailMessage

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.base import ContentFile
from django.utils import timezone
from weasyprint import HTML

from apps.anagrafica.models import Categoria, Soggetto
from apps.calendario.models import Appuntamento
from apps.comunicazioni import servizi as comunicazioni
from apps.core.models import DocumentoPubblico, Organizzazione
from apps.organi import servizi as organi
from apps.organi.forms import RiunioneForm
from apps.organi.models import Organo, Riunione
from apps.protocollo import posta
from apps.protocollo import servizi as protocollo
from apps.protocollo.models import CasellaPosta
from apps.soci import servizi as soci
from apps.soci.models import Sezione, TipologiaSocio
from apps.tesoreria import servizi as tesoreria

if Soggetto.objects.exists() or get_user_model().objects.exists():
    print("RIFIUTATO: il database contiene già dati. Usare un database vuoto creato apposta.")
    sys.exit(1)

random.seed(7)
OGGI = timezone.localdate()
ANNO = OGGI.year
U = get_user_model()

# --- ente e utenti ---------------------------------------------------------------------------
org = Organizzazione.corrente()
org.denominazione = "Associazione di Esempio - Federazione Provinciale"
org.denominazione_breve = "Associazione di Esempio"
org.indirizzo, org.cap, org.comune, org.provincia = (
    "Piazza della Libertà 1",
    "85100",
    "Montebello",
    "PZ",
)
org.email, org.telefono = "segreteria@esempio.invalid", "0971 000000"
org.configurata = True
org.save()


def persona(cognome, nome, sesso="M", **extra):
    return Soggetto.objects.create(tipo="persona", cognome=cognome, nome=nome, sesso=sesso, **extra)


admin_scheda = persona(
    "Bianchi", "Laura", "F", email="laura.bianchi@esempio.invalid", titolo="Dott.ssa"
)
admin = U.objects.create_user(
    "demo",
    email="demo@esempio.invalid",
    password="Demo-Manuale-2026",
    first_name="Laura",
    last_name="Bianchi",
    soggetto=admin_scheda,
)
admin.groups.add(Group.objects.get(name="Amministratore di sistema"))

# --- sezioni, tipologie, soci ----------------------------------------------------------------
monte = Sezione.objects.filter(attiva=True).first() or Sezione.objects.create(
    codice="001", nome="Montebello"
)
monte.nome, monte.codice, monte.comune, monte.provincia = "Montebello", "001", "Montebello", "PZ"
monte.save()
valle = Sezione.objects.create(codice="002", nome="Valleverde", comune="Valleverde", provincia="PZ")
ordinario = TipologiaSocio.objects.get(nome="Ordinario")
ordinario.quota_annua = Decimal("25")
ordinario.save()

NOMI = [
    ("Rossi", "Mario", "M"),
    ("Verdi", "Giuseppe", "M"),
    ("Russo", "Anna", "F"),
    ("Esposito", "Luigi", "M"),
    ("Romano", "Teresa", "F"),
    ("Colombo", "Martino", "M"),
    ("Ricci", "Maria", "F"),
    ("Marino", "Antonio", "M"),
    ("Gallo", "Pietro", "M"),
    ("Greco", "Lucia", "F"),
    ("Bruno", "Franco", "M"),
    ("Conti", "Elena", "F"),
    ("De Luca", "Paolo", "M"),
    ("Costa", "Giovanna", "F"),
    ("Fontana", "Carlo", "M"),
    ("Moretti", "Rita", "F"),
    ("Barbieri", "Enzo", "M"),
    ("Lombardi", "Silvia", "F"),
    ("Giordano", "Aldo", "M"),
    ("Rinaldi", "Paola", "F"),
]
tutti = []
for i, (cognome, nome, sesso) in enumerate(NOMI):
    s = persona(
        cognome,
        nome,
        sesso,
        email=f"{cognome.lower().replace(' ', '')}.{nome.lower()}@esempio.invalid",
        cellulare=f"333 {1000000 + i * 137:07d}",
        comune=random.choice(["Montebello", "Valleverde"]),
        provincia="PZ",
        data_nascita=date(1940 + i * 2, (i % 12) + 1, (i % 27) + 1),
        indirizzo=f"Via Roma {i + 1}",
        cap="85100",
    )
    tutti.append(s)

try:
    tesoreria.apri_esercizio(ANNO, admin)
except Exception as e:  # noqa: BLE001
    print("esercizio:", e)

soci_creati = []
for i, s in enumerate(tutti):
    socio = soci.ammetti_socio(
        s,
        ordinario,
        admin,
        data_ammissione=date(2005 + i % 18, 3, 1),
        sezione=monte if i % 3 else valle,
        delibera="Consiglio direttivo",
    )
    soci_creati.append(socio)
    try:
        if i % 4:  # tre su quattro pagati, gli altri da incassare
            soci.rilascia_tessera(
                socio, ANNO, admin, pagata_il=OGGI - timedelta(days=i * 3), metodo="contanti"
            )
        elif i % 8 == 0:
            soci.rilascia_tessera(socio, ANNO, admin)
    except Exception as e:  # noqa: BLE001
        print("tessera", s, e)

enti = [
    Soggetto.objects.create(
        tipo="ente", denominazione=d, email=f"info@{k}.invalid", comune="Montebello", provincia="PZ"
    )
    for d, k in (
        ("Comune di Montebello", "comune-montebello"),
        ("Prefettura di Esempio", "prefettura"),
        ("Istituto Comprensivo Montebello", "scuola-montebello"),
    )
]
autorita = Categoria.objects.get_or_create(nome="Autorità")[0]
for e in enti[:2]:
    e.categorie.add(autorita)

# --- organi e cariche ------------------------------------------------------------------------
cd = Organo.objects.filter(sezione__isnull=True, tipo="consiglio").first()
for s, ruolo in zip(
    tutti[:7],
    [
        "presidente",
        "vicepresidente",
        "segretario",
        "tesoriere",
        "consigliere",
        "consigliere",
        "consigliere",
    ],
    strict=True,
):
    organi.nomina(
        cd, s, ruolo, date(ANNO - 1, 4, 20), admin, atto=f"Assemblea del 20/04/{ANNO - 1}"
    )
for organo_sez in organi.crea_organi_sezione(monte, admin):
    if organo_sez.tipo == "consiglio":
        for s, ruolo in zip(
            tutti[7:11], ["presidente", "segretario", "consigliere", "consigliere"], strict=True
        ):
            organi.nomina(organo_sez, s, ruolo, date(ANNO - 1, 5, 10), admin)
organi.nomina(
    Organo.objects.get(sezione=monte, tipo="consiglio"),
    tutti[0],
    "consigliere",
    date(ANNO - 1, 5, 10),
    admin,
)


def riunione(giorni, punti, convoca=True):
    quando = timezone.localtime() + timedelta(days=giorni)
    dati = {
        "organo": cd.pk,
        "prima_convocazione": quando.strftime("%Y-%m-%dT18:00"),
        "luogo": "Sede sociale, Piazza della Libertà 1",
        "seconda_convocazione": (quando + timedelta(days=1)).strftime("%Y-%m-%dT18:00"),
        "modalita": "presenza",
        "punti": "\n".join(punti),
    }
    form = RiunioneForm(dati, instance=Riunione())
    assert form.is_valid(), form.errors
    r = organi.salva_riunione(form, form.titoli_punti(), admin)
    if convoca:
        organi.convoca(r, admin)
    return r


riunione(
    9,
    [
        "Approvazione del verbale della seduta precedente",
        "Programma della cerimonia del 4 Novembre",
        "Quote sociali " + str(ANNO + 1),
        "Varie ed eventuali",
    ],
)
riunione(30, ["Bilancio preventivo", "Varie ed eventuali"], convoca=False)

# --- protocollo e posta ----------------------------------------------------------------------
for oggetto, direzione, chi in [
    ("Richiesta di patrocinio per la cerimonia del 4 Novembre", "uscita", enti[0]),
    ("Invito alla commemorazione dei caduti", "entrata", enti[1]),
    ("Convocazione del consiglio direttivo", "interno", None),
    ("Richiesta di incontro con le classi terze", "uscita", enti[2]),
]:
    ruolo = "destinatario" if direzione == "uscita" else "mittente"
    corr = (
        [protocollo.corrispondente_da_soggetto(chi, ruolo)]
        if chi
        else [{"ruolo": "mittente", "descrizione": org.denominazione}]
    )
    protocollo.registra_protocollo(
        {"direzione": direzione, "mezzo": "pec" if chi else "mano", "oggetto": oggetto}, corr, admin
    )

casella = CasellaPosta.objects.create(
    nome="Posta della segreteria",
    server="imap.esempio.invalid",
    utente="segreteria@esempio.invalid",
)
for i, (mitt, ogg) in enumerate(
    [
        (
            "Comune di Montebello <protocollo@comune-montebello.invalid>",
            "Calendario delle cerimonie",
        ),
        ("Newsletter <news@offerte.invalid>", "Offerte della settimana"),
        ("posta-certificata@pec.invalid", "ACCETTAZIONE: invio documentazione"),
        ("Paolo De Luca <deluca.paolo@esempio.invalid>", "Richiesta di iscrizione per mio padre"),
    ]
):
    m = EmailMessage()
    m["From"], m["To"], m["Subject"] = mitt, "segreteria@esempio.invalid", ogg
    m["Date"] = (timezone.now() - timedelta(hours=i * 5)).strftime("%a, %d %b %Y %H:%M:%S +0100")
    m["Message-ID"] = f"<demo-{i}@esempio.invalid>"
    m.set_content("Buongiorno,\nvi scrivo in merito all'oggetto.\nCordiali saluti.")
    posta.salva_messaggio(casella, m.as_bytes())

# --- calendario, comunicazioni, documenti pubblici -------------------------------------------
Appuntamento.objects.create(
    titolo="Deposizione della corona al monumento",
    tipo="cerimonia",
    giorno=OGGI + timedelta(days=5),
    ora=time(10, 30),
    luogo="Piazza dei Caduti",
)
Appuntamento.objects.create(
    titolo="Invio del rendiconto", tipo="scadenza", giorno=OGGI - timedelta(days=2)
)
Appuntamento.objects.create(
    titolo="Rinnovo dell'assicurazione della sede",
    tipo="scadenza",
    giorno=OGGI + timedelta(days=12),
)
Appuntamento.objects.create(
    titolo="Incontro con le scuole",
    tipo="evento",
    giorno=OGGI + timedelta(days=16),
    fine_giorno=OGGI + timedelta(days=17),
    luogo="Istituto Comprensivo",
)
comunicazioni.crea_invio(
    admin,
    oggetto="Cerimonia del 4 Novembre",
    corpo="{{ saluto }} {{ nome }},\n\nti aspettiamo alla cerimonia.",
    finalita="istituzionale",
    soggetti=tutti[:12],
)

for titolo, ordine in (("Statuto sociale", 1), ("Regolamento", 2)):
    pdf = HTML(string=f"<h1>{titolo}</h1><p>Testo di esempio.</p>").write_pdf()
    d = DocumentoPubblico(
        titolo=titolo,
        descrizione="Testo di esempio",
        ordine=ordine,
        nome_file=f"{titolo.lower()}.pdf",
        dimensione=len(pdf),
        creato_da=admin,
        modificato_da=admin,
    )
    d.file.save("documento.pdf", ContentFile(pdf), save=False)
    d.save()

print(
    "Dati dimostrativi pronti:",
    Soggetto.objects.count(),
    "schede,",
    len(soci_creati),
    "soci. Accesso: demo / Demo-Manuale-2026",
)
