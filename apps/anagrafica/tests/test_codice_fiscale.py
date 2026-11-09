# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test del codice fiscale assistito (calcolo, controllo, elenco e correzione)
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
from datetime import date

import pytest

from apps.anagrafica import codice_fiscale as cf
from apps.anagrafica.models import Soggetto
from apps.core.models import EventoAudit

CF_ROSSI = "RSSMRA50C15A519V"  # Rossi Mario, M, 15/03/1950, Avigliano
ROSSI = {
    "cognome": "Rossi", "nome": "Mario", "sesso": "M",
    "data_nascita": date(1950, 3, 15), "luogo_nascita": "Avigliano",
}  # fmt: skip


class TestLuoghi:
    @pytest.mark.parametrize(
        ("testo", "codice"),
        [
            ("Avigliano", "A519"),
            ("AVIGLIANO", "A519"),
            ("Avigliano (PZ)", "A519"),
            ("ACI SANT'ANTONIO", "A029"),  # apostrofo
            ("Bolzano/Bozen", "A952"),  # nome bilingue
            ("BOLZANO .BOZEN.", "A952"),  # come negli elenchi in maiuscolo
            ("AGLIE'", "A074"),  # accento scritto come apostrofo
            ("Baiardo", "A581"),  # «i» per «j» (Bajardo)
            ("Germania", "Z112"),  # stato estero
            ("Castro (LE)", "M261"),  # omonimo con provincia
        ],
    )
    def test_grafie_riconosciute(self, testo, codice):
        assert codice in [luogo.codice for luogo in cf.luoghi(testo)]

    def test_omonimi(self):
        assert [luogo.etichetta for luogo in cf.luoghi("Castro")] == ["Castro (BG)", "Castro (LE)"]

    def test_sconosciuto(self):
        assert cf.luoghi("Paese che non esiste") == []


class TestCalcolo:
    def test_calcolo(self):
        assert cf.calcola(**ROSSI).codice == CF_ROSSI

    def test_dati_mancanti(self):
        calcolo = cf.calcola(**{**ROSSI, "sesso": "", "luogo_nascita": ""})
        assert not calcolo.codice and "sesso" in calcolo.errore and "luogo" in calcolo.errore

    def test_comuni_omonimi_da_scegliere(self):
        nato_1980 = {**ROSSI, "data_nascita": date(1980, 1, 1)}
        calcolo = cf.calcola(**{**nato_1980, "luogo_nascita": "Castro"})
        assert not calcolo.codice and len(calcolo.candidati) == 2
        assert cf.calcola(**{**nato_1980, "luogo_nascita": "Castro (LE)"}).codice[11:15] == "M261"

    def test_comune_esistente_alla_nascita(self):
        # Castro (LE) esiste dal 1975: per un nato nel 1950 resta solo Castro (BG)
        assert cf.calcola(**{**ROSSI, "luogo_nascita": "Castro"}).codice[11:15] == "C337"

    def test_luogo_sconosciuto(self):
        assert "non è tra i comuni" in cf.calcola(**{**ROSSI, "luogo_nascita": "Atlantide"}).errore


class TestAnomalie:
    def test_coerente(self):
        assert cf.anomalie(CF_ROSSI, **ROSSI) == []

    def test_tutte_le_differenze(self):
        trovate = cf.anomalie(
            CF_ROSSI, cognome="Bianchi", nome="Luigi", sesso="F",
            data_nascita=date(1950, 3, 16), luogo_nascita="Potenza",
        )  # fmt: skip
        assert len(trovate) == 5

    def test_omocodia_coerente(self):
        from codicefiscale import codicefiscale

        variante = codicefiscale.decode(CF_ROSSI)["omocodes"][1]  # cifre sostituite da lettere
        assert variante != CF_ROSSI and codicefiscale.is_valid(variante)
        assert cf.anomalie(variante, **ROSSI) == []


@pytest.mark.django_db
class TestEsameECorrezione:
    def test_stati(self):
        corretto = Soggetto.objects.create(codice_fiscale=CF_ROSSI, **ROSSI)
        mancante = Soggetto.objects.create(**ROSSI)
        incoerente = Soggetto.objects.create(
            codice_fiscale=CF_ROSSI.replace("RSS", "BNC"), **{**ROSSI, "cognome": "Rossi"}
        )
        assert cf.esamina(corretto).stato == "corretto"
        esame = cf.esamina(mancante)
        assert esame.stato == "mancante"
        # stesso codice di «corretto»: proposto comunque, la correzione poi lo rifiuta
        assert esame.proposta == CF_ROSSI
        assert cf.esamina(incoerente).stato in ("non_valido", "incoerente")

    def test_proposta_impossibile_spiegata(self):
        s = Soggetto.objects.create(cognome="Verdi", nome="Anna")
        esame = cf.esamina(s)
        assert esame.stato == "mancante" and not esame.proposta and "servono" in esame.nota

    def test_correzione_registrata(self, crea_utente):
        utente = crea_utente()
        s = Soggetto.objects.create(**ROSSI)
        cf.correggi(s, CF_ROSSI.lower(), utente)
        s.refresh_from_db()
        assert s.codice_fiscale == CF_ROSSI
        evento = EventoAudit.objects.filter(oggetto_id=str(s.pk)).latest("pk")
        assert evento.dettagli["codice_fiscale"] == {"prima": "", "dopo": CF_ROSSI}

    def test_correzione_rifiutata(self, crea_utente):
        utente = crea_utente()
        Soggetto.objects.create(codice_fiscale=CF_ROSSI, **ROSSI)
        doppione = Soggetto.objects.create(**ROSSI)
        with pytest.raises(cf.OperazioneNonValida, match="già usato"):
            cf.correggi(doppione, CF_ROSSI, utente)
        altro = Soggetto.objects.create(**{**ROSSI, "cognome": "Bianchi"})
        with pytest.raises(cf.OperazioneNonValida, match="non corrisponde"):
            cf.correggi(altro, CF_ROSSI, utente)


@pytest.mark.django_db
class TestViste:
    def test_calcola(self, client_ruolo):
        c = client_ruolo("Segretario")
        dati = {**ROSSI, "data_nascita": "1950-03-15"}
        r = c.post("/anagrafica/codici-fiscali/calcola/", dati).json()
        assert r["codice"] == CF_ROSSI and not r["errore"]
        r = c.post(
            "/anagrafica/codici-fiscali/calcola/",
            {**dati, "codice_fiscale": CF_ROSSI.replace("15A", "16A")},
        ).json()
        assert r["codice"] == CF_ROSSI

    def test_calcola_senza_permesso(self, client, crea_utente):
        client.force_login(crea_utente("nessuno"))
        assert client.post("/anagrafica/codici-fiscali/calcola/", ROSSI).status_code == 403

    def test_elenco_e_applica(self, client_ruolo):
        sbagliato = Soggetto.objects.create(codice_fiscale="RSSMRA50C15A519X", **ROSSI)
        c = client_ruolo("Segretario")
        r = c.get("/anagrafica/codici-fiscali/")
        assert r.status_code == 200 and CF_ROSSI in r.content.decode()
        r = c.post(
            "/anagrafica/codici-fiscali/",
            {"soggetto": sbagliato.pk, "codice": CF_ROSSI, "stato": "non_valido"},
        )
        assert r.status_code == 302
        sbagliato.refresh_from_db()
        assert sbagliato.codice_fiscale == CF_ROSSI

    def test_consigliere_vede_ma_non_corregge(self, client_ruolo):
        s = Soggetto.objects.create(codice_fiscale="RSSMRA50C15A519X", **ROSSI)
        c = client_ruolo("Consigliere")
        assert c.get("/anagrafica/codici-fiscali/").status_code == 200
        r = c.post("/anagrafica/codici-fiscali/", {"soggetto": s.pk, "codice": CF_ROSSI})
        assert r.status_code == 403
