# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test dei bandi (P2): registro, requisiti verificati sui dati del gestionale e a
# *              mano, candidatura dei progetti, promemoria rieseguibili, calendario, pagine.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from datetime import date, timedelta
from unittest import mock

import pytest
from django.urls import reverse

from apps.core.models import Organizzazione
from apps.progetti import requisiti, servizi
from apps.progetti.forms import BandoForm, ProgettoForm
from apps.progetti.models import Bando, Progetto

pytestmark = pytest.mark.django_db

OGGI = date.today()


@pytest.fixture
def utente(crea_utente):
    return crea_utente("presidente", ruoli=["Presidente"])


def _bando(utente, **extra):
    dati = {"titolo": "Memoria e territorio 2027", "finanziatore_testo": "Regione Basilicata",
            "scadenza": OGGI + timedelta(days=30)} | extra  # fmt: skip
    form = BandoForm(data=dati)
    assert form.is_valid(), form.errors
    return servizi.crea_bando(form, utente)


def _progetto(utente):
    form = ProgettoForm(data={"titolo": "Memoria a scuola", "sintesi": "Incontri",
                              "responsabile": utente.pk})  # fmt: skip
    assert form.is_valid(), form.errors
    return servizi.crea_progetto(form, utente)


class TestRequisiti:
    def test_dati_organizzazione(self, utente):
        org = Organizzazione.corrente()
        org.iscrizione_runts, org.provincia, org.comune, org.pec = "12345", "PZ", "Potenza", ""
        org.save()
        b = _bando(utente)
        servizi.aggiungi_requisito(b, utente, descrizione="", verifica="runts")
        servizi.aggiungi_requisito(b, utente, descrizione="Sede in Basilicata",
                                   verifica="sede_provincia", parametro="PZ, MT")  # fmt: skip
        servizi.aggiungi_requisito(b, utente, descrizione="", verifica="pec")
        servizi.aggiungi_requisito(b, utente, descrizione="Statuto registrato")
        r = requisiti.riepilogo(b)
        assert [e.esito for e in r["esiti"]] == ["si", "si", "no", "verificare"]
        assert r["esiti"][0].requisito.descrizione == "Iscrizione al RUNTS"
        assert (r["soddisfatti"], r["mancanti"], r["da_verificare"]) == (2, 1, 1)
        assert not r["tutti"]

    def test_esito_a_mano_prevale(self, utente):
        b = _bando(utente)
        req = servizi.aggiungi_requisito(b, utente, descrizione="", verifica="pec")
        assert requisiti.esito(req).esito == "no"
        servizi.indica_esito(req, utente, esito="si", nota="PEC della federazione, delega")
        e = requisiti.esito(req)
        assert e.esito == "si" and not e.automatico and "delega" in e.spiegazione
        servizi.indica_esito(req, utente, esito="")
        assert requisiti.esito(req).automatico

    def test_soci_e_parametri(self, utente):
        b = _bando(utente)
        with pytest.raises(servizi.OperazioneNonValida, match="numero intero"):
            servizi.aggiungi_requisito(b, utente, descrizione="", verifica="soci_attivi",
                                       parametro="tanti")  # fmt: skip
        with pytest.raises(servizi.OperazioneNonValida, match="parametro"):
            servizi.aggiungi_requisito(b, utente, descrizione="", verifica="sede_comune")
        req = servizi.aggiungi_requisito(b, utente, descrizione="", verifica="soci_attivi",
                                         parametro="30")  # fmt: skip
        e = requisiti.esito(req)
        assert e.esito == "no" and "0 soci attivi" in e.spiegazione

    def test_rendiconto(self, utente):
        from apps.tesoreria.models import Esercizio

        b = _bando(utente)
        req = servizi.aggiungi_requisito(b, utente, descrizione="", verifica="rendiconto")
        assert requisiti.esito(req).esito == "verificare"  # nessun esercizio
        Esercizio.objects.create(anno=OGGI.year - 1, stato="chiuso",
                                 approvazione="Assemblea del 20/04, delibera 2")  # fmt: skip
        assert requisiti.esito(req).esito == "si"


class TestCandidatura:
    def test_candida(self, utente):
        b, p = _bando(utente), _progetto(utente)
        servizi.candida(p, b, utente)
        b.refresh_from_db()
        assert p.stato == Progetto.Stato.CANDIDATO and p.bando == b
        assert b.stato == Bando.Stato.PARTECIPATO
        assert "Memoria e territorio" in p.passaggi.get(a="candidato").motivo
        with pytest.raises(servizi.OperazioneNonValida, match="in progettazione"):
            servizi.candida(p, b, utente)

    def test_bando_scaduto_o_scartato(self, utente):
        p = _progetto(utente)
        scaduto = _bando(utente, scadenza=OGGI - timedelta(days=1))
        with pytest.raises(servizi.OperazioneNonValida, match="scaduto"):
            servizi.candida(p, scaduto, utente)
        b = _bando(utente)
        with pytest.raises(servizi.OperazioneNonValida, match="perché"):
            servizi.cambia_stato_bando(b, Bando.Stato.SCARTATO, utente)
        servizi.cambia_stato_bando(b, Bando.Stato.SCARTATO, utente, "Fuori dalle finalità")
        with pytest.raises(servizi.OperazioneNonValida, match="scartato"):
            servizi.candida(p, b, utente)


class TestPromemoria:
    def test_soglie_una_volta(self, utente):
        b = _bando(utente, scadenza=OGGI + timedelta(days=6))
        _bando(utente, titolo="Lontano", scadenza=OGGI + timedelta(days=40))
        with mock.patch("apps.core.avvisi.avvisa") as avvisa:
            assert servizi.promemoria_bandi() == 1
            assert servizi.promemoria_bandi() == 0  # rieseguibile
            assert servizi.promemoria_bandi(OGGI + timedelta(days=5)) == 1  # 1 giorno prima
            assert servizi.promemoria_bandi(OGGI + timedelta(days=5)) == 0
        assert avvisa.call_count == 2 and avvisa.call_args.args[0] == "bandi"
        assert "domani" in avvisa.call_args.args[1]
        b.refresh_from_db()
        assert b.promemoria == [2, 7]

    def test_partecipato_non_avvisato(self, utente):
        b = _bando(utente, scadenza=OGGI + timedelta(days=3))
        servizi.cambia_stato_bando(b, Bando.Stato.PARTECIPATO, utente)
        with mock.patch("apps.core.avvisi.avvisa") as avvisa:
            assert servizi.promemoria_bandi() == 0
        avvisa.assert_not_called()

    def test_nuova_scadenza_azzera(self, utente):
        b = _bando(utente, scadenza=OGGI + timedelta(days=3))
        with mock.patch("apps.core.avvisi.avvisa"):
            servizi.promemoria_bandi()
        form = BandoForm(data={"titolo": b.titolo, "finanziatore_testo": "Regione",
                               "scadenza": OGGI + timedelta(days=20)}, instance=b)  # fmt: skip
        assert form.is_valid()
        servizi.modifica_bando(form, utente)
        b.refresh_from_db()
        assert b.promemoria == []

    def test_calendario(self, utente):
        from apps.calendario import servizi as calendario

        b = _bando(utente, scadenza=OGGI + timedelta(days=4))
        titoli = [e.titolo for e in calendario.eventi(utente, dal=OGGI, al=OGGI + timedelta(10))]
        assert f"Scadenza bando: {b}" in titoli


class TestPagine:
    def test_percorso(self, client_ruolo):
        c = client_ruolo("Segretario")
        r = c.post(
            reverse("progetti:bando_nuovo"),
            {
                "titolo": "Bando cultura",
                "finanziatore_testo": "Fondazione",
                "scadenza": (OGGI + timedelta(9)).isoformat(),
                "importo_massimo": "15000",
            },
            follow=True,
        )
        assert "Bando cultura" in r.content.decode()
        b = Bando.objects.get()
        r = c.post(
            reverse("progetti:bando_azione", args=[b.pk, "requisito"]),
            {"verifica": "codice_fiscale", "parametro": "", "descrizione": ""},
            follow=True,
        )
        assert "Codice fiscale dell&#x27;ente" in r.content.decode()
        assert c.get(reverse("progetti:bandi")).status_code == 200
        p = _progetto(c.utente)
        r = c.post(
            reverse("progetti:progetto_azione", args=[p.pk, "candida"]),
            {"bando": b.pk},
            follow=True,
        )
        assert "candidato al bando" in r.content.decode()
        assert c.get(reverse("core:cruscotto")).status_code == 200

    def test_consigliere_consulta_soltanto(self, client_ruolo, utente):
        b = _bando(utente)
        c = client_ruolo("Consigliere")
        assert c.get(b.get_absolute_url()).status_code == 200
        r = c.post(reverse("progetti:bando_azione", args=[b.pk, "stato"]), {"stato": "scartato"})
        assert r.status_code == 403
        assert c.get(reverse("progetti:bando_nuovo")).status_code == 403

    def test_avvisi_per_chi_gestisce_i_bandi(self, client_ruolo):
        from apps.core import avvisi

        c = client_ruolo("Progettista")
        with mock.patch.object(
            avvisi, "canali_disponibili", return_value=[("telegram", "Telegram")]
        ):
            r = c.get(reverse("core:avvisi"))
        assert r.status_code == 200 and "Scadenze dei bandi" in r.content.decode()
