# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test dell'importazione dal Protocollo ANCR (schema PostgreSQL sintetico)
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import json
from datetime import datetime

import pytest
from django.db import connection
from django.utils import timezone
from psycopg.conninfo import make_conninfo

from apps.anagrafica.models import Soggetto
from apps.comunicazioni.models import Lista
from apps.core.models import Sequenza
from apps.migrazione import protocollo
from apps.protocollo.models import Protocollo

SCHEMA = "vecchio_protocollo"
ANNO = timezone.localdate().year - 1


@pytest.fixture
def fonte(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path / "media"
    cartella = tmp_path / "uploads"
    (cartella / "emails").mkdir(parents=True)
    (cartella / "abc123.pdf").write_bytes(b"%PDF-1.4 lettera")
    (cartella / "emails" / "posta.txt").write_bytes(b"testo")
    allegati = json.dumps([
        {"filename": "abc123.pdf", "originalname": "Lettera prefettura.pdf",
         "path": "/x/abc123.pdf"},
        {"filename": "posta.txt", "path": "/uploads/emails/posta.txt"},
        {"filename": "manca.pdf"},
        {"filename": "../../segreto", "path": "/uploads/../../segreto"},
    ])  # fmt: skip
    with connection.cursor() as c:
        c.execute(f"drop schema if exists {SCHEMA} cascade; create schema {SCHEMA}")
        c.execute(f"set search_path to {SCHEMA}")
        c.execute("""
            create table users (id int primary key, username text, email text);
            create table contatti (id int primary key, nome text, cognome text,
              organizzazione text, email text, telefono text, indirizzo text, citta text,
              cap text, provincia text, tipo text, note text);
            create table liste_distribuzione (id int primary key, nome text, descrizione text);
            create table lista_distribuzione_contatti (lista_distribuzione_id int,
              contatto_id int);
            create table protocolli (id int primary key, numero_protocollo text, tipo text,
              canale text, oggetto text, mittente text, destinatario text,
              email_destinatario text, data_protocollo timestamptz, user_id int,
              allegati json, note text, status text, note_annullamento text);
            create table registri_giornalieri (id int primary key);
            insert into registri_giornalieri values (1);
        """)
        c.execute("insert into users values (1, 'segreteria', 'seg@example.org')")
        c.execute(
            "insert into contatti values "
            "(1, 'Mario', 'Rossi', '', 'mario@example.org', '0971', '', 'Ruoti', '', 'pz', "
            "'persona', ''),"
            "(2, '', '', 'Prefettura di Potenza', 'pref@pec.it', '', '', 'Potenza', '', '', "
            "'organizzazione', '')"
        )
        c.execute("insert into liste_distribuzione values (1, 'Istituzioni', '')")
        c.execute("insert into lista_distribuzione_contatti values (1, 2)")
        c.execute(
            "insert into protocolli values "
            "(1, %s, 'entrata', 'email', 'Invito cerimonia', 'Prefettura <pref@pec.it>', '',"
            " '', %s, 1, %s, 'urgente', 'attivo', null),"
            "(2, %s, 'uscita', 'cartaceo', 'Risposta', 'ANCR', 'Prefettura; Comune',"
            " 'pref@pec.it; comune@pec.it', %s, 1, null, '', 'annullato', 'doppione')",
            [f"{ANNO}-00001", datetime(ANNO, 3, 1, 10), allegati,
             f"{ANNO}-00007", datetime(ANNO, 3, 2, 9)],
        )  # fmt: skip
        c.execute("set search_path to public")
    d = connection.settings_dict
    dsn = make_conninfo(
        host=d["HOST"], port=str(d["PORT"]), dbname=d["NAME"], user=d["USER"],
        password=d["PASSWORD"], options=f"-c search_path={SCHEMA}",
    )  # fmt: skip
    yield dsn, cartella
    with connection.cursor() as c:
        c.execute(f"drop schema if exists {SCHEMA} cascade")


@pytest.mark.django_db(transaction=True)
class TestProtocollo:
    def test_anteprima(self, fonte):
        dsn, cartella = fonte
        r = protocollo.importa(dsn, None, cartella_allegati=cartella)
        assert r.conteggi()["Protocolli"] == {"nuovo": 2}
        assert not Protocollo.objects.exists()

    def test_importa_con_numeri_originali(self, fonte, crea_utente):
        dsn, cartella = fonte
        seg = crea_utente("seg")  # stessa email dell'operatore del vecchio protocollo
        Soggetto.objects.create(tipo=Soggetto.Tipo.PERSONA, cognome="Rossi", nome="Mario",
                                comune="Avigliano")  # fmt: skip
        r = protocollo.importa(dsn, None, cartella_allegati=cartella, esegui=True)
        p1 = Protocollo.objects.get(anno=ANNO, numero=1)
        assert p1.direzione == "entrata" and p1.mezzo == "email" and p1.creato_da == seg
        assert p1.registrato_il.date().isoformat() == f"{ANNO}-03-01"
        assert "urgente" in p1.note and "registrato da segreteria" in p1.note
        prefettura = Soggetto.objects.get(denominazione="Prefettura di Potenza")
        assert p1.mittenti[0].soggetto == prefettura
        nomi = sorted(a.nome for a in p1.allegati.all())
        assert nomi == ["Lettera prefettura.pdf", "posta.txt"]  # «manca» e «../segreto» no
        voce = next(v for v in r.parti["Protocolli"] if v.descrizione.startswith(f"{ANNO}-00001"))
        assert "2 documenti non trovati" in voce.note
        p7 = Protocollo.objects.get(anno=ANNO, numero=7)
        assert p7.annullato and p7.motivo_annullamento == "doppione"
        assert [c.indirizzo for c in p7.destinatari] == ["pref@pec.it", "comune@pec.it"]
        # la numerazione riprende dopo l'ultimo numero importato
        assert Sequenza.objects.get(chiave="protocollo", anno=ANNO).ultimo_numero == 7
        rossi = Soggetto.objects.get(cognome="Rossi")
        assert rossi.comune == "Avigliano" and rossi.email == "mario@example.org"
        assert list(Lista.objects.get(nome="Istituzioni").soggetti.all()) == [prefettura]
        assert any("registri_giornalieri" in a for a in r.avvisi)

    def test_rieseguibile(self, fonte):
        dsn, cartella = fonte
        protocollo.importa(dsn, None, cartella_allegati=cartella, esegui=True)
        r = protocollo.importa(dsn, None, cartella_allegati=cartella, esegui=True)
        assert r.conteggi()["Protocolli"] == {"invariato": 2}
        assert Protocollo.objects.count() == 2 and Soggetto.objects.count() == 2

    def test_anno_gia_usato_non_si_importa(self, fonte):
        from apps.protocollo.models import Corrispondente
        from apps.protocollo.servizi import registra_storico

        dsn, _ = fonte
        registra_storico(
            {"direzione": "interno", "oggetto": "Registrato qui"}, anno=ANNO, numero=1,
            registrato_il=timezone.now(), utente=None,
            corrispondenti=[{"ruolo": Corrispondente.Ruolo.MITTENTE, "descrizione": "Noi"}],
        )  # fmt: skip
        r = protocollo.importa(dsn, None, esegui=True)
        assert r.conteggi()["Protocolli"] == {"saltato": 2}
        assert any(f"Anno {ANNO}" in a for a in r.avvisi)
        assert Protocollo.objects.count() == 1
