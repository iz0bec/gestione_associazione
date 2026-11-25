# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test dei dati condivisi fra federazione e sezioni (F4): numeri del
# *              tesseramento, cariche, eventi condivisi, iscrizione dei propri soci.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import uuid
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.api.models import DatiControparte
from apps.collegamenti import condivisi
from apps.eventi.models import Adesione, AdesioneInviata, Evento, EventoCondiviso
from apps.soci.models import Sezione

from . import test_verifica_soci as base
from .test_verifica_soci import ANNO, CF_BIANCHI, CF_ROSSI, _controparte, _socio

pytestmark = pytest.mark.django_db
_ambiente, admin, avigliano = base._ambiente, base.admin, base.avigliano


def _evento(**extra):
    dati = {"titolo": "Commemorazione provinciale", "inizio": timezone.now() + timedelta(days=9),
            "posti": 50, "accompagnatori": 1} | extra  # fmt: skip
    return Evento.objects.create(**dati)


class TestApi:
    def test_numeri_del_tesseramento(self, client, admin, avigliano):
        _socio(admin, avigliano, "Rossi", "Mario", CF_ROSSI)
        ctp, _ = _controparte("sezione", avigliano)
        r = ctp.chiama(client, "GET", f"/api/v1/tesseramento?anno={ANNO}")
        assert r.status_code == 200, r.content
        d = r.json()
        assert d["sezione"]["nome"] == "Avigliano" and d["anno"] == ANNO
        assert d["soci_attivi"] == 1 and d["cessati"] == 0
        assert "Rossi" not in r.content.decode()  # solo conteggi

    def test_campo_condiviso_negli_eventi(self, client, avigliano):
        _evento(titolo="Interno")
        _evento(titolo="Provinciale", condiviso=True)
        ctp, _ = _controparte("sezione", avigliano, ambiti=("eventi:lettura",))
        eventi = ctp.chiama(client, "GET", "/api/v1/eventi").json()["risultati"]
        condivisi_ = {e["titolo"]: e["condiviso"] for e in eventi}
        assert condivisi_ == {"Interno": False, "Provinciale": True}

    def test_adesione_da_una_sezione(self, client, avigliano):
        e = _evento(condiviso=True)
        ctp, cliente = _controparte("sezione", avigliano, ambiti=("adesioni:scrittura",))
        r = ctp.cifrato(client, "POST", f"/api/v1/eventi/{e.uuid}/adesioni",
                        {"cognome": "Bianchi", "nome": "Laura", "accompagnatori": 1},
                        extra={"Idempotency-Key": "adesione-sezione-01"})  # fmt: skip
        assert r.status_code == 201, r.content
        a = Adesione.objects.get(evento=e)
        assert a.cliente_api == cliente and a.accompagnatori == 1


class TestLettura:
    def test_cariche_numeri_ed_eventi(self, admin, avigliano, monkeypatch):
        _, sezione = _controparte("sezione", avigliano)
        u = str(uuid.uuid4())
        inizio = (timezone.now() + timedelta(days=3)).isoformat()
        risposte = {
            "/organigramma": [{"organo": "Consiglio direttivo", "tipo": "consiglio", "sezione": None,
                               "componenti": [{"ruolo": "presidente", "ruolo_descrizione": "Presidente",
                                               "nome": "Verdi Luigi", "dal": None}]}],
            f"/tesseramento?anno={ANNO}": {"anno": ANNO, "soci_attivi": 7, "tessere": 5},
        }  # fmt: skip

        def leggi(cliente, percorso):
            if percorso.startswith("/eventi"):
                return {"risultati": [{"uuid": u, "versione": 2, "titolo": "Gita a Redipuglia",
                                       "inizio": inizio, "luogo": "Redipuglia", "condiviso": True,
                                       "adesioni_aperte": True, "accompagnatori_max": 1}],
                        "successivo": None}  # fmt: skip
            if percorso.startswith("/tesseramento"):
                return risposte[f"/tesseramento?anno={ANNO}"]
            return risposte[percorso]

        monkeypatch.setattr(condivisi, "_leggi", leggi)
        assert condivisi.aggiorna(sezione) == "1 eventi condivisi"
        dati = condivisi.dati_di(sezione)
        assert dati["organigramma"].dati[0]["componenti"][0]["nome"] == "Verdi Luigi"
        assert dati["tesseramento"].dati["soci_attivi"] == 7
        e = EventoCondiviso.objects.get(cliente=sezione)
        assert e.titolo == "Gita a Redipuglia" and e.versione == 2
        # non più condiviso: sparisce (nessuno iscritto)
        monkeypatch.setattr(condivisi, "_leggi", lambda c, p: {"risultati": [], "successivo": None}
                            if p.startswith("/eventi") else {})  # fmt: skip
        condivisi.aggiorna_eventi(sezione)
        assert not EventoCondiviso.objects.exists()

    def test_errore_resta_sulla_voce(self, avigliano, monkeypatch):
        _, sezione = _controparte("sezione", avigliano)

        def guasto(c, p):
            raise condivisi.OperazioneNonValida(
                "la controparte non ci ha concesso l'ambito necessario"
            )

        monkeypatch.setattr(condivisi, "_leggi", guasto)
        assert condivisi.aggiorna(sezione).startswith("eventi:")
        voce = DatiControparte.objects.get(cliente=sezione, tipo="organigramma")
        assert "ambito" in voce.errore and voce.letto_il is None


class TestIscrizione:
    @pytest.fixture
    def evento(self):
        _, federazione = _controparte("federazione")
        return EventoCondiviso.objects.create(
            cliente=federazione, uuid=uuid.uuid4(), titolo="Cerimonia del 4 novembre",
            inizio=timezone.now() + timedelta(days=5), letto_il=timezone.now(),
            dati={"adesioni_aperte": True, "accompagnatori_max": 2},
        )  # fmt: skip

    def test_iscrivi_e_annulla(self, admin, evento, monkeypatch):
        socio = _socio(admin, Sezione.predefinita(), "Rossi", "Mario", CF_ROSSI)
        chiamate = []

        class Risposta:
            def __init__(self, stato):
                self.stato = stato

        def chiama(cliente, metodo, percorso, corpo=None, **opzioni):
            chiamate.append((metodo, percorso, corpo, opzioni.get("extra")))
            return Risposta(201 if metodo == "POST" else 204), None, []

        monkeypatch.setattr(condivisi.client, "chiama", chiama)
        monkeypatch.setattr(condivisi.client, "json_risposta",
                            lambda r: {"uuid": str(uuid.uuid4()), "versione": 1})  # fmt: skip
        a = condivisi.iscrivi(evento, socio.soggetto, admin, accompagnatori=1)
        assert chiamate[0][0] == "POST" and chiamate[0][2]["cognome"] == "Rossi"
        assert set(chiamate[0][2]) == {"cognome", "nome", "accompagnatori", "note",
                                       "riferimento_esterno"}  # fmt: skip
        with pytest.raises(condivisi.OperazioneNonValida, match="già iscritto"):
            condivisi.iscrivi(evento, socio.soggetto, admin)
        condivisi.annulla(a, admin)
        assert chiamate[1][0] == "DELETE" and chiamate[1][3] == {"If-Match": '"1"'}
        a.refresh_from_db()
        assert a.annullata

    def test_pagine(self, client_ruolo, evento, monkeypatch):
        utente = client_ruolo("Amministratore di sistema")
        bianchi = _socio(utente.utente, Sezione.predefinita(), "Bianchi", "Laura", CF_BIANCHI)
        r = utente.get(reverse("eventi:elenco")).content.decode()
        assert "Eventi delle installazioni collegate" in r and "Cerimonia del 4 novembre" in r
        pagina = utente.get(evento.get_absolute_url()).content.decode()
        assert "Iscrivi i nostri soci" in pagina and "Bianchi Laura" in pagina

        def iscrivi(ev, soggetto, u, **k):
            return AdesioneInviata.objects.create(evento=ev, soggetto=soggetto, cognome="Bianchi")

        monkeypatch.setattr(condivisi, "iscrivi", iscrivi)
        r = utente.post(evento.get_absolute_url(), {"soggetti": [bianchi.soggetto.pk],
                                                     "accompagnatori": 0}, follow=True)  # fmt: skip
        assert "Iscritti: 1." in r.content.decode()


def test_pagina_installazioni_collegate(client_ruolo, avigliano):
    utente = client_ruolo("Amministratore di sistema")
    _socio(utente.utente, avigliano, "Rossi", "Mario", CF_ROSSI)
    _, sezione = _controparte("sezione", avigliano)
    DatiControparte.objects.create(cliente=sezione, tipo="tesseramento", letto_il=timezone.now(),
                                   dati={"anno": ANNO, "soci_attivi": 3})  # fmt: skip
    r = utente.get(reverse("api:collegati")).content.decode()
    assert "Federazione e sezioni collegate" in r and "1 numero diverso" in r


def test_calendario_mostra_gli_eventi_condivisi(admin):
    from apps.calendario import servizi

    _, federazione = _controparte("federazione")
    EventoCondiviso.objects.create(cliente=federazione, uuid=uuid.uuid4(), titolo="Raduno",
                                   inizio=timezone.now() + timedelta(days=2),
                                   letto_il=timezone.now())  # fmt: skip
    oggi = timezone.localdate()
    titoli = [e.titolo for e in servizi.eventi(admin, dal=oggi, al=oggi + timedelta(days=10))]
    assert any(t.startswith("Raduno (") for t in titoli)
