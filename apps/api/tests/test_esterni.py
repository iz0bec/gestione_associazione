# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test della fase F3 (sistemi esterni): dati personali solo cifrati, adesioni con
# *              Idempotency-Key e If-Match, domande di iscrizione, messaggi del modulo contatti,
# *              documenti pubblici, organigramma, verifica tessera, limiti di frequenza.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from datetime import date, timedelta

import pytest
from django.core.files.base import ContentFile
from django.utils import timezone

from apps.api import jwe
from apps.api.models import ClienteApi
from apps.core.cifratura import nuova_chiave
from apps.eventi.models import Adesione, Evento

from .aiuti import Controparte

TUTTI = ["eventi:lettura", "adesioni:lettura", "adesioni:scrittura", "domande:scrittura",
         "contatti:scrittura", "documenti:lettura", "organigramma:lettura", "tessere:verifica"]  # fmt: skip


@pytest.fixture(autouse=True)
def _cifratura(settings, tmp_path):
    settings.CHIAVE_CIFRATURA = nuova_chiave()
    settings.API_TLS_CERTIFICATO = ""
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def sito():
    ctp = Controparte("Sito WordPress")
    ClienteApi.objects.create(nome="Sito", tipo="integrazione", origine="invito_nostro",
                              stato="attiva", istanza=ctp.uuid, jwks=ctp.jwks,
                              ambiti=TUTTI)  # fmt: skip
    return ctp


def _evento(**extra):
    dati = {"titolo": "Pranzo sociale", "inizio": timezone.now() + timedelta(days=5),
            "pubblico": True, "posti": 3, "accompagnatori": 1} | extra  # fmt: skip
    return Evento.objects.create(**dati)


def _chiave(n=1):
    return {"Idempotency-Key": f"chiave-di-prova-{n:04d}"}


@pytest.mark.django_db
class TestCifratura:
    def test_prova_cifrata_andata_e_ritorno(self, client, sito):
        r = sito.cifrato(client, "POST", "/api/v1/prova", {"saluto": "è così"})
        assert r.status_code == 200, r.content
        diagnosi = r.json()
        assert diagnosi["cifratura"] == "valida"
        eco = jwe.decifra_json(diagnosi["risposta_cifrata"], lambda kid: sito.cifratura)
        assert eco == {"eco": {"saluto": "è così"}}

    def test_jwe_alterato(self, client, sito):
        r = sito.chiama(client, "POST", "/api/v1/prova", corpo=b"a.b.c.d.e", tipo=jwe.TIPO)
        assert r.json()["cifratura"] == "non-valida"


@pytest.mark.django_db
class TestAdesioni:
    def test_solo_cifrate_e_con_chiave(self, client, sito):
        e = _evento()
        percorso = f"/api/v1/eventi/{e.uuid}/adesioni"
        r = sito.chiama(client, "POST", percorso, {"cognome": "Rossi"}, extra=_chiave())
        assert (r.status_code, r.json()["codice"]) == (415, "cifratura-richiesta")
        r = sito.chiama(client, "POST", percorso, {"cognome": "Rossi"})  # né cifrata né chiave
        assert (r.status_code, r.json()["codice"]) == (415, "cifratura-richiesta")
        r = sito.cifrato(client, "POST", percorso, {"cognome": "Rossi"})
        assert r.status_code == 400 and "Idempotency-Key" in r.json()["detail"]

    def test_adesione_ripetizione_e_conflitto(self, client, sito):
        e = _evento()
        percorso = f"/api/v1/eventi/{e.uuid}/adesioni"
        dati = {"cognome": "Rossi", "nome": "Anna", "email": "anna@example.org",
                "accompagnatori": 1, "riferimento_esterno": "wp-17"}  # fmt: skip
        r = sito.cifrato(client, "POST", percorso, dati, extra=_chiave())
        assert r.status_code == 201, r.content
        adesione = sito.decifra(r)
        assert adesione["origine"] == "integrazione" and adesione["riferimento_esterno"] == "wp-17"
        assert r["Location"] == f"/api/v1/adesioni/{adesione['uuid']}" and r["ETag"] == '"1"'
        salvata = Adesione.objects.get()
        assert salvata.cliente_api.nome == "Sito"
        # stessa chiave e stesso contenuto (cifrato di nuovo): stessa risposta, nessun doppione
        r2 = sito.cifrato(client, "POST", percorso, dati, extra=_chiave())
        assert r2.status_code == 201 and r2["Idempotent-Replayed"] == "true"
        assert sito.decifra(r2)["uuid"] == adesione["uuid"] and Adesione.objects.count() == 1
        r3 = sito.cifrato(client, "POST", percorso, dati | {"nome": "Bea"}, extra=_chiave())
        assert (r3.status_code, r3.json()["codice"]) == (422, "idempotenza-conflitto")
        # posti esauriti (3 posti: 2 occupati, ne servirebbero 2)
        r4 = sito.cifrato(client, "POST", percorso, {"cognome": "Verdi", "accompagnatori": 1},
                          extra=_chiave(2))  # fmt: skip
        assert r4.status_code == 409 and "Posti esauriti" in r4.json()["detail"]

    def test_eventi_non_pubblici_e_lettura_delle_proprie(self, client, sito):
        interno = _evento(pubblico=False)
        r = sito.cifrato(client, "POST", f"/api/v1/eventi/{interno.uuid}/adesioni",
                         {"cognome": "Rossi"}, extra=_chiave())  # fmt: skip
        assert r.status_code == 404
        e = _evento()
        Adesione.objects.create(evento=e, cognome="Dalla segreteria", origine="segreteria")
        sito.cifrato(client, "POST", f"/api/v1/eventi/{e.uuid}/adesioni", {"cognome": "Rossi"},
                     extra=_chiave())  # fmt: skip
        r = sito.chiama(client, "GET", f"/api/v1/eventi/{e.uuid}/adesioni")
        assert [a["cognome"] for a in sito.decifra(r)] == ["Rossi"]

    def test_annullamento_con_if_match(self, client, sito):
        e = _evento()
        r = sito.cifrato(client, "POST", f"/api/v1/eventi/{e.uuid}/adesioni",
                         {"cognome": "Rossi"}, extra=_chiave())  # fmt: skip
        uuid_adesione = sito.decifra(r)["uuid"]
        versione_evento = Evento.objects.get(pk=e.pk).versione
        percorso = f"/api/v1/adesioni/{uuid_adesione}"
        assert sito.chiama(client, "DELETE", percorso).status_code == 412
        assert sito.chiama(client, "DELETE", percorso, extra={"If-Match": '"9"'}).status_code == 412
        r = sito.chiama(client, "DELETE", percorso, extra={"If-Match": '"1"'})
        assert r.status_code == 204
        adesione = Adesione.objects.get(uuid=uuid_adesione)
        assert adesione.annullata and adesione.versione == 2
        assert Evento.objects.get(pk=e.pk).versione == versione_evento + 1
        altra = Controparte()
        ClienteApi.objects.create(nome="Altro", tipo="integrazione", origine="invito_nostro",
                                  stato="attiva", istanza=altra.uuid, jwks=altra.jwks,
                                  ambiti=TUTTI)  # fmt: skip
        r = altra.chiama(client, "DELETE", percorso, extra={"If-Match": '"2"'})
        assert r.status_code == 404  # le adesioni di altri non si toccano


DOMANDA = {
    "cognome": "Bianchi", "nome": "Mario", "codice_fiscale": "BNCMRA80A01G942Q",
    "data_nascita": "1980-01-01", "luogo_nascita": "Potenza", "email": "mario@example.org",
    "indirizzo": "Via Roma 1", "cap": "85100", "comune": "Potenza", "provincia": "PZ",
    "accetta_statuto": True, "consenso_trattamento": True, "riferimento_esterno": "wp-domanda-3",
    "prestato_il": "2026-11-18T10:00:00Z",
}  # fmt: skip


@pytest.mark.django_db
class TestDomandeEContatti:
    def test_domanda_in_attesa(self, client, sito):
        from apps.soci.models import DomandaIscrizione

        r = sito.cifrato(client, "POST", "/api/v1/domande", DOMANDA, extra=_chiave())
        assert r.status_code == 201, r.content
        domanda = DomandaIscrizione.objects.get()
        assert r.json() == {"uuid": str(domanda.uuid), "stato": "in_attesa"}
        assert domanda.origine == "integrazione" and domanda.cliente_api.nome == "Sito"
        assert domanda.consenso_comunicazioni  # compreso nel trattamento, come nel modulo
        senza = {k: v for k, v in DOMANDA.items() if k != "consenso_trattamento"}
        r = sito.cifrato(client, "POST", "/api/v1/domande", senza, extra=_chiave(2))
        assert r.status_code == 422 and DomandaIscrizione.objects.count() == 1

    def test_contatti_tra_la_posta_da_protocollare(self, client, sito):
        from apps.protocollo.models import CasellaPosta, MessaggioRicevuto

        dati = {"nome": "Luisa Neri", "email": "luisa@example.org", "oggetto": "Informazioni",
                "testo": "Vorrei iscrivermi.", "telefono": "333 1234567"}  # fmt: skip
        r = sito.cifrato(client, "POST", "/api/v1/contatti", dati, extra=_chiave())
        assert r.status_code == 201, r.content
        messaggio = MessaggioRicevuto.objects.get()
        assert messaggio.stato == "nuovo" and messaggio.oggetto == "Informazioni"
        assert messaggio.mittente_email == "luisa@example.org"
        assert "Vorrei iscrivermi." in messaggio.testo and "333 1234567" in messaggio.testo
        assert messaggio.casella.interna
        assert not CasellaPosta.objects.exists()  # fuori da elenchi e scaricamento
        r = sito.cifrato(client, "POST", "/api/v1/contatti", dati | {"email": "no"},
                         extra=_chiave(2))  # fmt: skip
        assert r.status_code == 422

    def test_la_casella_interna_si_vede_nella_posta(self, client_ruolo, client, sito):
        sito.cifrato(client, "POST", "/api/v1/contatti",
                     {"nome": "Luisa", "email": "l@example.org", "testo": "Ciao"},
                     extra=_chiave())  # fmt: skip
        segreteria = client_ruolo("Amministratore di sistema", username="segreteria")
        pagina = segreteria.get("/protocollo/posta/").content.decode()
        assert "Modulo contatti (API)" in pagina


@pytest.mark.django_db
class TestDatiPubblici:
    def test_documenti(self, client, sito):
        from apps.core.models import DocumentoPubblico

        d = DocumentoPubblico(titolo="Statuto", nome_file="statuto.pdf", dimensione=8)
        d.file.save("statuto.pdf", ContentFile(b"%PDF-1.4"), save=False)
        d.save()
        DocumentoPubblico.objects.create(titolo="Bozza", pubblicato=False, file="x.pdf")
        elenco = sito.chiama(client, "GET", "/api/v1/documenti").json()
        assert [x["titolo"] for x in elenco] == ["Statuto"]
        r = sito.chiama(client, "GET", elenco[0]["file"])
        assert r.status_code == 200 and r.content == b"%PDF-1.4"

    def test_organigramma(self, client, sito):
        from apps.anagrafica.models import Soggetto
        from apps.organi.models import Carica, Organo

        organo = Organo.objects.filter(tipo="consiglio").first() or Organo.objects.create(
            nome="Consiglio direttivo", sigla="CD", tipo="consiglio"
        )
        persona = Soggetto.objects.create(tipo="persona", cognome="Verdi", nome="Paolo")
        Carica.objects.create(organo=organo, soggetto=persona, ruolo="presidente",
                              dal=date(2024, 1, 1))  # fmt: skip
        dati = sito.chiama(client, "GET", "/api/v1/organigramma").json()
        consiglio = next(o for o in dati if o["organo"] == organo.nome)
        assert {"ruolo": "presidente", "ruolo_descrizione": "Presidente", "nome": persona.nome_completo,
                "dal": "2024-01-01"} in consiglio["componenti"]  # fmt: skip

    def test_verifica_tessera_senza_dati_personali(self, client, sito, crea_utente):
        from apps.anagrafica.models import Soggetto
        from apps.soci import servizi as soci
        from apps.soci import tessera_digitale
        from apps.soci.models import TipologiaSocio

        admin = crea_utente("admin", ruoli=["Amministratore di sistema"])
        s = Soggetto.objects.create(tipo="persona", cognome="Rossi", nome="Anna")
        socio = soci.ammetti_socio(s, TipologiaSocio.objects.get(nome="Ordinario"), admin)
        tessera = soci.rilascia_tessera(socio, timezone.localdate().year, admin)
        codice = tessera_digitale.token_di(tessera)
        r = sito.chiama(client, "GET", f"/api/v1/tessere/{codice}")
        assert r.status_code == 200, r.content
        dati = r.json()
        assert set(dati) == {"valida", "motivo", "anno", "sezione"}
        assert "Rossi" not in r.content.decode()
        assert sito.chiama(client, "GET", "/api/v1/tessere/inesistente").status_code == 404


@pytest.mark.django_db
def test_limiti_di_frequenza(client, sito, settings):
    settings.API_LIMITE_MINUTO = 2
    for _ in range(2):
        assert sito.chiama(client, "POST", "/api/v1/prova").status_code == 200
    r = sito.chiama(client, "POST", "/api/v1/prova")
    assert (r.status_code, r.json()["codice"], r["Retry-After"]) == (429, "troppe-richieste", "60")
