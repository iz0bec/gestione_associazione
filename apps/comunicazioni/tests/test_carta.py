# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test delle comunicazioni su carta: chi non ha l'email riceve lettera e busta
# *              (con il consenso, se serve), elenco CSV, buste in Word, lettere in PDF.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import io
import zipfile

import pytest
from django.urls import reverse

from apps.anagrafica.models import Consenso, Soggetto
from apps.comunicazioni import carta, servizi
from apps.comunicazioni.models import Finalita

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def senza_rubrica_implicita():
    from apps.core.models import Organizzazione

    Organizzazione.objects.update(consensi_impliciti_rubrica=False)


@pytest.fixture
def utente(crea_utente):
    return crea_utente("segr", ruoli=["Segretario"])


def persona(cognome, email="", consenso=False, **extra):
    s = Soggetto.objects.create(cognome=cognome, nome="Mario", email=email, **extra)
    if consenso:
        Consenso.objects.create(soggetto=s, finalita="comunicazioni", prestato=True)
    return s


def _invio(utente, finalita, soggetti):
    return servizi.crea_invio(utente, oggetto="Assemblea {{ nome }}",
                              corpo="{{ saluto }} {{ nome }},\nci vediamo.", finalita=finalita,
                              soggetti=soggetti)  # fmt: skip


@pytest.fixture
def soggetti():
    return [
        persona(
            "Rossi",
            indirizzo="Via Roma 1",
            cap="85021",
            comune="Avigliano",
            provincia="PZ",
            consenso=True,
        ),  # fmt: skip
        persona("Bianchi", consenso=True),  # senza indirizzo
        persona("Verdi", indirizzo="Via Po 2", cap="85100", comune="Potenza"),  # senza consenso
        persona("Neri", email="neri@example.org", consenso=True),
        persona(
            "Gialli",
            indirizzo="Via Ex 3",
            comune="Potenza",
            consenso=True,
            data_decesso="2020-01-01",
        ),  # fmt: skip
    ]


class TestDestinatari:
    def test_con_consenso(self, utente, soggetti):
        invio = _invio(utente, Finalita.COMUNICAZIONI, soggetti)
        nomi = [d.soggetto.cognome for d in carta.destinatari_su_carta(invio)]
        assert nomi == ["Bianchi", "Rossi"]  # Verdi senza consenso, Neri ha l'email, Gialli no
        assert carta.senza_consenso(invio) == 1
        righe = {r["Nominativo"]: r for r in carta.righe(invio)}
        assert righe["Mario Rossi"]["Riga3"] == "85021 Avigliano (PZ)"
        assert righe["Mario Bianchi"]["Avviso"]

    def test_istituzionale_senza_consenso(self, utente, soggetti):
        invio = _invio(utente, Finalita.ISTITUZIONALE, soggetti)
        assert len(carta.destinatari_su_carta(invio)) == 3
        assert carta.senza_consenso(invio) == 0


class TestFile:
    def test_csv_buste_lettere(self, utente, soggetti):
        invio = _invio(utente, Finalita.COMUNICAZIONI, soggetti)
        dati, nome = carta.csv(invio, utente)
        testo = dati.decode("utf-8-sig")
        assert nome.endswith(".csv") and "Mario Rossi" in testo and "Verdi" not in testo
        dati, _ = carta.docx(invio, utente)
        documento = zipfile.ZipFile(io.BytesIO(dati)).read("word/document.xml").decode()
        assert "Via Roma 1" in documento and "Prot. n." not in documento
        dati, _ = carta.docx(invio, utente, compilate=False)
        assert "MERGEFIELD Riga1" in zipfile.ZipFile(io.BytesIO(dati)).read(
            "word/document.xml").decode()  # fmt: skip
        dati, nome = carta.lettere(invio, utente)
        assert dati.startswith(b"%PDF") and nome.endswith(".pdf")

    def test_viste(self, client, utente, soggetti):
        client.force_login(utente)
        invio = _invio(utente, Finalita.COMUNICAZIONI, soggetti)
        pagina = client.get(reverse("comunicazioni:invio", args=[invio.pk])).content.decode()
        assert "Su carta: 2 destinatari senza email" in pagina
        assert "manca il consenso" in pagina
        assert "Etichette adesive" in pagina
        for formato in ("csv", "buste", "stampa-unione", "lettere", "etichette"):
            r = client.get(reverse("comunicazioni:carta", args=[invio.pk, formato]))
            assert r.status_code == 200 and "attachment" in r["Content-Disposition"]
        assert (
            client.get(reverse("comunicazioni:carta", args=[invio.pk, "altro"])).status_code == 404
        )

    def test_nessuno_su_carta(self, client, utente):
        client.force_login(utente)
        invio = _invio(utente, Finalita.ISTITUZIONALE, [persona("Neri", email="n@example.org")])
        assert client.get(reverse("comunicazioni:carta", args=[invio.pk, "csv"])).status_code == 404
