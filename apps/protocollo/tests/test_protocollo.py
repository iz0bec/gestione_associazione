# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test del protocollo: numerazione, allegati, riservati, annullamento,
# *              registro giornaliero, posta ricevuta (anche PEC), cifratura delle caselle.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import hashlib
from datetime import timedelta
from email.message import EmailMessage

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from apps.anagrafica.models import Soggetto
from apps.core.cifratura import nuova_chiave
from apps.core.models import EventoAudit
from apps.protocollo import posta, servizi
from apps.protocollo.forms import CampoSegnatura, CasellaForm
from apps.protocollo.models import (
    CasellaPosta,
    MessaggioRicevuto,
    Protocollo,
    RegistroGiornaliero,
)
from apps.protocollo.servizi import OperazioneNonValida

pytestmark = pytest.mark.django_db
ANNO = timezone.localdate().year


@pytest.fixture(autouse=True)
def cartella_media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def utente(crea_utente):
    return crea_utente("addetto", ruoli=["Addetto protocollo"])


@pytest.fixture
def comune():
    return Soggetto.objects.create(
        tipo="ente", denominazione="Comune di Avigliano", pec="protocollo@pec.comune.example.it"
    )


def _registra(utente, direzione="entrata", oggetto="Richiesta patrocinio", soggetto=None, **extra):
    ruolo = "mittente" if direzione == "entrata" else "destinatario"
    corr = (
        [servizi.corrispondente_da_soggetto(soggetto, ruolo)]
        if soggetto
        else [{"ruolo": ruolo, "descrizione": "Mario Rossi", "indirizzo": "mario@example.org"}]
    )
    return servizi.registra_protocollo(
        {"direzione": direzione, "mezzo": "email", "oggetto": oggetto, **extra}, corr, utente
    )


def _pdf(nome="documento.pdf", contenuto=b"%PDF-1.4 prova"):
    return SimpleUploadedFile(nome, contenuto, content_type="text/html")


class TestRegistrazione:
    def test_numeri_progressivi_e_corrispondenti(self, utente, comune):
        p1 = _registra(utente, soggetto=comune)
        p2 = _registra(utente, "uscita", "Risposta", soggetto=comune)
        assert (p1.numero, p2.numero, p1.anno) == (1, 2, ANNO)
        assert p1.segnatura == f"{ANNO}-00001"
        c = p1.corrispondenti.get()
        assert c.soggetto == comune and c.indirizzo == comune.pec
        assert EventoAudit.objects.filter(azione="creazione", oggetto_id=str(p1.pk)).exists()

    def test_corrispondenti_obbligatori(self, utente):
        with pytest.raises(OperazioneNonValida):
            servizi.registra_protocollo({"direzione": "entrata", "oggetto": "x"}, [], utente)
        with pytest.raises(OperazioneNonValida):
            servizi.registra_protocollo(
                {"direzione": "uscita", "oggetto": "x"},
                [{"ruolo": "mittente", "descrizione": "A"}],
                utente,
            )
        servizi.registra_protocollo({"direzione": "interno", "oggetto": "Nota"}, [], utente)

    def test_annullamento(self, utente):
        p = _registra(utente)
        with pytest.raises(OperazioneNonValida):
            servizi.annulla_protocollo(p, utente, "no")
        servizi.annulla_protocollo(p, utente, "registrato due volte")
        p.refresh_from_db()
        assert p.annullato and p.annullato_da == utente
        with pytest.raises(OperazioneNonValida):
            servizi.annulla_protocollo(p, utente, "ancora una volta")
        assert _registra(utente).numero == 2  # il numero annullato non si riusa

    def test_segnatura_nei_moduli(self, utente):
        p = _registra(utente)
        campo = CampoSegnatura(required=False)
        assert campo.clean(f"{ANNO}-00001") == p
        assert campo.clean(f"1/{ANNO}") == p
        with pytest.raises(Exception):  # noqa: B017
            campo.clean(f"{ANNO}-00099")


class TestAllegati:
    def test_salvataggio_con_impronta(self, utente):
        p = _registra(utente)
        contenuto = b"%PDF-1.4 contenuto"
        a = servizi.aggiungi_allegato(p, _pdf("../../etc/Lettera finale.PDF", contenuto), utente)
        assert a.nome == "Lettera finale.PDF" and a.tipo == "application/pdf"
        assert a.impronta == hashlib.sha256(contenuto).hexdigest()
        assert a.file.name.startswith(f"protocollo/{ANNO}/00001/") and a.file.name.endswith(".pdf")
        assert "Lettera" not in a.file.name

    def test_tipi_e_dimensioni(self, utente, settings):
        p = _registra(utente)
        with pytest.raises(OperazioneNonValida):
            servizi.carica_allegati(p, [_pdf("virus.exe")], utente)
        settings.PROTOCOLLO_ALLEGATO_MAX_MB = 0
        with pytest.raises(OperazioneNonValida):
            servizi.carica_allegati(p, [_pdf()], utente)

    def test_nessun_allegato_su_annullato(self, utente):
        p = _registra(utente)
        servizi.annulla_protocollo(p, utente, "errore materiale")
        with pytest.raises(OperazioneNonValida):
            servizi.carica_allegati(p, [_pdf()], utente)

    def test_download_sicuro(self, client, utente):
        p = _registra(utente)
        a = servizi.aggiungi_allegato(p, _pdf("<script>.pdf"), utente)
        client.force_login(utente)
        r = client.get(reverse("protocollo:allegato", args=[a.pk]))
        assert r.status_code == 200 and r["Content-Type"] == "application/pdf"
        assert r["Content-Disposition"].startswith("attachment")
        assert "sandbox" in r["Content-Security-Policy"]
        assert b"".join(r.streaming_content) == b"%PDF-1.4 prova"


class TestRiservati:
    def test_visibili_solo_con_permesso(self, client_ruolo, utente):
        p = _registra(utente, riservato=True)
        a = servizi.aggiungi_allegato(p, _pdf(), utente)
        c = client_ruolo("Consigliere")
        assert c.get(reverse("protocollo:dettaglio", args=[p.pk])).status_code == 404
        assert c.get(reverse("protocollo:allegato", args=[a.pk])).status_code == 404
        assert "Richiesta patrocinio" not in c.get(reverse("protocollo:elenco")).content.decode()
        c.logout()
        s = client_ruolo("Segretario", username="segretario")
        assert s.get(reverse("protocollo:dettaglio", args=[p.pk])).status_code == 200
        assert EventoAudit.objects.filter(azione="consultazione", oggetto_id=str(p.pk)).exists()


class TestRegistroGiornaliero:
    def test_generazione_unica_con_impronta(self, utente):
        p = _registra(utente)
        ieri = timezone.localdate() - timedelta(days=1)
        Protocollo.objects.filter(pk=p.pk).update(registrato_il=timezone.now() - timedelta(days=1))
        with pytest.raises(OperazioneNonValida):
            servizi.genera_registro_giornaliero(timezone.localdate())
        r, creato = servizi.genera_registro_giornaliero(ieri)
        assert creato and r.registrazioni == 1 and r.primo_numero == p.segnatura
        with r.file.open("rb") as f:
            dati = f.read()
        assert dati.startswith(b"%PDF") and hashlib.sha256(dati).hexdigest() == r.impronta
        assert servizi.genera_registro_giornaliero(ieri) == (r, False)

    def test_comando_genera_i_mancanti(self, utente):
        p = _registra(utente)
        Protocollo.objects.filter(pk=p.pk).update(registrato_il=timezone.now() - timedelta(days=3))
        call_command("registro_giornaliero")
        assert RegistroGiornaliero.objects.count() == 3  # tre giorni conclusi, anche vuoti
        call_command("registro_giornaliero")
        assert RegistroGiornaliero.objects.count() == 3


def _casella(pec=False, settings=None):
    c = CasellaPosta(nome="Segreteria", pec=pec, server="imap.example.org", utente="u")
    c.save()
    return c


def _email(
    mittente="Mario Rossi <mario@example.org>", oggetto="Domanda", html=False, allegato=True
):
    m = EmailMessage()
    m["From"] = mittente
    m["To"] = "segreteria@example.org"
    m["Subject"] = oggetto
    m["Date"] = "Mon, 02 Nov 2026 10:00:00 +0100"
    m["Message-ID"] = f"<{oggetto}@example.org>"
    if html:
        m.set_content("<p>Testo <b>in HTML</b><script>alert(1)</script></p>", subtype="html")
    else:
        m.set_content("Buongiorno,\nallego la domanda.")
    if allegato:
        m.add_attachment(
            b"%PDF-1.4 domanda", maintype="application", subtype="pdf", filename="domanda.pdf"
        )
    return m


class TestPosta:
    def test_salvataggio_e_duplicati(self):
        casella = _casella()
        grezzo = _email().as_bytes()
        m = posta.salva_messaggio(casella, grezzo)
        assert m.mittente_email == "mario@example.org" and "allego la domanda" in m.testo
        assert [a["nome"] for a in m.allegati] == ["domanda.pdf"]
        assert posta.salva_messaggio(casella, grezzo) is None

    def test_html_ridotto_a_testo(self):
        m = posta.salva_messaggio(_casella(), _email(html=True, allegato=False).as_bytes())
        assert "<" not in m.testo and "Testo in HTML" in m.testo

    def test_pec_usa_il_messaggio_originale(self):
        originale = _email(mittente="Comune <protocollo@pec.comune.example.it>", oggetto="Nota")
        busta = EmailMessage()
        busta["From"] = (
            "Per conto di: protocollo@pec.comune.example.it <posta-certificata@pec.example>"
        )
        busta["Subject"] = "POSTA CERTIFICATA: Nota"
        busta["Message-ID"] = "<busta@pec.example>"
        busta.set_content("Messaggio di posta certificata")
        busta.add_attachment(
            b"<daticert/>", maintype="application", subtype="xml", filename="daticert.xml"
        )
        busta.add_attachment(originale)
        busta.get_payload()[-1].set_param("filename", "postacert.eml", header="Content-Disposition")
        m = posta.salva_messaggio(_casella(pec=True), busta.as_bytes())
        assert m.mittente_email == "protocollo@pec.comune.example.it" and m.oggetto == "Nota"
        assert [a["nome"] for a in m.allegati] == ["domanda.pdf"]

    def test_protocollazione(self, utente, comune):
        casella = _casella()
        m = posta.salva_messaggio(
            casella, _email(mittente=f"Comune <{comune.pec}>", oggetto="Invito").as_bytes()
        )
        p = servizi.protocolla_messaggio(m, utente, oggetto="Invito alla cerimonia")
        m.refresh_from_db()
        assert m.stato == "protocollato" and m.protocollo == p
        assert p.corrispondenti.get().soggetto == comune and p.direzione == "entrata"
        assert sorted(a.nome for a in p.allegati.all()) == ["domanda.pdf", "messaggio.eml"]
        with pytest.raises(OperazioneNonValida):
            servizi.protocolla_messaggio(m, utente, oggetto="di nuovo")

    def test_scarto_con_motivo(self, utente):
        m = posta.salva_messaggio(_casella(), _email().as_bytes())
        with pytest.raises(OperazioneNonValida):
            servizi.scarta_messaggio(m, utente, " ")
        servizi.scarta_messaggio(m, utente, "pubblicità")
        assert MessaggioRicevuto.objects.get().stato == "scartato"

    def test_scaricamento_imap(self, monkeypatch):
        casella = _casella()
        messaggi = {b"1": _email(oggetto="Uno").as_bytes(), b"2": _email(oggetto="Due").as_bytes()}

        class ImapFinto:
            def select(self, cartella, readonly):
                assert readonly is True  # mai modificare la casella
                return "OK", [b"2"]

            def uid(self, comando, *argomenti):
                if comando == "SEARCH":
                    return "OK", [b"1 2"]
                uid, cosa = argomenti
                if "SIZE" in cosa:
                    return "OK", [f"1 (UID {uid.decode()} RFC822.SIZE 1000)".encode()]
                assert "PEEK" in cosa
                return "OK", [(b"1", messaggi[uid])]

            def logout(self):
                pass

        monkeypatch.setattr(posta, "_connetti", lambda c: ImapFinto())
        assert posta.scarica_casella(casella) == 2
        assert posta.scarica_casella(casella) == 0


class TestCifratura:
    def test_password_cifrata(self, settings):
        settings.CHIAVE_CIFRATURA = nuova_chiave()
        dati = {"nome": "PEC", "server": "imap.example.org", "porta": 993, "ssl": "on",
                "utente": "u", "cartella": "INBOX", "giorni": 30, "attiva": "on",
                "nuova_password": "segretissima"}  # fmt: skip
        form = CasellaForm(dati)
        assert form.is_valid(), form.errors
        c = form.save()
        assert "segretissima" not in c.password_cifrata and c.password() == "segretissima"
        # modifica senza password: resta quella salvata
        form = CasellaForm({**dati, "nuova_password": "", "nome": "PEC 2"}, instance=c)
        assert form.is_valid() and form.save().password() == "segretissima"

    def test_senza_chiave_non_si_salva(self, settings):
        settings.CHIAVE_CIFRATURA = ""
        form = CasellaForm({"nome": "x", "server": "s", "porta": 993, "utente": "u",
                            "cartella": "INBOX", "giorni": 1, "nuova_password": "p"})  # fmt: skip
        assert not form.is_valid()


class TestViste:
    def test_registrazione_da_interfaccia(self, client, utente, comune):
        client.force_login(utente)
        r = client.post(
            reverse("protocollo:nuovo"),
            {
                "direzione": "entrata",
                "mezzo": "pec",
                "oggetto": "  Invito   alla cerimonia ",
                "mittenti": [comune.pk],
                "mittenti_altri": "Prefettura <prefettura@example.org>\nCarabinieri",
                "allegati": [_pdf("invito.pdf"), _pdf("programma.pdf", b"%PDF-1.4 b")],
            },
        )
        p = Protocollo.objects.get()
        assert r.status_code == 302 and p.oggetto == "Invito alla cerimonia"
        assert [c.descrizione for c in p.corrispondenti.all()] == [
            "Comune di Avigliano", "Prefettura", "Carabinieri",
        ]  # fmt: skip
        assert p.allegati.get(principale=True).nome == "invito.pdf"

    def test_modifica_solo_dati_accessori(self, client, crea_utente, utente):
        p = _registra(utente)
        segretario = crea_utente("segr", ruoli=["Segretario"])
        client.force_login(segretario)
        client.post(
            reverse("protocollo:modifica", args=[p.pk]),
            {"oggetto": "cambiato", "note": "nota", "riservato": "on"},
        )
        p.refresh_from_db()
        assert p.oggetto == "Richiesta patrocinio" and p.note == "nota" and p.riservato

    def test_pagine(self, client, utente, comune, settings):
        settings.CHIAVE_CIFRATURA = nuova_chiave()
        p = _registra(utente, soggetto=comune)
        m = posta.salva_messaggio(_casella(), _email().as_bytes())
        admin = type(utente).objects.create_superuser("root", "r@example.org", "x-Password-123")
        client.force_login(admin)
        for url in [
            reverse("protocollo:elenco"),
            reverse("protocollo:elenco") + "?q=patrocinio&direzione=entrata",
            reverse("protocollo:nuovo") + "?direzione=uscita",
            reverse("protocollo:nuovo") + f"?risposta={p.pk}",
            reverse("protocollo:dettaglio", args=[p.pk]),
            reverse("protocollo:modifica", args=[p.pk]),
            reverse("protocollo:registri"),
            reverse("protocollo:posta"),
            reverse("protocollo:messaggio", args=[m.pk]),
            reverse("protocollo:caselle"),
            reverse("protocollo:casella_nuova"),
            reverse("protocollo:classificazioni"),
            reverse("anagrafica:dettaglio", args=[comune.pk]),
            reverse("core:cruscotto"),
        ]:
            assert client.get(url).status_code == 200, url
        r = client.get(reverse("protocollo:ricevuta", args=[p.pk]))
        assert r.content.startswith(b"%PDF")
        r = client.get(
            reverse("protocollo:cerca_soggetti"),
            {"campo": "mittenti", "cerca_mittenti": "avigl"},
            HTTP_HX_REQUEST="true",
        )
        assert "Comune di Avigliano" in r.content.decode()
        r = client.get(reverse("protocollo:esporta"))
        assert "Richiesta patrocinio" in r.content.decode("utf-8-sig")

    def test_permessi(self, client_ruolo, utente):
        p = _registra(utente)
        c = client_ruolo("Consigliere")
        assert c.get(reverse("protocollo:elenco")).status_code == 200
        assert c.get(reverse("protocollo:nuovo")).status_code == 403
        assert c.get(reverse("protocollo:posta")).status_code == 403
        assert (
            c.post(reverse("protocollo:annulla", args=[p.pk]), {"motivo": "prova"}).status_code
            == 403
        )
        c.logout()
        a = client_ruolo("Addetto protocollo", username="addetto2")
        r = a.post(reverse("protocollo:annulla", args=[p.pk]), {"motivo": "motivo valido"})
        assert r.status_code == 403 and not Protocollo.objects.get().annullato
