# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test del libro soci, del tesseramento e delle domande di iscrizione
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import time
from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

import pytest
from django.urls import reverse

from apps.anagrafica.models import Consenso, Soggetto
from apps.core.models import EventoAudit, Organizzazione
from apps.soci import servizi
from apps.soci.forms import DomandaPubblicaForm
from apps.soci.models import CartaTessera, DomandaIscrizione, Socio, Tessera, TipologiaSocio
from apps.soci.servizi import OperazioneNonValida

CF_ROSSI = "RSSMRA50C15A519V"  # Rossi Mario, 15/03/1950
CF_BIANCHI = "BNCLRA80A41F205G"  # Bianchi Laura, 01/01/1980
ANNO = date.today().year
pytestmark = pytest.mark.django_db


@pytest.fixture
def ordinario():
    tipologia = TipologiaSocio.objects.get(nome="Ordinario")
    tipologia.quota_annua = Decimal("25.00")
    tipologia.save()
    return tipologia


@pytest.fixture
def onorario():
    return TipologiaSocio.objects.get(nome="Onorario")  # quota 0


@pytest.fixture
def persona():
    def _crea(cognome="Rossi", nome="Mario", **extra):
        return Soggetto.objects.create(cognome=cognome, nome=nome, **extra)

    return _crea


@pytest.fixture
def admin_utente(crea_utente):
    return crea_utente("capo", ruoli=["Amministratore di sistema"])


@pytest.fixture
def socio(persona, ordinario, admin_utente):
    return servizi.ammetti_socio(persona(codice_fiscale=CF_ROSSI), ordinario, admin_utente)


class TestAmmissione:
    def test_numeri_progressivi_e_categoria(self, persona, ordinario, admin_utente):
        a = servizi.ammetti_socio(persona("Alfa"), ordinario, admin_utente)
        b = servizi.ammetti_socio(persona("Beta"), ordinario, admin_utente)
        assert (a.numero, b.numero) == (1, 2)
        assert a.soggetto.categorie.filter(nome="Socio").exists()
        assert EventoAudit.objects.filter(azione="creazione", oggetto_id=str(a.pk)).exists()

    def test_rifiuti(self, persona, ordinario, admin_utente):
        ente = Soggetto.objects.create(tipo="ente", denominazione="Comune")
        with pytest.raises(OperazioneNonValida):
            servizi.ammetti_socio(ente, ordinario, admin_utente)
        defunto = persona(data_decesso=date(2020, 1, 1))
        with pytest.raises(OperazioneNonValida):
            servizi.ammetti_socio(defunto, ordinario, admin_utente)
        p = persona("Gamma")
        servizi.ammetti_socio(p, ordinario, admin_utente)
        with pytest.raises(OperazioneNonValida):
            servizi.ammetti_socio(p, ordinario, admin_utente)

    def test_numero_non_riusato_dopo_cessazione(self, socio, persona, ordinario, admin_utente):
        servizi.cessa_socio(socio, admin_utente, data_cessazione=date.today(), causa="dimissioni")
        nuovo = servizi.ammetti_socio(persona("Delta"), ordinario, admin_utente)
        assert nuovo.numero == socio.numero + 1


class TestCessazione:
    def test_decesso_aggiorna_anagrafica(self, socio, admin_utente):
        oggi = date.today()
        servizi.cessa_socio(socio, admin_utente, data_cessazione=oggi, causa="decesso")
        socio.refresh_from_db()
        socio.soggetto.refresh_from_db()
        assert socio.stato == "cessato" and socio.soggetto.data_decesso == oggi
        assert not socio.soggetto.categorie.filter(nome="Socio").exists()
        with pytest.raises(OperazioneNonValida):
            servizi.cambia_stato(socio, "attivo", admin_utente)  # deceduto

    def test_riammissione(self, socio, admin_utente):
        servizi.cessa_socio(socio, admin_utente, data_cessazione=date.today(), causa="dimissioni")
        servizi.cambia_stato(socio, "attivo", admin_utente)
        socio.refresh_from_db()
        assert socio.stato == "attivo" and socio.data_cessazione is None
        assert socio.soggetto.categorie.filter(nome="Socio").exists()

    def test_cessazione_prima_dell_ammissione(self, socio, admin_utente):
        with pytest.raises(OperazioneNonValida):
            servizi.cessa_socio(
                socio,
                admin_utente,
                data_cessazione=socio.data_ammissione - timedelta(days=1),
                causa="altro",
            )


class TestTessere:
    def test_rilascio_con_quota_della_tipologia(self, socio, admin_utente):
        t = servizi.rilascia_tessera(socio, ANNO, admin_utente)
        assert t.importo == Decimal("25.00") and t.stato == "da pagare"
        assert not t.attribuita and t.codice == "da attribuire"
        with pytest.raises(OperazioneNonValida):
            servizi.rilascia_tessera(socio, ANNO, admin_utente)

    def test_annullamento_e_nuovo_rilascio(self, socio, admin_utente):
        t1 = servizi.rilascia_tessera(socio, ANNO, admin_utente)
        with pytest.raises(OperazioneNonValida):
            servizi.annulla_tessera(t1, admin_utente, "  ")
        servizi.annulla_tessera(t1, admin_utente, "errore di quota")
        t2 = servizi.rilascia_tessera(socio, ANNO, admin_utente, importo=Decimal("30"))
        assert t2.importo == Decimal("30") and t2.pk != t1.pk

    def test_pagamento_e_ricevute_progressive(self, socio, persona, ordinario, admin_utente):
        altro = servizi.ammetti_socio(persona("Verdi"), ordinario, admin_utente)
        t1 = servizi.rilascia_tessera(socio, ANNO, admin_utente)
        t2 = servizi.rilascia_tessera(altro, ANNO, admin_utente, pagata_il=date.today())
        t1 = servizi.registra_pagamento(
            t1, admin_utente, pagata_il=date.today(), metodo="bonifico", riferimento="CRO1"
        )
        assert (t2.ricevuta_numero, t1.ricevuta_numero) == (1, 2)
        assert t1.codice_ricevuta == f"{date.today().year}/0002"
        with pytest.raises(OperazioneNonValida):
            servizi.registra_pagamento(t1, admin_utente, pagata_il=date.today(), metodo="pos")

    def test_esente_non_si_incassa(self, persona, onorario, admin_utente):
        s = servizi.ammetti_socio(persona(), onorario, admin_utente)
        t = servizi.rilascia_tessera(s, ANNO, admin_utente, pagata_il=date.today())
        assert t.stato == "esente" and t.ricevuta_numero is None
        with pytest.raises(OperazioneNonValida):
            servizi.registra_pagamento(t, admin_utente, pagata_il=date.today(), metodo="contanti")

    def test_solo_soci_attivi(self, socio, admin_utente):
        servizi.cambia_stato(socio, "sospeso", admin_utente)
        with pytest.raises(OperazioneNonValida):
            servizi.rilascia_tessera(socio, ANNO, admin_utente)


def _lotto(utente, da=1001, a=1005, **extra):
    return servizi.carica_lotto(
        utente, anno=ANNO, numero_da=da, numero_a=a, costo_unitario=Decimal("2.50"), **extra
    )


class TestTessereFisiche:
    def test_carico_e_formattazione(self, admin_utente):
        lotto = _lotto(admin_utente, 7, 9, serie="ab", cifre=6)
        assert list(CartaTessera.objects.values_list("codice", flat=True)) == [
            "AB 000007", "AB 000008", "AB 000009",
        ]  # fmt: skip
        assert lotto.quantita == 3 and str(lotto) == f"{ANNO}: AB 000007 – AB 000009"

    def test_carico_sovrapposto_rifiutato(self, admin_utente):
        _lotto(admin_utente, 1, 10)
        with pytest.raises(OperazioneNonValida):
            _lotto(admin_utente, 10, 20)
        with pytest.raises(OperazioneNonValida):
            _lotto(admin_utente, 30, 20)
        assert CartaTessera.objects.count() == 10

    def test_attribuzione_prossima_e_numero_indicato(self, socio, persona, ordinario, admin_utente):
        _lotto(admin_utente)
        t1 = servizi.rilascia_tessera(socio, ANNO, admin_utente, carta="prossima")
        assert t1.codice == "1001" and t1.carta.stato == "attribuita"
        altro = servizi.ammetti_socio(persona("Verdi"), ordinario, admin_utente)
        t2 = servizi.rilascia_tessera(altro, ANNO, admin_utente, carta="1004")
        assert t2.codice == "1004"
        terzo = servizi.ammetti_socio(persona("Neri"), ordinario, admin_utente)
        with pytest.raises(OperazioneNonValida):  # già attribuita
            servizi.rilascia_tessera(terzo, ANNO, admin_utente, carta="1004")
        with pytest.raises(OperazioneNonValida):  # non caricata
            servizi.rilascia_tessera(terzo, ANNO, admin_utente, carta="9999")
        assert not Tessera.objects.filter(socio=terzo).exists()  # tutto annullato
        t3 = servizi.rilascia_tessera(terzo, ANNO, admin_utente)
        assert servizi.attribuisci_carta(t3, admin_utente).codice == "1002"
        with pytest.raises(OperazioneNonValida):
            servizi.attribuisci_carta(t3, admin_utente)

    def test_annullamento_libera_o_annulla_la_tessera(self, socio, admin_utente):
        _lotto(admin_utente)
        t = servizi.rilascia_tessera(socio, ANNO, admin_utente, carta="prossima")
        servizi.annulla_tessera(t, admin_utente, "attribuita per errore", libera_carta=True)
        assert CartaTessera.objects.get(codice="1001").stato == "disponibile"
        t = servizi.rilascia_tessera(socio, ANNO, admin_utente, carta="prossima")
        assert t.codice == "1001"
        servizi.annulla_tessera(t, admin_utente, "tessera rovinata")
        assert CartaTessera.objects.get(codice="1001").stato == "annullata"
        t = servizi.rilascia_tessera(socio, ANNO, admin_utente, carta="prossima")
        assert t.codice == "1002"

    def test_stato_e_giacenza(self, socio, admin_utente):
        _lotto(admin_utente)
        servizi.rilascia_tessera(socio, ANNO, admin_utente, carta="prossima")
        carta = CartaTessera.objects.get(codice="1005")
        with pytest.raises(OperazioneNonValida):
            servizi.cambia_stato_carta(carta, "smarrita", admin_utente, "")
        servizi.cambia_stato_carta(carta, "restituita", admin_utente, "reso a fine anno")
        with pytest.raises(OperazioneNonValida):
            servizi.cambia_stato_carta(
                CartaTessera.objects.get(codice="1001"), "smarrita", admin_utente, "x"
            )
        g = servizi.giacenza(ANNO)
        assert (g["totale"], g["disponibile"], g["attribuita"], g["restituita"]) == (5, 3, 1, 1)
        assert g["costo"] == Decimal("10.00")  # 4 tessere non restituite x 2,50

    def test_rinnovo_e_attribuzione_massiva(self, persona, ordinario, admin_utente):
        soci = [servizi.ammetti_socio(persona(f"S{i}"), ordinario, admin_utente) for i in range(4)]
        _lotto(admin_utente, 1, 2)
        rilasciate, _ = servizi.rinnovo_massivo(ANNO, admin_utente, attribuisci=True)
        assert [t.codice for t in rilasciate] == ["1", "2", "da attribuire", "da attribuire"]
        _lotto(admin_utente, 50, 60)
        fatte, mancanti = servizi.attribuzione_massiva(ANNO, admin_utente)
        assert [t.socio for t in fatte] == soci[2:] and mancanti == 0
        assert [t.codice for t in fatte] == ["50", "51"]


class TestMorositaERinnovo:
    def test_in_regola_morosi_esenti(self, persona, ordinario, onorario, admin_utente):
        pagante = servizi.ammetti_socio(persona("Uno"), ordinario, admin_utente)
        moroso = servizi.ammetti_socio(persona("Due"), ordinario, admin_utente)
        senza = servizi.ammetti_socio(persona("Tre"), ordinario, admin_utente)
        esente = servizi.ammetti_socio(persona("Quattro"), onorario, admin_utente)
        servizi.rilascia_tessera(pagante, ANNO, admin_utente, pagata_il=date.today())
        servizi.rilascia_tessera(moroso, ANNO, admin_utente)
        servizi.rilascia_tessera(esente, ANNO, admin_utente)
        assert set(Socio.objects.in_regola(ANNO)) == {pagante}
        assert set(Socio.objects.morosi(ANNO)) == {moroso, senza}

    def test_rinnovo_massivo(self, persona, ordinario, admin_utente):
        soci = [servizi.ammetti_socio(persona(f"S{i}"), ordinario, admin_utente) for i in range(3)]
        servizi.rilascia_tessera(soci[0], ANNO, admin_utente)
        servizi.cambia_stato(soci[2], "sospeso", admin_utente)
        rilasciate, errori = servizi.rinnovo_massivo(ANNO, admin_utente)
        assert [t.socio for t in rilasciate] == [soci[1]] and errori == []
        assert servizi.soci_da_rinnovare(ANNO).count() == 0


class TestDomande:
    def _domanda(self, **extra):
        dati = {
            "nome": "Laura", "cognome": "Bianchi", "codice_fiscale": CF_BIANCHI,
            "data_nascita": date(1980, 1, 1), "luogo_nascita": "Milano",
            "email": "laura@example.org", "indirizzo": "Via Roma 1", "cap": "20100",
            "comune": "Milano", "provincia": "MI", "accetta_statuto": True,
            "consenso_comunicazioni": True,
        }  # fmt: skip
        return DomandaIscrizione.objects.create(**{**dati, **extra})

    def test_accoglimento_crea_anagrafica_socio_e_consensi(self, ordinario, admin_utente):
        d = self._domanda()
        socio = servizi.accogli_domanda(
            d, admin_utente, tipologia=ordinario, data_ammissione=date.today(), tessera_anno=ANNO
        )
        d.refresh_from_db()
        assert d.stato == "accolta" and d.socio == socio
        assert socio.soggetto.codice_fiscale == CF_BIANCHI and socio.tessere.count() == 1
        consensi = {
            c.finalita: c.prestato for c in Consenso.objects.filter(soggetto=socio.soggetto)
        }
        assert consensi == {"comunicazioni": True, "immagini": False}
        with pytest.raises(OperazioneNonValida):
            servizi.accogli_domanda(
                d, admin_utente, tipologia=ordinario, data_ammissione=date.today()
            )

    def test_accoglimento_usa_scheda_esistente(self, persona, ordinario, admin_utente):
        esistente = persona("Bianchi", "Laura", codice_fiscale=CF_BIANCHI)
        socio = servizi.accogli_domanda(
            self._domanda(), admin_utente, tipologia=ordinario, data_ammissione=date.today()
        )
        assert socio.soggetto == esistente and Soggetto.objects.count() == 1

    def test_rigetto_richiede_motivo(self, admin_utente):
        d = self._domanda()
        with pytest.raises(OperazioneNonValida):
            servizi.respingi_domanda(d, admin_utente, "")
        servizi.respingi_domanda(d, admin_utente, "requisiti statutari mancanti")
        d.refresh_from_db()
        assert d.stato == "respinta"


class TestModuloPubblico:
    DATI = {
        "nome": "Laura", "cognome": "Bianchi", "codice_fiscale": CF_BIANCHI.lower(),
        "data_nascita": "1980-01-01", "luogo_nascita": "Milano", "email": "laura@example.org",
        "indirizzo": "Via Roma 1", "cap": "20100", "comune": "Milano", "provincia": "mi",
        "accetta_statuto": "on", "privacy": "on",
    }  # fmt: skip

    @pytest.fixture(autouse=True)
    def attiva(self):
        org = Organizzazione.corrente()
        org.iscrizioni_online = True
        org.save()

    def _token(self, secondi_fa):
        """Token come se il modulo fosse stato aperto `secondi_fa` secondi fa."""
        emesso = time.time() - secondi_fa
        with mock.patch("apps.soci.forms._adesso", return_value=emesso):
            return DomandaPubblicaForm().initial["token"]

    def _invia(self, client, secondi_fa=60, **extra):
        dati = {**self.DATI, "token": self._token(secondi_fa), **extra}
        return client.post(reverse("iscrizione"), dati)

    def test_disattivato_404(self, client):
        org = Organizzazione.corrente()
        org.iscrizioni_online = False
        org.save()
        assert client.get(reverse("iscrizione")).status_code == 404

    def test_invio_valido(self, client):
        assert client.get(reverse("iscrizione")).status_code == 200
        r = self._invia(client)
        assert r.status_code == 302, r.context["form"].errors
        d = DomandaIscrizione.objects.get()
        assert d.origine == "pubblica" and d.codice_fiscale == CF_BIANCHI and d.provincia == "MI"

    def test_campo_trappola(self, client):
        self._invia(client, sito="http://spam.example")
        assert not DomandaIscrizione.objects.exists()

    def test_invio_troppo_rapido(self, client):
        self._invia(client, secondi_fa=1)
        assert not DomandaIscrizione.objects.exists()

    def test_token_manomesso(self, client):
        dati = {**self.DATI, "token": "falso"}
        client.post(reverse("iscrizione"), dati)
        assert not DomandaIscrizione.objects.exists()

    def test_limite_per_ip(self, client):
        for _ in range(4):
            self._invia(client)
        assert DomandaIscrizione.objects.count() == 3

    def test_privacy_obbligatoria(self, client):
        dati = {k: v for k, v in self.DATI.items() if k != "privacy"}
        self.DATI, salvati = dati, self.DATI
        try:
            self._invia(client)
        finally:
            self.DATI = salvati
        assert not DomandaIscrizione.objects.exists()


class TestViste:
    def test_pagine_principali(self, client, socio, admin_utente):
        t = servizi.rilascia_tessera(socio, ANNO, admin_utente, pagata_il=date.today())
        d = DomandaIscrizione.objects.create(
            nome="A", cognome="B", codice_fiscale=CF_BIANCHI, data_nascita=date(1980, 1, 1),
            luogo_nascita="X", email="a@example.org", indirizzo="via", cap="00100",
            comune="Roma", provincia="RM",
        )  # fmt: skip
        client.force_login(admin_utente)
        for url in [
            reverse("soci:elenco"),
            reverse("soci:elenco") + "?quota=morosi",
            reverse("soci:nuovo") + "?q=rossi",
            reverse("soci:dettaglio", args=[socio.pk]),
            reverse("soci:modifica", args=[socio.pk]),
            reverse("soci:tessere"),
            reverse("soci:rinnovo") + f"?anno={ANNO}",
            reverse("soci:domande"),
            reverse("soci:domanda", args=[d.pk]),
            reverse("soci:domanda_nuova"),
            reverse("soci:tipologie"),
            reverse("anagrafica:dettaglio", args=[socio.soggetto.pk]),
            reverse("core:cruscotto"),
        ]:
            assert client.get(url).status_code == 200, url
        r = client.get(reverse("soci:ricevuta", args=[t.pk]))
        assert r.status_code == 200 and r["Content-Type"] == "application/pdf"
        assert r.content.startswith(b"%PDF")
        r = client.get(reverse("soci:libro_pdf"))
        assert r.status_code == 200 and r.content.startswith(b"%PDF")

    def test_ricerca_htmx_parziale(self, client, socio, admin_utente):
        client.force_login(admin_utente)
        r = client.get(reverse("soci:elenco"), {"q": "rossi"}, HTTP_HX_REQUEST="true")
        html = r.content.decode()
        assert 'id="tabella-soci"' in html and "<html" not in html and "Rossi" in html

    def test_ammissione_da_interfaccia(self, client, persona, ordinario, admin_utente):
        p = persona(codice_fiscale=CF_ROSSI)
        client.force_login(admin_utente)
        r = client.post(
            reverse("soci:ammissione", args=[p.pk]),
            {
                "tipologia": ordinario.pk,
                "data_ammissione": date.today().isoformat(),
                "tessera": "on",
            },
        )
        socio = Socio.objects.get(soggetto=p)
        assert r.status_code == 302 and socio.tessere.count() == 1

    def test_incasso_da_interfaccia(self, client, socio, crea_utente):
        t = servizi.rilascia_tessera(socio, ANNO, None)
        tesoriere = crea_utente("tesoriere", ruoli=["Tesoriere"])
        client.force_login(tesoriere)
        client.post(
            reverse("soci:pagamento", args=[t.pk]),
            {
                "pagamento-pagata_il": date.today().isoformat(),
                "pagamento-metodo": "contanti",
                "pagamento-importo": "25.00",
            },
        )
        t.refresh_from_db()
        assert t.pagata and t.ricevuta_numero == 1

    def test_permessi(self, client_ruolo, socio):
        t = servizi.rilascia_tessera(socio, ANNO, None)
        c = client_ruolo("Consigliere")
        assert c.get(reverse("soci:elenco")).status_code == 200
        assert c.get(reverse("soci:nuovo")).status_code == 403
        assert c.get(reverse("soci:libro_pdf")).status_code == 403
        dati = {"pagamento-pagata_il": date.today().isoformat(), "pagamento-metodo": "pos",
                "pagamento-importo": "25"}  # fmt: skip
        assert c.post(reverse("soci:pagamento", args=[t.pk]), dati).status_code == 403
        c.logout()
        segretario = client_ruolo("Segretario", username="segretario")
        assert segretario.post(reverse("soci:pagamento", args=[t.pk]), dati).status_code == 403
        assert segretario.get(reverse("soci:libro_pdf")).status_code == 200

    def test_tessere_fisiche_da_interfaccia(self, client, client_ruolo, socio, admin_utente):
        client.force_login(admin_utente)
        r = client.post(
            reverse("soci:lotto_nuovo"),
            {"anno": ANNO, "serie": "", "numero_da": 100, "numero_a": 104, "cifre": 0,
             "data_acquisizione": date.today().isoformat(), "fornitore": "Sede centrale",
             "costo_unitario": "3.00"},
        )  # fmt: skip
        assert r.status_code == 302 and CartaTessera.objects.count() == 5
        t = servizi.rilascia_tessera(socio, ANNO, admin_utente)
        client.post(reverse("soci:attribuisci", args=[t.pk]), {"codice": "103"})
        t.refresh_from_db()
        assert t.codice == "103"
        for url in [reverse("soci:tessere_fisiche"), reverse("soci:lotto_nuovo"),
                    reverse("soci:tessere") + "?stato=da_attribuire"]:  # fmt: skip
            assert client.get(url).status_code == 200, url
        r = client.get(reverse("soci:esporta_tesserati"), {"anno": ANNO})
        assert "103;Sezione principale;001;1;;Rossi" in r.content.decode("utf-8-sig")
        client.logout()
        c = client_ruolo("Consigliere")
        assert c.get(reverse("soci:tessere_fisiche")).status_code == 200
        assert c.get(reverse("soci:lotto_nuovo")).status_code == 403

    def test_esportazione_csv_sicura(self, client, persona, ordinario, admin_utente):
        servizi.ammetti_socio(persona("=HYPERLINK(1)"), ordinario, admin_utente)
        client.force_login(admin_utente)
        r = client.get(reverse("soci:esporta"))
        assert "'=HYPERLINK(1)" in r.content.decode("utf-8-sig")
        assert Tessera.objects.count() == 0
