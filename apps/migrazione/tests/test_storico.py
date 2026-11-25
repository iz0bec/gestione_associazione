# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test dell'importazione dello storico dai gestionali precedenti: foto dei soci,
# *              passaggi di consegne e cessioni dei beni (Gestione Soci), riunioni e verbali
# *              delle assemblee (Gestione Assemblee). Rieseguibile.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import io
import sqlite3

import pytest
from PIL import Image

from apps.anagrafica.models import Soggetto
from apps.migrazione import assemblee, gestione_soci
from apps.organi.models import Organo, Riunione
from apps.patrimonio.models import Bene, PassaggioConsegne, Uscita

from . import test_gestione_soci as base
from .test_gestione_soci import CF_BIANCHI, _opzioni

pytestmark = pytest.mark.django_db
# stesse fixture dell'importazione di Gestione Soci
cartella_media, ruoti, sorgente = base.cartella_media, base.ruoti, base.sorgente


@pytest.fixture
def storico(sorgente, tmp_path):
    """Il database di prova di Gestione Soci con passaggi, cessioni e la foto di un socio."""
    conn = sqlite3.connect(sorgente)
    conn.executescript(
        """
        create table passaggi_consegne (id integer primary key, consegnante_nome,
          consegnante_cognome, consegnante_ruolo, consegnante_data, ricevente_nome,
          ricevente_cognome, ricevente_ruolo, ricevente_data, note_osservazioni, data_creazione,
          utente_creazione_id, numero_beni_totali, valore_totale_patrimonio, pdf_filename);
        create table beni_passaggio_snapshot (id integer primary key, passaggio_consegne_id,
          bene_originale_id, nome, categoria, descrizione, numero_inventario, data_acquisizione,
          valore_acquisizione, valore_attuale, stato_conservazione, ubicazione, note,
          data_snapshot);
        create table cessioni_beni (id integer primary key, bene_id, tipo_cessione, data_cessione,
          data_restituzione_prevista, data_restituzione_effettiva, destinatario_nome,
          destinatario_cognome, destinatario_organizzazione, destinatario_codice_fiscale,
          destinatario_indirizzo, destinatario_telefono, destinatario_email, motivo_cessione,
          condizioni_cessione, valore_cessione, documento_cessione, numero_protocollo, stato,
          note, data_creazione, data_modifica, utente_creazione_id, utente_modifica_id,
          stato_restituzione, note_restituzione);
        insert into passaggi_consegne values (1, 'Mario', 'Rossi', 'Presidente', '07/08/2025',
          'Anna', 'Verdi', 'Presidente', '07/08/2025', 'Tutto in ordine', '2025-08-07 10:00:00',
          1, 1, 300, '');
        insert into beni_passaggio_snapshot values (1, 1, 1, 'Bandiera', 'Cimeli', '', 'B-7',
          '2001-05-01', 0, 300, 'BUONO', 'Sede', '', '2025-08-07');
        insert into cessioni_beni values (1, 1, 'PRESTITO', '2025-08-06', '2025-08-20',
          '2025-08-21', '', '', 'Comune di Ruoti', '', '', '', '', 'Mostra del 4 novembre', '',
          0, '', '2025-00012', 'RESTITUITA', '', '2025-08-06', '2025-08-21', 1, 1, 'BUONO', '');
        """
    )
    conn.commit()
    conn.close()
    soci = tmp_path / "uploads" / "soci"
    soci.mkdir(parents=True)
    buf = io.BytesIO()
    Image.new("RGB", (40, 50), (120, 30, 30)).save(buf, "JPEG")
    (soci / "foto.jpg").write_bytes(buf.getvalue())
    return sorgente, tmp_path / "uploads"


class TestGestioneSoci:
    def test_foto_passaggi_e_cessioni(self, storico, ruoti):
        db, uploads = storico
        r = gestione_soci.importa(db, _opzioni(cartella_file=str(uploads)), None, esegui=True)
        laura = Soggetto.objects.get(codice_fiscale=CF_BIANCHI)
        assert laura.foto and laura.foto.name.startswith("anagrafica/foto")
        p = PassaggioConsegne.objects.get()
        assert p.consegnante == "Mario Rossi" and p.ricevente_ruolo == "Presidente"
        assert p.numero_beni == 1 and p.beni[0]["codice"] == "B-7" and p.file and p.impronta
        u = Uscita.objects.get()
        assert u.tipo == "prestito" and u.restituito_il and u.rientro == "integro"
        assert "2025-00012" in u.condizioni and u.controparte_testo == "Comune di Ruoti"
        assert Bene.objects.get().stato == Bene.Stato.IN_DOTAZIONE
        assert not any("passaggi_consegne" in a or "cessioni" in a for a in r.avvisi)

    def test_rieseguibile_e_foto_aggiunta_dopo(self, storico, ruoti):
        db, uploads = storico
        gestione_soci.importa(db, _opzioni(cartella_file=str(uploads / "altrove")), None,
                              esegui=True)  # fmt: skip
        laura = Soggetto.objects.get(codice_fiscale=CF_BIANCHI)
        assert not laura.foto
        r = gestione_soci.importa(db, _opzioni(cartella_file=str(uploads)), None, esegui=True)
        laura.refresh_from_db()
        assert laura.foto
        assert PassaggioConsegne.objects.count() == 1 and Uscita.objects.count() == 1
        voci = {v.descrizione: v.stato for v in r.parti["Soci"]}
        assert voci["Bianchi Laura"] == "aggiornato"


@pytest.fixture
def assemblee_db(tmp_path):
    percorso = tmp_path / "ancr_gestione.db"
    conn = sqlite3.connect(percorso)
    conn.executescript(
        """
        create table contatti (id integer primary key, nome, cognome, email, telefono, cellulare,
          indirizzo, citta, cap, provincia, data_nascita, luogo_nascita, codice_fiscale,
          professione, note);
        create table template_email (id integer primary key, nome, tipo, oggetto, corpo);
        create table assemblee (id integer primary key, tipo, data_convocazione, luogo_prima_conv,
          data_prima_conv, luogo_seconda_conv, data_seconda_conv, punti_discussione, stato,
          created_at, created_by, protocollato, numero_protocollo, data_protocollazione,
          protocollo_id);
        create table verbali (id integer primary key, assemblea_id, data_riunione, luogo_riunione,
          num_partecipanti, presidente_riunione, segretario_riunione, punti_discussi,
          decisioni_votazioni, provvedimenti, firma_presidente, firma_segretario, luogo_firma,
          data_firma, created_at, created_by, protocollato, numero_protocollo,
          data_protocollazione, protocollo_id);
        insert into assemblee values (1, 'generale', '2025-03-01', 'Sede sociale',
          '2025-03-20 17:00:00', 'Sede sociale', '2025-03-20 18:00:00',
          'Relazione del presidente
Approvazione del rendiconto', 'completata', '2025-03-01', 1, 1, '2025-00031', '', null);
        insert into assemblee values (2, 'direttivo', '2025-05-01', 'Sede', '2025-05-10 18:00:00',
          '', null, 'Programma del 4 novembre', 'annullata', '2025-05-01', 1, 0, '', '', null);
        insert into verbali values (1, 1, '2025-03-20', 'Sede sociale', 23, 'Mario Rossi',
          'Anna Verdi', 'Discussione ampia', 'Rendiconto approvato all''unanimità', '',
          '', '', '', '', '', 1, 1, '2025-00040', '', null);
        """
    )
    conn.commit()
    conn.close()
    return percorso


class TestAssemblee:
    def test_riunioni_e_verbali(self, assemblee_db):
        assemblea = Organo.objects.filter(sezione=None, tipo="assemblea").first()
        consiglio = Organo.objects.filter(sezione=None, tipo="consiglio").first()
        if assemblea is None:
            assemblea = Organo.objects.create(
                nome="Assemblea dei soci", sigla="ASS", tipo="assemblea"
            )
        if consiglio is None:
            consiglio = Organo.objects.create(
                nome="Consiglio direttivo", sigla="CD", tipo="consiglio"
            )
        r = assemblee.importa(assemblee_db, None, esegui=True)
        a = Riunione.objects.get(organo=assemblea)
        assert a.luogo == "Sede sociale" and a.punti.count() == 2 and "2025-00031" in a.premessa
        v = a.verbale
        assert not v.chiuso and v.presidente == "Mario Rossi" and "unanimità" in v.varie
        d = Riunione.objects.get(organo=consiglio)
        assert d.stato == Riunione.Stato.ANNULLATA and not hasattr(d, "verbale")
        assert not any("assemblee" in x for x in r.avvisi)
        assemblee.importa(assemblee_db, None, esegui=True)
        assert Riunione.objects.count() == 2
