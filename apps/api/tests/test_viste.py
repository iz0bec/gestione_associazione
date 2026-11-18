# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test di Sistema → Collegamenti API (permessi, invito mostrato una volta,
# *              attivazione solo con la conferma dell'impronta) e coerenza con il contratto
# *              OpenAPI degli endpoint già implementati.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import json
import re
from pathlib import Path

import pytest
from django.conf import settings as impostazioni
from django.urls import resolve

from apps.api.models import ClienteApi
from apps.core.cifratura import nuova_chiave
from apps.core.models import EventoAudit

from .aiuti import Controparte

CONTRATTO = Path(impostazioni.BASE_DIR) / "docs" / "api" / "openapi.yaml"
# operationId implementati → (metodo, percorso del contratto, URL reale)
IMPLEMENTATI = {
    "descriviIstanza": ("get", "/.well-known/gestione-associazione",
                        "/.well-known/gestione-associazione"),
    "chiaviIstanza": ("get", "/.well-known/gestione-associazione/jwks.json",
                      "/.well-known/gestione-associazione/jwks.json"),
    "abbina": ("post", "/abbinamenti", "/api/v1/abbinamenti"),
    "prova": ("post", "/prova", "/api/v1/prova"),
    "aggiornaChiavi": ("put", "/chiavi", "/api/v1/chiavi"),
    "elencaCambiamenti": ("get", "/cambiamenti", "/api/v1/cambiamenti"),
    "riepilogoFlusso": ("get", "/riepiloghi/{flusso}", "/api/v1/riepiloghi/eventi"),
    "elencaEventi": ("get", "/eventi", "/api/v1/eventi"),
    "leggiEvento": ("get", "/eventi/{uuid}", "/api/v1/eventi/7c1e2a9e-5d0b-4c71-9a43-0d2f7f6f3b11"),
    "elencaSezioni": ("get", "/sezioni", "/api/v1/sezioni"),
}  # fmt: skip


@pytest.fixture(autouse=True)
def _cifratura(settings):
    settings.CHIAVE_CIFRATURA = nuova_chiave()
    settings.API_TLS_CERTIFICATO = ""


def test_gli_endpoint_implementati_sono_nel_contratto():
    testo = CONTRATTO.read_text()
    for operazione, (metodo, percorso, url) in IMPLEMENTATI.items():
        blocco = re.search(
            rf"\n  {re.escape(percorso)}:\n(.*?)(?=\n  /|\ncomponents:)", testo, re.S
        )
        assert blocco, f"{percorso} assente dal contratto"
        assert re.search(
            rf"(?:^|\n)    {metodo}:\n(?:.*\n)*?\s+operationId: {operazione}\n", blocco.group(1)
        ), f"{operazione} non è {metodo.upper()} {percorso}"
        assert resolve(url).func.__module__ == "apps.api.endpoint", url


@pytest.mark.django_db
def test_solo_l_amministratore(client_ruolo):
    client = client_ruolo("Segretario")
    assert client.get("/sistema/api/").status_code == 403
    assert client.post("/sistema/api/invito/", {"nome": "X"}).status_code == 403


@pytest.mark.django_db
def test_invito_attivazione_e_revoca(client_ruolo):
    client = client_ruolo("Amministratore di sistema")
    r = client.get("/sistema/api/")
    assert r.status_code == 200 and "Questa istanza" in r.content.decode()
    r = client.post("/sistema/api/invito/", {"nome": "Sito eventi", "tipo": "integrazione",
                                             "ambiti": ["eventi:lettura"]})  # fmt: skip
    assert r.status_code == 200
    codice = re.search(r'value="(ga1-[^"]+)"', r.content.decode()).group(1)
    assert codice not in json.dumps(
        list(EventoAudit.objects.values("dettagli", "oggetto_descrizione"))
    )
    cliente = ClienteApi.objects.get(nome="Sito eventi")
    ctp = Controparte()
    r = ctp.chiama(client, "POST", "/api/v1/abbinamenti", ctp.richiesta_abbinamento(),
                   extra={"Invito": codice})  # fmt: skip
    assert r.status_code == 201
    pagina = client.get(f"/sistema/api/{cliente.pk}/").content.decode()
    assert r.json()["impronta"] in pagina
    client.post(f"/sistema/api/{cliente.pk}/attiva/")  # senza conferma: resta in prova
    cliente.refresh_from_db()
    assert cliente.stato == "in_prova"
    client.post(f"/sistema/api/{cliente.pk}/attiva/", {"impronta_confermata": "1"})
    cliente.refresh_from_db()
    assert cliente.stato == "attiva"
    client.post(f"/sistema/api/{cliente.pk}/revoca/")
    cliente.refresh_from_db()
    assert cliente.stato == "revocata"
    assert client.get(f"/sistema/api/{cliente.pk}/modifica/").status_code == 404


@pytest.mark.django_db
def test_modifica_e_regole_degli_indirizzi(client_ruolo):
    client = client_ruolo("Amministratore di sistema")
    cliente = ClienteApi.objects.create(nome="Sezione", tipo="installazione",
                                        origine="invito_nostro")  # fmt: skip
    dati = {"nome": "Sezione", "indirizzo_interno": "http://example.org:8000",
            "verifica_tls": "pubblica", "ip_ammessi": "192.168.0.0/24\nnon-ip"}  # fmt: skip
    r = client.post(f"/sistema/api/{cliente.pk}/modifica/", dati)
    errori = r.context["form"].errors
    assert "indirizzo_interno" in errori and "ip_ammessi" in errori
    dati.update(indirizzo_interno="http://192.168.0.39:8000", rete_interna="on",
                http_in_chiaro="on", ip_ammessi="192.168.0.0/24")  # fmt: skip
    r = client.post(f"/sistema/api/{cliente.pk}/modifica/", dati)
    assert r.status_code == 302, r.context["form"].errors
    cliente.refresh_from_db()
    assert cliente.http_in_chiaro and cliente.ip_ammessi == "192.168.0.0/24"


@pytest.mark.django_db
def test_usa_invito_controlla_gli_indirizzi(client_ruolo):
    client = client_ruolo("Amministratore di sistema")
    r = client.post("/sistema/api/usa-invito/", {
        "nome": "Federazione", "codice": "ga1-x", "indirizzo_pubblico": "http://example.org",
        "verifica_tls": "pubblica",
    })  # fmt: skip
    assert "indirizzo_pubblico" in r.context["form"].errors
    assert not ClienteApi.objects.exists()
