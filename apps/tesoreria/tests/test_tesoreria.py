# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test della tesoreria: esercizi e saldi, prima nota, giroconti, quote in
# *              prima nota, chiusura con riporto, preventivo e rendiconto per cassa.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.anagrafica.models import Soggetto
from apps.soci import servizi as soci
from apps.soci.models import TipologiaSocio
from apps.tesoreria import servizi
from apps.tesoreria.models import Conto, Esercizio, Movimento, Voce

pytestmark = pytest.mark.django_db
ANNO = date.today().year
D = Decimal


@pytest.fixture(autouse=True)
def cartella_media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def tesoriere(crea_utente):
    return crea_utente("tesoriere", ruoli=["Tesoriere"])


@pytest.fixture
def cassa():
    return Conto.objects.get(nome="Cassa")


@pytest.fixture
def banca():
    return Conto.objects.get(nome="Banca")


def voce(codice):
    return Voce.objects.get(codice=codice)


def mov(utente, tipo, importo, conto, codice=None, giorno=None, **extra):
    return servizi.registra_movimento(
        {"data": giorno or date(ANNO, 3, 1), "tipo": tipo, "importo": D(importo), "conto": conto,
         "voce": voce(codice) if codice else None, "descrizione": f"{tipo} {importo}", **extra},
        utente,
    )  # fmt: skip


class TestPianoDeiConti:
    def test_voci_modello_d(self):
        assert voce("E.A.1").descrizione == "Entrate da quote associative e apporti dei fondatori"
        assert voce("U.A.2").descrizione == "Servizi"
        assert voce("E.A.10").descrizione == "Altre entrate"
        assert voce("U.IMP.1").descrizione == "Imposte"
        assert Voce.objects.filter(padre__isnull=True).count() == 58


class TestPrimaNota:
    def test_saldi_numerazione_giroconti(self, tesoriere, cassa, banca):
        e = servizi.apri_esercizio(ANNO, tesoriere)
        servizi.imposta_saldi_iniziali(e, {cassa: D("100"), banca: D("1000")}, tesoriere)
        m1 = mov(tesoriere, "entrata", "50", cassa, "E.A.4")
        m2 = mov(tesoriere, "uscita", "30.50", banca, "U.A.2")
        m3 = mov(tesoriere, "giroconto", "40", cassa, conto_destinazione=banca)
        assert (m1.numero, m2.numero, m3.numero) == (1, 2, 3) and m3.voce is None
        assert servizi.saldo(cassa, e) == D("110.00") and servizi.saldo(banca, e) == D("1009.50")
        servizi.annulla_movimento(m2, tesoriere, "doppio")
        assert servizi.saldo(banca, e) == D("1040.00")
        assert servizi.riepilogo(e) == {"entrate": D("50"), "uscite": D("0"), "avanzo": D("50")}

    def test_regole(self, tesoriere, cassa):
        with pytest.raises(ValidationError):  # esercizio mancante
            mov(tesoriere, "entrata", "10", cassa, "E.A.4")
        servizi.apri_esercizio(ANNO, tesoriere)
        with pytest.raises(ValidationError):  # voce di uscita su un'entrata
            mov(tesoriere, "entrata", "10", cassa, "U.A.2")
        with pytest.raises(ValidationError):  # giroconto sullo stesso conto
            mov(tesoriere, "giroconto", "10", cassa, conto_destinazione=cassa)
        with pytest.raises(ValidationError):
            servizi.apri_esercizio(ANNO, tesoriere)

    def test_giustificativo(self, tesoriere, cassa):
        servizi.apri_esercizio(ANNO, tesoriere)
        f = SimpleUploadedFile("fattura 12.pdf", b"%PDF-1.4 fattura")
        m = servizi.registra_movimento(
            {"data": date(ANNO, 2, 1), "tipo": "uscita", "importo": D("12"), "conto": cassa,
             "voce": voce("U.E.1"), "descrizione": "Cancelleria"},
            tesoriere, giustificativo=f,
        )  # fmt: skip
        assert m.giustificativo_nome == "fattura 12.pdf" and "fattura" not in m.giustificativo.name
        with pytest.raises(ValidationError):
            servizi.registra_movimento(
                {"data": date(ANNO, 2, 1), "tipo": "uscita", "importo": D("1"), "conto": cassa,
                 "voce": voce("U.E.1"), "descrizione": "x"},
                tesoriere, giustificativo=SimpleUploadedFile("virus.exe", b"MZ"),
            )  # fmt: skip


class TestQuote:
    def test_incasso_va_in_prima_nota(self, tesoriere, cassa, banca):
        ordinario = TipologiaSocio.objects.get(nome="Ordinario")
        ordinario.quota_annua = D("20")
        ordinario.save()
        servizi.apri_esercizio(ANNO, tesoriere)  # il listino dell'anno prende la quota
        s1 = soci.ammetti_socio(Soggetto.objects.create(cognome="Uno"), ordinario, tesoriere)
        s2 = soci.ammetti_socio(Soggetto.objects.create(cognome="Due"), ordinario, tesoriere)
        t1 = soci.rilascia_tessera(s1, ANNO, tesoriere, pagata_il=date.today())  # contanti
        t2 = soci.rilascia_tessera(s2, ANNO, tesoriere)
        soci.registra_pagamento(t2, tesoriere, pagata_il=date.today(), metodo="bonifico")
        m1, m2 = Movimento.objects.get(tessera=t1), Movimento.objects.get(tessera=t2)
        assert m1.conto == cassa and m2.conto == banca and m1.voce.codice == "E.A.1"
        assert m1.controparte == s1.soggetto and "ricevuta n." in m1.documento

    def test_quote_senza_esercizio_si_recuperano(self, tesoriere):
        ordinario = TipologiaSocio.objects.get(nome="Ordinario")
        ordinario.quota_annua = D("20")
        ordinario.save()
        s = soci.ammetti_socio(Soggetto.objects.create(cognome="Tre"), ordinario, tesoriere)
        t = soci.rilascia_tessera(s, ANNO, tesoriere, pagata_il=date.today())
        assert t.pagata and not Movimento.objects.exists()  # l'incasso resta valido
        e = servizi.apri_esercizio(ANNO, tesoriere)
        assert servizi.quote_da_registrare(e).count() == 1
        assert servizi.registra_quote_mancanti(e, tesoriere) == (1, [])
        assert servizi.quote_da_registrare(e).count() == 0


class TestChiusura:
    def test_chiusura_riporto_e_riapertura(self, tesoriere, cassa, banca):
        prec = servizi.apri_esercizio(ANNO - 1, tesoriere)
        servizi.imposta_saldi_iniziali(prec, {cassa: D("10"), banca: D("500")}, tesoriere)
        mov(tesoriere, "entrata", "90", cassa, "E.A.1", giorno=date(ANNO - 1, 5, 5))
        servizi.chiudi_esercizio(prec, tesoriere, "Assemblea del 20/04")
        corrente = Esercizio.objects.get(anno=ANNO)  # creato dalla chiusura
        iniziali = {s.conto: s.iniziale for s in corrente.saldi.all()}
        assert iniziali == {cassa: D("100.00"), banca: D("500.00")}
        assert not servizi.saldi_iniziali_modificabili(corrente)
        with pytest.raises(ValidationError):  # esercizio chiuso: niente movimenti
            mov(tesoriere, "uscita", "5", cassa, "U.E.1", giorno=date(ANNO - 1, 6, 1))
        with pytest.raises(ValidationError):  # l'anno in corso non si chiude
            servizi.chiudi_esercizio(corrente, tesoriere)
        servizi.riapri_esercizio(prec, tesoriere, "correzione")
        mov(tesoriere, "uscita", "5", cassa, "U.E.1", giorno=date(ANNO - 1, 6, 1))
        servizi.chiudi_esercizio(Esercizio.objects.get(anno=ANNO - 1), tesoriere)
        assert corrente.saldi.get(conto=cassa).iniziale == D("95.00")  # riporto aggiornato


class TestRendiconto:
    def test_modello_d(self, tesoriere, cassa, banca):
        prec = servizi.apri_esercizio(ANNO - 1, tesoriere)
        mov(tesoriere, "entrata", "200", cassa, "E.A.1", giorno=date(ANNO - 1, 1, 10))
        servizi.chiudi_esercizio(prec, tesoriere)
        e = Esercizio.objects.get(anno=ANNO)
        mov(tesoriere, "entrata", "300", cassa, "E.A.1")
        mov(tesoriere, "entrata", "50", banca, "E.A.4.6")  # sottovoce «Offerte e donazioni»
        mov(tesoriere, "uscita", "120", banca, "U.A.2.1")  # sottovoce «Corone e onoranze»
        mov(tesoriere, "uscita", "10", banca, "U.D.1")
        mov(tesoriere, "uscita", "100", banca, "U.INV.1")
        mov(tesoriere, "giroconto", "100", cassa, conto_destinazione=banca)
        r = servizi.rendiconto(e)
        a = r["gestione"][0]
        entrate = {v.codice: (cor, pr) for v, cor, pr in a.entrate}
        assert entrate["E.A.1"] == (D("300"), D("200")) and entrate["E.A.4"] == (D("50"), D("0"))
        assert a.tot_uscite == D("120") and a.avanzo == D("230")
        assert r["gestione"][3].tot_uscite == D("10")
        assert r["avanzo"] == D("220") and r["investimenti"].tot_uscite == D("100")
        assert r["avanzo_complessivo"] == D("120")
        assert r["cassa"] == D("400") and r["banca"] == D("-80")

    def test_preventivo(self, tesoriere, cassa):
        e = servizi.apri_esercizio(ANNO, tesoriere)
        servizi.salva_preventivo(e, {voce("E.A.1"): D("500")}, tesoriere)
        mov(tesoriere, "entrata", "300", cassa, "E.A.1")
        riga = servizi.confronto_preventivo(e)[0]
        assert (riga["previsto"], riga["effettivo"], riga["differenza"]) == (
            D("500"),
            D("300"),
            D("-200"),
        )


class TestViste:
    def test_pagine(self, client, tesoriere, cassa):
        client.force_login(tesoriere)
        assert client.get(reverse("tesoreria:cruscotto")).status_code == 200
        client.post(reverse("tesoreria:esercizio_nuovo"), {"anno": ANNO})
        e = Esercizio.objects.get(anno=ANNO)
        r = client.post(
            reverse("tesoreria:movimento_nuovo"),
            {"tipo": "uscita", "data": date(ANNO, 4, 1).isoformat(), "importo": "25.00",
             "conto": cassa.pk, "voce": voce("U.A.2.1").pk, "descrizione": "Corona 25 aprile",
             "controparte_testo": "Fioraio", "file": SimpleUploadedFile("ricevuta.pdf", b"%PDF-1.4")},
        )  # fmt: skip
        m = Movimento.objects.get()
        assert r.status_code == 302 and m.giustificativo_nome == "ricevuta.pdf"
        r = client.post(
            reverse("tesoreria:movimento_nuovo"),
            {"tipo": "entrata", "data": date(ANNO, 4, 1).isoformat(), "importo": "5",
             "conto": cassa.pk, "voce": voce("U.A.2").pk, "descrizione": "errata"},
        )  # fmt: skip
        assert r.status_code == 200 and Movimento.objects.count() == 1
        for url in [
            reverse("tesoreria:cruscotto") + f"?anno={ANNO}",
            reverse("tesoreria:prima_nota") + "?q=corona",
            reverse("tesoreria:movimento", args=[m.pk]),
            reverse("tesoreria:movimento_modifica", args=[m.pk]),
            reverse("tesoreria:preventivo", args=[ANNO]),
            reverse("tesoreria:rendiconto", args=[ANNO]),
            reverse("tesoreria:rendiconti"),
            reverse("tesoreria:conti"),
            reverse("tesoreria:voci"),
            reverse("tesoreria:sottovoce_nuova"),
            reverse("tesoreria:giustificativo", args=[m.pk]),
        ]:
            assert client.get(url).status_code == 200, url
        assert client.get(
            reverse("tesoreria:rendiconto", args=[ANNO]) + "?formato=pdf"
        ).content.startswith(b"%PDF")
        assert "Corona 25 aprile" in client.get(
            reverse("tesoreria:esporta") + f"?anno={ANNO}"
        ).content.decode("utf-8-sig")
        assert "25,00" in client.get(
            reverse("tesoreria:rendiconto", args=[ANNO]) + "?formato=csv"
        ).content.decode("utf-8-sig")
        r = client.get(
            reverse("tesoreria:prima_nota"), {"anno": ANNO, "q": "corona"}, HTTP_HX_REQUEST="true"
        )
        assert 'id="tabella-movimenti"' in r.content.decode() and "<html" not in r.content.decode()
        client.post(
            reverse("tesoreria:preventivo", args=[ANNO]), {f"voce-{voce('U.A.2').pk}": "300"}
        )
        assert e.previsioni.get(voce__codice="U.A.2").importo == D("300")

    def test_permessi(self, client_ruolo):
        servizi.apri_esercizio(ANNO, None)
        c = client_ruolo("Consigliere")
        assert c.get(reverse("tesoreria:rendiconto", args=[ANNO])).status_code == 200
        assert c.get(reverse("tesoreria:prima_nota")).status_code == 403
        assert c.get(reverse("tesoreria:movimento_nuovo")).status_code == 403
        c.logout()
        s = client_ruolo("Segretario", username="segr")
        assert s.get(reverse("tesoreria:cruscotto")).status_code == 403
