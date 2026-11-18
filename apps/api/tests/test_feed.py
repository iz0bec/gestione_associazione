# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test della fase F2: feed dei cambiamenti (outbox, progressivi, catena di
# *              impronte, conservazione), risorse eventi e sezioni con visibilità per
# *              controparte, riepiloghi, rotazione delle chiavi delle due parti e notifiche.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import json
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.api import chiavi, feed, servizi
from apps.api.models import Cambiamento, ClienteApi, NotificaApi
from apps.collegamenti import client as collegamenti
from apps.collegamenti.trasporto import ErroreTrasporto, Risposta
from apps.core.cifratura import nuova_chiave
from apps.eventi import servizi as eventi
from apps.eventi.models import Evento
from apps.soci.models import Sezione

from .aiuti import Controparte


@pytest.fixture(autouse=True)
def _cifratura(settings):
    settings.CHIAVE_CIFRATURA = nuova_chiave()
    settings.API_TLS_CERTIFICATO = ""


def _evento(**extra):
    dati = {"titolo": "Commemorazione", "inizio": timezone.now() + timedelta(days=10)} | extra
    return Evento.objects.create(**dati)


def _controparte(tipo="installazione", ambiti=("eventi:lettura", "sezioni:lettura"), **extra):
    ctp = Controparte()
    cliente = ClienteApi.objects.create(
        nome="Controparte", tipo=tipo, origine="invito_nostro", stato="attiva",
        istanza=ctp.uuid, jwks=ctp.jwks, ambiti=list(ambiti), **extra,
    )  # fmt: skip
    return ctp, cliente


def _voci(flusso):
    return [feed.come_evento(c) for c in Cambiamento.objects.filter(flusso=flusso)]


@pytest.mark.django_db
class TestOutbox:
    def test_ogni_modifica_finisce_nel_feed_con_la_catena(self):
        e = _evento()
        e.luogo = "Piazza"
        e.save()
        e.annullato = True
        e.save()
        voci = _voci("eventi")
        assert [v["type"] for v in voci] == [
            "it.gestioneassociazione.evento.creato.v1",
            "it.gestioneassociazione.evento.modificato.v1",
            "it.gestioneassociazione.evento.annullato.v1",
        ]
        assert [v["data"]["versione"] for v in voci] == [1, 2, 3]
        assert [v["ga_progressivo"] for v in voci] == [1, 2, 3]
        assert all(v["subject"] == str(e.uuid) for v in voci)
        assert voci[0]["ga_precedente"] == feed.ORIGINE
        assert feed.verifica_catena(voci) == voci[-1]["ga_impronta"]
        assert voci[0]["source"] == f"urn:uuid:{chiavi.istanza().uuid}"

    def test_la_catena_rileva_alterazioni_e_buchi(self):
        for _ in range(3):
            _evento()
        voci = _voci("eventi")
        alterate = json.loads(json.dumps(voci))
        alterate[1]["subject"] = "00000000-0000-0000-0000-000000000000"
        with pytest.raises(feed.CatenaInterrotta, match="Impronta errata"):
            feed.verifica_catena(alterate)
        with pytest.raises(feed.CatenaInterrotta, match="Manca il progressivo 2"):
            feed.verifica_catena([voci[0], voci[2]])

    def test_adesioni_e_sezioni(self):
        e = _evento(posti=10)
        adesione = eventi.aderisci(e, {"cognome": "Rossi"}, origine="segreteria")
        eventi.annulla_adesione(adesione)
        e.refresh_from_db()
        assert e.versione == 3
        s = Sezione.objects.create(codice="PZ001", nome="Potenza")
        s.attiva = False
        s.save()
        assert [v["data"]["versione"] for v in _voci("sezioni") if v["subject"] == str(s.uuid)] == [
            1,
            2,
        ]

    def test_una_copia_vecchia_non_riporta_indietro_la_versione(self):
        e = _evento()
        copia = Evento.objects.get(pk=e.pk)
        e.luogo = "A"
        e.save()
        copia.luogo = "B"
        copia.save()
        e.refresh_from_db()
        assert e.versione == 3 and e.luogo == "B"

    def test_conservazione_tiene_l_ultimo(self):
        for _ in range(3):
            _evento()
        Cambiamento.objects.update(momento=timezone.now() - timedelta(days=401))
        assert feed.conserva() == 2
        assert list(Cambiamento.objects.values_list("progressivo", flat=True)) == [3]
        _evento()  # la catena continua dall'ultimo conservato
        voci = _voci("eventi")
        assert voci[1]["ga_precedente"] == voci[0]["ga_impronta"]
        with pytest.raises(feed.CatenaInterrotta):
            feed.pagina("eventi", 0, 10)
        assert [v["ga_progressivo"] for v in feed.pagina("eventi", 2, 10)[0]] == [3, 4]


@pytest.mark.django_db
class TestRisorse:
    def test_cambiamenti_a_pagine_e_ambiti(self, client):
        ctp, _ = _controparte(ambiti=["eventi:lettura"])
        for _ in range(5):
            _evento()
        r = ctp.chiama(client, "GET", "/api/v1/cambiamenti?flusso=eventi&dopo=1&limite=2")
        assert r.status_code == 200, r.content
        dati = r.json()
        assert [v["ga_progressivo"] for v in dati["cambiamenti"]] == [2, 3] and dati["ultimo"] == 5
        r = ctp.chiama(client, "GET", "/api/v1/cambiamenti?flusso=sezioni")
        assert (r.status_code, r.json()["codice"]) == (403, "ambito-mancante")
        r = ctp.chiama(client, "GET", "/api/v1/cambiamenti?flusso=soci:X")
        assert r.status_code == 404
        Cambiamento.objects.filter(progressivo__lt=5).delete()
        r = ctp.chiama(client, "GET", "/api/v1/cambiamenti?flusso=eventi&dopo=1")
        assert (r.status_code, r.json()["codice"]) == (410, "cursore-scaduto")

    def test_eventi_visibili_alle_integrazioni(self, client):
        pubblico, privato = _evento(pubblico=True, titolo="Aperto"), _evento(titolo="Interno")
        ctp, _ = _controparte(tipo="integrazione", ambiti=["eventi:lettura"])
        r = ctp.chiama(client, "GET", "/api/v1/eventi")
        assert [e["titolo"] for e in r.json()["risultati"]] == ["Aperto"]
        assert ctp.chiama(client, "GET", f"/api/v1/eventi/{privato.uuid}").status_code == 404
        r = ctp.chiama(client, "GET", f"/api/v1/eventi/{pubblico.uuid}")
        assert r.status_code == 200 and r["ETag"] == '"1"'
        assert r.json()["posti_liberi"] is None and r.json()["uuid"] == str(pubblico.uuid)
        sede, _ = _controparte(ambiti=["eventi:lettura"])
        r = sede.chiama(client, "GET", "/api/v1/eventi")
        assert len(r.json()["risultati"]) == 2

    def test_eventi_a_pagine_con_cursore(self, client):
        ctp, _ = _controparte()
        inizio = timezone.now() + timedelta(days=1)
        for n in range(5):
            _evento(titolo=f"E{n}", inizio=inizio + timedelta(hours=n // 2))
        visti, cursore = [], None
        while True:
            percorso = "/api/v1/eventi?limite=2" + (f"&cursore={cursore}" if cursore else "")
            dati = ctp.chiama(client, "GET", percorso).json()
            visti += [e["titolo"] for e in dati["risultati"]]
            cursore = dati["successivo"]
            if not cursore:
                break
        assert visti == ["E0", "E1", "E2", "E3", "E4"]

    def test_sezioni_e_riepilogo(self, client):
        ctp, cliente = _controparte()
        Sezione.objects.create(codice="PZ001", nome="Potenza")
        r = ctp.chiama(client, "GET", "/api/v1/sezioni")
        sezioni = r.json()
        assert "PZ001" in [s["codice"] for s in sezioni]
        r = ctp.chiama(client, "GET", "/api/v1/riepiloghi/sezioni")
        riepilogo = r.json()
        assert riepilogo["risorse"] == len(sezioni)
        assert riepilogo["impronta"] == feed.impronta_riepilogo(
            (s["uuid"], s["versione"]) for s in sezioni
        )
        assert riepilogo["progressivo"] == feed.ultimo("sezioni")


@pytest.mark.django_db
class TestRotazione:
    def test_la_controparte_presenta_chiavi_nuove(self, client):
        ctp, cliente = _controparte()
        nuova = Controparte()
        corpo = {"jwks": nuova.jwks}
        r = ctp.chiama(client, "PUT", "/api/v1/chiavi", corpo)
        assert r.status_code == 200, r.content
        cliente.refresh_from_db()
        assert cliente.jwks == nuova.jwks
        nuova.uuid = ctp.uuid
        assert nuova.chiama(client, "POST", "/api/v1/prova").status_code == 200
        assert ctp.chiama(client, "POST", "/api/v1/prova").status_code == 401  # chiave vecchia

    def test_dopo_la_nostra_rotazione_chi_ha_le_vecchie_chiavi_verifica(self, client, crea_utente):
        vecchie = chiavi.jwks()
        servizi.ruota_chiavi(crea_utente("admin"))
        r = client.get("/.well-known/gestione-associazione/jwks.json")
        assert r["Signature-Input"].count("ga") >= 2  # firma nuova e firma con la chiave in uscita
        risposta = Risposta(stato=r.status_code, corpo=r.content, destinazione=None,
                            intestazioni={k.lower(): v for k, v in r.headers.items()})  # fmt: skip
        esito = collegamenti._verifica_risposta(risposta, vecchie)  # verificata con «ga1»
        assert esito.etichetta == "ga1"
        assert collegamenti._verifica_risposta(risposta, chiavi.jwks()).etichetta == "ga"
        with pytest.raises(collegamenti.ErroreCollegamento):
            collegamenti._verifica_risposta(risposta, Controparte().jwks)

    def test_aggiorna_identita_accetta_solo_chiavi_firmate_da_una_nota(self, monkeypatch):
        ctp, cliente = _controparte(indirizzo_pubblico="https://sede.example.org")
        nuova = Controparte()

        def risposta(dati, firmatari):
            corpo = json.dumps(dati).encode()
            intestazioni = {"content-digest": collegamenti.f.content_digest(corpo)}
            ingressi, valori = [], []
            for n, (kid, chiave) in enumerate(firmatari):
                msg = collegamenti.f.Messaggio(intestazioni=dict(intestazioni), stato=200)
                i, v = collegamenti.f.firma(msg, collegamenti.f.componenti_risposta(False),
                                  collegamenti.f.parametri_firma(kid, timezone.now().timestamp(), "n" * 20),
                                  chiave, etichetta="ga" + (str(n) if n else ""))  # fmt: skip
                ingressi.append(i)
                valori.append(v)
            intestazioni |= {"signature-input": ", ".join(ingressi), "signature": ", ".join(valori)}
            return Risposta(stato=200, intestazioni=intestazioni, corpo=corpo, destinazione=None)

        firmatari = [(nuova.kid, nuova.firma), (ctp.kid, ctp.firma)]

        def remota(dest, metodo, percorso, intestazioni=None, corpo=b""):
            if percorso.endswith("jwks.json"):
                return risposta(nuova.jwks, firmatari)
            return risposta({"istanza": str(ctp.uuid), "tls_spki": ["B" * 43 + "="]}, firmatari)

        monkeypatch.setattr(collegamenti, "richiesta", remota)
        assert collegamenti.aggiorna_identita(cliente) == (True, "Chiavi o impronte aggiornate.")
        cliente.refresh_from_db()
        assert cliente.jwks == nuova.jwks and cliente.tls_spki == ["B" * 43 + "="]
        estranea = Controparte()
        firmatari[:] = [(estranea.kid, estranea.firma)]  # nessuna chiave nota: rifiutate
        nuova.jwks = estranea.jwks
        cambiate, esito = collegamenti.aggiorna_identita(cliente)
        assert not cambiate and "Firma della risposta non valida" in esito


@pytest.mark.django_db
class TestNotifiche:
    def test_coda_consegna_e_ripetizioni(self, monkeypatch):
        _, cliente = _controparte(indirizzo_notifiche="https://sito.example.org/ga/avvisi",
                                  notifiche_flussi=["eventi"])  # fmt: skip
        _controparte(notifiche_flussi=["eventi"])  # senza indirizzo: nessuna notifica
        _evento()
        notifica = NotificaApi.objects.get()
        assert notifica.cliente == cliente
        chiamate = []
        esiti = [ErroreTrasporto("rifiutata"), 503, 204]

        def remota(dest, metodo, percorso, intestazioni=None, corpo=b""):
            chiamate.append((dest.url, percorso, intestazioni["Content-Type"], json.loads(corpo)))
            esito = esiti.pop(0)
            if isinstance(esito, Exception):
                raise esito
            return Risposta(stato=esito, intestazioni={}, corpo=b"", destinazione=dest)

        monkeypatch.setattr(collegamenti, "richiesta", remota)
        assert collegamenti.invia_notifiche() == (0, 1)
        notifica.refresh_from_db()
        assert notifica.tentativi == 1 and notifica.prossimo_tentativo > timezone.now()
        assert collegamenti.invia_notifiche() == (0, 0)  # non ancora dovuta
        NotificaApi.objects.update(prossimo_tentativo=timezone.now())
        collegamenti.invia_notifiche()
        notifica.refresh_from_db()
        assert "HTTP 503" in notifica.ultimo_errore
        NotificaApi.objects.update(prossimo_tentativo=timezone.now())
        assert collegamenti.invia_notifiche() == (1, 0)
        notifica.refresh_from_db()
        assert notifica.stato == "consegnata"
        url, percorso, tipo, evento = chiamate[-1]
        assert (url, percorso, tipo) == ("https://sito.example.org", "/ga/avvisi",
                                         "application/cloudevents+json")  # fmt: skip
        assert evento["type"] == "it.gestioneassociazione.evento.creato.v1"

    def test_dopo_24_ore_resta_fallita_e_si_riprova(self, monkeypatch, crea_utente):
        _, cliente = _controparte(indirizzo_notifiche="https://sito.example.org/",
                                  notifiche_flussi=["eventi"])  # fmt: skip
        _evento()
        monkeypatch.setattr(collegamenti, "richiesta", lambda *a, **k: (_ for _ in ()).throw(
            ErroreTrasporto("giù")))  # fmt: skip
        NotificaApi.objects.update(tentativi=11)
        collegamenti.invia_notifiche()
        notifica = NotificaApi.objects.get()
        assert notifica.stato == "fallita" and notifica.tentativi == 12
        assert servizi.riprova_notifiche(cliente, crea_utente("admin")) == 1
        notifica.refresh_from_db()
        assert notifica.stato == "in_coda" and notifica.tentativi == 0
