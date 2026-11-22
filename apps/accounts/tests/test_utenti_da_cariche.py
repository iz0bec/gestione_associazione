# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test degli utenti «standard» creati dalle cariche degli organi sociali: proposte,
# *              password per carica, utenti attivi, sezioni, bozze con le credenziali.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from datetime import date

import pytest
from django.urls import reverse

from apps.accounts import servizi
from apps.accounts.models import Utente
from apps.anagrafica.models import Soggetto
from apps.comunicazioni.models import Invio
from apps.organi.models import Carica, Organo

pytestmark = pytest.mark.django_db
URL = "/sistema/utenti/dalle-cariche/"


def carica(organo, cognome, ruolo, email="", nome="Mario", al=None):
    s = Soggetto.objects.create(tipo="persona", cognome=cognome, nome=nome, email=email)
    Carica.objects.create(organo=organo, soggetto=s, ruolo=ruolo, dal=date(2025, 1, 1), al=al)
    return s


@pytest.fixture
def organi():
    consiglio = Organo.objects.get(sigla="CD")
    controllo = Organo.objects.filter(tipo="controllo").first() or Organo.objects.create(
        nome="Collegio dei revisori", sigla="CR", tipo="controllo"
    )
    return consiglio, controllo


@pytest.fixture
def admin(client, crea_utente):
    client.force_login(crea_utente("capo", ruoli=["Amministratore di sistema"]))
    return client


def test_proposte(organi, crea_utente):
    consiglio, controllo = organi
    pres = carica(consiglio, "Rossi", "presidente", "rossi@example.org")
    carica(controllo, "Verdi", "componente")
    carica(consiglio, "Cessato", "consigliere", al=date(2025, 6, 1))  # non più in carica
    gia = carica(consiglio, "Bianchi", "segretario")
    crea_utente("bianchi", soggetto=gia)  # ha già un utente
    proposte = {p["soggetto"].cognome: p for p in servizi.proposte_da_cariche()}
    assert set(proposte) == {"Rossi", "Verdi"}
    assert proposte["Rossi"]["categoria"] == "presidente" and proposte["Rossi"]["ruoli"] == [
        "Presidente"
    ]
    assert proposte["Verdi"]["categoria"] == "controllo" and proposte["Verdi"]["ruoli"] == [
        "Revisore"
    ]
    assert proposte["Rossi"]["username"] == "mario.rossi" and pres.pk


def test_creazione_dalla_pagina(admin, organi):
    consiglio, controllo = organi
    carica(consiglio, "Rossi", "presidente", "rossi@example.org")
    carica(consiglio, "Neri", "vicepresidente", "neri@example.org", nome="Anna")
    carica(consiglio, "Gialli", "segretario", "", nome="Luca")  # senza email
    carica(consiglio, "Blu", "consigliere", "blu@example.org")
    carica(controllo, "Verdi", "componente", "verdi@example.org")
    assert "Utenti dalle cariche" in admin.get("/sistema/utenti/").content.decode()
    pagina = admin.get(URL).content.decode()
    assert "mario.rossi" in pagina and "senza email" in pagina
    scelti = [
        s.pk
        for s in Soggetto.objects.filter(cognome__in=["Rossi", "Neri", "Gialli", "Blu", "Verdi"])
    ]
    r = admin.post(URL, {
        "soggetto": scelti, "password_presidente": "Presidenti-Comuni-2027",
        "attiva": ["presidente", "vicepresidente", "segretario"], "bozze": "on",
    })  # fmt: skip
    testo = r.content.decode()
    assert (
        r.status_code == 200
        and "Presidenti-Comuni-2027" in testo
        and r["Cache-Control"] == "no-store"
    )
    rossi = Utente.objects.get(username="mario.rossi")
    assert (
        rossi.is_active and not rossi.deve_cambiare_password and rossi.soggetto.cognome == "Rossi"
    )
    assert rossi.check_password("Presidenti-Comuni-2027")
    assert [g.name for g in Utente.objects.get(username="luca.gialli").groups.all()] == [
        "Segretario",
        "Tesoriere",
    ]
    assert Utente.objects.get(username="luca.gialli").email == "luca.gialli@senza-email.invalid"
    assert not Utente.objects.get(username="mario.blu").is_active  # consigliere: non attivo
    assert not Utente.objects.get(username="mario.verdi").is_active
    # bozze per gli attivi: Rossi e Neri dirette; Gialli (senza email) «per conto»: l'ente non ha
    # una casella, quindi alla carica più alta con un'email
    bozze = Invio.objects.filter(origine="utenti-cariche")
    assert bozze.count() == 3 and all(b.stato == "bozza" for b in bozze)
    corpo = bozze.get(oggetto__startswith="Accesso al gestionale -",
                      destinatari__soggetto__cognome="Rossi").corpo  # fmt: skip
    assert "Presidenti-Comuni-2027" in corpo and "Manuale in PDF" in corpo
    assert "stessa carica" not in corpo  # non si dice che la password è condivisa
    conto = bozze.get(oggetto__contains="per conto di Luca Gialli")
    assert conto.destinatari.get().soggetto.cognome == "Rossi"  # la carica più alta con email
    assert "luca.gialli" in conto.corpo and "dotarsi di un indirizzo" in conto.corpo
    assert "Uso di queste informazioni" in conto.corpo  # l'ente non ha una casella: al presidente
    assert "per conto" in testo and "Luca Gialli" in testo
    # rieseguendo non ricrea nulla
    assert admin.post(URL, {"soggetto": scelti}).status_code == 200
    assert Utente.objects.filter(username__startswith="mario.rossi").count() == 1


def test_password_troppo_corta(admin, organi):
    consiglio, _ = organi
    s = carica(consiglio, "Rossi", "presidente")
    r = admin.post(URL, {"soggetto": [s.pk], "password_presidente": "corta"})
    assert "Password per «Presidente»" in r.content.decode()
    assert not Utente.objects.filter(soggetto=s).exists()


def test_sezione_in_installazione_multisezione(organi):
    from apps.soci.models import Sezione

    Sezione.objects.create(codice="A", nome="Alfa")
    beta = Sezione.objects.create(codice="B", nome="Beta")
    locale = Organo.objects.create(
        nome="Direttivo Beta", sigla="DB", tipo="consiglio", sezione=beta
    )
    s = carica(locale, "Locale", "presidente")
    creati, _ = servizi.crea_utenti_da_cariche(None, {s.pk}, {}, {"presidente"})
    assert list(creati[0][0].sezioni.all()) == [beta]


def test_per_conto_alla_casella_dell_ente(organi):
    from apps.core.models import Organizzazione

    Organizzazione.objects.update(email="sezione@example.org")
    consiglio, _ = organi
    carica(consiglio, "Rossi", "presidente", "rossi@example.org")
    s = carica(consiglio, "Solo", "segretario")  # senza email: va comunque alla casella dell'ente
    creati, usate = servizi.crea_utenti_da_cariche(None, {s.pk}, {}, {"segretario"})
    bozze, senza = servizi.bozze_credenziali(None, creati, usate, "https://gestione.example.org")
    assert senza == [] and bozze[0].destinatari.get().email == "sezione@example.org"
    assert bozze[0].corpo.startswith("Alla cortese attenzione dell'incaricato della trattazione")
    Organizzazione.objects.update(email="")
    altro_organo = Organo.objects.create(nome="Commissione", sigla="CM", tipo="altro")
    s2 = carica(altro_organo, "Altro", "componente")  # nessuno con l'email, né l'ente
    creati, usate = servizi.crea_utenti_da_cariche(None, {s2.pk}, {}, {"altro"})
    assert servizi.bozze_credenziali(None, creati, usate, "x")[1] == [creati[0][0]]


def test_permesso(client_ruolo):
    assert client_ruolo("Consigliere").get(URL).status_code == 403
    assert reverse("utenti:da_cariche") == URL
