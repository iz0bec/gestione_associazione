# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test dell'importazione da Gestione Soci (database SQLite sintetico)
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import sqlite3
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.anagrafica.models import Soggetto
from apps.migrazione import gestione_soci
from apps.migrazione.comune import FonteNonValida
from apps.patrimonio.models import Bene
from apps.soci.models import Sezione, Socio, TipologiaSocio
from apps.tesoreria.models import Esercizio, Movimento

CF_ROSSI = "RSSMRA50C15A519V"
CF_BIANCHI = "BNCLRA80A41F205G"
ANNO = timezone.localdate().year - 1

SCHEMA = """
create table soci (id integer primary key, nome, cognome, sesso, data_nascita, luogo_nascita,
  codice_fiscale, indirizzo, citta, cap, telefono, email, anno_iscrizione, foto, sezione);
create table tessere (id integer primary key, numero, anno, data_rilascio, data_scadenza,
  quota_versata, note, socio_id);
create table movimenti (id integer primary key, data, tipo, importo, descrizione, categoria,
  causale, numero_documento);
create table anni_contabili (id integer primary key, anno, saldo_iniziale, saldo_finale, chiuso);
create table beni_patrimoniali (id integer primary key, nome, descrizione, categoria,
  modalita_acquisizione, data_acquisizione, valore_acquisizione, valore_attuale,
  numero_inventario, ubicazione, stato_conservazione, documento_acquisizione, note);
create table valutazioni_beni (id integer primary key, bene_id, data_valutazione, valore,
  metodo_valutazione, note);
"""


@pytest.fixture(autouse=True)
def cartella_media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"


@pytest.fixture
def sorgente(tmp_path):
    percorso = tmp_path / "gest.db"
    conn = sqlite3.connect(percorso)
    conn.executescript(SCHEMA)
    conn.executemany(
        "insert into soci values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            (1, "MARIO", "ROSSI", "M", "1950-03-15", "AVIGLIANO", CF_ROSSI, "VIA ROMA 1",
             "RUOTI", "85056", "0971 1234", "mario@vecchio.it", 2010, "", "BAS / PZ / RUOTI"),
            (2, "Laura", "Bianchi", "F", "1980-01-01", "Milano", CF_BIANCHI, "", "Ruoti",
             "85056", "", "laura@vecchio.it", 2020, "foto.jpg", "BAS / PZ / RUOTI"),
            (3, "Ugo", "Altrove", "M", "1970-01-01", "Matera", "", "", "Matera", "", "", "",
             2015, "", "BAS / PZ / MATERA"),
        ],
    )  # fmt: skip
    conn.executemany(
        "insert into tessere values (?,?,?,?,?,?,?,?)",
        [
            (1, "031763", ANNO, f"{ANNO}-01-01", f"{ANNO + 1}-05-31", 5.0, "", 1),
            (2, "031764", ANNO, f"{ANNO}-02-01", f"{ANNO + 1}-05-31", 5.0, "", 2),
            (3, "031765", ANNO, f"{ANNO}-02-01", f"{ANNO + 1}-05-31", 5.0, "", 3),
        ],
    )
    conn.executemany(
        "insert into movimenti values (?,?,?,?,?,?,?,?)",
        [
            (1, f"{ANNO}-01-01", "ENTRATA", 5, "Quota tessera 31763", "quote_sociali", "", "T1"),
            (2, f"{ANNO}-02-01", "ENTRATA", 5, "Quota tessera 31764", "quote_sociali", "", "T2"),
            (3, f"{ANNO}-06-01", "USCITA", 7.5, "Francobolli", "posta", "", ""),
        ],
    )
    conn.execute("insert into anni_contabili values (1, ?, 100, 102.5, 0)", (ANNO,))
    conn.execute(
        "insert into beni_patrimoniali values (1,'Bandiera','Storica','Cimeli','DONAZIONE',"
        "'2001-05-01',0,300,'B-7','Sede','BUONO','','')"
    )
    conn.execute("insert into valutazioni_beni values (1, 1, '2024-01-01', 300, 'perizia', '')")
    conn.commit()
    conn.close()
    return percorso


@pytest.fixture
def ruoti():
    return Sezione.objects.create(codice="R01", nome="ANCR Ruoti", comune="Ruoti", provincia="PZ")


def _opzioni(**extra):
    return gestione_soci.Opzioni(tipologia=TipologiaSocio.objects.get(nome="Ordinario"), **extra)


@pytest.mark.django_db
class TestGestioneSoci:
    def test_anteprima_non_modifica(self, sorgente, ruoti):
        r = gestione_soci.importa(sorgente, _opzioni(), None)
        assert r.conteggi()["Soci"] == {"nuovo": 2, "errore": 1}  # Matera: sezione assente
        assert not Socio.objects.exists() and not Esercizio.objects.filter(anno=ANNO).exists()

    def test_importa_tutto(self, sorgente, ruoti):
        r = gestione_soci.importa(sorgente, _opzioni(), None, esegui=True)
        rossi = Socio.objects.get(soggetto__codice_fiscale=CF_ROSSI)
        assert rossi.sezione == ruoti and rossi.data_ammissione.year == 2010
        assert rossi.soggetto.cognome == "Rossi" and rossi.soggetto.comune == "Ruoti"
        tessera = rossi.tessere.get(anno=ANNO)
        assert tessera.carta.numero == 31763 and tessera.importo == Decimal("5.00")
        assert tessera.pagata and tessera.incasso_esterno
        # tesoreria: esercizio passato con saldo iniziale, movimenti e chiusura
        es = Esercizio.objects.get(anno=ANNO)
        assert es.stato == Esercizio.Stato.CHIUSO
        assert es.movimenti.count() == 3
        assert es.movimenti.get(descrizione="Francobolli").voce.codice == "U.E.2.3"
        assert es.saldi.get(conto__nome="Cassa").finale == Decimal("102.50")
        assert not any("saldo finale" in a for a in r.avvisi)
        assert Esercizio.objects.get(anno=ANNO + 1).saldi.get(conto__nome="Cassa").iniziale == (
            Decimal("102.50")
        )
        # le quote non finiscono due volte in prima nota
        assert not Movimento.objects.filter(tessera__isnull=False).exists()
        bene = Bene.objects.get(nome="Bandiera")
        assert bene.codice_precedente == "B-7" and bene.valore == Decimal("300")
        assert bene.valutazioni.get().metodo == "perizia"

    def test_rieseguibile(self, sorgente, ruoti):
        gestione_soci.importa(sorgente, _opzioni(), None, esegui=True)
        r = gestione_soci.importa(sorgente, _opzioni(), None, esegui=True)
        assert r.conteggi()["Soci"]["invariato"] == 2
        assert Socio.objects.count() == 2 and Bene.objects.count() == 1
        assert Movimento.objects.count() == 3

    def test_prevalgono_i_dati_locali(self, sorgente, ruoti):
        s = Soggetto.objects.create(
            tipo=Soggetto.Tipo.PERSONA, cognome="Bianchi", nome="Laura",
            codice_fiscale=CF_BIANCHI, email="laura@registro.it",
        )  # fmt: skip
        r = gestione_soci.importa(sorgente, _opzioni(), None, esegui=True)
        s.refresh_from_db()
        assert s.email == "laura@registro.it"  # non sovrascritta
        assert s.cap == "85056"  # completata
        voce = next(v for v in r.parti["Soci"] if "Bianchi" in v.descrizione)
        assert any("non sovrascritti: email" in n for n in voce.note)
        assert any("foto" in n for n in voce.note)

    def test_crea_sezioni(self, sorgente, ruoti):
        gestione_soci.importa(sorgente, _opzioni(crea_sezioni=True), None, esegui=True)
        assert Socio.objects.get(soggetto__cognome="Altrove").sezione.comune == "Matera"

    def test_database_sbagliato(self, tmp_path):
        altro = tmp_path / "altro.db"
        sqlite3.connect(altro).execute("create table x (id)").connection.close()
        with pytest.raises(FonteNonValida):
            gestione_soci.importa(altro, _opzioni(), None)

    def test_comando(self, sorgente, ruoti, capsys):
        call_command("importa_gestionale", "gestione-soci", str(sorgente))
        uscita = capsys.readouterr().out
        assert "ANTEPRIMA" in uscita and "Soci: errore 1, nuovo 2" in uscita
        assert not Socio.objects.exists()
