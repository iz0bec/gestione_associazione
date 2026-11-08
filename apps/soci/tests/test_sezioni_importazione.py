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
from apps.soci.models import CartaTessera, Sezione, Socio, Tessera, TipologiaSocio

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
    return Sezione.objects.create(
        codice="N01", nome="Sezione Nord", comune="Nordville", provincia="PZ"
    )


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
             "NORDVILLE", "1001", "x"],
            ["A124", "Bianchi", "Laura", CF_BIANCHI, date(1980, 1, 1), "Potenza", "", "Nordville",
             "1002", "y"],
            ["A125", "Senza", "Sezione", "", "", "", "", "Altrove", "", ""],
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
        assert r.sezioni_nuove == ["Altrove"] and r.riepilogo["errore"] == 0
        assert Sezione.objects.get(nome="Altrove").comune == "Altrove"
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

    def test_vista_anteprima_e_conferma(self, client, capo, ordinario, nord, crea_utente):
        from unittest import mock

        from django.core.management import call_command

        def processo(argomenti, **_):  # il processo separato, eseguito qui
            call_command("lavoro_importazione", argomenti[-1])

        client.force_login(capo)
        assert client.get(reverse("soci:importa")).status_code == 200
        f = SimpleUploadedFile("registro.xlsx", xlsx(self.righe()))
        with mock.patch("apps.soci.lavori_importazione.subprocess.Popen", side_effect=processo):
            r = client.post(reverse("soci:importa"), {"file": f, "tipologia": ordinario.pk,
                                                     "azione": "anteprima"})  # fmt: skip
            assert r.status_code == 302 and "lavoro=" in r.url
            lavoro = r.url.split("lavoro=")[1]
            html = client.get(r.url).content.decode()
            assert "Anteprima" in html and "Nordville → N01 Sezione Nord" in html
            assert 'Altrove → <span class="text-red">non abbinata' in html
            assert 'id="modale-importazione"' in html and not Socio.objects.exists()
            # la finestra chiede l'avanzamento: a lavoro finito rimanda al rapporto
            a = client.get(reverse("soci:importa_avanzamento", args=[lavoro]))
            assert a.status_code == 204 and "lavoro=" in a["HX-Redirect"]
            r = client.post(reverse("soci:importa"), {"azione": "esegui", "lavoro": lavoro})
            assert r.status_code == 302 and Socio.objects.count() == 2
            assert "Esito dell" in client.get(r.url).content.decode()
            r = client.post(reverse("soci:importa"), {"azione": "esegui", "lavoro": lavoro})
            assert r.url == reverse("soci:importa")  # anteprima già usata
        # il lavoro di un altro utente non è visibile
        altro = crea_utente("altro", ruoli=["Amministratore di sistema"])
        client.force_login(altro)
        assert client.get(reverse("soci:importa_avanzamento", args=[lavoro])).status_code == 404

    def test_avanzamento_in_corso(self, client, capo):
        from apps.soci import lavori_importazione

        client.force_login(capo)
        lavoro = lavori_importazione.nuovo(capo, "r.csv", b"Cognome;Nome\nA;B\n", {}, [], [], 120)
        lavori_importazione.scrivi(lavoro, stato="in_corso", fatte=30)
        html = client.get(reverse("soci:importa_avanzamento", args=[lavoro])).content.decode()
        assert "riga 30 di 120" in html and "25%" in html and 'hx-trigger="every 1s"' in html
        pagina = client.get(reverse("soci:importa") + f"?lavoro={lavoro}").content.decode()
        assert "data-modale-aperto" in pagina

    def test_permesso(self, client_ruolo):
        assert client_ruolo("Consigliere").get(reverse("soci:importa")).status_code == 403


INTESTAZIONI_REGISTRO = [
    None, "Opzioni", "Regione", "Federazione", "Sezione", "Cognome", "Nome", "Luogo Di Nascita",
    "Data Di Nascita", "CodiceFiscale", "Indirizzo", "CAP", "Città", "PR", "Telefono", "Email",
    "Data Di Ammissione A Socio", "Numero Tessera Anno 2025", "Numero Tessera", "Data Tessera",
    "Anno Sociale", "Scheda Completa", "Scheda Completa Percentuale",
    "Data Di Annullamento Iscrizione", "Codice Incarico Socio Ordinario", "Valido",
]  # fmt: skip


class TestFormatoRegistroNazionale:
    """Stessa struttura dell'estratto «Gestione Registro Soci» (dati inventati)."""

    def file(self):
        wb = Workbook()
        ws = wb.active
        ws.append(["Gestione Registro Soci - Associazione Nazionale Combattenti e Reduci"])
        ws.append(INTESTAZIONI_REGISTRO)
        ws.append([None, None, "BASILICATA", "POTENZA MATERA", "RIONERO IN VULTURE", "ROSSI",
                   "MARIO", "Avigliano", "15 marzo 1950", CF_ROSSI, "VIA ROMA,1", 85028,
                   "RIONERO IN VULTURE", "pz", "0972-123456, 3331234567", None,
                   "01 gennaio 2023", 31767, "029037", "01 febbraio 2026", 2026, "Completa", 1,
                   None, "Presidente"])  # fmt: skip
        ws.append([None, None, "BASILICATA", "POTENZA MATERA", "RIONERO IN VULTURE", "BIANCHI",
                   "Laura", "Milano", "01 gennaio 1980", CF_BIANCHI, None, None, None, None,
                   3471234567, None, "05 aprile 2024", None, None, None, 2026,
                   "1) Numero Tessera assente", 0.9, "10 marzo 2026", "Socio"])  # fmt: skip
        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    def test_importazione(self, capo, ordinario):
        mappa, righe, ignorate = importazione.leggi("registro.xlsx", self.file())
        assert {"tessera_precedente", "anno_tessera", "data_cessazione", "incarico"} <= set(
            mappa.values()
        )
        assert "Regione" in ignorate and righe[0]["_anno_tessera_precedente"] == 2025
        opzioni = importazione.Opzioni(tipologia=ordinario, crea_sezioni=True)
        r = importazione.elabora(righe, opzioni, capo, esegui=True)
        assert r.riepilogo["errore"] == 0 and r.sezioni_nuove == ["Rionero in Vulture"]
        rossi = Socio.objects.get(soggetto__codice_fiscale=CF_ROSSI)
        p = rossi.soggetto
        assert (p.cognome, p.nome, p.comune, p.provincia, p.indirizzo) == (
            "Rossi", "Mario", "Rionero in Vulture", "PZ", "Via Roma,1",
        )  # fmt: skip
        assert (p.telefono, p.cellulare) == ("0972-123456", "3331234567")
        assert p.luogo_nascita == "Avigliano (PZ)"  # provincia ricavata dal codice fiscale
        assert rossi.data_ammissione == date(2023, 1, 1) and "Presidente" in rossi.note
        assert rossi.sezione.nome == "Rionero in Vulture"
        t26, t25 = rossi.tessera_anno(2026), rossi.tessera_anno(2025)
        assert (t26.codice, t26.data_rilascio, t25.codice) == ("29037", date(2026, 2, 1), "31767")
        assert t26.carta.lotto.fornitore == servizi.FORNITORE_REGISTRO
        bianchi = Socio.objects.get(soggetto__codice_fiscale=CF_BIANCHI)
        assert bianchi.stato == "cessato" and bianchi.data_cessazione == date(2026, 3, 10)
        assert not bianchi.tessere.exists() and bianchi.soggetto.cellulare == "3471234567"
        # l'estratto della sola sezione si abbina alla sezione già creata, anche se scritta diversa
        Sezione.objects.filter(nome="Rionero in Vulture").update(
            nome="ANCR Sezione di Rionero in Vulture"
        )
        r = importazione.elabora(righe, importazione.Opzioni(tipologia=ordinario), capo)
        assert r.riepilogo == {"nuovo": 0, "aggiornato": 0, "invariato": 2, "errore": 0}


class TestQuoteImportate:
    def test_scelta_da_incassare_o_pagate(self, capo, ordinario):
        from apps.tesoreria import servizi as tesoreria

        ordinario.quota_annua = 25
        ordinario.save()
        _, righe, _ = importazione.leggi("r.xlsx", TestFormatoRegistroNazionale().file())
        base = {"tipologia": ordinario, "crea_sezioni": True}
        r = importazione.elabora(righe, importazione.Opzioni(**base), capo)
        assert r.riepilogo["errore"] == 0
        importazione.elabora(righe, importazione.Opzioni(**base, quote_pagate=True), capo,
                             esegui=True)  # fmt: skip
        t = Socio.objects.get(soggetto__codice_fiscale=CF_ROSSI).tessera_anno(2026)
        assert t.pagata and t.incasso_esterno and t.pagata_il == date(2026, 2, 1)
        assert t.codice_ricevuta == "" and not Socio.objects.morosi(2026).exists()
        e = tesoreria.apri_esercizio(2026, capo)
        assert not tesoreria.quote_da_registrare(e).exists()
        assert tesoreria.registra_quota(t, capo)[0] is None


class TestColonnaValido:
    """«Valido» = socio validato (attivo e in regola): se richiesto decide se la quota è pagata."""

    def file(self):
        return xlsx([
            ["Cognome", "Nome", "Data di nascita", "Sezione", "Numero Tessera", "Anno Sociale",
             "Valido"],
            ["Rossi", "Mario", "15/03/1950", "Nord", "101", 2026, "Sì"],
            ["Verdi", "Ugo", "01/01/1960", "Nord", "102", 2026, "NO"],
            ["Neri", "Ada", "02/02/1970", "Nord", "103", 2026, None],
        ])  # fmt: skip

    def _pagate(self):
        return {t.socio.soggetto.cognome: t.pagata
                for t in Tessera.objects.filter(anno=2026).select_related("socio__soggetto")}  # fmt: skip

    @pytest.mark.parametrize(("valido", "quote_pagate", "attese"), [
        (False, False, {"Rossi": False, "Verdi": False, "Neri": False}),  # colonna ignorata
        (False, True, {"Rossi": True, "Verdi": True, "Neri": True}),
        (True, False, {"Rossi": True, "Verdi": False, "Neri": False}),
        (True, True, {"Rossi": True, "Verdi": False, "Neri": True}),  # vuota: scelta generale
    ])  # fmt: skip
    def test_scelte(self, capo, ordinario, nord, valido, quote_pagate, attese):
        ordinario.quota_annua = 25
        ordinario.save()
        mappa, righe, _ = importazione.leggi("r.xlsx", self.file())
        assert "valido" in mappa.values()
        assert [r["valido"] for r in map(importazione._pulisci, righe)] == [True, False, None]
        opzioni = importazione.Opzioni(tipologia=ordinario, sezione=nord, valido=valido,
                                       quote_pagate=quote_pagate, abbina="nome")  # fmt: skip
        r = importazione.elabora(righe, opzioni, capo, esegui=True)
        assert r.riepilogo["errore"] == 0, [e.note for e in r.esiti]
        assert self._pagate() == attese

    def test_validato_dopo_su_tessera_esistente(self, capo, ordinario, nord):
        ordinario.quota_annua = 25
        ordinario.save()
        _, righe, _ = importazione.leggi("r.xlsx", self.file())
        base = {"tipologia": ordinario, "sezione": nord, "abbina": "nome"}
        importazione.elabora(righe, importazione.Opzioni(**base), capo, esegui=True)
        assert not any(self._pagate().values())
        r = importazione.elabora(righe, importazione.Opzioni(**base, valido=True), capo,
                                 esegui=True)  # fmt: skip
        assert self._pagate() == {"Rossi": True, "Verdi": False, "Neri": False}
        rossi = next(e for e in r.esiti if "Rossi" in e.nome)
        assert rossi.stato == "aggiornato" and any("validato" in n for n in rossi.note)


class TestAbbinamentoSezioni:
    """Ogni comune ha una sola sezione: il file si abbina per comune (o per nome o codice)."""

    def righe(self, valore):
        return [{"_riga": 2, "cognome": "Rossi", "nome": "Mario", "codice_fiscale": CF_ROSSI,
                 "sezione": valore}]  # fmt: skip

    def test_per_comune_nome_codice(self, capo, ordinario):
        s = Sezione.objects.create(codice="085", nome="ANCR Sezione di Rionero",
                                   comune="Rionero in Vulture, PZ")  # fmt: skip
        for campo, valore in [("comune", "RIONERO IN VULTURE"), ("nome", "Rionero"),
                              ("codice", "085")]:  # fmt: skip
            r = importazione.elabora(self.righe(valore), importazione.Opzioni(
                tipologia=ordinario, abbina=campo), capo)  # fmt: skip
            assert r.riepilogo["errore"] == 0, (campo, r.esiti[0].note)
            assert list(r.abbinamenti.values()) == ["085 ANCR Sezione di Rionero"]
        # per comune il nome non conta, e viceversa
        r = importazione.elabora(self.righe("Rionero"), importazione.Opzioni(tipologia=ordinario),
                                 capo)  # fmt: skip
        assert r.riepilogo["errore"] == 1 and "nessuna sezione con comune" in r.esiti[0].note[0]
        assert s.pk

    def test_comune_ambiguo_e_unicita(self, capo, ordinario):
        from apps.soci.forms import SezioneForm

        Sezione.objects.create(codice="A", nome="Uno", comune="Ruoti")
        Sezione.objects.create(codice="B", nome="Due", comune="RUOTI (PZ)")
        r = importazione.elabora(self.righe("Ruoti"), importazione.Opzioni(tipologia=ordinario),
                                 capo)  # fmt: skip
        assert "più sezioni con comune" in r.esiti[0].note[0]
        Sezione.objects.filter(codice="A").update(
            attiva=False
        )  # le sezioni disattivate non contano
        r = importazione.elabora(self.righe("Ruoti"), importazione.Opzioni(tipologia=ordinario),
                                 capo)  # fmt: skip
        assert r.riepilogo["errore"] == 0 and list(r.abbinamenti.values()) == ["B Due"]
        form = SezioneForm({"codice": "C", "nome": "Tre", "comune": "ruoti, pz", "ordine": 0,
                            "attiva": "on"})  # fmt: skip
        assert not form.is_valid() and "già una sezione" in str(form.errors["comune"])
        # una sezione con comune ripetuto si può sempre disattivare
        a = Sezione.objects.get(codice="A")
        form = SezioneForm({"codice": "A", "nome": "Uno", "comune": "Ruoti", "ordine": 0},
                           instance=a)  # fmt: skip
        assert form.is_valid(), form.errors


def test_sezione_nelle_schede(client_ruolo, nord, ordinario):
    from apps.anagrafica.models import Soggetto

    Sezione.objects.create(codice="S02", nome="Sezione Sud", comune="Sudville", provincia="PZ")
    c = client_ruolo("Segretario")
    s = Soggetto.objects.create(cognome="Rossi", nome="Mario")
    socio = servizi.ammetti_socio(s, ordinario, c.utente, sezione=nord)
    assert "Sezione di Sezione Nord" in c.get(f"/soci/{socio.pk}/").content.decode()
    assert "Sezione di Sezione Nord" in c.get(f"/anagrafica/{s.pk}/").content.decode()
