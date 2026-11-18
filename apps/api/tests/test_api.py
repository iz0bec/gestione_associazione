# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test dell'API v1 (fase F1): descrizione e chiavi dell'istanza, abbinamento con
# *              invito, /prova e tutti i rifiuti dell'ADR-030 §4 (ripetizione, destinatario,
# *              digest, orologio, stato, IP), firma delle risposte, rotazione e pulizia.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import json
import time
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.api import chiavi, servizi
from apps.api.models import ClienteApi, NonceVisto
from apps.core.cifratura import nuova_chiave
from apps.core.models import EventoAudit

from .aiuti import Controparte, messaggio, verifica_risposta


@pytest.fixture(autouse=True)
def _cifratura(settings):
    settings.CHIAVE_CIFRATURA = nuova_chiave()
    settings.API_TLS_CERTIFICATO = ""


@pytest.fixture
def amministratore(crea_utente):
    return crea_utente("admin", ruoli=["Amministratore di sistema"])


def _abbina(client, amministratore, controparte, ambiti=("eventi:lettura",)):
    _, codice = servizi.crea_invito(amministratore, nome="Sito", tipo="integrazione",
                                    ambiti=list(ambiti))  # fmt: skip
    r = controparte.chiama(client, "POST", "/api/v1/abbinamenti",
                           controparte.richiesta_abbinamento(), extra={"Invito": codice})  # fmt: skip
    assert r.status_code == 201, r.content
    return ClienteApi.objects.get(istanza=controparte.uuid), codice, r


def _codice(r):
    return r.json().get("codice")


@pytest.mark.django_db
class TestIstanza:
    def test_descrizione_firmata_e_jwks(self, client):
        r = client.get("/.well-known/gestione-associazione")
        assert r.status_code == 200
        dati = r.json()
        assert dati["istanza"] == str(chiavi.istanza().uuid)
        assert dati["versioni_api"] == ["v1"]
        assert dati["jwks_uri"].endswith("/.well-known/gestione-associazione/jwks.json")
        jwks = client.get("/.well-known/gestione-associazione/jwks.json")
        assert jwks["Content-Type"] == "application/jwk-set+json"
        chiavi_pubbliche = jwks.json()
        assert {k["use"] for k in chiavi_pubbliche["keys"]} == {"sig", "enc"}
        assert all(k["kid"] == chiavi.thumbprint(k) for k in chiavi_pubbliche["keys"])
        verifica_risposta(r, chiavi_pubbliche)
        verifica_risposta(jwks, chiavi_pubbliche)

    def test_le_private_sono_cifrate(self):
        chiavi.assicura_chiavi()
        from apps.api.models import ChiaveIstanza

        for c in ChiaveIstanza.objects.all():
            assert c.privata.startswith("gAAAA")  # token Fernet
            assert c.pubblica not in c.privata

    def test_senza_chiave_di_cifratura(self, client, settings):
        settings.CHIAVE_CIFRATURA = ""
        r = client.post("/api/v1/prova")
        assert r.status_code == 503
        assert _codice(r) == "non-configurata"

    def test_rotazione_con_sovrapposizione(self, amministratore):
        prima = {k["kid"] for k in chiavi.jwks()["keys"]}
        servizi.ruota_chiavi(amministratore)
        dopo = chiavi.jwks()["keys"]
        assert prima < {k["kid"] for k in dopo}  # le vecchie restano pubblicate
        assert sum("exp" in k for k in dopo) == 2
        from apps.api.models import ChiaveIstanza

        ChiaveIstanza.objects.filter(ritirata_il__isnull=False).update(
            valida_fino=timezone.now() - timedelta(seconds=1)
        )
        assert servizi.pulizia()["chiavi"] == 2
        assert {k["kid"] for k in chiavi.jwks()["keys"]}.isdisjoint(prima)


@pytest.mark.django_db
class TestAbbinamento:
    def test_abbinamento_completo(self, client, amministratore):
        ctp = Controparte()
        _, codice = servizi.crea_invito(amministratore, nome="Sito", tipo="integrazione",
                                        ambiti=["eventi:lettura"])  # fmt: skip
        corpo = json.dumps(ctp.richiesta_abbinamento()).encode()
        intestazioni = ctp.intestazioni("POST", "/api/v1/abbinamenti", corpo,
                                        extra={"Invito": codice})  # fmt: skip
        r = client.post("/api/v1/abbinamenti", data=corpo, content_type="application/json",
                        headers=intestazioni)  # fmt: skip
        assert r.status_code == 201, r.content
        cliente = ClienteApi.objects.get(istanza=ctp.uuid)
        esito = r.json()
        # risposta firmata dall'istanza e legata alla richiesta
        verifica_risposta(r, esito["jwks"], messaggio(intestazioni, "POST", "/api/v1/abbinamenti"))
        assert esito["stato"] == "in_prova"
        assert esito["istanza"] == str(chiavi.istanza().uuid)
        # stessa impronta calcolata dalle due parti
        assert esito["impronta"] == chiavi.impronta_abbinamento(ctp.jwks, chiavi.jwks())
        assert cliente.impronta == esito["impronta"]
        assert cliente.jwks == ctp.jwks and cliente.nome_dichiarato == ctp.nome
        # l'invito è monouso
        altra = Controparte()
        r = altra.chiama(client, "POST", "/api/v1/abbinamenti", altra.richiesta_abbinamento(),
                         extra={"Invito": codice})  # fmt: skip
        assert r.status_code == 410 and _codice(r) == "invito-non-valido"
        # il codice non finisce nel registro attività
        assert codice not in json.dumps(list(EventoAudit.objects.values("dettagli")))

    def test_firma_con_una_chiave_diversa_da_quella_presentata(self, client, amministratore):
        _, codice = servizi.crea_invito(amministratore, nome="X", tipo="integrazione", ambiti=[])
        impostore, vittima = Controparte(), Controparte()
        intestazioni = impostore.intestazioni(
            "POST", "/api/v1/abbinamenti", json.dumps(vittima.richiesta_abbinamento()).encode(),
            extra={"Invito": codice},
        )  # fmt: skip
        r = client.post("/api/v1/abbinamenti", data=vittima.richiesta_abbinamento(),
                        content_type="application/json", headers=intestazioni)  # fmt: skip
        assert r.status_code == 401
        assert not ClienteApi.objects.filter(istanza__isnull=False).exists()

    def test_invito_scaduto_e_jwks_non_valida(self, client, amministratore):
        ctp = Controparte()
        cliente, codice = servizi.crea_invito(amministratore, nome="X", tipo="integrazione",
                                              ambiti=[])  # fmt: skip
        cliente.inviti.update(scade_il=timezone.now())
        r = ctp.chiama(client, "POST", "/api/v1/abbinamenti", ctp.richiesta_abbinamento(),
                       extra={"Invito": codice})  # fmt: skip
        assert r.status_code == 410
        dati = ctp.richiesta_abbinamento()
        dati["jwks"]["keys"][0]["kid"] = "scelto-a-mano"
        codice = servizi.nuovo_invito(cliente, amministratore)
        r = ctp.chiama(client, "POST", "/api/v1/abbinamenti", dati, extra={"Invito": codice})
        assert r.status_code == 400 and "RFC 7638" in r.json()["detail"]

    def test_dati_personali_alle_integrazioni_solo_con_conferma(self, amministratore):
        with pytest.raises(servizi.OperazioneNonValida):
            servizi.crea_invito(amministratore, nome="X", tipo="integrazione",
                                ambiti=["soci:lettura"])  # fmt: skip
        servizi.crea_invito(amministratore, nome="X", tipo="integrazione", ambiti=["soci:lettura"],
                            dati_personali_confermati=True)  # fmt: skip
        servizi.crea_invito(amministratore, nome="Y", tipo="installazione",
                            ambiti=["soci:lettura"])  # fmt: skip


@pytest.mark.django_db
class TestProva:
    def test_in_prova_e_attivazione(self, client, amministratore):
        ctp = Controparte()
        cliente, _, _ = _abbina(client, amministratore, ctp)
        intestazioni = ctp.intestazioni("POST", "/api/v1/prova", b'{"a":1}')
        r = client.post("/api/v1/prova", data=b'{"a":1}', content_type="application/json",
                        headers=intestazioni)  # fmt: skip
        assert r.status_code == 200, r.content
        diagnosi = r.json()
        assert diagnosi["firma"] == "valida"
        assert diagnosi["controparte"] == {"stato": "in_prova", "ambiti": ["eventi:lettura"]}
        assert abs(diagnosi["orologio"]["scarto_secondi"]) <= 2
        # la risposta è firmata e legata alla richiesta
        verifica_risposta(r, chiavi.jwks(), messaggio(intestazioni, "POST", "/api/v1/prova"))
        with pytest.raises(servizi.OperazioneNonValida):
            servizi.attiva(cliente, amministratore, impronta_confermata=False)
        servizi.attiva(cliente, amministratore, impronta_confermata=True)
        cliente.refresh_from_db()
        assert cliente.stato == "attiva" and cliente.attivata_da == amministratore
        assert sorted(cliente.chiamate.values_list("stato", flat=True)) == [200, 201]

    @pytest.mark.parametrize(
        ("opzioni", "stato", "codice"),
        [
            ({"destinatario": "00000000-0000-0000-0000-000000000000"}, 421, "destinatario-errato"),
            ({"adesso": time.time() - 400}, 401, "firma-scaduta"),
            ({"corpo_inviato": b'{"a":2}'}, 400, "digest-errato"),
            ({"componenti": [("@method", []), ("@path", [])]}, 401, "firma-non-valida"),
        ],
    )
    def test_rifiuti(self, client, amministratore, opzioni, stato, codice):
        ctp = Controparte()
        _abbina(client, amministratore, ctp)
        r = ctp.chiama(client, "POST", "/api/v1/prova", {"a": 1}, **opzioni)
        assert (r.status_code, _codice(r)) == (stato, codice)
        assert r["Signature"]  # anche gli errori sono firmati

    def test_ripetizione_rifiutata(self, client, amministratore):
        ctp = Controparte()
        _abbina(client, amministratore, ctp)
        intestazioni = ctp.intestazioni("POST", "/api/v1/prova")
        assert client.generic("POST", "/api/v1/prova", headers=intestazioni).status_code == 200
        r = client.generic("POST", "/api/v1/prova", headers=intestazioni)
        assert (r.status_code, _codice(r)) == (401, "nonce-riusato")

    def test_senza_firma_e_controparte_sconosciuta(self, client):
        r = client.post("/api/v1/prova")
        assert (r.status_code, _codice(r)) == (401, "firma-non-valida")
        r = Controparte().chiama(client, "POST", "/api/v1/prova")
        assert r.status_code == 401 and "sconosciuta" in r.json()["detail"]
        assert client.get("/api/v1/prova").status_code == 405

    def test_stati_ip_e_scadenza(self, client, amministratore):
        ctp = Controparte()
        cliente, _, _ = _abbina(client, amministratore, ctp)
        servizi.attiva(cliente, amministratore, impronta_confermata=True)
        cliente.ip_ammessi = "10.9.9.0/24"
        cliente.save()
        r = ctp.chiama(client, "POST", "/api/v1/prova")
        assert (r.status_code, _codice(r)) == (403, "ip-non-ammesso")
        cliente.ip_ammessi = "127.0.0.1"
        cliente.scade_il = timezone.localdate() - timedelta(days=1)
        cliente.save()
        r = ctp.chiama(client, "POST", "/api/v1/prova")
        cliente.refresh_from_db()
        assert cliente.stato == "sospesa"  # sospesa automaticamente alla scadenza
        assert (r.status_code, _codice(r)) == (403, "controparte-non-attiva")
        servizi.revoca(cliente, amministratore)
        r = ctp.chiama(client, "POST", "/api/v1/prova")
        assert r.status_code == 403 and "revocata" in r.json()["detail"]

    def test_pulizia_dei_nonce(self, client, amministratore):
        ctp = Controparte()
        _abbina(client, amministratore, ctp)
        NonceVisto.objects.update(visto_il=timezone.now() - timedelta(minutes=11))
        assert servizi.pulizia()["nonce"] >= 1
