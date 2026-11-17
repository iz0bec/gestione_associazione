# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test delle spedizioni su carta: liste di distribuzione nella registrazione,
# *              indirizzi postali, destinatari in CSV, buste DL in Word ed etichette in PDF.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import io
import zipfile
from datetime import date

import pytest
from django.urls import reverse

from apps.anagrafica.models import Soggetto
from apps.comunicazioni.models import Lista
from apps.core.models import EventoAudit, Organizzazione
from apps.protocollo import buste, servizi
from apps.protocollo.models import Protocollo

pytestmark = pytest.mark.django_db


@pytest.fixture
def utente(crea_utente):
    return crea_utente("addetto", ruoli=["Addetto protocollo"])


@pytest.fixture
def prefetto():
    return Soggetto.objects.create(
        tipo="ente", denominazione="Prefettura di Potenza", qualifica="Ufficio di gabinetto",
        email="prefettura@example.org", indirizzo="Piazza Mario Pagano 1", cap="85100",
        comune="Potenza", provincia="PZ",
    )  # fmt: skip


@pytest.fixture
def sindaco():
    return Soggetto.objects.create(
        cognome="Rossi", nome="Mario", titolo="Dott.", email="sindaco@example.org",
        indirizzo="Corso Coviello 1", cap="85021", comune="Avigliano", provincia="PZ",
    )  # fmt: skip


def _registra(client, mezzo="raccomandata", **dati):
    return client.post(
        reverse("protocollo:nuovo"),
        {"direzione": "uscita", "mezzo": mezzo, "oggetto": "Invito alla cerimonia", **dati},
    )


class TestRegistrazione:
    def test_liste_di_distribuzione_senza_doppioni(self, client, utente, prefetto, sindaco):
        defunto = Soggetto.objects.create(
            cognome="Bianchi", nome="Luigi", data_decesso=date(2020, 1, 1)
        )
        lista = Lista.objects.create(nome="Autorità")
        lista.soggetti.set([prefetto, sindaco, defunto])
        client.force_login(utente)
        r = _registra(client, liste=[lista.pk], destinatari=[sindaco.pk])
        assert r.status_code == 302
        p = Protocollo.objects.get()
        assert sorted(c.descrizione for c in p.destinatari) == [
            "Prefettura di Potenza", "Rossi Mario",
        ]  # fmt: skip

    def test_indirizzo_postale_per_raccomandata(self, client, utente, prefetto):
        client.force_login(utente)
        _registra(client, destinatari=[prefetto.pk])
        c = Protocollo.objects.get().destinatari[0]
        assert c.indirizzo == "Piazza Mario Pagano 1, 85100 Potenza (PZ)"

    def test_email_per_email(self, client, utente, prefetto):
        client.force_login(utente)
        _registra(client, mezzo="email", destinatari=[prefetto.pk])
        assert Protocollo.objects.get().destinatari[0].indirizzo == "prefettura@example.org"

    def test_destinatario_libero_con_indirizzo_postale(self, client, utente):
        client.force_login(utente)
        _registra(client, destinatari_altri="Questura; Via Roma 1, 85100 Potenza (PZ)")
        c = Protocollo.objects.get().destinatari[0]
        assert (c.descrizione, c.indirizzo) == ("Questura", "Via Roma 1, 85100 Potenza (PZ)")


@pytest.mark.parametrize(
    ("testo", "atteso"),
    [
        ("Via Roma 1, 85100 Potenza (PZ)", ("Via Roma 1", "85100", "Potenza", "PZ")),
        ("Via Roma 1, Potenza", ("Via Roma 1", "", "Potenza", "")),
        ("85100 Potenza (pz)", ("", "85100", "Potenza", "PZ")),
        ("Contrada Serra", ("Contrada Serra", "", "", "")),
        ("mario@example.org", ("", "", "", "")),
        ("", ("", "", "", "")),
    ],
)
def test_scomponi_indirizzo(testo, atteso):
    assert buste.scomponi_indirizzo(testo) == atteso


class TestSpedizione:
    @pytest.fixture
    def protocollo(self, utente, prefetto):
        return servizi.registra_protocollo(
            {"direzione": "uscita", "mezzo": "raccomandata", "oggetto": "Invito"},
            [
                servizi.corrispondente_da_soggetto(prefetto, "destinatario", postale=True),
                {"ruolo": "destinatario", "descrizione": "=Senza indirizzo", "indirizzo": ""},
            ],
            utente,
        )

    def test_csv(self, client, utente, protocollo):
        client.force_login(utente)
        r = client.get(reverse("protocollo:spedizione", args=[protocollo.pk, "csv"]))
        assert r.status_code == 200 and "attachment" in r["Content-Disposition"]
        assert r["Content-Security-Policy"] == "default-src 'none'; sandbox"
        righe = r.content.decode("utf-8-sig").splitlines()
        assert righe[0].startswith("Protocollo;Nominativo;Qualifica;Indirizzo;CAP")
        assert (
            f"{protocollo.segnatura};Prefettura di Potenza;Ufficio di gabinetto;"
            "Piazza Mario Pagano 1;85100;Potenza;PZ;Prefettura di Potenza;Ufficio di gabinetto;"
            "Piazza Mario Pagano 1;85100 Potenza (PZ);"
        ) in righe[1]
        assert "'=Senza indirizzo" in righe[2] and "indirizzo postale mancante" in righe[2]
        assert EventoAudit.objects.filter(azione="esportazione").exists()

    def _documento(self, risposta):
        assert risposta.status_code == 200
        with zipfile.ZipFile(io.BytesIO(risposta.content)) as z:
            assert "[Content_Types].xml" in z.namelist()
            return z.read("word/document.xml").decode()

    def test_buste_compilate(self, client, utente, protocollo):
        org = Organizzazione.corrente()
        org.denominazione, org.comune = "Associazione & Amici", "Avigliano"
        org.save()
        client.force_login(utente)
        xml = self._documento(
            client.get(reverse("protocollo:spedizione", args=[protocollo.pk, "buste"]))
        )
        assert 'w:w="12474" w:h="6237" w:orient="landscape"' in xml  # 220 × 110 mm
        assert "Associazione &amp; Amici" in xml and "RACCOMANDATA" in xml
        assert "85100 Potenza (PZ)" in xml and xml.count('w:type="page"') == 1
        assert "MERGEFIELD" not in xml

    def test_stampa_unione(self, client, utente, protocollo):
        client.force_login(utente)
        xml = self._documento(
            client.get(reverse("protocollo:spedizione", args=[protocollo.pk, "stampa-unione"]))
        )
        assert all(f"MERGEFIELD Riga{i} " in xml for i in range(1, 5))
        assert "Prefettura" not in xml

    def test_avviso_nel_dettaglio(self, client, utente, protocollo):
        client.force_login(utente)
        r = client.get(protocollo.get_absolute_url())
        assert "Buste DL compilate" in r.text and "Indirizzo postale mancante" in r.text

    def test_solo_spedizioni_su_carta(self, client, utente):
        client.force_login(utente)
        email = servizi.registra_protocollo(
            {"direzione": "uscita", "mezzo": "email", "oggetto": "Avviso"},
            [{"ruolo": "destinatario", "descrizione": "Mario", "indirizzo": "m@example.org"}],
            utente,
        )
        assert "Buste DL" not in client.get(email.get_absolute_url()).text
        r = client.get(reverse("protocollo:spedizione", args=[email.pk, "csv"]))
        assert r.status_code == 404

    def test_formato_sconosciuto(self, client, utente, protocollo):
        client.force_login(utente)
        r = client.get(reverse("protocollo:spedizione", args=[protocollo.pk, "pdf"]))
        assert r.status_code == 404

    def test_riservato_non_visibile(self, client_ruolo, utente, protocollo):
        protocollo.riservato = True
        protocollo.save()
        client = client_ruolo("Consigliere", username="consigliere")
        r = client.get(reverse("protocollo:spedizione", args=[protocollo.pk, "csv"]))
        assert r.status_code in (403, 404)


class TestSenzaEmail:
    def test_email_a_una_lista_buste_per_chi_non_ha_email(self, client, utente, prefetto):
        senza_email = Soggetto.objects.create(
            cognome="Verdi", nome="Anna", indirizzo="Via Appia 3", cap="85100", comune="Potenza",
            provincia="PZ",
        )  # fmt: skip
        lista = Lista.objects.create(nome="Consiglio")
        lista.soggetti.set([prefetto, senza_email])
        client.force_login(utente)
        _registra(client, mezzo="email", liste=[lista.pk])
        p = Protocollo.objects.get()
        assert [r["Nominativo"] for r in buste.righe_destinatari(p)] == ["Verdi Anna"]
        assert "Buste ed etichette (1 senza email)" in client.get(p.get_absolute_url()).text
        r = client.get(reverse("protocollo:spedizione", args=[p.pk, "csv"]))
        testo = r.content.decode("utf-8-sig")
        assert "Via Appia 3;85100;Potenza;PZ" in testo and "Prefettura" not in testo

    def test_email_con_tutti_gli_indirizzi_niente_buste(self, client, utente, prefetto):
        client.force_login(utente)
        _registra(client, mezzo="email", destinatari=[prefetto.pk])
        assert "Buste" not in client.get(Protocollo.objects.get().get_absolute_url()).text


class TestEtichette:
    def _riga(self, nome, via="Via Roma 1", comune="Potenza"):
        return buste.riga_busta(nome, "", via, "85100", comune, "PZ")

    def _contesto(self, monkeypatch, righe, formato="70x37", inizio=1):
        visto = {}
        monkeypatch.setattr(
            "apps.core.pdf.genera_pdf", lambda t, c: visto.update(c) or b"%PDF-finto"
        )
        dati, n, scartate = buste.pdf_etichette(righe, formato, inizio)
        return visto, n, scartate

    def test_disposizione_e_fogli(self, monkeypatch):
        righe = [self._riga(f"Socio {i}") for i in range(30)] + [self._riga("Senza", via="")]
        visto, n, scartate = self._contesto(monkeypatch, righe)
        assert (n, scartate) == (30, 1)
        primo, secondo = visto["fogli"]
        assert len(primo) == 24 and len(secondo) == 6
        assert (primo[0]["x"], primo[0]["y"]) == (0, 0.5)
        assert (primo[4]["x"], primo[4]["y"]) == (70, 37.5)  # seconda riga, seconda colonna
        assert primo[0]["righe"] == ["Socio 0", "Via Roma 1", "85100 Potenza (PZ)"]

    def test_foglio_gia_iniziato(self, monkeypatch):
        righe = [self._riga("Uno"), self._riga("Due")]
        visto, n, _ = self._contesto(monkeypatch, righe, "63x38", inizio=4)
        (foglio,) = visto["fogli"]
        assert n == 2 and foglio[0]["righe"][0] == "Uno"
        assert foglio[0]["x"] == pytest.approx(7.2) and foglio[0]["y"] == pytest.approx(53.2)

    def test_parametri_ripuliti(self):
        assert buste.formato_etichette("sconosciuto") == "70x37"
        assert buste.posizione_iniziale("99", "99x38") == 14
        assert buste.posizione_iniziale("x", "70x37") == 1

    def test_pdf_dal_protocollo(self, client, utente, prefetto):
        p = servizi.registra_protocollo(
            {"direzione": "uscita", "mezzo": "raccomandata", "oggetto": "Invito"},
            [servizi.corrispondente_da_soggetto(prefetto, "destinatario", postale=True)], utente,
        )  # fmt: skip
        client.force_login(utente)
        assert "Etichette adesive" in client.get(p.get_absolute_url()).text
        url = reverse("protocollo:spedizione", args=[p.pk, "etichette"])
        r = client.get(url, {"foglio": "99x38", "inizio": "3"})
        assert r.status_code == 200 and r.content.startswith(b"%PDF")
        assert r["Content-Type"] == "application/pdf" and "etichette_" in r["Content-Disposition"]
        evento = EventoAudit.objects.filter(azione="esportazione").latest("pk")
        assert evento.dettagli["etichette"] == 1 and evento.dettagli["formato"] == "99x38"


def test_etichette_della_lista(client, crea_utente, prefetto, sindaco):
    senza = Soggetto.objects.create(cognome="Verdi", nome="Anna")
    lista = Lista.objects.create(nome="Autorità")
    lista.soggetti.set([prefetto, sindaco, senza])
    client.force_login(crea_utente("segr", ruoli=["Segretario"]))
    assert "Etichette adesive" in client.get(
        reverse("comunicazioni:lista", args=[lista.pk])).text  # fmt: skip
    r = client.get(reverse("comunicazioni:lista_etichette", args=[lista.pk]))
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
    evento = EventoAudit.objects.filter(azione="esportazione").latest("pk")
    assert evento.dettagli["etichette"] == 2 and evento.dettagli["senza_indirizzo"] == 1
