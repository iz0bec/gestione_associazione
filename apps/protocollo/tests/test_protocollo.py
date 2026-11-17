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
from apps.core.forms import CasellaForm
from apps.core.models import EventoAudit
from apps.protocollo import posta, servizi
from apps.protocollo.forms import CampoSegnatura, leggi_corrispondenti_liberi
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

    def test_pec_firmata_come_aruba(self):
        """Busta reale: multipart/signed → multipart/mixed → postacert.eml (inline)."""
        from email.mime.multipart import MIMEMultipart

        originale = _email(mittente="ancr-fed-pzmt@pec.example.it", oggetto="test")
        misto = EmailMessage()
        misto.set_content("Messaggio di posta certificata")
        misto.add_attachment(originale)
        misto.get_payload()[-1].replace_header("Content-Disposition", "inline")
        misto.get_payload()[-1].set_param("filename", "postacert.eml", header="Content-Disposition")
        firmato = MIMEMultipart("signed", protocol="application/pkcs7-signature")
        firmato["From"] = (
            '"Per conto di: ancr-fed-pzmt@pec.example.it" <posta-certificata@pec.aruba.it>'
        )
        firmato["Reply-To"] = "ancr-fed-pzmt@pec.example.it"
        firmato["X-Trasporto"] = "posta-certificata"
        firmato["Subject"] = "POSTA CERTIFICATA: test"
        firmato["Message-ID"] = "<firmato@pec.example>"
        firmato.attach(misto)
        m = posta.salva_messaggio(_casella(pec=True), firmato.as_bytes())
        assert m.mittente_email == "ancr-fed-pzmt@pec.example.it" and m.oggetto == "test"
        assert "posta-certificata" not in m.mittente

    def test_busta_pec_senza_originale(self):
        busta = EmailMessage()
        busta["From"] = '"Per conto di: sede@pec.example.it" <posta-certificata@pec.aruba.it>'
        busta["X-Trasporto"] = "posta-certificata"
        busta["Message-ID"] = "<solo-busta@pec.example>"
        busta.set_content("Messaggio di posta certificata")
        m = posta.salva_messaggio(_casella(pec=True), busta.as_bytes())
        assert m.mittente == m.mittente_email == "sede@pec.example.it"

    def test_risposta_a_un_messaggio(self, client_ruolo, utente):
        p = _registra(utente)
        p.corrispondenti.update(  # come lo registrava la 1.0.20 da una busta PEC
            indirizzo="sede@pec.example.it",
            descrizione="Per conto di: sede@pec.example.it <sede@pec.example.it>",
        )
        r = client_ruolo("Segretario").get(reverse("protocollo:nuovo") + f"?risposta={p.pk}")
        riga = r.context["form"].initial["destinatari_altri"]
        assert riga == '"Per conto di: sede@pec.example.it" <sede@pec.example.it>'
        letti = leggi_corrispondenti_liberi(riga, "destinatario")
        assert letti[0]["indirizzo"] == "sede@pec.example.it"

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
        assert p.testo and p.testo == m.testo
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
        casella.cartella_processata = ""  # senza cartella: la casella non si modifica
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


class ImapConCartelle:
    """Server IMAP finto con cartelle, UID e capacità scelte."""

    def __init__(self, messaggi, capacita=("IMAP4REV1", "MOVE"), cartelle=("INBOX",), prefisso=""):
        self.prefisso = prefisso
        self.cartelle = {c: {} for c in cartelle}
        self.cartelle["INBOX"] = dict(messaggi)
        self.capacita = capacita
        self.comandi = []
        self.sottoscritte = []
        self.cancellati = set()

    def capability(self):
        return "OK", [" ".join(self.capacita).encode()]

    def namespace(self):
        return "OK", [f'(("{self.prefisso}" ".")) NIL NIL'.encode()]

    def select(self, cartella, readonly):
        self.readonly = readonly
        return "OK", [str(len(self.cartelle["INBOX"])).encode()]

    def status(self, cartella, cosa):
        return ("OK", [b"x"]) if cartella.strip('"') in self.cartelle else ("NO", [b"no"])

    def create(self, cartella):
        nome = cartella.strip('"')
        if not nome.startswith(self.prefisso):
            return "NO", [b"Client tried to access nonexistent namespace."]
        self.cartelle[nome] = {}
        return "OK", [b""]

    def subscribe(self, cartella):
        self.sottoscritte.append(cartella.strip('"'))
        return "OK", [b""]

    def _uids(self, insieme):
        return [u.encode() for u in insieme.split(",")]

    def uid(self, comando, *argomenti):
        self.comandi.append(comando)
        inbox = self.cartelle["INBOX"]
        if comando == "SEARCH":
            return "OK", [b" ".join(inbox)]
        if comando == "FETCH":
            uid, cosa = argomenti
            if "SIZE" in cosa:
                return "OK", [f"1 (UID {uid.decode()} RFC822.SIZE 1000)".encode()]
            return "OK", [(b"1", inbox[uid])]
        assert not self.readonly
        insieme, *resto = argomenti
        if comando == "MOVE":
            for u in self._uids(insieme):
                self.cartelle[resto[0].strip('"')][u] = inbox.pop(u)
        elif comando == "COPY":
            for u in self._uids(insieme):
                self.cartelle[resto[0].strip('"')][u] = inbox[u]
        elif comando == "STORE":
            assert resto == ["+FLAGS.SILENT", r"(\Deleted)"]
            self.cancellati.update(self._uids(insieme))
        elif comando == "EXPUNGE":
            for u in self._uids(insieme):  # solo i messaggi indicati
                assert u in self.cancellati
                inbox.pop(u)
        return "OK", [b""]

    def logout(self):
        pass


class TestCartellaProcessata:
    def _messaggi(self):
        return {b"1": _email(oggetto="Uno").as_bytes(), b"2": _email(oggetto="Due").as_bytes()}

    def test_spostati_con_move_e_cartella_creata(self, monkeypatch):
        casella = _casella()
        assert casella.cartella_processata == "PROCESSATA"
        imap = ImapConCartelle(self._messaggi())
        monkeypatch.setattr(posta, "_connetti", lambda c: imap)
        assert posta.scarica_casella(casella) == 2
        assert imap.cartelle["INBOX"] == {} and set(imap.cartelle["PROCESSATA"]) == {b"1", b"2"}
        assert imap.sottoscritte == ["PROCESSATA"] and "MOVE" in imap.comandi
        assert MessaggioRicevuto.objects.count() == 2

    def test_namespace_del_server(self, monkeypatch):
        """Aruba (Courier): le cartelle stanno sotto «INBOX.»."""
        imap = ImapConCartelle(self._messaggi(), prefisso="INBOX.")
        monkeypatch.setattr(posta, "_connetti", lambda c: imap)
        assert posta.scarica_casella(_casella()) == 2
        assert set(imap.cartelle["INBOX.PROCESSATA"]) == {b"1", b"2"}
        assert imap.sottoscritte == ["INBOX.PROCESSATA"]
        assert "«INBOX.PROCESSATA» (sarà creata" not in posta.verifica_casella(_casella())

    def test_gia_scaricati_spostati_comunque(self, monkeypatch):
        casella = _casella()
        messaggi = self._messaggi()
        posta.salva_messaggio(casella, messaggi[b"1"])
        imap = ImapConCartelle(messaggi, cartelle=("INBOX", "PROCESSATA"))
        monkeypatch.setattr(posta, "_connetti", lambda c: imap)
        assert posta.scarica_casella(casella) == 1
        assert imap.cartelle["INBOX"] == {} and imap.sottoscritte == []

    def test_copia_e_cancella_solo_i_copiati_senza_move(self, monkeypatch):
        imap = ImapConCartelle(self._messaggi(), capacita=("IMAP4REV1", "UIDPLUS"))
        monkeypatch.setattr(posta, "_connetti", lambda c: imap)
        assert posta.scarica_casella(_casella()) == 2
        assert imap.comandi.count("EXPUNGE") == 1 and "MOVE" not in imap.comandi
        assert imap.cartelle["INBOX"] == {} and len(imap.cartelle["PROCESSATA"]) == 2

    def test_server_senza_spostamento(self, monkeypatch):
        imap = ImapConCartelle(self._messaggi(), capacita=("IMAP4REV1",))
        monkeypatch.setattr(posta, "_connetti", lambda c: imap)
        with pytest.raises(posta.ErroreCasella, match="MOVE"):
            posta.scarica_casella(_casella())
        assert len(imap.cartelle["INBOX"]) == 2  # nulla toccato, ma i messaggi sono salvati
        assert MessaggioRicevuto.objects.count() == 2

    def test_errore_a_meta_sposta_quelli_salvati(self, monkeypatch):
        imap = ImapConCartelle(self._messaggi())
        salva = posta.salva_messaggio
        chiamate = []

        def salva_poi_errore(casella, grezzo):
            chiamate.append(1)
            if len(chiamate) == 2:
                raise RuntimeError("disco pieno")
            return salva(casella, grezzo)

        monkeypatch.setattr(posta, "_connetti", lambda c: imap)
        monkeypatch.setattr(posta, "salva_messaggio", salva_poi_errore)
        with pytest.raises(RuntimeError):
            posta.scarica_casella(_casella())
        assert list(imap.cartelle["PROCESSATA"]) == [b"1"] and list(imap.cartelle["INBOX"]) == [
            b"2"
        ]

    def test_verifica_avvisa_della_creazione(self, monkeypatch):
        imap = ImapConCartelle(self._messaggi())
        monkeypatch.setattr(posta, "_connetti", lambda c: imap)
        esito = posta.verifica_casella(_casella())
        assert "sarà creata" in esito and "PROCESSATA" not in imap.cartelle

    def test_modulo_rifiuta_la_stessa_cartella(self, settings):
        settings.CHIAVE_CIFRATURA = nuova_chiave()
        form = CasellaForm({
            "nome": "Email", "server": "imap.example.org", "porta": 993, "ssl": "on",
            "utente": "u", "cartella": "INBOX", "cartella_processata": "inbox", "giorni": 30,
            "nuova_password": "x",
        })  # fmt: skip
        assert not form.is_valid() and "cartella_processata" in form.errors
        form = CasellaForm({**form.data, "cartella_processata": "Già fatta"})
        assert not form.is_valid() and "cartella_processata" in form.errors


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
                "testo": "Gentile presidente,\r\nla invitiamo alla cerimonia.\r\n",
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
        assert p.testo == "Gentile presidente,\nla invitiamo alla cerimonia."
        dettaglio = client.get(p.get_absolute_url())
        assert "la invitiamo alla cerimonia" in dettaglio.text
        elenco = client.get(reverse("protocollo:elenco"), {"q": "invitiamo"})
        assert p.oggetto in elenco.text

    def test_modifica_solo_dati_accessori(self, client, crea_utente, utente):
        p = _registra(utente)
        segretario = crea_utente("segr", ruoli=["Segretario"])
        client.force_login(segretario)
        client.post(
            reverse("protocollo:modifica", args=[p.pk]),
            {"oggetto": "cambiato", "testo": "cambiato", "note": "nota", "riservato": "on"},
        )
        p.refresh_from_db()
        assert (
            p.testo == ""
            and p.oggetto == "Richiesta patrocinio"
            and p.note == "nota"
            and p.riservato
        )

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


class TestAzioniPostaInBlocco:
    def _tre(self):
        c = _casella()
        return [posta.salva_messaggio(c, _email(oggetto=f"Offerta-{i}", allegato=False).as_bytes())
                for i in range(3)]  # fmt: skip

    def test_scarto_e_ripristino(self, client_ruolo):
        from apps.protocollo.models import MessaggioRicevuto

        a, b, c = self._tre()
        client = client_ruolo("Addetto protocollo")
        pagina = client.get("/protocollo/posta/").content.decode()
        assert 'data-seleziona-tutte="messaggi"' in pagina and 'name="messaggi"' in pagina
        r = client.post("/protocollo/posta/azione/",
                        {"azione": "scarta", "messaggi": [a.pk, b.pk], "stato": "nuovo"})  # fmt: skip
        assert r.status_code == 302 and r["Location"].endswith("?stato=nuovo")
        stati = dict(MessaggioRicevuto.objects.values_list("pk", "stato"))
        assert stati == {a.pk: "nuovo", b.pk: "nuovo", c.pk: "nuovo"}  # senza motivo: niente
        r = client.post("/protocollo/posta/azione/", {"azione": "scarta", "motivo": "Pubblicità",
                        "messaggi": [a.pk, b.pk], "stato": "nuovo"}, follow=True)  # fmt: skip
        assert "2 messaggi scartati." in r.content.decode()
        a.refresh_from_db()
        assert a.stato == "scartato" and a.motivo_scarto == "Pubblicità"
        assert a.gestito_da == client.utente
        # già scartato: saltato
        r = client.post("/protocollo/posta/azione/", {"azione": "scarta", "motivo": "x",
                        "messaggi": [a.pk, c.pk], "stato": "nuovo"}, follow=True)  # fmt: skip
        assert "1 messaggi scartati. 1 saltati" in r.content.decode()
        r = client.post("/protocollo/posta/azione/",
                        {"azione": "ripristina", "messaggi": [a.pk], "stato": "scartato"})  # fmt: skip
        a.refresh_from_db()
        assert a.stato == "nuovo" and a.motivo_scarto == "" and a.gestito_da is None
        client.post(f"/protocollo/posta/{b.pk}/ripristina/")
        b.refresh_from_db()
        assert b.stato == "nuovo"

    def test_permessi(self, client_ruolo):
        a, _b, _c = self._tre()
        consigliere = client_ruolo("Consigliere", username="c")
        r = consigliere.post("/protocollo/posta/azione/",
                             {"azione": "scarta", "motivo": "x", "messaggi": [a.pk]})  # fmt: skip
        assert r.status_code == 403
        pagina = client_ruolo("Presidente", username="p").get("/protocollo/posta/").content
        assert b'name="messaggi"' not in pagina  # consulta ma non gestisce la posta


class TestPuliziaPostaScartata:
    def _scartati(self, utente, n=3, motivo="Pubblicità", prefisso="Offerta"):
        c = _casella()
        messaggi = [posta.salva_messaggio(c, _email(oggetto=f"{prefisso}-{i}").as_bytes())
                    for i in range(n)]  # fmt: skip
        for m in messaggi:
            servizi.scarta_messaggio(m, utente, motivo)
        return [type(m).objects.get(pk=m.pk) for m in messaggi]

    def test_contenuto_eliminato_e_riga_conservata(
        self, crea_utente, django_capture_on_commit_callbacks
    ):
        from django.core.files.storage import default_storage

        resp = crea_utente("segr", ruoli=["Segretario"])
        (m, *_altri) = self._scartati(resp)
        file = [m.file_eml.name, *(a["percorso"] for a in m.allegati)]
        assert all(default_storage.exists(f) for f in file) and m.allegati
        with django_capture_on_commit_callbacks(execute=True):
            servizi.ripulisci_messaggio(m, resp)
        m.refresh_from_db()
        assert m.ripulito_il and not m.testo and m.allegati == [] and not m.file_eml
        assert not any(default_storage.exists(f) for f in file)
        evento = EventoAudit.objects.filter(azione="eliminazione").latest("pk")
        assert evento.dettagli["motivo_scarto"] == "Pubblicità"
        assert evento.dettagli["allegati"] == ["domanda.pdf"]
        # la riga resta: lo stesso messaggio non viene riscaricato
        assert posta.salva_messaggio(m.casella, _email(oggetto="Offerta-0").as_bytes()) is None
        with pytest.raises(OperazioneNonValida):
            servizi.ripristina_messaggio(m, resp)
        with pytest.raises(OperazioneNonValida):
            servizi.ripulisci_messaggio(m, resp)

    def test_solo_scartati_e_solo_con_permesso(self, utente, crea_utente):
        c = _casella()
        nuovo = posta.salva_messaggio(c, _email(oggetto="Nuovo").as_bytes())
        with pytest.raises(OperazioneNonValida, match="permesso"):
            servizi.ripulisci_messaggio(nuovo, utente)  # addetto: non può
        with pytest.raises(OperazioneNonValida, match="scartati"):
            servizi.ripulisci_messaggio(nuovo, crea_utente("segr", ruoli=["Segretario"]))

    def test_pulizia_selettiva_dall_elenco(self, client_ruolo, crea_utente):
        from datetime import timedelta as td

        from apps.protocollo.models import MessaggioRicevuto

        client = client_ruolo("Segretario")
        a, b, c = self._scartati(client.utente)
        (d,) = self._scartati(client.utente, n=1, motivo="Duplicato", prefisso="Copia")
        MessaggioRicevuto.objects.filter(pk=a.pk).update(
            gestito_il=timezone.now() - td(days=90))  # fmt: skip
        pagina = client.get("/protocollo/posta/?stato=scartato").content.decode()
        assert "Elimina definitivamente" in pagina and "Elimina tutti i 4" in pagina
        pagina = client.get("/protocollo/posta/?stato=scartato&motivo=Duplicato").content.decode()
        assert "Elimina tutti i 1 filtrati" in pagina
        # selezionati
        r = client.post("/protocollo/posta/azione/", {"azione": "ripulisci", "messaggi": [b.pk],
                        "stato": "scartato"}, follow=True)  # fmt: skip
        assert "1 messaggi scartati eliminati definitivamente." in r.content.decode()
        # tutti quelli filtrati: scartati prima di 30 giorni fa con motivo «Pubblicità»
        prima = (timezone.localdate() - td(days=30)).isoformat()
        client.post("/protocollo/posta/azione/", {"azione": "ripulisci_filtrati",
                    "motivo": "Pubblicità", "prima_del": prima, "stato": "scartato"})  # fmt: skip
        ripuliti = set(
            MessaggioRicevuto.objects.filter(ripulito_il__isnull=False).values_list("pk", flat=True)
        )
        assert ripuliti == {a.pk, b.pk}
        pagina = client.get("/protocollo/posta/?stato=scartato").content.decode()
        assert "Offerta-2" in pagina and "Offerta-0" not in pagina and "Offerta-1" not in pagina
        assert client.get(f"/protocollo/posta/{a.pk}/").status_code == 404
        # l'addetto non vede i pulsanti e non può eliminare
        addetto = client_ruolo("Addetto protocollo", username="addetto2")
        assert "Elimina definitivamente" not in addetto.get(
            "/protocollo/posta/?stato=scartato").content.decode()  # fmt: skip
        addetto.post("/protocollo/posta/azione/", {"azione": "ripulisci", "messaggi": [c.pk],
                     "stato": "scartato"})  # fmt: skip
        c.refresh_from_db()
        assert c.ripulito_il is None
