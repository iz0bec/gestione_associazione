# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test dei promemoria per l'archivio centrale: nuovi soci e rettifiche da
# *              riportare a mano, accorpamento, nessun promemoria se l'archivio è collegato o
# *              se i dati arrivano proprio da lì, riepilogo per email, pagina da spuntare.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from apps.anagrafica.models import Soggetto
from apps.api.models import ClienteApi
from apps.core.models import Organizzazione
from apps.soci import importazione, promemoria, servizi
from apps.soci.models import PromemoriaArchivio, Sezione, TipologiaSocio

pytestmark = pytest.mark.django_db


@pytest.fixture
def capo(crea_utente):
    return crea_utente("capo", ruoli=["Amministratore di sistema"])


def _socio(utente, cognome="Rossi", **dati):
    p = Soggetto.objects.create(cognome=cognome, nome="Mario", **dati)
    return servizi.ammetti_socio(p, TipologiaSocio.objects.get(nome="Ordinario"), utente)


def test_nuovo_e_rettifiche_accorpate(capo):
    Organizzazione.objects.update(archivio_centrale="Federazione Potenza Matera")
    socio = _socio(capo, email="a@example.org")
    p = PromemoriaArchivio.objects.get()
    assert p.tipo == "nuovo" and p.archivio == "Federazione Potenza Matera"
    assert ["email", "", "a@example.org"] in p.modifiche
    s = socio.soggetto
    s.email, s.comune = "b@example.org", "Potenza"
    s.save()
    p.refresh_from_db()
    assert PromemoriaArchivio.objects.count() == 1  # stesso promemoria, valori finali
    assert ["email", "", "b@example.org"] in p.modifiche and [
        "comune",
        "",
        "Potenza",
    ] in p.modifiche
    promemoria.segna_fatti([p], capo)
    s.email = "c@example.org"
    s.save()
    nuovo = PromemoriaArchivio.objects.get(fatto_il__isnull=True)
    assert nuovo.tipo == "rettifica" and nuovo.modifiche == [
        ["email", "b@example.org", "c@example.org"]
    ]


def test_modifica_annullata_e_non_soci(capo):
    socio = _socio(capo, email="a@example.org")
    PromemoriaArchivio.objects.update(fatto_il=timezone.now())
    s = socio.soggetto
    s.email = "b@example.org"
    s.save()
    s.email = "a@example.org"
    s.save()  # tornato com'era: nulla da riportare
    p = PromemoriaArchivio.objects.get(fatto_il__isnull=True)
    assert p.modifiche == []
    altro = Soggetto.objects.create(cognome="Esterno")
    altro.email = "x@example.org"
    altro.save()
    assert PromemoriaArchivio.objects.filter(socio__soggetto=altro).count() == 0


def test_archivio_collegato_via_api(capo):
    ClienteApi.objects.create(nome="Federazione", tipo="installazione", origine="invito_nostro",
                              stato="attiva", ruolo="federazione", ambiti=["soci:lettura"])  # fmt: skip
    _socio(capo)
    assert not PromemoriaArchivio.objects.exists()


def test_nome_dell_archivio():
    Organizzazione.objects.update(archivio_centrale="", federazione="Potenza Matera")
    assert promemoria.nome_archivio() == "Federazione Potenza Matera"
    Sezione.objects.create(codice="X1", nome="Seconda")  # più sezioni: siamo la federazione
    assert promemoria.nome_archivio() == "Registro soci nazionale"


def test_importazione_dall_archivio_centrale(capo):
    righe = [{"_riga": 1, "cognome": "Bianchi", "nome": "Laura"}]
    opzioni = importazione.Opzioni(sezione=Sezione.predefinita(),
                                   tipologia=TipologiaSocio.objects.get(nome="Ordinario"))  # fmt: skip
    importazione.elabora(righe, opzioni, capo, esegui=True)
    assert not PromemoriaArchivio.objects.exists()
    righe = [{"_riga": 1, "cognome": "Verdi", "nome": "Gino"}]
    opzioni.da_archivio_centrale = False
    importazione.elabora(righe, opzioni, capo, esegui=True)
    assert PromemoriaArchivio.objects.get().socio.soggetto.cognome == "Verdi"


def test_riepilogo_per_email(capo, settings):
    settings.URL_PUBBLICO = "https://gestionale.example.org"
    _socio(capo, email="a@example.org")
    assert promemoria.invia_riepilogo() == 1
    assert "Rossi Mario" in mail.outbox[0].body or "Mario Rossi" in mail.outbox[0].body
    assert "/soci/archivio-centrale/" in mail.outbox[0].body
    assert promemoria.invia_riepilogo() == 0  # già segnalato


def test_pagina(client_ruolo, capo):
    _socio(capo)
    admin = client_ruolo("Amministratore di sistema")
    pagina = admin.get(reverse("soci:elenco")).content.decode()
    assert "Da riportare all" in pagina
    p = PromemoriaArchivio.objects.get()
    r = admin.get(reverse("soci:promemoria_archivio"))
    assert "Nuovo socio" in r.content.decode()
    r = admin.post(reverse("soci:promemoria_archivio"), {"scelti": [str(p.pk)]}, follow=True)
    assert "Segnati come riportati" in r.content.decode()
    p.refresh_from_db()
    assert p.fatto_il is not None
    assert "Niente da riportare" in admin.get(reverse("soci:promemoria_archivio")).content.decode()
    tesoriere = client_ruolo("Tesoriere", username="tesoriere")
    assert tesoriere.get(reverse("soci:promemoria_archivio")).status_code == 403


def test_anonimizzazione_cancella_i_promemoria(capo):
    socio = _socio(capo, email="a@example.org")
    s = socio.soggetto
    s.cognome, s.email, s.anonimizzato_il = "Anonimo", "", timezone.now()
    s.save()
    assert not PromemoriaArchivio.objects.exists()
