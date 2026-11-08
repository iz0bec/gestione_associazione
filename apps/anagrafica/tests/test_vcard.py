# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test dello scambio delle schede con le rubriche (vCard)
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from datetime import date

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.anagrafica import vcard
from apps.anagrafica.models import Categoria, Soggetto

VCF_MISTO = (
    # vCard 3.0 (Google/iPhone) con riga piegata ed escape
    "BEGIN:VCARD\r\nVERSION:3.0\r\nN:Bianchi;Anna;;Dott.;\r\nFN:Dott. Anna Bianchi\r\n"
    "EMAIL;TYPE=INTERNET:anna@example.org\r\nTEL;TYPE=CELL:+39 333 1234567\r\n"
    "ADR;TYPE=HOME:;;Via Roma\\, 5;Avigliano;PZ;85021;Italia\r\nBDAY:1970-05-02\r\n"
    "ORG:Comune di Avigliano\r\nTITLE:Assessore\r\nNOTE:Prima riga\\nseconda riga con un te\r\n"
    " sto piegato\r\nEND:VCARD\r\n"
    # vCard 2.1 (Android) in quoted-printable con gruppi
    "BEGIN:VCARD\nVERSION:2.1\nN;CHARSET=UTF-8;ENCODING=QUOTED-PRINTABLE:Nicol=C3=B2;Luc=C3=AC=\na;;;\n"
    "TEL;CELL:3471112223\nTEL;HOME:0971 123456\nTEL;CELL:3479998887\n"
    "item1.EMAIL;INTERNET:luca@pec.example.it\nEND:VCARD\n"
    # vCard 4.0: solo un ente
    "BEGIN:VCARD\nVERSION:4.0\nFN:Pro Loco Avigliano\nORG:Pro Loco Avigliano\n"
    "EMAIL:info@proloco.example.org\nBDAY:--0315\nPHOTO;ENCODING=b:AAAA\nEND:VCARD\n"
    # senza nome
    "BEGIN:VCARD\nVERSION:3.0\nTEL:123\nEND:VCARD\n"
)


@pytest.fixture
def rossi():
    s = Soggetto.objects.create(
        tipo="persona", titolo="Cav.", cognome="Rossi", nome="Mario", email="mario@example.org",
        cellulare="333 0000000", indirizzo="Via Garibaldi; 1", cap="85021", comune="Avigliano",
        provincia="PZ", data_nascita=date(1950, 3, 2), note="riservato",
    )  # fmt: skip
    s.categorie.add(Categoria.objects.create(nome="Reduci, combattenti"))
    return s


class TestLettura:
    def test_varianti_e_codifiche(self):
        anna, luca, ente, vuoto = vcard.leggi(VCF_MISTO.encode("utf-8"))
        assert anna.dati["cognome"] == "Bianchi" and anna.dati["titolo"] == "Dott."
        assert anna.dati["indirizzo"] == "Via Roma, 5" and anna.dati["cap"] == "85021"
        assert anna.dati["provincia"] == "PZ" and anna.dati["data_nascita"] == date(1970, 5, 2)
        assert anna.dati["cellulare"] == "+39 333 1234567"
        assert anna.dati["qualifica"] == "Assessore - Comune di Avigliano"
        assert anna.dati["note"] == "Prima riga\nseconda riga con un testo piegato"
        assert luca.dati["cognome"] == "Nicolò" and luca.dati["nome"] == "Lucìa"
        assert luca.dati["telefono"] == "0971 123456" and luca.altri == ["3479998887"]
        assert luca.dati["pec"] == "luca@pec.example.it" and "email" not in luca.dati
        assert ente.tipo == "ente" and ente.dati["denominazione"] == "Pro Loco Avigliano"
        assert "data_nascita" not in ente.dati
        assert vuoto.nome == ""

    def test_file_non_valido(self):
        with pytest.raises(vcard.FileNonValido):
            vcard.leggi(b"nome;cognome\nRossi;Mario\n")


@pytest.mark.django_db
class TestEsportazione:
    def test_vcard_rilegge_se_stessa(self, rossi, crea_utente):
        testo, n = vcard.esporta(Soggetto.objects.all(), crea_utente("u"))
        assert n == 1 and testo.startswith("BEGIN:VCARD\r\nVERSION:3.0\r\n")
        assert "N:Rossi;Mario;;Cav.;" in testo and "FN:Cav. Mario Rossi" in testo
        assert "CATEGORIES:Reduci\\, combattenti" in testo and "riservato" not in testo
        assert all(len(r.encode()) <= 75 for r in testo.split("\r\n"))
        (letto,) = vcard.leggi(testo.encode())
        assert letto.dati["indirizzo"] == "Via Garibaldi; 1"
        assert letto.dati["data_nascita"] == date(1950, 3, 2)
        assert letto.categorie == ["Reduci, combattenti"]

    def test_esclusi_i_deceduti(self, rossi, crea_utente):
        rossi.data_decesso = date(2020, 1, 1)
        rossi.save()
        assert vcard.esporta(Soggetto.objects.all(), crea_utente("u"))[1] == 0

    def test_viste_e_permessi(self, rossi, client_ruolo):
        assert client_ruolo("Consigliere", username="c").get(
            "/anagrafica/rubrica.vcf").status_code == 403  # fmt: skip
        client = client_ruolo("Segretario")
        r = client.get("/anagrafica/rubrica.vcf?q=rossi")
        assert r.status_code == 200 and r["Content-Type"].startswith("text/vcard")
        assert b"FN:Cav. Mario Rossi" in r.content
        r = client.get(f"/anagrafica/{rossi.pk}/vcard.vcf")
        assert 'filename="rossi-mario.vcf"' in r["Content-Disposition"]


@pytest.mark.django_db
class TestImportazione:
    def test_anteprima_non_salva_poi_conferma(self, rossi, client_ruolo):
        client = client_ruolo("Segretario")
        prima = Soggetto.objects.count()
        f = SimpleUploadedFile("rubrica.vcf", VCF_MISTO.encode(), content_type="text/vcard")
        r = client.post("/anagrafica/importa/", {"file": f})
        testo = r.content.decode()
        assert r.status_code == 200 and "Anteprima" in testo and "3 schede nuove" in testo
        assert Soggetto.objects.count() == prima
        r = client.post("/anagrafica/importa/", {"azione": "esegui"})
        assert Soggetto.objects.count() == prima + 3
        luca = Soggetto.objects.get(cognome="Nicolò")
        assert luca.creato_da == client.utente and "3479998887" in luca.note
        assert Soggetto.objects.get(denominazione="Pro Loco Avigliano").tipo == "ente"
        # di nuovo: nessun doppione
        f = SimpleUploadedFile("rubrica.vcf", VCF_MISTO.encode(), content_type="text/vcard")
        assert "0 schede nuove" in client.post("/anagrafica/importa/", {"file": f}).content.decode()

    def test_completa_senza_sovrascrivere(self, rossi, crea_utente):
        testo = ("BEGIN:VCARD\nVERSION:3.0\nN:Rossi;Mario;;;\nEMAIL:MARIO@example.org\n"
                 "TEL;TYPE=HOME:0971 55555\nADR:;;Altra via;Potenza;PZ;85100;\nEND:VCARD\n")  # fmt: skip
        cat = Categoria.objects.create(nome="Rubrica")
        (riga,) = vcard.importa(vcard.leggi(testo.encode()), crea_utente("u"), categoria=cat,
                                esegui=True)  # fmt: skip
        assert riga.esito == "aggiornato"
        rossi.refresh_from_db()
        assert rossi.telefono == "0971 55555" and rossi.indirizzo == "Via Garibaldi; 1"
        assert rossi.categorie.filter(nome="Rubrica").exists()

    def test_ambiguo_e_dati_non_validi(self, rossi, crea_utente):
        Soggetto.objects.create(tipo="persona", cognome="Rossi", nome="Mario")
        testo = ("BEGIN:VCARD\nVERSION:3.0\nN:Rossi;Mario;;;\nEND:VCARD\n"
                 "BEGIN:VCARD\nVERSION:3.0\nN:Verdi;Ugo;;;\nEMAIL:non-valida\n"
                 "ADR:;;Via X;Roma;Lazio;123;\nEND:VCARD\n")  # fmt: skip
        ambiguo, verdi = vcard.importa(vcard.leggi(testo.encode()), crea_utente("u"), esegui=True)
        assert ambiguo.esito == "ambiguo" and verdi.esito == "nuovo"
        v = Soggetto.objects.get(cognome="Verdi")
        assert v.email == "" and v.cap == "" and v.provincia == "" and v.comune == "Roma"

    def test_permesso(self, client_ruolo):
        assert client_ruolo("Tesoriere").get("/anagrafica/importa/").status_code == 403
