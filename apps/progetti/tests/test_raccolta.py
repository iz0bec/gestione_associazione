# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test della raccolta automatica dei bandi (P3): lettura di RSS, Atom, RDF e
# *              pagine web, parole chiave, proposte senza doppioni, vaglio, scaricamento sicuro.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from unittest import mock

import pytest
from django.urls import reverse

from apps.collegamenti.trasporto import Destinazione, Risposta
from apps.progetti import raccolta
from apps.progetti.models import Bando, BandoProposto, FonteBandi, ParolaChiave

pytestmark = pytest.mark.django_db

RSS = b"""<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>CSV</title>
<item><title>Bando volontariato 2027</title><link>https://esempio.it/bando-volontariato</link>
<description><![CDATA[<p>Contributi alle <b>associazioni</b> di promozione sociale</p>]]></description>
<pubDate>Fri, 10 Jul 2026 09:00:00 +0000</pubDate></item>
<item><title>Concessione demaniale a Maratea</title><link>https://esempio.it/demanio</link>
<description>Avviso per le associazioni</description></item>
<item><title>Incentivi all'export per le imprese</title><link>https://esempio.it/export</link></item>
</channel></rss>"""

ATOM = """<?xml version="1.0" encoding="utf-8"?><feed xmlns="http://www.w3.org/2005/Atom">
<title>Fondazione</title><entry><title>Memoria e Città: progetti con le scuole</title>
<link rel="alternate" href="https://esempio.it/memoria"/><updated>2026-11-10T10:00:00Z</updated>
<summary>Per enti del Terzo settore</summary></entry></feed>""".encode()

RDF = b"""<?xml version="1.0"?><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
xmlns="http://purl.org/rss/1.0/"><item rdf:about="https://esempio.it/rdf"><title>Avviso cultura</title>
<link>https://esempio.it/rdf</link></item></rdf:RDF>"""

PAGINA = """<html><body><nav><a href="/">Home</a></nav>
<a href="/avvisi/legalita-2027">Avviso pubblico per progetti di educazione alla legalità</a>
<a href="https://altro.it/x#a">Contributi alla cultura per le associazioni culturali</a>
<a href="mailto:a@b.it">Scrivici per avere informazioni sul bando</a></body></html>""".encode()


@pytest.fixture
def parole():
    for p in ("associazioni", "memoria", "legalità", "cultura", "terzo settore"):
        ParolaChiave.objects.create(parola=p)
    ParolaChiave.objects.create(parola="concessione demaniale", esclusa=True)


def _fonte(**extra):
    dati = {"nome": "CSV", "indirizzo": "https://esempio.it/feed/"} | extra
    return FonteBandi.objects.create(**dati)


class TestLettura:
    def test_rss(self):
        n = raccolta.leggi_feed(RSS)
        assert [x.link for x in n][:2] == ["https://esempio.it/bando-volontariato",
                                           "https://esempio.it/demanio"]  # fmt: skip
        assert n[0].sommario == "Contributi alle associazioni di promozione sociale"
        assert n[0].data.year == 2026

    def test_atom_e_rdf(self):
        a = raccolta.leggi_feed(ATOM)[0]
        assert (a.titolo, a.link, a.data.day) == (
            "Memoria e Città: progetti con le scuole", "https://esempio.it/memoria", 10,
        )  # fmt: skip
        assert raccolta.leggi_feed(RDF)[0].titolo == "Avviso cultura"

    def test_xml_pericoloso_o_rotto(self):
        bomba = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><rss>&a;</rss>'
        with pytest.raises(raccolta.ErroreRaccolta):
            raccolta.leggi_feed(bomba)
        with pytest.raises(raccolta.ErroreRaccolta):
            raccolta.leggi_feed(b"<html>non un feed")

    def test_pagina(self):
        n = raccolta.leggi_pagina(PAGINA, "text/html; charset=utf-8", "https://esempio.it/bandi/")
        assert [x.link for x in n] == ["https://esempio.it/avvisi/legalita-2027",
                                       "https://altro.it/x"]  # fmt: skip

    def test_parole_senza_accenti_e_maiuscole(self):
        assert raccolta.corrisponde("Educazione alla LEGALITA", ["legalità"], []) == (
            True, ["legalità"],
        )  # fmt: skip
        assert raccolta.corrisponde("Associazioni", ["associazione"], [])[0] is False
        assert raccolta.corrisponde("Associazioni e imprese", ["associazioni"], ["imprese"]) == (
            False, [],
        )  # fmt: skip


class TestRaccolta:
    def test_propone_senza_doppioni(self, parole):
        f = _fonte()
        with mock.patch.object(raccolta, "scarica", return_value=(RSS, "application/rss+xml")):
            assert raccolta.raccogli(f) == 1
            assert raccolta.raccogli(f) == 0  # rieseguibile
        p = BandoProposto.objects.get()
        assert p.titolo == "Bando volontariato 2027" and p.parole == "associazioni"
        f.refresh_from_db()
        assert f.errori == 0 and "3 elementi letti, 0 proposte" in f.ultimo_esito

    def test_proponi_tutto_rispetta_le_escluse(self, parole):
        f = _fonte(tutte=True)
        with mock.patch.object(raccolta, "scarica", return_value=(RSS, "application/rss+xml")):
            assert raccolta.raccogli(f) == 2  # tutto tranne la concessione demaniale

    def test_senza_parole_chiave(self):
        f = _fonte()
        with mock.patch.object(raccolta, "scarica") as scarica:
            assert raccolta.raccogli(f) == 0
        scarica.assert_not_called()
        f.refresh_from_db()
        assert f.errori == 1 and "parola chiave" in f.ultimo_esito

    def test_pagina_sorvegliata(self, parole):
        f = _fonte(tipo="pagina", indirizzo="https://esempio.it/bandi/")
        with mock.patch.object(raccolta, "scarica", return_value=(PAGINA, "text/html")):
            assert raccolta.raccogli(f) == 2

    def test_errore_registrato(self, parole):
        f = _fonte()
        with mock.patch.object(raccolta, "scarica", side_effect=raccolta.ErroreRaccolta("giù")):
            assert raccolta.raccogli(f) == 0
        f.refresh_from_db()
        assert (f.errori, f.ultimo_esito) == (1, "giù")

    def test_raccogli_tutte_avvisa(self, parole):
        _fonte()
        _fonte(nome="Spenta", indirizzo="https://esempio.it/altro/", attiva=False)
        with (
            mock.patch.object(raccolta, "scarica", return_value=(RSS, "application/rss+xml")),
            mock.patch("apps.core.avvisi.avvisa") as avvisa,
        ):
            assert raccolta.raccogli_tutte() == 1
        assert avvisa.call_args.args[0] == "bandi" and "1 nuovo" in avvisa.call_args.args[1]


class TestScaricamento:
    def _risposta(self, stato, corpo=b"", **intestazioni):
        return Risposta(stato, intestazioni, corpo, Destinazione(url="https://esempio.it"))

    def test_solo_https(self):
        with pytest.raises(raccolta.ErroreRaccolta, match="https"):
            raccolta.scarica("http://esempio.it/feed")

    def test_reindirizzamenti(self):
        risposte = [self._risposta(301, location="/nuovo/feed?x=1"), self._risposta(200, b"ok")]
        with mock.patch("apps.collegamenti.trasporto.richiesta", side_effect=risposte) as r:
            assert raccolta.scarica("https://esempio.it/feed")[0] == b"ok"
        assert r.call_args.args[2] == "/nuovo/feed?x=1"

    def test_reindirizzamento_verso_http_rifiutato(self):
        with (
            mock.patch("apps.collegamenti.trasporto.richiesta",
                       return_value=self._risposta(302, location="http://interno/")),
            pytest.raises(raccolta.ErroreRaccolta, match="https"),
        ):  # fmt: skip
            raccolta.scarica("https://esempio.it/feed")

    def test_indirizzo_privato_rifiutato(self):
        with pytest.raises(raccolta.ErroreRaccolta, match="privato"):
            raccolta.scarica("https://127.0.0.1/feed")


class TestVaglio:
    def test_accogli_e_scarta(self, crea_utente, parole):
        utente = crea_utente("p", ruoli=["Presidente"])
        f = _fonte(tutte=True)
        with mock.patch.object(raccolta, "scarica", return_value=(RSS, "application/rss+xml")):
            raccolta.raccogli(f)
        primo, secondo = BandoProposto.objects.order_by("pk")
        bando = raccolta.accogli(primo, utente)
        assert bando.stato == Bando.Stato.SEGNALATO and bando.finanziatore_testo == "CSV"
        assert bando.link == primo.link
        with pytest.raises(raccolta.ErroreRaccolta):
            raccolta.accogli(primo, utente)
        assert raccolta.scarta([secondo], utente) == 1
        secondo.refresh_from_db()
        assert secondo.stato == "scartato" and secondo.esaminato_da == utente

    def test_pagine(self, client_ruolo, parole):
        c = client_ruolo("Segretario")
        r = c.post(reverse("progetti:fonti"), {"azione": "portale", "portale": "csv-basilicata"},
                   follow=True)  # fmt: skip
        assert "CSV Basilicata" in r.content.decode()
        fonte = FonteBandi.objects.get()
        assert fonte.tutte and fonte.indirizzo.startswith("https://www.csvbasilicata.it/")
        with mock.patch.object(raccolta, "scarica", return_value=(RSS, "application/rss+xml")):
            r = c.post(reverse("progetti:fonti"), {"azione": "controlla", "fonte": fonte.pk},
                       follow=True)  # fmt: skip
        assert "Bando volontariato 2027" in r.content.decode()
        p = BandoProposto.objects.order_by("pk").first()
        r = c.post(reverse("progetti:proposte"), {"accogli": p.pk})
        assert r.status_code == 302 and "/modifica/" in r["Location"]
        r = c.post(
            reverse("progetti:fonti"),
            {"azione": "fonte", "nome": "Comune", "tipo": "feed", "indirizzo": "http://comune.it/"},
        )
        assert "Serve un indirizzo https" in r.content.decode()
        r = c.post(reverse("progetti:fonti"), {"azione": "suggerite"}, follow=True)
        assert ParolaChiave.objects.filter(esclusa=True).exists()

    def test_consigliere_escluso(self, client_ruolo):
        c = client_ruolo("Consigliere")
        assert c.get(reverse("progetti:proposte")).status_code == 403
        assert c.get(reverse("progetti:fonti")).status_code == 403
