# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test dell'anagrafica
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from datetime import date

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.anagrafica.forms import SoggettoForm
from apps.anagrafica.models import Categoria, Soggetto
from apps.anagrafica.validatori import valida_codice_fiscale, valida_partita_iva
from apps.core.models import EventoAudit

CF_ROSSI = "RSSMRA50C15A519V"  # Rossi Mario, M, 15/03/1950


class TestValidatori:
    def test_codice_fiscale(self):
        valida_codice_fiscale(CF_ROSSI)
        valida_codice_fiscale(CF_ROSSI.lower())
        with pytest.raises(ValidationError):
            valida_codice_fiscale("RSSMRA50C15A519X")

    def test_partita_iva(self):
        valida_partita_iva("00743110157")
        with pytest.raises(ValidationError):
            valida_partita_iva("00743110158")
        with pytest.raises(ValidationError):
            valida_partita_iva("123")


@pytest.mark.django_db
class TestModello:
    def test_vincolo_nome_obbligatorio(self):
        with pytest.raises(IntegrityError):
            Soggetto.objects.create(tipo="persona", nome="Senza cognome")

    def test_normalizzazione(self):
        s = Soggetto.objects.create(
            cognome="Rossi",
            codice_fiscale=" rssmra50c15a519v ",
            email="Mario@Example.ORG",
            provincia="pz",
        )
        assert (
            s.codice_fiscale == CF_ROSSI and s.email == "mario@example.org" and s.provincia == "PZ"
        )

    def test_codice_fiscale_vuoto_non_duplica(self):
        Soggetto.objects.create(cognome="A", codice_fiscale="")
        Soggetto.objects.create(cognome="B", codice_fiscale="")
        assert Soggetto.objects.filter(codice_fiscale__isnull=True).count() == 2

    def test_compleanni(self):
        oggi = date(2026, 2, 25)
        Soggetto.objects.create(cognome="Vicino", data_nascita=date(1940, 3, 1))
        Soggetto.objects.create(cognome="Bisestile", data_nascita=date(1944, 2, 29))
        Soggetto.objects.create(cognome="Lontano", data_nascita=date(1940, 6, 1))
        Soggetto.objects.create(
            cognome="Defunto", data_nascita=date(1930, 2, 26), data_decesso=date(2020, 1, 1)
        )
        nomi = [p.cognome for p in Soggetto.compleanni_prossimi(giorni=7, oggi=oggi)]
        assert nomi == ["Vicino", "Bisestile"] or nomi == ["Bisestile", "Vicino"]
        assert "Defunto" not in nomi and "Lontano" not in nomi

    def test_ricerca(self):
        Soggetto.objects.create(cognome="Verdi", nome="Giuseppe", comune="Avigliano")
        Soggetto.objects.create(tipo="ente", denominazione="Comune di Potenza")
        assert Soggetto.objects.ricerca("giuseppe avigliano").count() == 1
        assert Soggetto.objects.ricerca("potenza").count() == 1


@pytest.mark.django_db
class TestModulo:
    def dati(self, **extra):
        base = {"tipo": "persona", "cognome": "Rossi", "nome": "Mario", "nazione": "IT"}
        base.update(extra)
        return base

    def test_completa_dati_da_codice_fiscale(self):
        form = SoggettoForm(data=self.dati(codice_fiscale=CF_ROSSI))
        assert form.is_valid(), form.errors
        s = form.save()
        assert (
            s.sesso == "M"
            and s.data_nascita == date(1950, 3, 15)
            and "Avigliano" in s.luogo_nascita
        )

    def test_segnala_incoerenza_col_codice_fiscale(self):
        form = SoggettoForm(data=self.dati(codice_fiscale=CF_ROSSI, sesso="F"))
        assert not form.is_valid() and "sesso" in form.errors

    def test_ente_richiede_denominazione(self):
        form = SoggettoForm(data={"tipo": "ente", "nazione": "IT"})
        assert not form.is_valid() and "denominazione" in form.errors


@pytest.mark.django_db
class TestViste:
    def test_anonimo_rimandato_al_login(self, client):
        assert client.get("/anagrafica/").status_code == 302

    def test_senza_permesso_403(self, client, crea_utente):
        client.force_login(crea_utente("nessuno"))
        assert client.get("/anagrafica/").status_code == 403

    def test_elenco_e_ricerca_htmx(self, client_ruolo):
        c = client_ruolo("Consigliere")
        Soggetto.objects.create(cognome="Bianchi", nome="Anna")
        Soggetto.objects.create(cognome="Neri", nome="Paolo")
        pagina = c.get("/anagrafica/")
        assert pagina.status_code == 200 and "Bianchi" in pagina.content.decode()
        parziale = c.get("/anagrafica/?q=bianchi", HTTP_HX_REQUEST="true").content.decode()
        assert "Bianchi" in parziale and "Neri" not in parziale and "<html" not in parziale

    def test_consigliere_non_modifica(self, client_ruolo):
        s = Soggetto.objects.create(cognome="Rossi")
        c = client_ruolo("Consigliere")
        assert c.get(f"/anagrafica/{s.pk}/modifica/").status_code == 403
        assert c.post(f"/anagrafica/{s.pk}/archivia/", {"azione": "archivia"}).status_code == 403

    def test_inserimento_e_modifica_registrati(self, client_ruolo):
        c = client_ruolo("Segretario")
        socio = Categoria.objects.get(nome="Socio")
        r = c.post("/anagrafica/nuovo/", {
            "tipo": "persona", "cognome": "Gialli", "nome": "Ugo", "nazione": "IT",
            "categorie": [socio.pk],
        })  # fmt: skip
        s = Soggetto.objects.get(cognome="Gialli")
        assert r.status_code == 302 and s.creato_da == c.utente and socio in s.categorie.all()
        c.post(f"/anagrafica/{s.pk}/modifica/", {
            "tipo": "persona", "cognome": "Gialli", "nome": "Ugo", "nazione": "IT",
            "comune": "Avigliano", "categorie": [socio.pk],
        })  # fmt: skip
        eventi = EventoAudit.objects.filter(oggetto_id=str(s.pk)).order_by("id")
        assert [e.azione for e in eventi] == ["creazione", "modifica"]
        assert list(eventi[1].dettagli["campi"]) == ["comune"]

    def test_archiviazione(self, client_ruolo):
        s = Soggetto.objects.create(cognome="Rossi")
        c = client_ruolo("Segretario")
        c.post(f"/anagrafica/{s.pk}/archivia/", {"azione": "archivia"})
        s.refresh_from_db()
        assert not s.attivo
        tabella = c.get("/anagrafica/", HTTP_HX_REQUEST="true").content.decode()
        assert "Rossi" not in tabella
        archiviati = c.get("/anagrafica/?stato=archiviati", HTTP_HX_REQUEST="true").content.decode()
        assert "Rossi" in archiviati

    def test_esportazione(self, client_ruolo):
        Soggetto.objects.create(cognome='=HYPERLINK("http://x")', nome="Mario")
        assert (
            client_ruolo("Consigliere", username="c1").get("/anagrafica/esporta.csv").status_code
            == 403
        )
        r = client_ruolo("Segretario", username="s1").get("/anagrafica/esporta.csv")
        testo = r.content.decode("utf-8-sig")
        assert r.status_code == 200 and "'=HYPERLINK" in testo
        assert EventoAudit.objects.filter(azione="esportazione").exists()

    def test_consenso(self, client_ruolo):
        s = Soggetto.objects.create(cognome="Rossi")
        c = client_ruolo("Segretario")
        c.post(
            f"/anagrafica/{s.pk}/consenso/",
            {"finalita": "auguri", "prestato": "on", "data": "2026-01-10"},
        )
        assert s.consensi.get().finalita == "auguri"
