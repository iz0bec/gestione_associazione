# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test degli organi sociali: cariche, riunioni, convocazione, aventi
# *              diritto, presenze e deleghe, quorum, verbale, delibere e chiusura.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import hashlib
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.anagrafica.models import Soggetto
from apps.organi import servizi
from apps.organi.forms import DeliberaForm, RiunioneForm, VerbaleForm
from apps.organi.models import Delibera, Organo, Presenza, Riunione
from apps.organi.servizi import OperazioneNonValida
from apps.protocollo.models import Protocollo
from apps.soci import servizi as soci
from apps.soci.models import TipologiaSocio

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def cartella_media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def segretario(crea_utente):
    return crea_utente("segretario", ruoli=["Segretario"])


@pytest.fixture
def consiglio():
    return Organo.objects.get(sigla="CD")


@pytest.fixture
def assemblea():
    return Organo.objects.get(sigla="ASS")


def _persona(cognome):
    return Soggetto.objects.create(cognome=cognome, nome="Prova")


@pytest.fixture
def consiglieri(consiglio, segretario):
    ruoli = ["presidente", "segretario", "tesoriere", "consigliere", "consigliere"]
    persone = [_persona(f"C{i}") for i in range(5)]
    for p, r in zip(persone, ruoli, strict=True):
        servizi.nomina(consiglio, p, r, date(2025, 1, 1), segretario)
    return persone


def _riunione(organo, utente, punti=("Approvazione bilancio", "Varie"), giorni=7):
    dati = {
        "organo": organo.pk,
        "prima_convocazione": (timezone.localtime() + timedelta(days=giorni)).strftime(
            "%Y-%m-%dT18:00"
        ),
        "luogo": "Sede sociale",
        "seconda_convocazione": (timezone.localtime() + timedelta(days=giorni + 1)).strftime(
            "%Y-%m-%dT18:00"
        ),
        "modalita": "presenza",
        "punti": "\n".join(punti),
    }
    form = RiunioneForm(dati, instance=Riunione())
    assert form.is_valid(), form.errors
    return servizi.salva_riunione(form, form.titoli_punti(), utente)


class TestCariche:
    def test_nomina_e_fine(self, consiglio, consiglieri, segretario):
        assert consiglio.cariche_al().count() == 5
        carica = consiglio.cariche.first()
        with pytest.raises(OperazioneNonValida):
            servizi.nomina(consiglio, carica.soggetto, "consigliere", date(2025, 6, 1), segretario)
        servizi.termina_carica(carica, date(2025, 12, 31), segretario, "dimissioni")
        assert consiglio.cariche_al().count() == 4
        assert consiglio.cariche_al(date(2025, 6, 1)).count() == 5

    def test_assemblea_senza_cariche(self, assemblea, segretario):
        with pytest.raises(OperazioneNonValida):
            servizi.nomina(assemblea, _persona("X"), "presidente", date.today(), segretario)


class TestRiunioni:
    def test_convocazione_numerata_e_protocollata(self, consiglio, consiglieri, segretario):
        r1 = _riunione(consiglio, segretario)
        r2 = _riunione(consiglio, segretario, giorni=30)
        assert r1.stato == "bozza" and r1.numero is None and r1.punti.count() == 2
        servizi.convoca(r1, segretario, protocolla=True)
        servizi.convoca(r2, segretario)
        r1.refresh_from_db()
        r2.refresh_from_db()
        assert (r1.numero, r2.numero) == (1, 2) and r1.stato == "convocata"
        p = r1.protocollo_convocazione
        assert p.direzione == "uscita" and p.corrispondenti.count() == 5
        assert p.allegati.get().nome == "convocazione.pdf"
        with pytest.raises(OperazioneNonValida):
            servizi.convoca(r1, segretario)

    def test_modifica_odg_e_annullamento(self, consiglio, segretario):
        r = _riunione(consiglio, segretario)
        servizi._salva_punti(r, ["Primo", "Secondo", "Terzo"])
        assert [p.titolo for p in r.punti.all()] == ["Primo", "Secondo", "Terzo"]
        with pytest.raises(OperazioneNonValida):
            servizi._salva_punti(r, [" "])
        with pytest.raises(OperazioneNonValida):
            servizi.annulla_riunione(r, segretario, "")
        servizi.annulla_riunione(r, segretario, "rinviata a data da destinarsi")
        r.refresh_from_db()
        assert r.stato == "annullata" and not r.modificabile


class TestAventiDirittoEQuorum:
    def test_assemblea_soci_in_regola(self, assemblea, segretario):
        ordinario = TipologiaSocio.objects.get(nome="Ordinario")
        ordinario.quota_annua = Decimal("20")
        ordinario.save()
        anno = (timezone.localtime() + timedelta(days=7)).year
        soci_ = [soci.ammetti_socio(_persona(f"S{i}"), ordinario, segretario, data_ammissione=date(2020, 1, 1)) for i in range(4)]  # fmt: skip
        soci.rilascia_tessera(soci_[0], anno, segretario, pagata_il=date.today())
        soci.rilascia_tessera(soci_[1], anno, segretario, pagata_il=date.today())
        r = _riunione(assemblea, segretario)
        voti = {s.cognome: vota for s, _, vota in servizi.aventi_diritto(r)}
        assert voti == {"S0": True, "S1": True, "S2": False, "S3": False}

    def test_quorum_e_deleghe(self, assemblea, segretario):
        assemblea.solo_soci_in_regola = False
        assemblea.max_deleghe = 1
        assemblea.save()
        ordinario = TipologiaSocio.objects.get(nome="Ordinario")
        for i in range(10):
            soci.ammetti_socio(
                _persona(f"S{i}"), ordinario, segretario, data_ammissione=date(2020, 1, 1)
            )
        r = servizi.convoca(_riunione(assemblea, segretario), segretario)
        assert servizi.apri_presenze(r) == 10 and servizi.apri_presenze(r) == 0
        p = list(r.presenze.order_by("descrizione"))
        for x in p[:5]:
            servizi.imposta_presenza(x, Presenza.Stato.PRESENTE)
        q = servizi.quorum(r, "prima")
        assert (q.totale, q.richiesto, q.valido) == (5, 6, False)  # serve più della metà
        servizi.imposta_presenza(p[5], Presenza.Stato.DELEGA, p[0])
        assert servizi.quorum(r, "prima").valido
        with pytest.raises(OperazioneNonValida):  # massimo una delega
            servizi.imposta_presenza(p[6], Presenza.Stato.DELEGA, p[0])
        with pytest.raises(OperazioneNonValida):  # il delegato deve essere presente
            servizi.imposta_presenza(p[6], Presenza.Stato.DELEGA, p[7])
        servizi.imposta_presenza(p[0], Presenza.Stato.ASSENTE)  # le sue deleghe decadono
        p[5].refresh_from_db()
        assert p[5].stato == "assente" and p[5].delegato is None
        assert servizi.quorum(r, "seconda").valido  # seconda: qualunque numero


class TestVerbale:
    def _seduta(self, consiglio, segretario, presenti=3):
        r = servizi.convoca(_riunione(consiglio, segretario), segretario)
        servizi.apri_presenze(r)
        for x in list(r.presenze.all())[:presenti]:
            servizi.imposta_presenza(x, Presenza.Stato.PRESENTE)
        return r, servizi.apri_verbale(r, segretario)

    def _delibera(self, r, v, **extra):
        dati = {"punto": r.punti.first().pk, "oggetto": "Bilancio 2025", "testo": "Si approva.",
                "votazione": "palese", "favorevoli": 3, "contrari": 0, "astenuti": 0,
                "esito": "approvata", **extra}  # fmt: skip
        form = DeliberaForm(dati, riunione=r)
        assert form.is_valid(), form.errors
        return servizi.salva_delibera(form, v)

    def test_presidenza_proposta_e_chiusura(self, consiglio, consiglieri, segretario):
        r, v = self._seduta(consiglio, segretario)
        assert v.presidente == "C0 Prova" and v.segretario == "C1 Prova"
        form = VerbaleForm({"convocazione": "prima", "luogo": "Sede", "presidente": v.presidente,
                            "segretario": v.segretario, "varie": "Nessuna"}, instance=v)  # fmt: skip
        assert form.is_valid(), form.errors
        punto = r.punti.first()
        servizi.salva_verbale(form, {punto.pk: "Il tesoriere illustra il bilancio."}, segretario)
        self._delibera(r, v)
        self._delibera(r, v, oggetto="Quota 2026", unanimita=True)
        v = servizi.chiudi_verbale(v, segretario, protocolla=True)
        assert v.chiuso and v.numero == 1 and (v.presenti, v.aventi_diritto) == (3, 5)
        anno = timezone.localtime(v.inizio).year
        assert [d.codice for d in v.delibere.order_by("numero")] == [f"CD 1/{anno}", f"CD 2/{anno}"]
        with v.file.open("rb") as f:
            assert hashlib.sha256(f.read()).hexdigest() == v.impronta
        assert Protocollo.objects.get(direzione="interno").allegati.count() == 1
        r.refresh_from_db()
        assert r.stato == "verbalizzata"
        with pytest.raises(OperazioneNonValida):
            servizi.salva_delibera(DeliberaForm({}, riunione=r), v)
        with pytest.raises(OperazioneNonValida):
            servizi.chiudi_verbale(v, segretario)

    def test_senza_numero_legale_niente_delibere(self, consiglio, consiglieri, segretario):
        r, v = self._seduta(consiglio, segretario, presenti=2)
        self._delibera(r, v)
        with pytest.raises(OperazioneNonValida):
            servizi.chiudi_verbale(v, segretario)
        servizi.elimina_delibera(Delibera.objects.get())
        assert servizi.chiudi_verbale(v, segretario).chiuso  # seduta deserta verbalizzata

    def test_controlli_delibera(self, consiglio, consiglieri, segretario):
        r, _ = self._seduta(consiglio, segretario)
        base = {"oggetto": "x", "testo": "y", "votazione": "palese", "esito": "approvata"}
        assert not DeliberaForm(
            {**base, "favorevoli": 1, "contrari": 2, "astenuti": 0}, riunione=r
        ).is_valid()
        assert not DeliberaForm({**base, "unanimita": "on", "favorevoli": 3, "contrari": 1, "astenuti": 0}, riunione=r).is_valid()  # fmt: skip


class TestViste:
    def test_percorso_completo(self, client, consiglio, consiglieri, segretario):
        client.force_login(segretario)
        inizio = (timezone.localtime() + timedelta(days=3)).strftime("%Y-%m-%dT18:00")
        r = client.post(
            reverse("organi:riunione_nuova"),
            {"organo": consiglio.pk, "prima_convocazione": inizio, "luogo": "Sede",
             "modalita": "presenza", "punti": "Bilancio\nVarie"},
        )  # fmt: skip
        riunione = Riunione.objects.get()
        assert r.status_code == 302
        client.post(reverse("organi:convoca", args=[riunione.pk]))
        client.post(reverse("organi:presenze", args=[riunione.pk]))
        for p in riunione.presenze.all()[:4]:
            client.post(reverse("organi:presenza", args=[p.pk]), {"stato": "presente"})
        assert servizi.quorum(riunione).intervenuti == 4
        for url in [
            reverse("organi:organi"),
            reverse("organi:organo", args=[consiglio.pk]),
            reverse("organi:riunioni"),
            reverse("organi:riunione", args=[riunione.pk]),
            reverse("organi:presenze", args=[riunione.pk]),
            reverse("organi:verbale", args=[riunione.pk]),
            reverse("organi:delibere"),
            reverse("core:cruscotto"),
        ]:
            assert client.get(url).status_code == 200, url
        for url in [reverse("organi:convocazione", args=[riunione.pk]),
                    reverse("organi:verbale_pdf", args=[riunione.pk])]:  # fmt: skip
            assert client.get(url).content.startswith(b"%PDF")
        r = client.post(
            reverse("organi:presenza", args=[riunione.presenze.first().pk]),
            {"stato": "assente"},
            HTTP_HX_REQUEST="true",
        )
        assert 'id="elenco-presenze"' in r.content.decode() and "<html" not in r.content.decode()

    def test_permessi(self, client_ruolo, consiglio, segretario):
        riunione = _riunione(consiglio, segretario)
        c = client_ruolo("Consigliere")
        assert c.get(reverse("organi:riunione", args=[riunione.pk])).status_code == 200
        assert c.get(reverse("organi:riunione_nuova")).status_code == 403
        assert c.post(reverse("organi:convoca", args=[riunione.pk])).status_code == 403
        assert c.post(reverse("organi:nomina", args=[consiglio.pk])).status_code == 403
