# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test dell'importazione da Gestione Assemblee (database SQLite sintetico)
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import sqlite3
from datetime import date

import pytest

from apps.anagrafica.models import Soggetto
from apps.comunicazioni.models import Modello
from apps.migrazione import assemblee

CF_ROSSI = "RSSMRA50C15A519V"


@pytest.fixture
def sorgente(tmp_path):
    percorso = tmp_path / "ancr.db"
    conn = sqlite3.connect(percorso)
    conn.executescript(
        """
        create table contatti (id integer primary key, nome, cognome, email, telefono, cellulare,
          indirizzo, citta, cap, provincia, data_nascita, luogo_nascita, codice_fiscale,
          professione, note);
        create table template_email (id integer primary key, nome, tipo, oggetto, corpo);
        create table assemblee (id integer primary key);
        insert into assemblee values (1);
        """
    )
    conn.executemany(
        "insert into contatti values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            (1, "MARIO", "ROSSI", "", "347-1234567", "", "", "RUOTI", "", "pz", "1950-03-15",
             "", CF_ROSSI, "Pensionato", ""),
            (2, "Ugo", "Verdi", "ugo@example.org", "0971 22", "", "", "", "", "", None, "", "",
             "", "nota"),
            (3, "Domenico", "Troiano", "", "", "", "", "", "", "", "1947-04-13", "",
             "TRNDNC47D13H641D", "", ""),
        ],
    )  # fmt: skip
    conn.execute(
        "insert into template_email values (1, 'Auguri', 'compleanno', 'Auguri {nome}',"
        " 'Caro {nome} {cognome}, buon compleanno da {organizzazione}. {mittente_nome}')"
    )
    conn.commit()
    conn.close()
    return percorso


def test_converti_segnaposto():
    testo, ignoti = assemblee.converti_segnaposto("Auguri di {festivita}, {nome}! {firma}")
    assert testo == "Auguri di {{ ricorrenza }}, {{ nome }}! [firma]"
    assert ignoti == {"firma"}


@pytest.mark.django_db
class TestAssemblee:
    def test_importa_e_completa(self, sorgente):
        rossi = Soggetto.objects.create(
            tipo=Soggetto.Tipo.PERSONA, cognome="Rossi", nome="Mario", codice_fiscale=CF_ROSSI,
            comune="Avigliano",
        )  # fmt: skip
        troiano = Soggetto.objects.create(
            tipo=Soggetto.Tipo.PERSONA, cognome="Troiano", nome="Domenica",
            codice_fiscale="TRNDNC47D53H641H", data_nascita=date(1947, 4, 13),
        )  # fmt: skip
        r = assemblee.importa(sorgente, None, esegui=True)
        assert r.conteggi()["Contatti"] == {"aggiornato": 1, "nuovo": 1, "invariato": 1}
        rossi.refresh_from_db()
        assert rossi.comune == "Avigliano"  # prevale il dato locale
        assert rossi.cellulare == "347-1234567" and rossi.telefono == ""
        assert rossi.qualifica == "Pensionato"
        troiano.refresh_from_db()
        assert troiano.codice_fiscale == "TRNDNC47D53H641H"  # niente doppione, CF non toccato
        verdi = Soggetto.objects.get(cognome="Verdi")
        assert verdi.email == "ugo@example.org" and verdi.note == "nota"
        modello = Modello.objects.get(nome__endswith="(da Gestione Assemblee)")
        assert not modello.attivo and "{{ organizzazione }}" in modello.corpo
        assert "[mittente_nome]" in modello.corpo
        assert any("assemblee: 1 righe" in a for a in r.avvisi)

    def test_anteprima_e_rieseguibile(self, sorgente):
        assemblee.importa(sorgente, None)
        assert not Soggetto.objects.exists()
        assemblee.importa(sorgente, None, esegui=True)
        r = assemblee.importa(sorgente, None, esegui=True)
        assert r.conteggi()["Contatti"] == {"invariato": 3}
        assert (
            Soggetto.objects.count() == 3
            and Modello.objects.filter(nome__endswith="Assemblee)").count() == 1
        )
