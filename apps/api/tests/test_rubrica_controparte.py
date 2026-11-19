# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test della voce di rubrica della controparte collegata: endpoint /ente con i
# *              contatti istituzionali, creazione e aggiornamento dell'ente in anagrafica.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.anagrafica.models import Soggetto
from apps.api.models import ClienteApi
from apps.collegamenti import client as cl
from apps.collegamenti import rubrica
from apps.core.cifratura import nuova_chiave
from apps.core.models import Organizzazione
from apps.soci.models import Sezione

from .aiuti import Controparte

pytestmark = pytest.mark.django_db

CONTATTI = {
    "denominazione": "ANCR Sezione di Avigliano",
    "codice_fiscale": "96012340765",
    "indirizzo": "Via Roma 1",
    "cap": "85021",
    "comune": "Avigliano",
    "provincia": "pz",
    "telefono": "0971 123456",
    "email": "avigliano@esempio.it",
    "pec": "non-una-pec",
    "sito_web": "https://esempio.it",
}


@pytest.fixture(autouse=True)
def _ambiente(settings):
    settings.CHIAVE_CIFRATURA = nuova_chiave()
    settings.API_TLS_CERTIFICATO = ""


def _controparte(ruolo="sezione", sezione=None, stato="attiva"):
    ctp = Controparte()
    cliente = ClienteApi.objects.create(
        nome=f"Controparte {ruolo}", tipo="installazione", origine="invito_nostro",
        stato=stato, istanza=ctp.uuid, jwks=ctp.jwks, ambiti=[], ruolo=ruolo, sezione=sezione,
        abbinata_il=timezone.now(),
    )  # fmt: skip
    return ctp, cliente


@pytest.fixture
def risponde(monkeypatch):
    def imposta(dati, stato=200):
        risposta = type("R", (), {"stato": stato})()
        monkeypatch.setattr(cl, "chiama", lambda *a, **k: (risposta, None, []))
        monkeypatch.setattr(cl, "json_risposta", lambda r: dict(dati))

    return imposta


def test_endpoint_ente_restituisce_i_contatti(client):
    org = Organizzazione.corrente()
    org.denominazione, org.pec, org.telefono = "Federazione di Potenza", "fed@pec.it", "0971 1"
    org.save()
    ctp, _ = _controparte("federazione")
    r = ctp.chiama(client, "GET", "/api/v1/ente")
    assert r.status_code == 200
    dati = r.json()
    assert dati["denominazione"] == "Federazione di Potenza" and dati["pec"] == "fed@pec.it"
    assert set(dati) == {"denominazione", "codice_fiscale", "partita_iva", "indirizzo", "cap",
                         "comune", "provincia", "telefono", "email", "pec", "sito_web"}  # fmt: skip


def test_endpoint_ente_rifiuta_chi_non_e_attivo(client):
    ctp, _ = _controparte(stato="in_prova")
    assert ctp.chiama(client, "GET", "/api/v1/ente").status_code == 403


def test_crea_la_voce_e_completa_la_sezione(risponde, crea_utente):
    avigliano = Sezione.objects.create(codice="002", nome="Avigliano")
    _, cliente = _controparte("sezione", avigliano)
    risponde(CONTATTI)
    soggetto, creato = rubrica.aggiorna(cliente, crea_utente("admin"))
    assert creato and soggetto.tipo == Soggetto.Tipo.ENTE
    assert soggetto.denominazione == "ANCR Sezione di Avigliano"
    assert soggetto.provincia == "PZ" and soggetto.telefono == "0971 123456"
    assert soggetto.pec == ""  # non valida: scartata, mai inventata
    cliente.refresh_from_db()
    avigliano.refresh_from_db()
    assert cliente.soggetto == soggetto
    assert avigliano.email == "avigliano@esempio.it" and avigliano.provincia == "PZ"


def test_aggiorna_la_voce_esistente_senza_duplicare(risponde):
    esistente = Soggetto.objects.create(tipo="ente", denominazione="ancr sezione di avigliano")
    _, cliente = _controparte("sezione", Sezione.objects.create(codice="002", nome="Avigliano"))
    risponde(CONTATTI)
    soggetto, creato = rubrica.aggiorna(cliente)
    assert not creato and soggetto == esistente
    risponde({**CONTATTI, "telefono": "0971 999"})
    soggetto, creato = rubrica.aggiorna(cliente)
    assert not creato and soggetto.telefono == "0971 999"
    assert Soggetto.objects.filter(tipo="ente").count() == 1


def test_controparte_vecchia_o_pari(risponde):
    _, cliente = _controparte("federazione")
    risponde({}, stato=404)
    with pytest.raises(rubrica.OperazioneNonValida, match="ultima versione"):
        rubrica.aggiorna(cliente)
    _, pari = _controparte("pari")
    assert rubrica.aggiorna_se_possibile(pari) == (None, False, "")


def test_impostando_il_ruolo_si_crea_la_voce(risponde, client_ruolo):
    admin = client_ruolo("Amministratore di sistema")
    _, cliente = _controparte("pari")
    risponde(CONTATTI)
    dati = {"nome": cliente.nome, "ruolo": "federazione", "verifica_tls": cliente.verifica_tls,
            "ambiti": [], "notifiche_flussi": []}  # fmt: skip
    r = admin.post(reverse("api:modifica", args=[cliente.pk]), dati, follow=True)
    assert "Voce di rubrica" in r.content.decode(), r.content.decode()[:3000]
    cliente.refresh_from_db()
    assert cliente.soggetto and cliente.soggetto.denominazione == CONTATTI["denominazione"]
    r = admin.post(reverse("api:azione", args=[cliente.pk, "rubrica"]), follow=True)
    assert "aggiornata" in r.content.decode()
