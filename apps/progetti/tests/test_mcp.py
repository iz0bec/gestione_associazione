# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test del connettore MCP: spento di norma, token (impronta, revoca, scadenza),
# *              protocollo JSON-RPC, strumenti secondo i permessi, nessun dato personale,
# *              commenti solo se ammessi due volte, registro attività, pagina dei token.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import json
from datetime import date, timedelta

import pytest
from django.urls import reverse

from apps.anagrafica.models import Soggetto
from apps.core.models import EventoAudit
from apps.progetti import mcp, servizi
from apps.progetti.forms import IdeaForm
from apps.progetti.models import ConnettoreMCP, Idea, TokenMCP

pytestmark = pytest.mark.django_db
URL = "/progetti/mcp/"


@pytest.fixture
def attivo():
    c = ConnettoreMCP.corrente()
    c.attivo = True
    c.save()
    return c


@pytest.fixture
def segretario(crea_utente):
    return crea_utente("segretario", ruoli=["Segretario"])


def _rpc(client, valore, metodo, params=None, id_=1, **intestazioni):
    corpo = {"jsonrpc": "2.0", "method": metodo, "params": params or {}}
    if id_ is not None:
        corpo["id"] = id_
    return client.post(URL, json.dumps(corpo), content_type="application/json",
                       HTTP_AUTHORIZATION=f"Bearer {valore}", **intestazioni)  # fmt: skip


def _chiama(client, valore, nome, **argomenti):
    r = _rpc(client, valore, "tools/call", {"name": nome, "arguments": argomenti})
    risultato = r.json()["result"]
    testo = risultato["content"][0]["text"]
    return (json.loads(testo) if not risultato["isError"] else testo), risultato["isError"]


def _idea(utente, **extra):
    form = IdeaForm(
        data={"titolo": "Mostra", "descrizione": "Pannelli", "fonte": "interna"} | extra
    )
    assert form.is_valid(), form.errors
    return servizi.crea_idea(form, utente)


class TestAccesso:
    def test_spento_di_norma(self, client, segretario):
        _, valore = mcp.crea_token(segretario, "prova")
        assert _rpc(client, valore, "ping").status_code == 404

    def test_token(self, client, segretario, attivo):
        assert _rpc(client, "ga_mcp_falso", "ping").status_code == 401
        token, valore = mcp.crea_token(segretario, "prova")
        assert valore.startswith("ga_mcp_") and valore not in token.impronta
        assert _rpc(client, valore, "ping").json()["result"] == {}
        token.scade_il = date.today() - timedelta(days=1)
        token.save()
        assert _rpc(client, valore, "ping").status_code == 401
        token.scade_il = None
        token.save()
        mcp.revoca(token, segretario)
        assert _rpc(client, valore, "ping").status_code == 401

    def test_metodo_e_origine(self, client, segretario, attivo):
        _, valore = mcp.crea_token(segretario, "prova")
        assert client.get(URL).status_code == 405
        r = _rpc(client, valore, "ping", HTTP_ORIGIN="https://altro.example")
        assert r.status_code == 403
        r = client.post(URL, "[]", content_type="application/json",
                        HTTP_AUTHORIZATION=f"Bearer {valore}")  # fmt: skip
        assert r.json()["error"]["code"] == -32600


class TestProtocollo:
    def test_initialize_e_strumenti(self, client, segretario, attivo):
        _, valore = mcp.crea_token(segretario, "prova")
        r = _rpc(client, valore, "initialize", {"protocolVersion": "2025-03-26"}).json()
        assert r["result"]["protocolVersion"] == "2025-03-26"
        assert "tools" in r["result"]["capabilities"]
        assert _rpc(client, valore, "notifications/initialized", id_=None).status_code == 202
        nomi = {t["name"] for t in _rpc(client, valore, "tools/list").json()["result"]["tools"]}
        assert {"scheda_bando", "scheda_progetto", "elenca_idee"} <= nomi
        assert "aggiungi_commento" not in nomi  # commenti non ammessi
        r = _rpc(client, valore, "metodo/inesistente").json()
        assert r["error"]["code"] == -32601

    def test_strumenti_secondo_i_permessi(self, client, crea_utente, attivo):
        consigliere = crea_utente("cons", ruoli=["Consigliere"])
        _, valore = mcp.crea_token(consigliere, "prova")
        nomi = {t["name"] for t in _rpc(client, valore, "tools/list").json()["result"]["tools"]}
        assert "bandi_da_vagliare" not in nomi  # serve la gestione dei bandi
        _, errore = _chiama(client, valore, "bandi_da_vagliare")
        assert errore


class TestDati:
    def test_idea_senza_dati_personali(self, client, segretario, attivo):
        persona = Soggetto.objects.create(tipo="persona", cognome="Rossi", nome="Mario")
        idea = _idea(segretario, fonte="esterna", fonte_soggetto=persona.pk)
        altra = _idea(segretario, titolo="Lapide", fonte="esterna", fonte_testo="Mario Bianchi")
        _, valore = mcp.crea_token(segretario, "prova")
        dati, _ = _chiama(client, valore, "scheda_idea", id=idea.pk)
        assert dati["proposta_da"] == "persona (riservato)"
        dati, _ = _chiama(client, valore, "scheda_idea", id=altra.pk)
        assert "Bianchi" not in json.dumps(dati)
        elenco, _ = _chiama(client, valore, "elenca_idee")
        assert {x["codice"] for x in elenco} == {idea.codice, altra.codice}
        dati, errore = _chiama(client, valore, "scheda_idea", id=999)
        assert errore and dati == "Non trovato."

    def test_associazione_solo_aggregati(self, client, segretario, attivo):
        _, valore = mcp.crea_token(segretario, "prova")
        dati, _ = _chiama(client, valore, "dati_associazione")
        assert "soci_attivi" in dati and "rendiconto_anno_precedente" in dati

    def test_registro_attivita(self, client, segretario, attivo):
        token, valore = mcp.crea_token(segretario, "prova")
        _chiama(client, valore, "elenca_bandi")
        e = EventoAudit.objects.filter(oggetto_id=str(token.pk), azione="consultazione").get()
        assert e.dettagli["strumento"] == "elenca_bandi" and e.utente == segretario


class TestCommenti:
    def test_serve_doppio_consenso(self, client, segretario, attivo):
        idea = _idea(segretario)
        _, valore = mcp.crea_token(segretario, "prova", commenti=True)
        _, errore = _chiama(client, valore, "aggiungi_commento", tipo="idea", id=idea.pk,
                            testo="Coerente con la finalità b")  # fmt: skip
        assert errore  # il connettore non ammette commenti
        attivo.commenti_ammessi = True
        attivo.save()
        dati, errore = _chiama(client, valore, "aggiungi_commento", tipo="idea", id=idea.pk,
                               testo="Coerente con la finalità b")  # fmt: skip
        assert not errore and idea.commenti.get().testo.startswith("[Assistente] ")
        assert Idea.objects.get(pk=idea.pk).stato == "nuova"  # nient'altro cambia
        _, senza = mcp.crea_token(segretario, "senza")
        nomi = {t["name"] for t in _rpc(client, senza, "tools/list").json()["result"]["tools"]}
        assert "aggiungi_commento" not in nomi


class TestPagina:
    def test_token_mostrato_una_volta(self, client_ruolo):
        c = client_ruolo("Segretario")
        r = c.post(reverse("progetti:assistente"), {"azione": "crea", "nome": "Ollama"},
                   follow=True)  # fmt: skip
        testo = r.content.decode()
        assert "copiatelo ora" in testo and "ga_mcp_" in testo
        assert "ga_mcp_" not in c.get(reverse("progetti:assistente")).content.decode().replace(
            TokenMCP.objects.get().prefisso, ""
        )
        token = TokenMCP.objects.get()
        c.post(reverse("progetti:assistente"), {"azione": "revoca", "token": token.pk})
        token.refresh_from_db()
        assert token.revocato_il is not None

    def test_solo_amministratore_attiva(self, client_ruolo):
        c = client_ruolo("Segretario")
        r = c.post(reverse("progetti:assistente"), {"azione": "impostazioni", "attivo": "1"})
        assert r.status_code == 404 and not ConnettoreMCP.corrente().attivo
        a = client_ruolo("Amministratore di sistema", username="admin2")
        a.post(reverse("progetti:assistente"), {"azione": "impostazioni", "attivo": "1"})
        assert ConnettoreMCP.corrente().attivo

    def test_consigliere_senza_token(self, client_ruolo):
        assert client_ruolo("Consigliere").get(reverse("progetti:assistente")).status_code == 403
