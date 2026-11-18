# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test del client verso le altre installazioni (apps.collegamenti) contro
# *              un'installazione remota simulata: abbinamento con invito, prova, passaggio
# *              dall'indirizzo interno a quello pubblico, risposte manomesse o non firmate.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import json
import secrets
import time

import pytest

from apps.api import chiavi
from apps.api import firma as f
from apps.api.models import ClienteApi
from apps.collegamenti import client
from apps.collegamenti.trasporto import ErroreTrasporto, Risposta
from apps.core.cifratura import nuova_chiave

from .aiuti import Controparte

CODICE = "ga1-codice-di-prova"


@pytest.fixture(autouse=True)
def _cifratura(settings):
    settings.CHIAVE_CIFRATURA = nuova_chiave()
    settings.API_TLS_CERTIFICATO = ""


class Remota(Controparte):
    """Installazione remota simulata: risponde come l'API, con le proprie chiavi."""

    def __init__(self):
        super().__init__("Federazione")
        self.richieste = []
        self.irraggiungibili = set()
        self.impronta_falsa = False
        self.firma_altrui = False

    def _risposta(self, dest, stato, dati, msg_richiesta=None):
        corpo = json.dumps(dati).encode()
        intestazioni = {
            "content-type": "application/json",
            "content-digest": f.content_digest(corpo),
        }
        msg = f.Messaggio(intestazioni=dict(intestazioni), stato=stato, richiesta=msg_richiesta)
        chiave = Controparte().firma if self.firma_altrui else self.firma
        ingresso, valore = f.firma(
            msg,
            f.componenti_risposta(msg_richiesta is not None),
            f.parametri_firma(self.kid, time.time(), secrets.token_urlsafe(18)),
            chiave,
        )
        intestazioni.update({"signature-input": ingresso, "signature": valore})
        return Risposta(stato=stato, intestazioni=intestazioni, corpo=corpo, destinazione=dest)

    def __call__(self, dest, metodo, percorso, intestazioni=None, corpo=b""):
        if dest.url in self.irraggiungibili:
            raise ErroreTrasporto("connessione rifiutata")
        self.richieste.append((dest.url, metodo, percorso))
        if percorso == "/.well-known/gestione-associazione":
            return self._risposta(dest, 200, {"istanza": str(self.uuid), "nome": self.nome,
                                              "versioni_api": ["v1"], "jwks_uri": "x",
                                              "tls_spki": []})  # fmt: skip
        if percorso == "/.well-known/gestione-associazione/jwks.json":
            return self._risposta(dest, 200, self.jwks)
        percorso, _, query = percorso.partition("?")
        msg = f.Messaggio(intestazioni={k.lower(): v for k, v in intestazioni.items()},
                          metodo=metodo, percorso=percorso, query=query)  # fmt: skip
        nostre = {k["kid"]: k for k in chiavi.jwks()["keys"] if k["use"] == "sig"}
        f.verifica(msg, lambda kid: f.chiave_pubblica(nostre[kid]["x"]),
                   richiesti=f.richiesti(f.componenti_richiesta(bool(corpo))),
                   adesso=time.time())  # fmt: skip
        assert intestazioni["Destinatario-Istanza"] == str(self.uuid)
        assert f.verifica_digest(intestazioni.get("Content-Digest", ""), corpo) or not corpo
        if percorso == "/api/v1/abbinamenti":
            assert intestazioni["Invito"] == CODICE
            dati = json.loads(corpo)
            impronta = chiavi.impronta_abbinamento(self.jwks, dati["jwks"])
            if self.impronta_falsa:
                impronta = "0000 0000 0000 0000 0000 0000 0000 0000"
            return self._risposta(dest, 201, {"istanza": str(self.uuid), "stato": "in_prova",
                                              "impronta": impronta, "jwks": self.jwks}, msg)  # fmt: skip
        if percorso == "/api/v1/cambiamenti":
            return self._risposta(dest, 200, {"flusso": "eventi", "cambiamenti": [], "ultimo": 0},
                                  msg)  # fmt: skip
        if percorso == "/api/v1/prova":
            return self._risposta(dest, 200, {"firma": "valida", "orologio": {"scarto_secondi": 0},
                                              "controparte": {"stato": "in_prova", "ambiti": []},
                                              "indirizzo_ip_visto": "192.168.0.39"}, msg)  # fmt: skip
        return self._risposta(dest, 404, {"title": "non trovato"}, msg)


@pytest.fixture
def remota(monkeypatch):
    finta = Remota()
    monkeypatch.setattr(client, "richiesta", finta)
    return finta


def _abbina(utente, **extra):
    opzioni = {"indirizzo_pubblico": "https://federazione.example.org"} | extra
    return client.abbina(utente, codice=CODICE, nome="Federazione", ambiti=["eventi:lettura"],
                         **opzioni)  # fmt: skip


@pytest.mark.django_db
def test_abbinamento_e_prova(remota, crea_utente):
    admin = crea_utente("admin")
    cliente = _abbina(admin)
    assert cliente.stato == "in_prova" and cliente.origine == "invito_loro"
    assert cliente.istanza == remota.uuid and cliente.nome_dichiarato == "Federazione"
    assert cliente.impronta == chiavi.impronta_abbinamento(chiavi.jwks(), remota.jwks)
    riuscita, esito = client.prova(cliente)
    assert riuscita, esito
    cliente.refresh_from_db()
    assert "Riuscita" in cliente.ultimo_esito_prova and cliente.ultima_prova_il


@pytest.mark.django_db
def test_indirizzo_interno_prima_poi_pubblico(remota, crea_utente):
    remota.irraggiungibili.add("https://192.168.0.34:8003")
    cliente = _abbina(crea_utente("admin"), indirizzo_interno="https://192.168.0.34:8003",
                      rete_interna=True, verifica_tls="impronta", tls_spki=["x" * 43 + "="])  # fmt: skip
    assert remota.richieste[0][0] == "https://federazione.example.org"
    riuscita, esito = client.prova(cliente)
    assert riuscita and "Indirizzi non raggiunti: https://192.168.0.34:8003" in esito
    remota.irraggiungibili.clear()
    remota.richieste.clear()
    assert client.prova(cliente)[0]
    assert remota.richieste[0][0] == "https://192.168.0.34:8003"  # l'interno ha la precedenza


@pytest.mark.django_db
def test_impronta_diversa_interrompe_l_abbinamento(remota, crea_utente):
    remota.impronta_falsa = True
    with pytest.raises(client.ErroreCollegamento, match="impronta"):
        _abbina(crea_utente("admin"))
    assert not ClienteApi.objects.exists()


@pytest.mark.django_db
def test_risposte_firmate_da_altri_rifiutate(remota, crea_utente):
    cliente = _abbina(crea_utente("admin"))
    remota.firma_altrui = True
    riuscita, esito = client.prova(cliente)
    assert not riuscita and "Firma della risposta non valida" in esito
    with pytest.raises(client.ErroreCollegamento):
        client.scopri(client.destinazioni(cliente)[0])


@pytest.mark.django_db
def test_istanza_gia_registrata(remota, crea_utente):
    admin = crea_utente("admin")
    _abbina(admin)
    with pytest.raises(client.servizi.OperazioneNonValida, match="già registrata"):
        _abbina(admin)


@pytest.mark.django_db
def test_chiamata_con_query(remota, crea_utente):
    """@path e @query si firmano separati, come li vede il server."""
    cliente = _abbina(crea_utente("admin"))
    risposta, _, _ = client.chiama(cliente, "GET", "/cambiamenti?flusso=eventi&dopo=0")
    assert risposta.stato == 200
    assert remota.richieste[-1][2] == "/api/v1/cambiamenti?flusso=eventi&dopo=0"
