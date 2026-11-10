# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test delle comunicazioni: segnaposto, consensi ed esclusioni, coda di
# *              invio, anniversari (compleanni, onomastici, iscrizione, ricorrenze),
# *              auguri automatici, invii collegati ad altri moduli.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from apps.anagrafica.models import Categoria, Consenso, Soggetto
from apps.comunicazioni import anniversari, servizi
from apps.comunicazioni.models import (
    Automazione,
    Destinatario,
    Finalita,
    Invio,
    Lista,
    Modello,
    PromemoriaRinnovo,
    Ricorrenza,
)
from apps.core.models import Organizzazione
from apps.protocollo.models import Protocollo
from apps.soci import servizi as soci
from apps.soci.models import TipologiaSocio

pytestmark = pytest.mark.django_db
OGGI = date.today()


@pytest.fixture(autouse=True)
def ambiente(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    settings.MAILERS = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}
    org = Organizzazione.corrente()
    org.denominazione = "ANCR Sezione di Prova"
    org.email = "segreteria@example.org"
    org.save()


@pytest.fixture
def utente(crea_utente):
    return crea_utente("segr", ruoli=["Segretario"])


def persona(cognome, nome="Mario", email=None, consensi=(), **extra):
    p = Soggetto.objects.create(
        cognome=cognome,
        nome=nome,
        email=email if email is not None else f"{cognome.lower()}@example.org",
        **extra,
    )
    for finalita in consensi:
        Consenso.objects.create(soggetto=p, finalita=finalita, prestato=True)
    return p


class TestSegnaposto:
    def test_componi(self):
        assert servizi.componi(
            "{{ saluto }} {{nome}}, {{ ignoto }}", {"saluto": "Caro", "nome": "Ugo"}
        ) == ("Caro Ugo, {{ ignoto }}")
        assert servizi.segnaposto_sconosciuti("{{ nome }} {{ ignoto }}") == ["ignoto"]

    def test_contesto_soggetto(self, utente):
        p = persona("Rossi", sesso="F", data_nascita=date(1950, 1, 1))
        ordinario = TipologiaSocio.objects.get(nome="Ordinario")
        soci.ammetti_socio(p, ordinario, utente, data_ammissione=date(OGGI.year - 10, 1, 1))
        c = servizi.contesto_soggetto(Soggetto.objects.get(pk=p.pk))
        assert c["saluto"] == "Cara" and c["anni_socio"] == 10 and c["numero_socio"] == 1


class TestDestinatari:
    def test_esclusioni_e_consensi(self, utente):
        ok = persona("Ok", consensi=["comunicazioni"])
        senza_consenso = persona("Senza")
        revocato = persona("Revocato", consensi=["comunicazioni"])
        Consenso.objects.create(
            soggetto=revocato,
            finalita="comunicazioni",
            prestato=False,
            data=OGGI + timedelta(days=1),
        )
        senza_email = persona("Noemail", email="", consensi=["comunicazioni"])
        morto = persona("Morto", consensi=["comunicazioni"], data_decesso=date(2020, 1, 1))
        invio = servizi.crea_invio(
            utente, oggetto="Gita", corpo="{{ saluto }} {{ nome }}", finalita=Finalita.COMUNICAZIONI,
            soggetti=[ok, senza_consenso, revocato, senza_email, morto],
            indirizzi=[("Ospite", "ospite@example.org"), ("Doppio", "ok@example.org")],
        )  # fmt: skip
        stati = {d.nome: (d.stato, d.motivo) for d in invio.destinatari.all()}
        assert stati["Ok Mario"] == ("in_attesa", "")
        assert stati["Senza Mario"] == ("escluso", "consenso non prestato")
        assert stati["Revocato Mario"] == ("escluso", "consenso non prestato")
        assert stati["Noemail Mario"] == ("escluso", "senza email")
        assert stati["Morto Mario"] == ("escluso", "deceduto")
        assert stati["Ospite"] == ("in_attesa", "") and "Doppio" not in stati

    def test_istituzionale_senza_consenso(self, utente):
        invio = servizi.crea_invio(
            utente, oggetto="Convocazione", corpo="x", finalita=Finalita.ISTITUZIONALE,
            soggetti=[persona("Rossi")],
        )  # fmt: skip
        assert invio.destinatari.get().stato == "in_attesa"

    def test_lista_dinamica(self, utente):
        cat = Categoria.objects.get(nome="Autorità")
        sindaco = persona("Sindaco")
        sindaco.categorie.add(cat)
        ordinario = TipologiaSocio.objects.get(nome="Ordinario")
        socio = soci.ammetti_socio(persona("Socio"), ordinario, utente)
        extra = persona("Extra")
        lista = Lista.objects.create(nome="Cerimonia", soci_attivi=True)
        lista.categorie.add(cat)
        lista.soggetti.add(extra)
        assert set(servizi.soggetti_lista(lista)) == {sindaco, socio.soggetto, extra}


class TestCoda:
    def _invio(self, utente, **extra):
        return servizi.crea_invio(
            utente, oggetto="Ciao {{ nome }}", corpo="{{ saluto }} {{ nome }},\nprova.",
            finalita=Finalita.ISTITUZIONALE,
            soggetti=[persona("Rossi", sesso="M"), persona("Bianchi", "Anna", sesso="F")],
            allegati=[("programma.pdf", b"%PDF-1.4 x")], **extra,
        )  # fmt: skip

    def test_invio_personalizzato(self, utente):
        invio = self._invio(utente, protocolla=True)
        assert len(mail.outbox) == 0  # in bozza non parte nulla
        servizi.conferma(invio, utente)
        assert servizi.elabora_coda() == (2, 0)
        oggetti = sorted(m.subject for m in mail.outbox)
        assert oggetti == ["Ciao Anna", "Ciao Mario"]
        m = next(m for m in mail.outbox if m.subject == "Ciao Anna")
        assert m.body.startswith("Cara Anna,") and m.to == ["Bianchi Anna <bianchi@example.org>"]
        assert m.reply_to == ["segreteria@example.org"] and m.attachments[0][0] == "programma.pdf"
        assert "ANCR Sezione di Prova" in m.alternatives[0][0]
        invio.refresh_from_db()
        assert invio.stato == "inviato" and invio.protocollo.corrispondenti.count() == 2
        assert Protocollo.objects.get().allegati.count() == 2

    def test_titolo_con_un_solo_destinatario(self, utente, client):
        uno = servizi.crea_invio(
            utente, oggetto="Buon compleanno, {{ nome }}!", corpo="x",
            finalita=Finalita.ISTITUZIONALE, soggetti=[persona("Verdi", "Alessandra")],
        )  # fmt: skip
        assert uno.titolo == "Buon compleanno, Alessandra!"
        due = self._invio(utente)  # più destinatari: il segnaposto personale resta
        assert due.titolo == "Ciao {{ nome }}"
        client.force_login(utente)
        pagina = client.get(reverse("comunicazioni:invii")).content.decode()
        assert "Buon compleanno, Alessandra!" in pagina

    def test_errori_e_tentativi(self, utente):
        invio = servizi.conferma(self._invio(utente), utente)
        with mock.patch.object(
            servizi.EmailMultiAlternatives, "send", side_effect=OSError("smtp giù")
        ):
            for _ in range(servizi.MAX_TENTATIVI):
                assert servizi.elabora_coda() == (0, 2)
        invio.refresh_from_db()
        assert invio.stato == "con_errori" and invio.destinatari.filter(stato="errore").count() == 2

    def test_programmato_e_lotto(self, utente, settings):
        invio = self._invio(utente, programmato_il=timezone.now() + timedelta(hours=2))
        servizi.conferma(invio, utente)
        assert servizi.elabora_coda() == (0, 0)
        Invio.objects.filter(pk=invio.pk).update(programmato_il=None)
        settings.COMUNICAZIONI_LOTTO = 1
        assert servizi.elabora_coda() == (1, 0)
        assert Invio.objects.get(pk=invio.pk).stato == "in_coda"

    def test_segnaposto_sconosciuto_blocca(self, utente):
        invio = servizi.crea_invio(
            utente, oggetto="x", corpo="{{ sconosciuto }}", finalita=Finalita.ISTITUZIONALE,
            soggetti=[persona("Rossi")],
        )  # fmt: skip
        with pytest.raises(servizi.OperazioneNonValida):
            servizi.conferma(invio, utente)


class TestAnniversari:
    def test_tipi(self, utente):
        oggi = date(2027, 3, 1)  # 2027 non bisestile
        persona("Bisestile", data_nascita=date(1960, 2, 29))
        persona("Bianchi", "Maria Teresa", data_nascita=date(1970, 5, 5))
        persona("Verdi", "Nicolò")
        persona("Neri", "Luigi", data_decesso=date(2020, 3, 1))
        ordinario = TipologiaSocio.objects.get(nome="Ordinario")
        soci.ammetti_socio(persona("Anziano"), ordinario, utente, data_ammissione=date(2002, 3, 1))
        Ricorrenza.objects.create(
            nome="Fondazione della sezione", giorno=1, mese=3, anno_inizio=1927
        )
        eventi = anniversari.eventi(dal=oggi, giorni=0)
        tipi = {(e.tipo, e.titolo, e.anni) for e in eventi}
        assert ("compleanno", "Bisestile Mario", 67) in tipi
        assert ("anzianita", "Anziano Mario", 25) in tipi
        assert ("ricorrenza", "Fondazione della sezione", 100) in tipi
        assert ("scomparsa", "Neri Luigi", 7) in tipi
        assert ("compleanno", "Neri Luigi", None) not in {(e.tipo, e.titolo, None) for e in eventi}
        nomi = {
            e.titolo
            for e in anniversari.eventi(dal=date(2027, 9, 12), giorni=0, tipi=["onomastico"])
        }
        assert "Bianchi Maria Teresa" in nomi  # Maria, 12 settembre
        assert {e.titolo for e in anniversari.onomastici(date(2027, 12, 6), date(2027, 12, 6))} == {
            "Verdi Nicolò"
        }


class TestAuguriAutomatici:
    def test_compleanni_una_volta_sola(self, utente):
        Automazione.objects.filter(tipo="compleanno").update(
            attiva=True, destinatari="anagrafica", ora=8
        )
        festeggiato = persona("Festa", data_nascita=OGGI.replace(year=1960), consensi=["auguri"])
        persona("Riservato", data_nascita=OGGI.replace(year=1961))  # senza consenso
        assert servizi.auguri_del_giorno(adesso=timezone.localtime().replace(hour=7)) == []
        creati = servizi.auguri_del_giorno(adesso=timezone.localtime().replace(hour=9))
        assert len(creati) == 1 and creati[0].stato == "in_coda"
        servizi.elabora_coda()
        assert len(mail.outbox) == 1 and mail.outbox[0].subject == "Buon compleanno, Mario!"
        assert mail.outbox[0].to[0].endswith("<festa@example.org>")
        Automazione.objects.update(ultimo_giorno=None)  # anche rieseguendo, nessun doppione
        servizi.auguri_del_giorno(adesso=timezone.localtime().replace(hour=9))
        assert Destinatario.objects.filter(soggetto=festeggiato).count() == 1

    def test_anzianita_solo_anni_scelti(self, utente):
        Automazione.objects.filter(tipo="anzianita").update(attiva=True, ora=0, anni="10,25")
        ordinario = TipologiaSocio.objects.get(nome="Ordinario")
        for anni, nome in ((10, "Dieci"), (11, "Undici")):
            p = persona(nome, consensi=["auguri"])
            soci.ammetti_socio(
                p, ordinario, utente, data_ammissione=OGGI.replace(year=OGGI.year - anni)
            )
        creati = servizi.auguri_del_giorno()
        assert [d.nome for d in creati[0].destinatari.all()] == ["Dieci Mario"]
        assert creati[0].destinatari.get().contesto == {"anni": 10}

    def test_ricorrenza_automatica(self, utente):
        lista = Lista.objects.create(nome="Tutti", soci_attivi=False)
        lista.soggetti.add(persona("Rossi", consensi=["comunicazioni"]))
        Ricorrenza.objects.create(
            nome="Festa della sezione", giorno=OGGI.day, mese=OGGI.month, anno_inizio=1950,
            lista=lista, invio_automatico=True,
        )  # fmt: skip
        creati = servizi.auguri_del_giorno()
        assert len(creati) == 1 and creati[0].contesto["anni"] == OGGI.year - 1950
        assert servizi.auguri_del_giorno() == []


class TestCollegamenti:
    def test_ricevuta_e_domanda(self, utente):
        ordinario = TipologiaSocio.objects.get(nome="Ordinario")
        ordinario.quota_annua = Decimal("20")
        ordinario.save()
        socio = soci.ammetti_socio(persona("Rossi"), ordinario, utente)
        t = soci.rilascia_tessera(socio, OGGI.year, utente, pagata_il=OGGI)
        invio = servizi.da_tessera(t, utente)
        assert (
            invio.allegati.get().nome.startswith("ricevuta_")
            and invio.contesto["importo"] == "20,00"
        )
        servizi.conferma(invio, utente)
        servizi.elabora_coda()
        assert "ricevuta n. " in mail.outbox[0].body
        from apps.soci.models import DomandaIscrizione

        d = DomandaIscrizione.objects.create(
            nome="Laura", cognome="Bianchi", codice_fiscale="BNCLRA80A41F205G",
            data_nascita=date(1980, 1, 1), luogo_nascita="Milano", email="laura@example.org",
            indirizzo="Via Roma", cap="20100", comune="Milano", provincia="MI",
        )  # fmt: skip
        soci.respingi_domanda(d, utente, "requisiti mancanti")
        d.refresh_from_db()
        invio = servizi.da_domanda(d, utente)
        dest = invio.destinatari.get()
        assert dest.email == "laura@example.org" and dest.soggetto is None
        assert "respinta (requisiti mancanti)" in servizi.messaggio(invio, dest).body

    def test_convocazione(self, utente):
        from apps.organi import servizi as organi
        from apps.organi.forms import RiunioneForm
        from apps.organi.models import Organo, Riunione

        cd = Organo.objects.get(sigla="CD")
        organi.nomina(cd, persona("Presidente"), "presidente", date(2025, 1, 1), utente)
        quando = (timezone.localtime() + timedelta(days=5)).strftime("%Y-%m-%dT18:00")
        form = RiunioneForm({"organo": cd.pk, "prima_convocazione": quando, "luogo": "Sede",
                             "modalita": "presenza", "punti": "Bilancio"}, instance=Riunione())  # fmt: skip
        assert form.is_valid()
        r = organi.convoca(organi.salva_riunione(form, form.titoli_punti(), utente), utente)
        invio = servizi.da_riunione(r, utente)
        m = servizi.messaggio(invio, invio.destinatari.get())
        assert "1. Bilancio" in m.body and m.attachments[0][0] == "convocazione.pdf"


class TestViste:
    def test_pagine_e_invio(self, client, utente):
        client.force_login(utente)
        rossi = persona("Rossi", consensi=["comunicazioni"])
        lista = Lista.objects.create(nome="Prova")
        lista.soggetti.add(rossi)
        for url in [
            reverse("comunicazioni:invii"),
            reverse("comunicazioni:nuovo")
            + f"?modello={Modello.objects.first().pk}&soggetto={rossi.pk}",
            reverse("comunicazioni:modelli"),
            reverse("comunicazioni:modello_nuovo"),
            reverse("comunicazioni:liste"),
            reverse("comunicazioni:lista", args=[lista.pk]),
            reverse("comunicazioni:lista_nuova"),
            reverse("comunicazioni:anniversari") + "?giorni=365",
            reverse("comunicazioni:auguri"),
            reverse("comunicazioni:automazione", args=[Automazione.objects.first().pk]),
            reverse("comunicazioni:onomastici") + "?q=mar",
            reverse("anagrafica:dettaglio", args=[rossi.pk]),
            reverse("core:cruscotto"),
        ]:
            assert client.get(url).status_code == 200, url
        r = client.get(reverse("comunicazioni:cerca"), {"cerca": "ross"}, HTTP_HX_REQUEST="true")
        assert "Rossi Mario" in r.content.decode()
        r = client.post(
            reverse("comunicazioni:nuovo"),
            {"oggetto": "Avviso", "corpo": "{{ saluto }} {{ nome }}", "finalita": "comunicazioni",
             "liste": [lista.pk], "indirizzi": "Ospite <ospite@example.org>\nnon-valido"},
        )  # fmt: skip
        assert r.status_code == 200 and "Indirizzi non validi" in r.content.decode()
        r = client.post(
            reverse("comunicazioni:nuovo"),
            {"oggetto": "Avviso", "corpo": "{{ saluto }} {{ nome }}", "finalita": "comunicazioni",
             "liste": [lista.pk], "indirizzi": "Ospite <ospite@example.org>"},
        )  # fmt: skip
        invio = Invio.objects.get()
        assert r.status_code == 302 and invio.destinatari.count() == 2
        assert "Gentile Ospite" in client.get(invio.get_absolute_url()).content.decode()
        client.post(reverse("comunicazioni:conferma", args=[invio.pk]))
        assert len(mail.outbox) == 2 and Invio.objects.get().stato == "inviato"

    def test_modello_con_segnaposto_errato(self, client, utente):
        client.force_login(utente)
        r = client.post(reverse("comunicazioni:modello_nuovo"),
                        {"nome": "X", "uso": "generico", "oggetto": "{{ nme }}", "corpo": "x", "attivo": "on"})  # fmt: skip
        assert r.status_code == 200 and "Segnaposto sconosciuti: nme" in r.content.decode()

    def test_permessi(self, client_ruolo):
        c = client_ruolo("Consigliere")
        assert c.get(reverse("comunicazioni:anniversari")).status_code == 200
        assert c.get(reverse("comunicazioni:invii")).status_code == 403
        assert c.get(reverse("comunicazioni:nuovo")).status_code == 403


class TestPromemoriaRinnovo:
    @pytest.fixture
    def soci_misti(self, utente):
        ordinario = TipologiaSocio.objects.get(nome="Ordinario")
        ordinario.quota_annua = Decimal("25")
        ordinario.save()
        moroso = soci.ammetti_socio(persona("Moroso"), ordinario, utente)
        con_tessera = soci.ammetti_socio(persona("Tessera"), ordinario, utente)
        soci.rilascia_tessera(con_tessera, OGGI.year, utente, importo=Decimal("30"))
        pagato = soci.ammetti_socio(persona("Pagato"), ordinario, utente)
        soci.rilascia_tessera(pagato, OGGI.year, utente, pagata_il=OGGI)
        soci.ammetti_socio(persona("Senzamail", email=""), ordinario, utente)
        return moroso, con_tessera

    def _attiva(self, date=None):
        PromemoriaRinnovo.objects.filter(pk=1).update(
            attivo=True, ora=8, date_invio=date or f"{OGGI:%d/%m}", ultimo_giorno=None
        )

    def test_date_scelte(self):
        p = PromemoriaRinnovo(date_invio="15/01, 1-3; 31/12, 40/2, xx, 5/13")
        assert p.date_scelte() == {(15, 1), (1, 3), (31, 12)}

    def test_automatico_solo_nei_giorni_e_dopo_l_ora(self, soci_misti):
        alle = timezone.localtime().replace(hour=9)
        assert servizi.promemoria_rinnovo(adesso=alle) is None  # spento
        domani = OGGI + timedelta(days=1)
        self._attiva(f"{domani:%d/%m}")
        assert servizi.promemoria_rinnovo(adesso=alle) is None  # non è il giorno
        self._attiva()
        assert servizi.promemoria_rinnovo(adesso=alle.replace(hour=7)) is None  # troppo presto
        invio = servizi.promemoria_rinnovo(adesso=alle)
        assert invio.stato == "in_coda" and invio.origine == "rinnovo"
        dest = {d.nome: d for d in invio.destinatari.all()}
        assert set(dest) == {"Moroso Mario", "Tessera Mario", "Senzamail Mario"}
        assert dest["Senzamail Mario"].stato == "escluso"
        assert dest["Moroso Mario"].contesto == {"anno_quota": OGGI.year, "importo": "25,00"}
        assert dest["Tessera Mario"].contesto["importo"] == "30,00"
        servizi.elabora_coda()
        oggetti = {m.subject for m in mail.outbox}
        assert oggetti == {f"Rinnovo della quota associativa {OGGI.year}"} and len(mail.outbox) == 2
        assert "25,00 euro" in next(m.body for m in mail.outbox if "moroso" in m.to[0].lower())
        assert servizi.promemoria_rinnovo(adesso=alle) is None  # una volta al giorno
        PromemoriaRinnovo.objects.update(ultimo_giorno=None)
        assert servizi.promemoria_rinnovo(adesso=alle) is None  # nessun doppione

    def test_prepara_ora_in_bozza(self, soci_misti, client_ruolo):
        c = client_ruolo("Tesoriere")
        pagina = c.get("/comunicazioni/promemoria-rinnovo/").content.decode()
        assert "Soci non in regola" in pagina and ">3<" in pagina.replace(" ", "")
        r = c.post("/comunicazioni/promemoria-rinnovo/prepara/")
        invio = Invio.objects.get(origine="rinnovo")
        assert r.status_code == 302 and invio.stato == "bozza" and invio.creato_da == c.utente
        r = c.post("/comunicazioni/promemoria-rinnovo/prepara/", follow=True)
        assert "Nessun socio da sollecitare" in r.content.decode()

    def test_impostazioni_e_permessi(self, client_ruolo):
        assert client_ruolo("Consigliere", username="c").get(
            "/comunicazioni/promemoria-rinnovo/").status_code == 403  # fmt: skip
        presidente = client_ruolo("Presidente", username="p")
        assert presidente.get("/comunicazioni/promemoria-rinnovo/").status_code == 200
        assert presidente.post("/comunicazioni/promemoria-rinnovo/", {}).status_code == 403
        c = client_ruolo("Segretario", username="s")
        r = c.post("/comunicazioni/promemoria-rinnovo/",
                   {"attivo": "on", "date_invio": "1/3, 15/1", "ora": "10"})  # fmt: skip
        assert r.status_code == 302
        p = PromemoriaRinnovo.corrente()
        assert p.attivo and p.date_invio == "15/01, 01/03" and p.ora == 10
        r = c.post("/comunicazioni/promemoria-rinnovo/", {"date_invio": "mai", "ora": "10"})
        assert "giorno/mese" in r.content.decode()
