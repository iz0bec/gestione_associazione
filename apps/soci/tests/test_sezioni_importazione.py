# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test di sezioni (visibilità per utente), listino annuale del tesseramento,
# *              foto dei soggetti e importazione dal registro soci nazionale.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import io
from datetime import date
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from openpyxl import Workbook
from PIL import Image

from apps.anagrafica.models import Soggetto
from apps.soci import importazione, servizi
from apps.soci.models import CartaTessera, Sezione, Socio, TipologiaSocio

pytestmark = pytest.mark.django_db
ANNO = date.today().year
D = Decimal
CF_ROSSI = "RSSMRA50C15A519V"
CF_BIANCHI = "BNCLRA80A41F205G"


@pytest.fixture(autouse=True)
def cartella_media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def capo(crea_utente):
    return crea_utente("capo", ruoli=["Amministratore di sistema"])


@pytest.fixture
def ordinario():
    return TipologiaSocio.objects.get(nome="Ordinario")


@pytest.fixture
def nord():
    return Sezione.objects.create(codice="N01", nome="Sezione Nord")


def xlsx(righe, titolo=True):
    wb = Workbook()
    ws = wb.active
    if titolo:  # gli estratti hanno spesso un titolo sopra le intestazioni
        ws.append(["Registro soci nazionale - estrazione del 01/02/2026"])
        ws.append([])
    for r in righe:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


INTESTAZIONI = ["Matricola", "Cognome", "Nome", "Codice Fiscale", "Data di nascita", "Comune",
                "E-mail", "Sezione", "N. Tessera", "Colonna sconosciuta"]  # fmt: skip


class TestSezioni:
    def test_sezione_predefinita_e_carte_per_sezione(self, capo, ordinario, nord):
        principale = Sezione.objects.get(codice="001")
        a = servizi.ammetti_socio(Soggetto.objects.create(cognome="A"), ordinario, capo)
        b = servizi.ammetti_socio(
            Soggetto.objects.create(cognome="B"), ordinario, capo, sezione=nord
        )
        assert a.sezione == principale and b.sezione == nord
        servizi.carica_lotto(capo, anno=ANNO, numero_da=1, numero_a=3, sezione=principale)
        ta = servizi.rilascia_tessera(a, ANNO, capo, carta="prossima")
        tb = servizi.rilascia_tessera(b, ANNO, capo, carta="prossima")
        assert ta.codice == "1" and not tb.attribuita  # le carte della principale non vanno a Nord
        with pytest.raises(servizi.OperazioneNonValida, match="sezione"):
            servizi.attribuisci_carta(tb, capo, "2")

    def test_utente_limitato_alla_sua_sezione(self, client, crea_utente, capo, ordinario, nord):
        a = servizi.ammetti_socio(Soggetto.objects.create(cognome="Alfa"), ordinario, capo)
        b = servizi.ammetti_socio(
            Soggetto.objects.create(cognome="Beta"), ordinario, capo, sezione=nord
        )
        segretario = crea_utente("nord", ruoli=["Segretario"])
        segretario.sezioni.add(nord)
        client.force_login(segretario)
        html = client.get(reverse("soci:elenco")).content.decode()
        assert "Beta" in html and "Alfa" not in html
        assert client.get(reverse("soci:dettaglio", args=[a.pk])).status_code == 404
        assert client.get(reverse("soci:dettaglio", args=[b.pk])).status_code == 200
        r = client.get(reverse("soci:esporta"))
        assert "Beta" in r.content.decode("utf-8-sig") and "Alfa" not in r.content.decode(
            "utf-8-sig"
        )
        # chi non ha sezioni assegnate vede tutto
        client.force_login(capo)
        html = client.get(reverse("soci:elenco")).content.decode()
        assert "Beta" in html and "Alfa" in html

    def test_pagine_sezioni(self, client, capo, nord):
        client.force_login(capo)
        assert client.get(reverse("soci:sezioni")).status_code == 200
        r = client.post(reverse("soci:sezione_nuova"), {"codice": "S02", "nome": "Sud",
                                                       "provincia": "pz", "ordine": 2, "attiva": "on"})  # fmt: skip
        assert r.status_code == 302 and Sezione.objects.get(codice="S02").provincia == "PZ"


class TestListino:
    def test_quote_per_anno_e_costo_acquisto(self, capo, ordinario):
        ordinario.quota_annua = D("25")
        ordinario.save()
        lst = servizi.prepara_listino(ANNO, capo)
        assert servizi.quota_per(ordinario, ANNO) == D("25")
        servizi.salva_listino(ANNO, capo, costo_acquisto=D("3.50"), quote={ordinario: D("30")})
        assert servizi.quota_per(ordinario, ANNO) == D("30")
        socio = servizi.ammetti_socio(Soggetto.objects.create(cognome="X"), ordinario, capo)
        assert servizi.rilascia_tessera(socio, ANNO, capo).importo == D("30")
        lotto = servizi.carica_lotto(capo, anno=ANNO, numero_da=1, numero_a=2)
        assert lotto.costo_unitario == D("3.50")  # dal listino
        # l'anno dopo riparte dal listino precedente
        assert servizi.prepara_listino(ANNO + 1).costo_acquisto == D("3.50")
        assert servizi.quota_per(ordinario, ANNO + 1) == D("30")
        assert lst.pk == servizi.prepara_listino(ANNO).pk

    def test_pagina_listino(self, client, capo, ordinario):
        client.force_login(capo)
        assert client.get(reverse("soci:listino")).status_code == 200
        dati = {"costo_acquisto": "4", "note": ""}
        for t in TipologiaSocio.objects.filter(attiva=True):
            dati[f"quota_{t.pk}"] = "20" if t == ordinario else "0"
        r = client.post(reverse("soci:listino") + f"?anno={ANNO}", dati)
        assert r.status_code == 302 and servizi.quota_per(ordinario, ANNO) == D("20")


class TestFoto:
    def test_foto_soggetto(self, client, capo):
        s = Soggetto.objects.create(cognome="Verdi", nome="Anna")
        img = io.BytesIO()
        Image.new("RGB", (2000, 1500), "blue").save(img, "JPEG")
        client.force_login(capo)
        dati = {"tipo": "persona", "cognome": "Verdi", "nome": "Anna", "nazione": "IT",
                "nuova_foto": SimpleUploadedFile("a.jpg", img.getvalue(), "image/jpeg")}  # fmt: skip
        r = client.post(reverse("anagrafica:modifica", args=[s.pk]), dati)
        assert r.status_code == 302, r.content.decode()[:2000]
        s.refresh_from_db()
        assert s.foto and max(Image.open(s.foto.open("rb")).size) == 600
        assert "foto.jpg" not in s.foto.name  # nome casuale
        r = client.get(reverse("anagrafica:foto", args=[s.pk]))
        assert r.status_code == 200 and r["Content-Type"] == "image/jpeg"
        client.logout()
        assert client.get(reverse("anagrafica:foto", args=[s.pk])).status_code == 302


class TestImportazione:
    def righe(self):
        return [
            INTESTAZIONI,
            ["A123", "ROSSI", "MARIO", CF_ROSSI, "15/03/1950", "AVIGLIANO", "M.Rossi@Example.org",
             "Sezione Nord", "1001", "x"],
            ["A124", "Bianchi", "Laura", CF_BIANCHI, date(1980, 1, 1), "Potenza", "", "Sezione Nord",
             "1002", "y"],
            ["A125", "Senza", "Sezione", "", "", "", "", "Sezione Inesistente", "", ""],
        ]  # fmt: skip

    def test_lettura_intestazioni(self):
        mappa, righe, ignorate = importazione.leggi("registro.xlsx", xlsx(self.righe()))
        assert {"matricola", "cognome", "codice_fiscale", "sezione", "tessera"} <= set(
            mappa.values()
        )
        assert ignorate == ["Colonna sconosciuta"] and len(righe) == 3
        with pytest.raises(importazione.FileNonValido):
            importazione.leggi("registro.xls", b"x")

    def test_anteprima_non_modifica_ed_esecuzione(self, capo, ordinario, nord):
        _, righe, _ = importazione.leggi("r.xlsx", xlsx(self.righe()))
        esistente = Soggetto.objects.create(cognome="Bianchi", nome="Laura",
                                            codice_fiscale=CF_BIANCHI, email="laura@locale.it")  # fmt: skip
        servizi.carica_lotto(capo, anno=ANNO, numero_da=1000, numero_a=1010, sezione=nord)
        opzioni = importazione.Opzioni(tipologia=ordinario, anno_tessere=ANNO)
        anteprima = importazione.elabora(righe, opzioni, capo)
        assert anteprima.riepilogo == {"nuovo": 1, "aggiornato": 1, "invariato": 0, "errore": 1}
        assert not Socio.objects.exists() and Soggetto.objects.count() == 1  # nulla scritto
        r = importazione.elabora(righe, opzioni, capo, esegui=True)
        assert r.riepilogo == anteprima.riepilogo
        rossi = Socio.objects.get(matricola="A123")
        assert rossi.sezione == nord and rossi.soggetto.cognome == "Rossi"
        assert rossi.soggetto.email == "m.rossi@example.org"
        assert rossi.soggetto.data_nascita == date(1950, 3, 15)
        assert rossi.tessera_anno(ANNO).codice == "1001"
        esistente.refresh_from_db()
        assert esistente.email == "laura@locale.it"  # non sovrascritto
        assert esistente.socio.matricola == "A124" and esistente.comune == "Potenza"
        assert CartaTessera.objects.get(codice="1002").stato == "attribuita"
        # rieseguire non duplica nulla
        r2 = importazione.elabora(righe, opzioni, capo, esegui=True)
        assert r2.riepilogo["nuovo"] == 0 and Socio.objects.count() == 2

    def test_creazione_sezioni_e_limiti_utente(self, capo, ordinario, nord):
        _, righe, _ = importazione.leggi("r.xlsx", xlsx(self.righe()))
        opzioni = importazione.Opzioni(tipologia=ordinario, crea_sezioni=True)
        r = importazione.elabora(righe, opzioni, capo, esegui=True)
        assert r.sezioni_nuove == ["Sezione Inesistente"] and r.riepilogo["errore"] == 0
        limitate = importazione.Opzioni(tipologia=ordinario, sezioni_consentite={nord.pk})
        r = importazione.elabora(righe, limitate, capo)
        assert "non consentita" in r.esiti[2].note[0]

    def test_csv_e_nominativo(self, capo, ordinario):
        contenuto = "Nominativo;Codice fiscale;Comune\nVERDI GIUSEPPE;XXXX;Melfi\n".encode("cp1252")
        _, righe, _ = importazione.leggi("r.csv", contenuto)
        opzioni = importazione.Opzioni(tipologia=ordinario, sezione=Sezione.predefinita())
        r = importazione.elabora(righe, opzioni, capo, esegui=True)
        assert r.riepilogo["nuovo"] == 1 and "non valido" in r.esiti[0].note[0]
        s = Socio.objects.get().soggetto
        assert (s.cognome, s.nome, s.comune, s.codice_fiscale) == (
            "Verdi",
            "Giuseppe",
            "Melfi",
            None,
        )

    def test_vista_anteprima_e_conferma(self, client, capo, ordinario, nord):
        client.force_login(capo)
        assert client.get(reverse("soci:importa")).status_code == 200
        f = SimpleUploadedFile("registro.xlsx", xlsx(self.righe()))
        r = client.post(reverse("soci:importa"), {"file": f, "tipologia": ordinario.pk,
                                                 "azione": "anteprima"})  # fmt: skip
        html = r.content.decode()
        assert "Anteprima" in html and "Sezione Inesistente" in html and not Socio.objects.exists()
        r = client.post(reverse("soci:importa"), {"azione": "esegui"})
        assert r.status_code == 200 and Socio.objects.count() == 2
        r = client.post(reverse("soci:importa"), {"azione": "esegui"})  # anteprima già usata
        assert r.status_code == 302

    def test_permesso(self, client_ruolo):
        assert client_ruolo("Consigliere").get(reverse("soci:importa")).status_code == 403
