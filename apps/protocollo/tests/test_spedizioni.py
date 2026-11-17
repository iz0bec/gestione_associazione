# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test della spedizione per email e PEC dei protocolli in uscita: indirizzi
# *              proposti, coda, invio, interruttore, errori e ricevute PEC agganciate.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from email import message_from_bytes, policy
from email.message import EmailMessage

import pytest
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.anagrafica.models import Soggetto
from apps.core.cifratura import nuova_chiave
from apps.core.models import Organizzazione, ServizioInvio
from apps.protocollo import posta, servizi, spedizioni
from apps.protocollo.models import CasellaPosta, DestinatarioSpedizione, MessaggioRicevuto
from apps.protocollo.servizi import OperazioneNonValida

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def ambiente(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    settings.CHIAVE_CIFRATURA = nuova_chiave()
    settings.MAILERS = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}


@pytest.fixture
def utente(crea_utente):
    return crea_utente("addetto", ruoli=["Addetto protocollo"])


@pytest.fixture
def comune():
    return Soggetto.objects.create(
        tipo="ente",
        denominazione="Comune di Avigliano",
        email="info@comune.example.it",
        pec="protocollo@pec.comune.example.it",
    )


@pytest.fixture
def pec():
    """Servizio di invio PEC (Sistema → Servizi di posta)."""
    s = ServizioInvio(
        nome="PEC sezione", tipo="pec", indirizzo="sez@pec.example.it", server="smtps.pec.example"
    )
    s.imposta_password("segreta")
    s.save()
    return s


@pytest.fixture
def casella():
    """Casella PEC letta via IMAP, in cui arrivano le ricevute."""
    c = CasellaPosta(
        nome="PEC sezione", pec=True, server="imaps.pec.example", utente="sez@pec.example.it"
    )
    c.imposta_password("segreta")
    c.save()
    return c


def _protocollo(utente, *soggetti, direzione="uscita", mezzo="pec"):
    corr = [servizi.corrispondente_da_soggetto(s, "destinatario") for s in soggetti] or [
        {"ruolo": "destinatario", "descrizione": "Mario Rossi", "indirizzo": "mario@example.org"}
    ]
    if direzione == "entrata":
        corr = [{**c, "ruolo": "mittente"} for c in corr]
    p = servizi.registra_protocollo(
        {"direzione": direzione, "mezzo": mezzo, "oggetto": "Richiesta patrocinio"}, corr, utente
    )
    servizi.aggiungi_allegato(
        p, SimpleUploadedFile("lettera.pdf", b"%PDF-1.4 lettera"), utente, principale=True
    )
    return p


def _spedisci(p, utente, servizio=None, destinatari=None, testo="Si trasmette la lettera."):
    destinatari = destinatari or [
        (r["corrispondente"], r["nome"], r["indirizzo"])
        for r in spedizioni.indirizzi_proposti(p, pec=bool(servizio and servizio.pec))
    ]
    return spedizioni.prepara_spedizione(
        p, utente, servizio=servizio, destinatari=destinatari, testo=testo,
        allegati=p.allegati.all(),
    )  # fmt: skip


class TestPreparazione:
    def test_indirizzi_per_canale(self, utente, comune):
        p = _protocollo(utente, comune)
        assert spedizioni.indirizzi_proposti(p, pec=True)[0]["indirizzo"] == comune.pec
        assert spedizioni.indirizzi_proposti(p, pec=False)[0]["indirizzo"] == comune.email

    def test_solo_uscita_non_annullati(self, utente, comune):
        with pytest.raises(OperazioneNonValida, match="uscita"):
            _spedisci(_protocollo(utente, comune, direzione="entrata"), utente)
        p = _protocollo(utente, comune)
        servizi.annulla_protocollo(p, utente, "errore di oggetto")
        with pytest.raises(OperazioneNonValida, match="annullato"):
            _spedisci(p, utente)

    def test_indirizzo_non_valido_e_permesso(self, utente, comune, crea_utente):
        p = _protocollo(utente, comune)
        with pytest.raises(OperazioneNonValida, match="non valido"):
            _spedisci(p, utente, destinatari=[(None, "Ente", "non-un-indirizzo")])
        lettore = crea_utente("lettore", ruoli=["Revisore"])
        with pytest.raises(OperazioneNonValida, match="permesso"):
            _spedisci(p, lettore)

    def test_limite_dimensione(self, utente, comune, settings):
        settings.PROTOCOLLO_SPEDIZIONE_MAX_MB = 0
        with pytest.raises(OperazioneNonValida, match="MB"):
            _spedisci(_protocollo(utente, comune), utente)

    def test_servizio_disattivato_rifiutato(self, utente, comune, pec):
        pec.attivo = False
        pec.save()
        with pytest.raises(OperazioneNonValida, match="disattivato"):
            _spedisci(_protocollo(utente, comune), utente, servizio=pec)

    def test_server_generale_registrato(self, utente, comune, pec):
        pec.tipo, pec.generale = "email", True
        pec.save()
        s = _spedisci(_protocollo(utente, comune, mezzo="email"), utente)
        assert s.servizio == pec and s.mittente == "sez@pec.example.it" and s.canale == "email"


class TestInvio:
    def test_email_dal_server_generale(self, utente, comune):
        p = _protocollo(utente, comune, mezzo="email")
        s = _spedisci(p, utente)
        assert spedizioni.spedisci(s) == (1, 0)
        (m,) = mail.outbox
        assert m.to == [f"Comune di Avigliano <{comune.email}>"]
        assert m.subject.startswith(f"Prot. n. {p.segnatura} del ")
        assert [a[0] for a in m.attachments] == ["lettera.pdf"]
        d = s.destinatari.get()
        assert d.stato == "inviato" and d.message_id == m.extra_headers["Message-ID"]
        assert s.canale == "email" and s.servizio is None
        assert s.mittente == "noreply@localhost" and m.reply_to == []

    def test_pec_dal_servizio(self, utente, comune, pec, monkeypatch):
        usate = []
        monkeypatch.setattr(
            spedizioni, "_connessione", lambda c: usate.append(c) or mail.mailers.default
        )
        s = _spedisci(_protocollo(utente, comune), utente, servizio=pec)
        assert spedizioni.spedisci() == (1, 0)
        assert usate == [pec] and s.canale == "pec"
        assert "sez@pec.example.it" in mail.outbox[0].from_email
        assert mail.outbox[0].to == [f"Comune di Avigliano <{comune.pec}>"]

    def test_interruttore_spento_lascia_in_coda(self, utente, comune):
        Organizzazione.objects.filter(pk=1).update(invio_email=False)
        s = _spedisci(_protocollo(utente, comune), utente)
        assert spedizioni.spedisci() == (0, 0) and not mail.outbox
        assert s.destinatari.get().stato == "in_attesa"

    def test_errori_ripetuti_e_riprova(self, utente, comune, monkeypatch):
        class Guasto:
            def send_messages(self, messaggi):
                raise OSError("server irraggiungibile")

            def close(self):
                pass

        monkeypatch.setattr(spedizioni, "_connessione", lambda c: Guasto())
        s = _spedisci(_protocollo(utente, comune), utente)
        for _ in range(spedizioni.MAX_TENTATIVI):
            assert spedizioni.spedisci() == (0, 1)
        d = s.destinatari.get()
        assert d.stato == "errore" and "irraggiungibile" in d.dettaglio
        monkeypatch.undo()
        assert spedizioni.riprova(s, utente) == 1
        assert spedizioni.spedisci() == (1, 0)

    def test_comando_invia_coda(self, utente, comune):
        from django.core.management import call_command

        _spedisci(_protocollo(utente, comune), utente)
        call_command("invia_coda")
        assert len(mail.outbox) == 1


def _ricevuta(tipo, riferimento, msgid):
    m = EmailMessage()
    m["From"] = "posta-certificata@pec.example"
    m["Subject"] = f"{tipo.upper()}: Prot. n. ..."
    m["Message-ID"] = msgid
    m["X-Ricevuta"] = tipo
    m["X-Riferimento-Message-ID"] = riferimento
    m.set_content("Ricevuta di posta certificata")
    m.add_attachment(b"<daticert/>", maintype="application", subtype="xml", filename="daticert.xml")
    return m.as_bytes()


class TestRicevute:
    def test_accettazione_e_consegna_agganciate(self, utente, comune, pec, casella):
        p = _protocollo(utente, comune)
        s = _spedisci(p, utente, servizio=pec)
        spedizioni.spedisci()
        d = s.destinatari.get()
        consegna = posta.salva_messaggio(
            casella, _ricevuta("avvenuta-consegna", d.message_id, "<c@pec.example>")
        )
        # l'accettazione arrivata dopo non fa tornare indietro l'esito
        posta.salva_messaggio(casella, _ricevuta("accettazione", d.message_id, "<a@pec.example>"))
        d.refresh_from_db()
        assert d.stato == "consegnato"
        assert consegna.stato == "protocollato" and consegna.protocollo == p
        nomi = sorted(a.nome for a in p.allegati.all())
        assert nomi == [
            "lettera.pdf",
            f"ricevuta accettazione - {comune.pec}.eml",
            f"ricevuta avvenuta-consegna - {comune.pec}.eml",
        ]
        assert not MessaggioRicevuto.objects.da_esaminare().exists()

    def test_mancata_consegna(self, utente, comune, pec, casella):
        s = _spedisci(_protocollo(utente, comune), utente, servizio=pec)
        spedizioni.spedisci()
        d = s.destinatari.get()
        posta.salva_messaggio(
            casella, _ricevuta("errore-consegna", d.message_id, "<e@pec.example>")
        )
        d.refresh_from_db()
        assert d.stato == DestinatarioSpedizione.Stato.NON_CONSEGNATO

    def test_ricevuta_estranea_resta_da_esaminare(self, casella):
        m = posta.salva_messaggio(
            casella, _ricevuta("accettazione", "<altro@x>", "<r@pec.example>")
        )
        assert m.stato == "nuovo" and m.protocollo is None

    def test_casella_non_pec_ignora_le_intestazioni(self, utente, comune, pec, casella):
        s = _spedisci(_protocollo(utente, comune), utente, servizio=pec)
        spedizioni.spedisci()
        casella.pec = False
        casella.save()
        d = s.destinatari.get()
        m = posta.salva_messaggio(
            casella, _ricevuta("accettazione", d.message_id, "<n@pec.example>")
        )
        assert m.stato == "nuovo"


class TestViste:
    def test_modulo_e_spedizione(self, client_ruolo, comune, pec):
        client = client_ruolo("Addetto protocollo")
        p = _protocollo(client.utente, comune)
        url = reverse("protocollo:spedisci", args=[p.pk])
        r = client.get(url)
        assert r.status_code == 200
        assert r.context["form"]["da"].initial == str(pec.pk)  # protocollo per PEC
        assert comune.pec in r.content.decode()
        r = client.get(url, {"da": ""})  # server generale: indirizzo email
        assert comune.email in r.content.decode()
        allegato = p.allegati.get()
        r = client.post(url, {
            "da": "", "testo": "Si trasmette.", "documenti": [allegato.pk],
            "dest_0": "on", "indirizzo_0": comune.email,
        })  # fmt: skip
        assert r.status_code == 302
        assert len(mail.outbox) == 1
        r = client.get(p.get_absolute_url())
        assert "Spedizioni" in r.content.decode() and "Inviato" in r.content.decode()

    def test_destinatario_scelto_senza_indirizzo(self, client_ruolo):
        client = client_ruolo("Addetto protocollo")
        p = _protocollo(client.utente)
        r = client.post(reverse("protocollo:spedisci", args=[p.pk]), {
            "da": "", "testo": "x", "dest_0": "on", "indirizzo_0": "",
        })  # fmt: skip
        assert r.status_code == 200 and not mail.outbox

    def test_senza_permesso(self, client_ruolo, crea_utente):
        p = _protocollo(crea_utente("autore", ruoli=["Addetto protocollo"]))
        client = client_ruolo("Revisore")
        assert client.get(reverse("protocollo:spedisci", args=[p.pk])).status_code == 403

    def test_entrata_rimanda_alla_scheda(self, client_ruolo, comune):
        client = client_ruolo("Addetto protocollo")
        p = _protocollo(client.utente, comune, direzione="entrata")
        assert client.get(reverse("protocollo:spedisci", args=[p.pk])).status_code == 302


def test_messaggio_con_message_id_del_dominio(utente, comune, pec):
    s = _spedisci(_protocollo(utente, comune), utente, servizio=pec)
    email, message_id = spedizioni.messaggio(s, s.destinatari.get())
    grezzo = message_from_bytes(email.message().as_bytes(), policy=policy.default)
    assert message_id.endswith("@pec.example.it>") and grezzo["Message-ID"] == message_id
    assert grezzo["X-Gestione-Protocollo"] == s.protocollo.segnatura
