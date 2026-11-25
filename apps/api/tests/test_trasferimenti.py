# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test del trasferimento di un socio fra installazioni collegate (F5): partenza
# *              con il consenso, arrivo (accogli/respingi), esito che fa cessare il socio alla
# *              partenza, spostamento fra sezioni in federazione con l'allineamento.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import uuid
from datetime import date, timedelta

import pytest
from django.urls import reverse

from apps.collegamenti import soci as allineamento_soci
from apps.collegamenti import trasferimenti
from apps.soci import allineamento
from apps.soci.models import Sezione, Socio, TrasferimentoEsterno

from . import test_verifica_soci as base
from .test_verifica_soci import ANNO, CF_BIANCHI, CF_ROSSI, _controparte, _remota, _socio

pytestmark = pytest.mark.django_db
_ambiente, admin, avigliano = base._ambiente, base.admin, base.avigliano


class _Risposta:
    def __init__(self, stato):
        self.stato = stato


@pytest.fixture
def posta(monkeypatch):
    inviati = []

    def chiama(cliente, metodo, percorso, corpo=None, **opzioni):
        inviati.append((percorso, corpo))
        return _Risposta(201 if percorso == "/trasferimenti" else 200), None, []

    monkeypatch.setattr(trasferimenti.client, "chiama", chiama)
    return inviati


def _richiesta(**extra):
    socio = _remota("Bianchi", "Laura", CF_BIANCHI, data_iscrizione="2015-03-01",
                    tessere=[{"anno": ANNO, "codice": "551", "pagata": True}])  # fmt: skip
    return {"uuid": str(uuid.uuid4()), "socio": socio,
            "sezione": {"codice": "009", "nome": "Ruoti"},
            "consenso_il": str(date.today()), "consenso_modo": "domanda scritta",
            "motivo": "cambio di residenza"} | extra  # fmt: skip


class TestPartenza:
    def test_invia_con_consenso(self, admin, posta):
        socio = _socio(admin, Sezione.predefinita(), "Rossi", "Mario", CF_ROSSI)
        _, sorella = _controparte("pari")
        with pytest.raises(trasferimenti.OperazioneNonValida, match="consenso"):
            trasferimenti.invia(socio, sorella, admin, consenso_il=None, consenso_modo="")
        t = trasferimenti.invia(socio, sorella, admin, consenso_il=date.today(),
                                consenso_modo="email del socio", motivo="residenza")  # fmt: skip
        percorso, corpo = posta[0]
        assert percorso == "/trasferimenti" and corpo["socio"]["codice_fiscale"] == CF_ROSSI
        assert corpo["consenso_modo"] == "email del socio" and t.stato == "in_attesa"
        with pytest.raises(trasferimenti.OperazioneNonValida, match="già una richiesta"):
            trasferimenti.invia(socio, sorella, admin, consenso_il=date.today(), consenso_modo="x")

    def test_esito_accolto_fa_cessare(self, admin, posta):
        socio = _socio(admin, Sezione.predefinita(), "Rossi", "Mario", CF_ROSSI)
        _, sorella = _controparte("pari")
        t = trasferimenti.invia(socio, sorella, admin, consenso_il=date.today(), consenso_modo="x")
        trasferimenti.ricevi_esito(sorella, t.uuid, {"esito": "accolto"})
        socio.refresh_from_db()
        assert socio.stato == Socio.Stato.CESSATO
        assert socio.causa_cessazione == Socio.Cessazione.TRASFERIMENTO
        # la riga per la federazione dice il perché della cessazione
        riga = allineamento.elenco(socio.sezione)[0]
        assert riga["causa_cessazione"] == "Trasferimento ad altra sezione"

    def test_esito_respinto(self, admin, posta):
        socio = _socio(admin, Sezione.predefinita(), "Rossi", "Mario", CF_ROSSI)
        _, sorella = _controparte("pari")
        t = trasferimenti.invia(socio, sorella, admin, consenso_il=date.today(), consenso_modo="x")
        trasferimenti.ricevi_esito(sorella, t.uuid, {"esito": "respinto", "motivo": "dati"})
        socio.refresh_from_db()
        t.refresh_from_db()
        assert socio.stato == Socio.Stato.ATTIVO and t.esito_motivo == "dati"


class TestArrivo:
    def test_endpoint_e_accoglimento(self, client, admin, posta):
        ctp, sorella = _controparte("pari", ambiti=("trasferimenti:scrittura",))
        r = ctp.cifrato(client, "POST", "/api/v1/trasferimenti", _richiesta(),
                        extra={"Idempotency-Key": "trasferimento-0001"})  # fmt: skip
        assert r.status_code == 201, r.content
        t = TrasferimentoEsterno.objects.get(direzione="entrata")
        assert t.nome == "Bianchi Laura" and t.cliente == sorella and t.dati
        trasferimenti.accogli(t, admin)
        t.refresh_from_db()
        socio = Socio.objects.get(soggetto__codice_fiscale=CF_BIANCHI)
        assert t.stato == "accolto" and t.socio == socio and t.dati == {} and t.esito_inviato
        assert socio.data_ammissione == date(2015, 3, 1) and socio.tessere.get(anno=ANNO).pagata
        assert posta[-1][0] == f"/trasferimenti/{t.uuid}/esito"
        assert posta[-1][1]["esito"] == "accolto"
        # verso la federazione la riga dice da dove arriva
        assert allineamento.elenco(socio.sezione)[0]["trasferito_da"] == "009"

    def test_senza_ambito_rifiutato(self, client):
        ctp, _ = _controparte("pari", ambiti=())
        r = ctp.cifrato(client, "POST", "/api/v1/trasferimenti", _richiesta(),
                        extra={"Idempotency-Key": "trasferimento-0002"})  # fmt: skip
        assert r.status_code == 403

    def test_respingi_richiede_il_motivo(self, admin, posta):
        _, sorella = _controparte("pari")
        t = trasferimenti.ricevi(sorella, _richiesta())
        with pytest.raises(trasferimenti.OperazioneNonValida, match="motivo"):
            trasferimenti.respingi(t, admin, "")
        trasferimenti.respingi(t, admin, "non residente")
        assert t.stato == "respinto" and t.dati == {}

    def test_esito_non_inviato_si_riprova(self, admin, monkeypatch):
        _, sorella = _controparte("pari")
        t = trasferimenti.ricevi(sorella, _richiesta())

        def guasto(*a, **k):
            raise trasferimenti.client.ErroreCollegamento("giù")

        monkeypatch.setattr(trasferimenti.client, "chiama", guasto)
        trasferimenti.respingi(t, admin, "doppione")
        assert not TrasferimentoEsterno.objects.get(pk=t.pk).esito_inviato
        monkeypatch.setattr(trasferimenti.client, "chiama",
                            lambda *a, **k: (_Risposta(200), None, []))  # fmt: skip
        assert trasferimenti.invia_esiti_sospesi() == 1


class TestFederazione:
    """Siamo la federazione: il socio passa dalla sezione A (Ruoti) alla B (Avigliano)."""

    def test_sposta_il_socio_fra_le_sezioni(self, admin, avigliano, monkeypatch):
        ruoti = Sezione.objects.create(codice="009", nome="Ruoti")
        socio = _socio(admin, ruoti, "Rossi", "Mario", CF_ROSSI)
        _, sez_b = _controparte("sezione", avigliano)
        riga = _remota("Rossi", "Mario", CF_ROSSI, trasferito_da="009")
        monkeypatch.setattr(allineamento_soci, "scarica", lambda c: [riga])
        v = allineamento_soci.verifica(sez_b, admin)
        voce = v.proposta["voci"][0]
        assert voce["stato"] == "differenze" and voce["trasferimento"] == "009"
        assert voce["modifiche"][0] == ["sezione", "Ruoti", "Avigliano"]
        allineamento_soci.applica(v, [0], admin)
        socio.refresh_from_db()
        assert socio.sezione == avigliano and socio.stato == Socio.Stato.ATTIVO
        assert socio.trasferimenti.get().da == ruoti

    def test_la_cessazione_per_trasferimento_non_fa_cessare(self, admin, avigliano, monkeypatch):
        ruoti = Sezione.objects.create(codice="009", nome="Ruoti")
        socio = _socio(admin, ruoti, "Rossi", "Mario", CF_ROSSI)
        _, sez_a = _controparte("sezione", ruoti)
        riga = _remota("Rossi", "Mario", CF_ROSSI, stato_socio="cessato",
                       data_cessazione=str(date.today()),
                       causa_cessazione="Trasferimento ad altra sezione")  # fmt: skip
        monkeypatch.setattr(allineamento_soci, "scarica", lambda c: [riga])
        v = allineamento_soci.verifica(sez_a, admin)
        assert v.proposta["conteggi"]["invariato"] == 1
        # e se è già stato spostato altrove, la riga della vecchia sezione non lo segnala
        Socio.objects.filter(pk=socio.pk).update(sezione=avigliano)
        v = allineamento_soci.verifica(sez_a, admin)
        assert v.proposta["voci"][0]["stato"] == "invariato"


class TestViste:
    def test_pagine(self, client_ruolo, monkeypatch):
        utente = client_ruolo("Amministratore di sistema")
        socio = _socio(utente.utente, Sezione.predefinita(), "Rossi", "Mario", CF_ROSSI)
        _, sorella = _controparte("pari")
        pagina = utente.get(reverse("soci:dettaglio", args=[socio.pk])).content.decode()
        assert "Trasferisci a un&#x27;altra sezione collegata" in pagina or \
            "Trasferisci a un'altra sezione collegata" in pagina  # fmt: skip
        r = utente.get(reverse("soci:trasferisci_collegata", args=[socio.pk]))
        assert sorella.nome in r.content.decode()
        t = trasferimenti.ricevi(sorella, _richiesta())
        r = utente.get(reverse("soci:trasferimenti_esterni")).content.decode()
        assert "Bianchi Laura" in r
        r = utente.get(t.get_absolute_url()).content.decode()
        assert "Accogli" in r and "domanda scritta" in r

    def test_verifica_tessera_sconosciuta(self, client_ruolo):
        utente = client_ruolo("Amministratore di sistema")
        r = utente.get(reverse("soci:verifica_tessera_collegata") + "?codice=xyz")
        assert "Codice sconosciuto" in r.content.decode()


def test_eventi_e_cariche_anche_fra_sezioni_pari(avigliano, monkeypatch):
    from apps.collegamenti import condivisi

    _, sorella = _controparte("pari")
    letti = []

    def leggi(cliente, percorso):
        letti.append(percorso)
        return {"risultati": [], "successivo": None} if percorso.startswith("/eventi") else []

    monkeypatch.setattr(condivisi, "_leggi", leggi)
    condivisi.aggiorna(sorella)
    assert "/organigramma" in letti and not any(p.startswith("/tesseramento") for p in letti)
    assert any(p.startswith("/eventi") for p in letti)
    assert timedelta  # usato per coerenza con gli altri test
