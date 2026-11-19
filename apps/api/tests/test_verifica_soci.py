# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test della verifica dei soci fra federazione e sezione (ADR-030, F4): elenco
# *              cifrato visibile solo per la propria sezione, popolamento di chi manca,
# *              modifiche campo per campo da scegliere, regole di chi aggiorna cosa (la
# *              federazione solo anagrafiche, la sezione anche stato e rinnovi), viste.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.anagrafica.models import Soggetto
from apps.api.models import ClienteApi, VerificaSoci
from apps.collegamenti import soci as verifica_soci
from apps.core.cifratura import nuova_chiave
from apps.soci import allineamento, servizi
from apps.soci.models import (
    ListinoTessere,
    PromemoriaArchivio,
    Sezione,
    Socio,
    Tessera,
    TipologiaSocio,
)

from .aiuti import Controparte

pytestmark = pytest.mark.django_db
ANNO = date.today().year
CF_ROSSI = "RSSMRA50C15A519V"
CF_BIANCHI = "BNCLRA80A41F205G"


@pytest.fixture(autouse=True)
def _ambiente(settings, tmp_path):
    settings.CHIAVE_CIFRATURA = nuova_chiave()
    settings.API_TLS_CERTIFICATO = ""
    settings.MEDIA_ROOT = tmp_path
    ListinoTessere.objects.update_or_create(
        anno=ANNO, defaults={"costo_acquisto": Decimal("3.50"), "quota_federale": Decimal("1.50")}
    )
    TipologiaSocio.objects.filter(nome="Ordinario").update(quota_annua=Decimal("30"))


@pytest.fixture
def admin(crea_utente):
    return crea_utente("admin", ruoli=["Amministratore di sistema"])


@pytest.fixture
def avigliano():
    return Sezione.objects.create(codice="002", nome="Avigliano")


def _socio(utente, sezione, cognome, nome, cf=None, **anagrafica):
    p = Soggetto.objects.create(cognome=cognome, nome=nome, codice_fiscale=cf, **anagrafica)
    ordinario = TipologiaSocio.objects.get(nome="Ordinario")
    return servizi.ammetti_socio(p, ordinario, utente, sezione=sezione,
                                 data_ammissione=date(2020, 1, 1))  # fmt: skip


def _controparte(ruolo, sezione=None, ambiti=("soci:lettura",)):
    ctp = Controparte()
    cliente = ClienteApi.objects.create(
        nome=f"Controparte {ruolo}", tipo="installazione", origine="invito_nostro",
        stato="attiva", istanza=ctp.uuid, jwks=ctp.jwks, ambiti=list(ambiti), ruolo=ruolo,
        sezione=sezione, abbinata_il=timezone.now(),
    )  # fmt: skip
    return ctp, cliente


def _remota(cognome, nome, cf="", modificato=None, tessere=(), **campi):
    riga = {
        "codice_fiscale": cf, "cognome": cognome, "nome": nome, "matricola": "",
        "tipologia": "Ordinario", "data_iscrizione": "2019-05-01", "stato_socio": "attivo",
        "data_cessazione": "", "causa_cessazione": "", "tessere": list(tessere),
        "modificato_il": (modificato or timezone.now() + timedelta(hours=1)).isoformat(),
    }  # fmt: skip
    riga.update(campi)
    return riga


class TestElenco:
    def test_la_sezione_vede_solo_i_propri_soci_cifrati(self, client, admin, avigliano):
        potenza = Sezione.objects.create(codice="003", nome="Potenza")
        mio = _socio(admin, avigliano, "Rossi", "Mario", CF_ROSSI, email="m@example.org")
        _socio(admin, potenza, "Bianchi", "Laura", CF_BIANCHI)
        cessato = _socio(admin, avigliano, "Verdi", "Gino")
        servizi.cessa_socio(cessato, admin, data_cessazione=date(2024, 3, 1),
                            causa=Socio.Cessazione.DIMISSIONI)  # fmt: skip
        tessera = servizi.rilascia_tessera(mio, ANNO, admin)
        ctp, _ = _controparte("sezione", avigliano)
        r = ctp.chiama(client, "GET", "/api/v1/soci")
        assert r.status_code == 200
        dati = ctp.decifra(r)
        assert dati["sezione"]["codice"] == "002"
        per_cognome = {s["cognome"]: s for s in dati["soci"]}
        assert set(per_cognome) == {"Rossi", "Verdi"}
        assert per_cognome["Rossi"]["email"] == "m@example.org"
        assert per_cognome["Rossi"]["tessere"][0]["anno"] == tessera.anno
        assert per_cognome["Verdi"]["stato_socio"] == "cessato"
        assert per_cognome["Verdi"]["causa_cessazione"].startswith("Dimissioni")

    def test_senza_ambito_o_ruolo(self, client, avigliano):
        ctp, _ = _controparte("sezione", avigliano, ambiti=("tessere:scambio",))
        assert ctp.chiama(client, "GET", "/api/v1/soci").status_code == 403
        ctp, _ = _controparte("", None)
        assert ctp.chiama(client, "GET", "/api/v1/soci").status_code == 403


class TestDallaFederazione:
    """Siamo la sezione: dalla federazione arrivano le anagrafiche (e i soci che mancano)."""

    def test_popola_chi_manca_e_propone_le_modifiche(self, admin, monkeypatch):
        sezione = Sezione.predefinita()
        presente = _socio(admin, sezione, "Rossi", "Mario", CF_ROSSI, email="vecchia@example.org")
        _socio(admin, sezione, "Solo", "Qui")
        _, federazione = _controparte("federazione")
        righe = [
            _remota("Rossi", "Mario", CF_ROSSI, email="nuova@example.org", stato_socio="sospeso",
                    tessere=[{"anno": ANNO, "codice": "77", "pagata": True}]),
            _remota("BIANCHI", "LAURA", CF_BIANCHI, comune="Potenza", stato_socio="sospeso",
                    tessere=[{"anno": ANNO, "codice": "78", "data": f"{ANNO}-02-01",
                              "pagata": True, "pagata_il": f"{ANNO}-02-01"}]),
        ]  # fmt: skip
        monkeypatch.setattr(verifica_soci, "scarica", lambda c: righe)
        v = verifica_soci.verifica(federazione, admin)
        assert v.proposta["conteggi"] == {"nuovo": 1, "differenze": 1, "invariato": 0,
                                          "escluso": 0}  # fmt: skip
        rossi = next(x for x in v.proposta["voci"] if x["codice_fiscale"] == CF_ROSSI)
        # dalla federazione né stato né rinnovi: solo l'email
        assert rossi["modifiche"] == [["email", "vecchia@example.org", "nuova@example.org"]]
        assert rossi["piu_recente"] == "controparte"
        assert len(v.proposta["solo_qui"]) == 1  # «Solo Qui» non è presso la federazione

        v = verifica_soci.applica(v, [0, 1], admin)
        assert [e["esito"] for e in v.esiti] == ["aggiornato", "creato"] and v.righe == []
        presente.refresh_from_db()
        assert presente.soggetto.email == "nuova@example.org"
        assert presente.stato == Socio.Stato.ATTIVO
        assert not presente.tessere.exists()
        # popolamento: il socio nuovo arriva con stato e tessera
        nuova = Socio.objects.get(soggetto__codice_fiscale=CF_BIANCHI)
        assert nuova.sezione == sezione and nuova.soggetto.cognome == "Bianchi"
        assert nuova.stato == Socio.Stato.SOSPESO
        t = Tessera.objects.get(socio=nuova, anno=ANNO)
        assert t.carta.codice == "78" and t.pagata
        with pytest.raises(verifica_soci.OperazioneNonValida):
            verifica_soci.applica(v, [0], admin)
        # i dati arrivano dall'archivio centrale (la federazione): nessun promemoria per loro
        assert not PromemoriaArchivio.objects.filter(
            socio__in=[presente, nuova], aggiornato_il__gte=v.creata_il
        ).exists()

    def test_solo_le_voci_scelte_e_dato_locale_piu_recente(self, admin, monkeypatch):
        sezione = Sezione.predefinita()
        socio = _socio(admin, sezione, "Rossi", "Mario", CF_ROSSI, email="mia@example.org")
        _, federazione = _controparte("federazione")
        ieri = timezone.now() - timedelta(days=1)
        righe = [_remota("Rossi", "Mario", CF_ROSSI, modificato=ieri, email="sua@example.org"),
                 _remota("Bianchi", "Laura", CF_BIANCHI)]  # fmt: skip
        monkeypatch.setattr(verifica_soci, "scarica", lambda c: righe)
        v = verifica_soci.verifica(federazione, admin)
        assert v.proposta["voci"][0]["piu_recente"] == "qui"
        verifica_soci.applica(v, [1], admin)  # solo il nuovo
        socio.refresh_from_db()
        assert socio.soggetto.email == "mia@example.org"
        assert Socio.objects.filter(soggetto__codice_fiscale=CF_BIANCHI).exists()

    def test_allineati_e_altra_sezione(self, admin, monkeypatch, avigliano):
        sezione = Sezione.predefinita()
        socio = _socio(admin, sezione, "Rossi", "Mario", CF_ROSSI)
        _socio(admin, avigliano, "Bianchi", "Laura", CF_BIANCHI)
        _, federazione = _controparte("federazione")
        righe = allineamento.elenco(sezione) + [_remota("Bianchi", "Laura", CF_BIANCHI)]
        monkeypatch.setattr(verifica_soci, "scarica", lambda c: righe)
        v = verifica_soci.verifica(federazione, admin)
        assert v.proposta["conteggi"]["invariato"] == 1
        escluso = v.proposta["voci"][1]
        assert escluso["stato"] == "escluso" and "Avigliano" in escluso["motivo"]
        assert socio.pk


class TestDallaSezione:
    """Siamo la federazione: dalla sezione arrivano anche stato, cessazioni e rinnovi."""

    def test_rinnovo_e_cessazione(self, admin, monkeypatch, avigliano):
        rossi = _socio(admin, avigliano, "Rossi", "Mario", CF_ROSSI)
        bianchi = _socio(admin, avigliano, "Bianchi", "Laura", CF_BIANCHI)
        _, sezione = _controparte("sezione", avigliano)
        righe = [
            _remota("Rossi", "Mario", CF_ROSSI, tessere=[
                {"anno": ANNO, "codice": "123", "data": f"{ANNO}-01-10", "pagata": True,
                 "pagata_il": f"{ANNO}-01-10"}]),
            _remota("Bianchi", "Laura", CF_BIANCHI, stato_socio="cessato",
                    data_cessazione=f"{ANNO}-03-01", causa_cessazione="Decesso"),
        ]  # fmt: skip
        monkeypatch.setattr(verifica_soci, "scarica", lambda c: righe)
        v = verifica_soci.verifica(sezione, admin)
        modifiche = {x["nome"]: x["modifiche"] for x in v.proposta["voci"]}
        assert ["tessera " + str(ANNO), "—", "123"] in modifiche["Rossi Mario"]
        assert ["quota " + str(ANNO), "da versare", "versata"] in modifiche["Rossi Mario"]
        assert modifiche["Bianchi Laura"][0][0] == "cessazione"
        v = verifica_soci.applica(v, [0, 1], admin)
        assert all(e["esito"] == "aggiornato" for e in v.esiti), v.esiti
        t = Tessera.objects.get(socio=rossi, anno=ANNO)
        assert t.carta.codice == "123" and t.pagata and t.incasso_esterno
        bianchi.refresh_from_db()
        assert bianchi.stato == Socio.Stato.CESSATO
        assert bianchi.causa_cessazione == Socio.Cessazione.DECESSO
        # sulla federazione le novità della sezione vanno riportate nel registro nazionale
        Socio.objects.get(pk=rossi.pk).soggetto.save()  # nessuna modifica: nessun promemoria
        assert PromemoriaArchivio.objects.filter(socio=rossi).count() == 1  # quello del nuovo

    def test_un_cessato_non_si_riattiva(self, admin, monkeypatch, avigliano):
        socio = _socio(admin, avigliano, "Rossi", "Mario", CF_ROSSI)
        servizi.cessa_socio(socio, admin, data_cessazione=date(2024, 1, 1),
                            causa=Socio.Cessazione.DIMISSIONI)  # fmt: skip
        _, sezione = _controparte("sezione", avigliano)
        righe = [_remota("Rossi", "Mario", CF_ROSSI, tessere=[{"anno": ANNO, "codice": "9"}])]
        monkeypatch.setattr(verifica_soci, "scarica", lambda c: righe)
        v = verifica_soci.verifica(sezione, admin)
        assert v.proposta["conteggi"]["invariato"] == 1


class TestViste:
    def test_verifica_e_applicazione(self, client_ruolo, monkeypatch, avigliano):
        admin = client_ruolo("Amministratore di sistema")
        _, sezione = _controparte("sezione", avigliano)
        righe = [_remota("Bianchi", "Laura", CF_BIANCHI)]
        monkeypatch.setattr(verifica_soci, "scarica", lambda c: righe)
        pagina = admin.get(reverse("api:controparte", args=[sezione.pk])).content.decode()
        assert "Verifica soci" in pagina
        r = admin.post(reverse("api:verifica_soci_nuova", args=[sezione.pk]), follow=True)
        assert r.status_code == 200 and "da creare" in r.content.decode()
        v = VerificaSoci.objects.get()
        r = admin.post(reverse("api:verifica_soci", args=[v.pk]), {"scelti": ["0"]}, follow=True)
        assert "Soci creati o aggiornati: 1." in r.content.decode()
        assert Socio.objects.get(soggetto__codice_fiscale=CF_BIANCHI).sezione == avigliano

    def test_controparte_non_raggiungibile(self, client_ruolo, avigliano):
        admin = client_ruolo("Amministratore di sistema")
        _, sezione = _controparte("sezione", avigliano)
        r = admin.post(reverse("api:verifica_soci_nuova", args=[sezione.pk]), follow=True)
        assert "Controparte non raggiungibile" in r.content.decode()
        assert not VerificaSoci.objects.exists()

    def test_permesso(self, client_ruolo, avigliano):
        tesoriere = client_ruolo("Tesoriere")
        _, sezione = _controparte("sezione", avigliano)
        r = tesoriere.post(reverse("api:verifica_soci_nuova", args=[sezione.pk]))
        assert r.status_code == 403
