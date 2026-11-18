# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test della F4 blocco A (ciclo delle tessere via API): flusso «tessere» risolto
# *              per la controparte, documenti visibili solo alla propria sezione, coda dei
# *              documenti in arrivo, conferma con protocollo e lotto, presa in carico automatica,
# *              lettura dei flussi con verifica della catena.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import base64
import json
import uuid
from datetime import date
from decimal import Decimal

import pytest

from apps.api import arrivi, feed
from apps.api.models import Cambiamento, ClienteApi, CursoreFlusso, DocumentoRicevuto
from apps.core.cifratura import nuova_chiave
from apps.soci import ciclo
from apps.soci.models import (
    ListinoTessere,
    LottoTessere,
    RichiestaTessere,
    Sezione,
)

from .aiuti import Controparte

pytestmark = pytest.mark.django_db
ANNO = date.today().year + 1


@pytest.fixture(autouse=True)
def _ambiente(settings, tmp_path):
    settings.CHIAVE_CIFRATURA = nuova_chiave()
    settings.API_TLS_CERTIFICATO = ""
    settings.MEDIA_ROOT = tmp_path
    ListinoTessere.objects.update_or_create(
        anno=ANNO, defaults={"costo_acquisto": Decimal("3.50"), "quota_federale": Decimal("1.50")}
    )


@pytest.fixture
def admin(crea_utente):
    return crea_utente("admin", ruoli=["Amministratore di sistema", "Addetto protocollo"])


@pytest.fixture
def sezioni():
    return (Sezione.objects.create(codice="002", nome="Avigliano", email="a@example.org"),
            Sezione.objects.create(codice="003", nome="Potenza", email="p@example.org"))  # fmt: skip


def _controparte(ruolo, sezione=None, ambiti=("tessere:scambio",)):
    ctp = Controparte()
    cliente = ClienteApi.objects.create(
        nome=f"Controparte {ruolo}", tipo="installazione", origine="invito_nostro",
        stato="attiva", istanza=ctp.uuid, jwks=ctp.jwks, ambiti=list(ambiti), ruolo=ruolo,
        sezione=sezione,
    )  # fmt: skip
    return ctp, cliente


def _consegna(utente, sezione, da=1, a=10):
    blocco = ciclo.carica_blocco(utente, anno=ANNO, numero_da=da, numero_a=a + 1000, serie="Z")
    return ciclo.consegna(utente, blocco=blocco, sezione=sezione, numero_da=da, numero_a=a)


class TestLatoServer:
    def test_la_sezione_vede_solo_i_propri_documenti(self, client, admin, sezioni):
        avigliano, potenza = sezioni
        ctp, _ = _controparte("sezione", avigliano)
        mia = _consegna(admin, avigliano, 1, 10)
        altrui = _consegna(admin, potenza, 2001, 2010)
        r = ctp.chiama(client, "GET", "/api/v1/cambiamenti?flusso=tessere")
        assert r.status_code == 200, r.content
        voci = r.json()["cambiamenti"]
        assert {v["subject"] for v in voci} == {str(mia.uuid)}
        assert feed.verifica_catena(voci)
        r = ctp.chiama(client, "GET", f"/api/v1/ciclo-tessere/consegna/{mia.uuid}")
        dati = r.json()
        assert (dati["numero_da"], dati["numero_a"], dati["importo"]) == (1, 10, "50.00")
        assert base64.b64decode(dati["pdf"]).startswith(b"%PDF")
        assert (
            ctp.chiama(client, "GET", f"/api/v1/ciclo-tessere/consegna/{altrui.uuid}").status_code
            == 404
        )

    def test_ricevute_dei_versamenti_nel_flusso(self, client, admin, sezioni):
        from apps.tesoreria import incassi
        from apps.tesoreria import servizi as tesoreria

        tesoreria.apri_esercizio(date.today().year, admin)
        ctp, _ = _controparte("sezione", sezioni[0])
        incasso = incassi.registra_incasso({
            "data": date.today(), "tipo": "tessere", "nominativo": "Sezione di Avigliano",
            "importo": Decimal("50"), "metodo": "bonifico", "causale": "Tessere",
            "sezione": sezioni[0], "anno_tessere": ANNO,
        }, admin)  # fmt: skip
        incassi.registra_incasso(
            {
                "data": date.today(),
                "tipo": "donazione",
                "nominativo": "Anna",
                "importo": Decimal("5"),
                "metodo": "contanti",
                "causale": "Offerta",
            },
            admin,
        )  # fmt: skip — gli altri incassi non sono esposti
        voci = ctp.chiama(client, "GET", "/api/v1/cambiamenti?flusso=tessere").json()["cambiamenti"]
        assert [v["data"]["risorsa"] for v in voci] == ["ricevuta"]
        dati = ctp.chiama(client, "GET", f"/api/v1/ciclo-tessere/ricevuta/{incasso.uuid}").json()
        assert dati["ricevuta"] == incasso.codice_ricevuta and dati["importo"] == "50.00"

    def test_senza_ruolo_o_ambito(self, client, sezioni):
        pari, _ = _controparte("pari")
        assert pari.chiama(client, "GET", "/api/v1/cambiamenti?flusso=tessere").status_code == 403
        senza, _ = _controparte("sezione", sezioni[0], ambiti=())
        r = senza.chiama(client, "GET", "/api/v1/cambiamenti?flusso=tessere")
        assert (r.status_code, r.json()["codice"]) == (403, "ambito-mancante")

    def test_lato_sezione_richieste_e_prese_in_carico(self, client, admin):
        ctp, _ = _controparte("federazione")
        propria = Sezione.predefinita()
        richiesta = ciclo.registra_richiesta(admin, anno=ANNO, sezione=propria, quantita=40)
        lotto = ciclo.carica_lotto(admin, anno=ANNO, numero_da=5, numero_a=9, sezione=propria,
                                   consegna_uuid=uuid.uuid4())  # fmt: skip
        ciclo.carica_lotto(
            admin, anno=ANNO, numero_da=50, numero_a=59, sezione=propria
        )  # non da consegna
        voci = ctp.chiama(client, "GET", "/api/v1/cambiamenti?flusso=tessere").json()["cambiamenti"]
        assert [(v["data"]["risorsa"], v["subject"]) for v in voci] == [
            ("richiesta", str(richiesta.uuid)), ("presa", str(lotto.uuid))]  # fmt: skip


def _documento_consegna(**extra):
    return {"uuid": str(uuid.uuid4()), "versione": 1, "anno": ANNO, "numero": 7,
            "data": date.today().isoformat(), "serie": "Q", "numero_da": 101, "numero_a": 110,
            "cifre": 0, "quantita": 10, "prezzo_unitario": "5.00", "importo": "50.00",
            "modalita": "ritiro", "modalita_descrizione": "Ritiro presso la sede",
            "note_distribuzione": "", "mittente": "Federazione Potenza Matera",
            "pdf": base64.b64encode(b"%PDF-1.4 consegna").decode()} | extra  # fmt: skip


class TestDocumentiInArrivo:
    def test_consegna_presa_in_carico_con_protocollo(self, admin):
        _, federazione = _controparte("federazione")
        documento, nuovo = arrivi.ricevi(federazione, "consegna", _documento_consegna())
        assert nuovo and documento.stato == "da_esaminare" and documento.pdf
        assert not LottoTessere.objects.exists()  # nulla finché non si conferma
        arrivi.conferma(documento, admin, protocolla=True)
        documento.refresh_from_db()
        assert documento.stato == "applicato" and documento.protocollo.direzione == "entrata"
        assert documento.protocollo.mezzo == "api" and documento.protocollo.allegati.count() == 1
        lotto = LottoTessere.objects.get()
        assert (lotto.numero_da, lotto.numero_a, lotto.costo_unitario) == (
            101,
            110,
            Decimal("5.00"),
        )
        assert str(lotto.consegna_uuid) == documento.dati["uuid"] and lotto.carte.count() == 10
        # la presa in carico entra nel flusso letto dalla federazione
        assert Cambiamento.objects.filter(risorsa="presa", soggetto=lotto.uuid).exists()
        with pytest.raises(arrivi.OperazioneNonValida, match="già stato gestito"):
            arrivi.conferma(documento, admin)

    def test_versioni_e_aggiornamenti(self, admin):
        _, federazione = _controparte("federazione")
        dati = _documento_consegna()
        documento, _ = arrivi.ricevi(federazione, "consegna", dati)
        assert arrivi.ricevi(federazione, "consegna", dati)[1] is False  # stessa versione
        arrivi.conferma(documento, admin, protocolla=False)
        documento, _ = arrivi.ricevi(federazione, "consegna", dati | {"versione": 2})
        assert documento.stato == "applicato" and "dopo la conferma" in documento.motivo
        with pytest.raises(arrivi.OperazioneNonValida, match="non previsto"):
            arrivi.ricevi(federazione, "richiesta", {"uuid": str(uuid.uuid4())})

    def test_presa_in_carico_automatica_sulla_federazione(self, admin, sezioni):
        consegna = _consegna(admin, sezioni[0])
        _, sezione = _controparte("sezione", sezioni[0])
        documento, _ = arrivi.ricevi(sezione, "presa", {
            "uuid": str(uuid.uuid4()), "versione": 1, "consegna": str(consegna.uuid),
            "data": "2026-12-01", "quantita": 10,
        })  # fmt: skip
        consegna.refresh_from_db()
        assert consegna.presa_in_carico_il == date(2026, 12, 1) and documento.stato == "applicato"

    def test_richiesta_registrata_sulla_federazione(self, admin, sezioni):
        _, sezione = _controparte("sezione", sezioni[0])
        documento, _ = arrivi.ricevi(sezione, "richiesta", {
            "uuid": str(uuid.uuid4()), "versione": 1, "anno": ANNO, "quantita": 35,
            "data": date.today().isoformat(), "note": "Integrazione", "mittente": "Sezione",
        })  # fmt: skip
        arrivi.conferma(documento, admin, protocolla=False)
        richiesta = RichiestaTessere.objects.get()
        assert (richiesta.sezione, richiesta.quantita, richiesta.cliente_api) == (
            sezioni[0],
            35,
            sezione,
        )
        assert not Cambiamento.objects.filter(risorsa="richiesta").exists()  # non torna indietro
        assert ciclo.quadratura(ANNO)[0].richieste == 35

    def test_scarto_con_motivo(self, admin):
        _, federazione = _controparte("federazione")
        documento, _ = arrivi.ricevi(federazione, "consegna", _documento_consegna())
        with pytest.raises(arrivi.OperazioneNonValida, match="motivo"):
            arrivi.scarta(documento, admin, " ")
        arrivi.scarta(documento, admin, "numeri già ricevuti a mano")
        assert DocumentoRicevuto.objects.get().stato == "scartato"


class TestLettura:
    def test_cursore_catena_e_documenti(self, admin, monkeypatch):
        from apps.collegamenti import sincronizza

        _, federazione = _controparte("federazione")
        documenti = {}
        voci = []
        precedente = feed.ORIGINE
        for n in (1, 2):
            dati = _documento_consegna(numero=n, numero_da=n * 100, numero_a=n * 100 + 9)
            documenti[dati["uuid"]] = dati
            evento = {"specversion": "1.0", "id": f"tessere:{n}", "source": "urn:uuid:x",
                      "type": "it.gestioneassociazione.consegna.creato.v1", "subject": dati["uuid"],
                      "time": "2026-11-18T10:00:00Z", "datacontenttype": "application/json",
                      "ga_flusso": "tessere:002", "ga_progressivo": n, "ga_precedente": precedente,
                      "data": {"risorsa": "consegna", "versione": 1}}  # fmt: skip
            evento["ga_impronta"] = feed.impronta(precedente, feed.canonico(evento))
            precedente = evento["ga_impronta"]
            voci.append(evento)
        chiamate = []

        def remoto(cliente, percorso):
            chiamate.append(percorso)
            if percorso.startswith("/cambiamenti"):
                dopo = int(percorso.split("dopo=")[1].split("&")[0])
                return {"cambiamenti": [v for v in voci if v["ga_progressivo"] > dopo], "ultimo": 2}
            return json.loads(json.dumps(documenti[percorso.rsplit("/", 1)[1]]))

        monkeypatch.setattr(sincronizza, "_get", remoto)
        assert sincronizza.sincronizza(federazione) == 2
        cursore = CursoreFlusso.objects.get()
        assert (cursore.progressivo, cursore.impronta, cursore.ultimo_errore) == (2, precedente, "")
        assert DocumentoRicevuto.objects.filter(stato="da_esaminare").count() == 2
        assert sincronizza.sincronizza(federazione) == 0  # niente di nuovo
        # una voce alterata ferma la lettura senza avanzare il cursore
        voci.append(dict(voci[1], ga_progressivo=3, ga_precedente=precedente, ga_impronta="0" * 64))
        sincronizza.sincronizza(federazione)
        cursore.refresh_from_db()
        assert cursore.progressivo == 2 and "Impronta errata" in cursore.ultimo_errore


class TestPagine:
    def test_coda_nella_campagna(self, client_ruolo):
        segreteria = client_ruolo("Segretario")
        _, federazione = _controparte("federazione")
        documento, _ = arrivi.ricevi(federazione, "consegna", _documento_consegna())
        pagina = segreteria.get(f"/soci/tessere/campagna/{ANNO}/").content.decode()
        assert "Documenti in arrivo dai collegamenti" in pagina and "Prendi in carico" in pagina
        assert segreteria.get(f"/soci/tessere/arrivi/{documento.pk}/pdf/").status_code == 200
        r = segreteria.post(f"/soci/tessere/arrivi/{documento.pk}/conferma/", {"anno": ANNO})
        assert r["Location"] == f"/soci/tessere/campagna/{ANNO}/"
        assert (
            DocumentoRicevuto.objects.get().stato == "applicato" and LottoTessere.objects.exists()
        )

    def test_scheda_della_controparte_con_ruolo(self, client_ruolo, sezioni):
        admin = client_ruolo("Amministratore di sistema")
        _, cliente = _controparte("pari")
        url = f"/sistema/api/{cliente.pk}/modifica/"
        dati = {"nome": cliente.nome, "ruolo": "sezione", "verifica_tls": "pubblica"}
        r = admin.post(url, dati)
        assert "sezione" in r.context["form"].errors
        r = admin.post(url, dati | {"sezione": sezioni[0].pk})
        assert r.status_code == 302
        cliente.refresh_from_db()
        assert (cliente.ruolo, cliente.sezione) == ("sezione", sezioni[0])
        _, altra = _controparte("pari")
        r = admin.post(f"/sistema/api/{altra.pk}/modifica/",
                       {"nome": altra.nome, "ruolo": "sezione", "sezione": sezioni[0].pk,
                        "verifica_tls": "pubblica"})  # fmt: skip
        assert "già collegata" in str(r.context["form"].errors)
