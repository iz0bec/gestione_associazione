# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test del calendario: impegni per permesso, iCal, collegamento personale
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from datetime import date, timedelta

import pytest
from django.utils import timezone

from apps.anagrafica.models import Soggetto
from apps.calendario import servizi
from apps.calendario.models import FeedCalendario
from apps.comunicazioni.models import Ricorrenza
from apps.organi import servizi as organi
from apps.organi.models import Organo
from apps.organi.tests.test_organi import _riunione
from apps.patrimonio import servizi as patrimonio
from apps.patrimonio.tests.test_patrimonio import bene

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def cartella_media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def impegni(crea_utente):
    segretario = crea_utente("segr", ruoli=["Segretario"])
    r = _riunione(
        Organo.objects.get(sigla="CD"), segretario, punti=("Bilancio; consuntivo", "Varie")
    )
    organi.convoca(r, segretario)
    _riunione(Organo.objects.get(sigla="CD"), segretario, giorni=10)  # in preparazione: esclusa
    oggi = timezone.localdate()
    Ricorrenza.objects.create(nome="Festa dell'Unità nazionale", giorno=4, mese=11,
                              anno_inizio=1918)  # fmt: skip
    b = bene(segretario)
    patrimonio.registra_uscita(b, segretario, tipo="prestito", data=oggi, motivo="mostra",
                               controparte_testo="Comune",
                               restituzione_prevista=oggi + timedelta(days=20))  # fmt: skip
    s = Soggetto.objects.create(cognome="Rossi", nome="Mario", data_nascita=date(1950, 3, 2))
    from apps.soci import servizi as soci
    from apps.soci.models import TipologiaSocio

    soci.ammetti_socio(s, TipologiaSocio.objects.get(nome="Ordinario"), segretario)
    return r


class TestImpegni:
    def test_secondo_i_permessi(self, impegni, crea_utente):
        dal, al = servizi.periodo()
        segretario = crea_utente("s2", ruoli=["Segretario"])
        titoli = [e.titolo for e in servizi.eventi(segretario, dal=dal, al=al)]
        assert sum("convocazione" in t for t in titoli) == 2  # prima e seconda, una riunione
        assert "Festa dell'Unità nazionale" in titoli
        assert any(t.startswith("Restituzione prevista: INV 00001") for t in titoli)
        assert not any(t.startswith("Compleanno") for t in titoli)
        con = servizi.eventi(segretario, dal=dal, al=al, compleanni=True)
        assert "Compleanno di Mario Rossi" in [e.titolo for e in con]
        nessuno = crea_utente("x")
        assert servizi.eventi(nessuno, dal=dal, al=al, compleanni=True) == []

    def test_prossimi_in_ordine(self, impegni, crea_utente):
        righe = servizi.prossimi(crea_utente("s2", ruoli=["Segretario"]), giorni=400)
        giorni = [g for g, _e in righe]
        assert giorni == sorted(giorni) and len(righe) >= 4

    def test_29_febbraio(self):
        e = servizi.Evento(uid="x", titolo="x", inizio=date(2024, 2, 29), annuale=True)
        assert e.nel(2026) == date(2026, 2, 28) and e.nel(2028) == date(2028, 2, 29)


class TestIcs:
    def test_formato(self, impegni, crea_utente):
        testo = servizi.calendario_di(crea_utente("s2", ruoli=["Segretario"]),
                                      base_url="https://esempio.it/")  # fmt: skip
        assert testo.startswith("BEGIN:VCALENDAR\r\nVERSION:2.0\r\n")
        assert testo.rstrip().endswith("END:VCALENDAR") and "\n" not in testo.replace("\r\n", "")
        assert all(len(r.encode()) <= 75 for r in testo.split("\r\n"))
        assert testo.count("BEGIN:VEVENT") == testo.count("END:VEVENT") >= 4
        piatto = testo.replace("\r\n ", "")
        assert "DTSTART;VALUE=DATE:19181104" in piatto and "RRULE:FREQ=YEARLY" in piatto
        assert "1. Bilancio\\; consuntivo\\n2. Varie" in piatto
        assert f"URL:https://esempio.it/organi/riunioni/{impegni.pk}/" in piatto
        assert f"UID:riunione-{impegni.pk}-1@" in piatto
        inizio = timezone.localtime(impegni.prima_convocazione).astimezone(timezone.UTC)
        assert f"DTSTART:{inizio:%Y%m%dT%H%M%SZ}" in piatto

    def test_scarica(self, impegni, client_ruolo):
        r = client_ruolo("Consigliere").get("/calendario/calendario.ics")
        assert r.status_code == 200 and r["Content-Type"].startswith("text/calendar")
        assert "attachment" in r["Content-Disposition"] and b"BEGIN:VEVENT" in r.content

    def test_coriandoli_con_i_compleanni(self, crea_utente, client):
        from apps.soci import servizi as soci
        from apps.soci.models import TipologiaSocio

        segretario = crea_utente("s3", ruoli=["Segretario"])
        client.force_login(segretario)
        assert b"data-coriandoli" not in client.get("/calendario/?compleanni=1").content
        domani = timezone.localdate() + timedelta(days=1)
        s = Soggetto.objects.create(cognome="Bianchi", nome="Anna",
                                    data_nascita=domani.replace(year=1960))  # fmt: skip
        soci.ammetti_socio(s, TipologiaSocio.objects.get(nome="Ordinario"), segretario)
        assert b"data-coriandoli" in client.get("/calendario/?compleanni=1").content
        assert b"data-coriandoli" not in client.get("/calendario/").content


class TestCollegamento:
    def test_creato_letto_revocato(self, impegni, client_ruolo, client):
        c = client_ruolo("Segretario")
        pagina = c.get("/calendario/").content.decode()
        assert "Crea il collegamento" in pagina and "Prossimi 60 giorni" in pagina
        c.post("/calendario/collegamento/", {"azione": "crea", "compleanni": "1"})
        pagina = c.get("/calendario/").content.decode()
        indirizzo = pagina.split("data-copia")[0].rsplit('value="', 1)[1].split('"')[0]
        codice = indirizzo.rsplit("/", 1)[1].removesuffix(".ics")
        feed = FeedCalendario.objects.get(utente=c.utente)
        assert feed.compleanni and codice not in feed.impronta and len(codice) > 30
        assert "data-copia" not in c.get("/calendario/").content.decode()  # mostrato una volta
        c.logout()
        r = client.get(f"/calendario/feed/{codice}.ics")
        assert r.status_code == 200 and b"Compleanno di Mario Rossi" in r.content
        assert client.get("/calendario/feed/sbagliato.ics").status_code == 404
        feed.refresh_from_db()
        assert feed.ultimo_accesso is not None
        c.force_login(c.utente)
        c.post("/calendario/collegamento/", {"azione": "revoca"})
        assert client.get(f"/calendario/feed/{codice}.ics").status_code == 404

    def test_utente_disattivato(self, crea_utente, client):
        u = crea_utente("u", ruoli=["Consigliere"])
        codice = servizi.crea_collegamento(u)
        assert client.get(f"/calendario/feed/{codice}.ics").status_code == 200
        u.is_active = False
        u.save()
        assert client.get(f"/calendario/feed/{codice}.ics").status_code == 404

    def test_compleanni_solo_con_permesso(self, crea_utente, client):
        u = crea_utente("u", ruoli=["Addetto protocollo"])
        client.force_login(u)
        client.post("/calendario/collegamento/", {"azione": "crea", "compleanni": "1"})
        assert not FeedCalendario.objects.get(utente=u).compleanni


def _app(**extra):
    from apps.calendario.models import Appuntamento

    dati = {"titolo": "Cerimonia al monumento", "tipo": "cerimonia",
            "giorno": timezone.localdate() + timedelta(days=3)}  # fmt: skip
    return Appuntamento.objects.create(**{**dati, **extra})


class TestAppuntamenti:
    def test_nel_calendario_e_nell_ics(self, crea_utente):
        from datetime import time

        oggi = timezone.localdate()
        _app(ora=time(10, 30), luogo="Piazza")
        _app(titolo="Annullato", annullato=True)
        _app(titolo="Rendiconto", tipo="scadenza", giorno=oggi - timedelta(days=2))
        _app(titolo="Festa", giorno=oggi + timedelta(days=5), fine_giorno=oggi + timedelta(days=7))
        u = crea_utente("c", ruoli=["Consigliere"])
        righe = servizi.occorrenze(u, oggi - timedelta(days=5), oggi + timedelta(days=10))
        titoli = [e.titolo for _g, e in righe]
        assert "Cerimonia al monumento" in titoli and "Annullato" not in titoli
        assert titoli.count("Festa") == 3  # tre giorni
        scadenza = next(e for _g, e in righe if e.titolo == "Scadenza: Rendiconto")
        assert scadenza.stato == "scaduto"
        testo = servizi.calendario_di(u).replace("\r\n ", "")
        assert "SUMMARY:Cerimonia al monumento" in testo and "LOCATION:Piazza" in testo
        assert f"DTEND;VALUE=DATE:{oggi + timedelta(days=8):%Y%m%d}" in testo
        assert servizi.eventi(crea_utente("x"), dal=oggi, al=oggi) == []  # senza permessi

    def test_scadenza_annuale(self, crea_utente):
        oggi = timezone.localdate()
        a = _app(titolo="Assicurazione", tipo="scadenza", annuale=True,
                 giorno=(oggi - timedelta(days=1)).replace(year=2020))  # fmt: skip
        assert a.prossima == (oggi - timedelta(days=1)).replace(year=oggi.year) and a.scaduto
        u = crea_utente("s", ruoli=["Segretario"])
        assert servizi.scadenze_aperte(u) == [a]
        servizi.segna_fatto(a, u)
        assert a.fatto and not a.scaduto and servizi.scadenze_aperte(u) == []
        a.completato_il = oggi.replace(year=oggi.year - 1)  # fatta l'anno scorso
        assert not a.fatto and a.scaduto

    def test_mese(self, crea_utente):
        oggi = timezone.localdate()
        _app(giorno=oggi)
        settimane = servizi.mese(crea_utente("c", ruoli=["Consigliere"]), oggi.year, oggi.month)
        assert all(len(s) == 7 for s in settimane) and settimane[0][0]["giorno"].weekday() == 0
        cella = next(c for s in settimane for c in s if c["giorno"] == oggi)
        assert [e.titolo for e in cella["eventi"]] == ["Cerimonia al monumento"]


class TestVisteAppuntamenti:
    def test_permessi(self, client_ruolo):
        a = _app()
        c = client_ruolo("Consigliere", username="c")
        assert c.get(f"/calendario/appuntamenti/{a.pk}/").status_code == 200
        assert c.get("/calendario/appuntamenti/nuovo/").status_code == 403
        assert c.post(f"/calendario/appuntamenti/{a.pk}/azione/",
                      {"azione": "annulla"}).status_code == 403  # fmt: skip
        assert c.get("/calendario/mese/?m=2026-02").status_code == 200

    def test_crea_modifica_fatto_annulla(self, client_ruolo):
        from apps.calendario.models import Appuntamento

        c = client_ruolo("Tesoriere")
        giorno = timezone.localdate() + timedelta(days=4)
        r = c.post("/calendario/appuntamenti/nuovo/", {
            "titolo": "Invio del rendiconto", "tipo": "scadenza", "giorno": giorno.isoformat(),
        })  # fmt: skip
        a = Appuntamento.objects.get(titolo="Invio del rendiconto")
        assert r.status_code == 302 and a.creato_da == c.utente
        assert "Invio del rendiconto" in c.get("/").content.decode()  # nel cruscotto
        assert "Scadenze da fare" in c.get("/calendario/").content.decode()
        c.post(f"/calendario/appuntamenti/{a.pk}/azione/", {"azione": "fatto"})
        a.refresh_from_db()
        assert a.completato_il == timezone.localdate()
        r = c.post(f"/calendario/appuntamenti/{a.pk}/modifica/", {
            "titolo": "Invio rendiconto", "tipo": "scadenza", "giorno": giorno.isoformat(),
            "ora": "10:00", "ora_fine": "09:00",
        })  # fmt: skip
        assert r.status_code == 200 and "prima di quella di inizio" in r.content.decode()
        c.post(f"/calendario/appuntamenti/{a.pk}/azione/", {"azione": "annulla"})
        a.refresh_from_db()
        assert a.annullato
        assert c.get(f"/calendario/appuntamenti/{a.pk}/modifica/").status_code == 404

    def test_mese_mostra_gli_impegni(self, client_ruolo):
        oggi = timezone.localdate()
        _app(giorno=oggi, titolo="Deposizione corona")
        testo = client_ruolo("Segretario").get(f"/calendario/mese/?m={oggi:%Y-%m}").content
        assert b"Deposizione corona" in testo and b"mese-griglia" in testo
