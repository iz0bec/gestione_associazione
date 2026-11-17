# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test delle comunicazioni anche per SMS (Skebby, Aruba, Twilio) e su WhatsApp
# *              Business: numeri, testo breve, richieste ai fornitori (simulate), coda, pagine.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.anagrafica.models import Soggetto
from apps.comunicazioni import messaggi, servizi
from apps.comunicazioni.models import ConsegnaMessaggio, Finalita
from apps.core.cifratura import nuova_chiave
from apps.core.models import Organizzazione, ServizioMessaggi

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def ambiente(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    settings.CHIAVE_CIFRATURA = nuova_chiave()
    settings.MAILERS = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}
    Organizzazione.objects.update_or_create(
        pk=1, defaults={"denominazione": "ANCR Avigliano", "invio_email": True}
    )


class Fornitore:
    """Al posto di _http: registra le richieste e risponde come il fornitore."""

    def __init__(self):
        self.richieste = []
        self.guasto = None

    def __call__(self, metodo, url, *, json_dati=None, form=None, intestazioni=None, utente=None):
        self.richieste.append({"metodo": metodo, "url": url, "json": json_dati, "form": form,
                               "intestazioni": intestazioni or {}, "utente": utente})  # fmt: skip
        if self.guasto:
            return 400, {"error": {"message": self.guasto}}
        if url.endswith("/login?username=utente&password=segreta"):
            return 200, "UK123;SK456"
        if url.endswith("/status"):
            return 200, {"sms": [{"type": "GP", "quantity": 120}]}
        if url.endswith("/sms"):
            return 201, {"result": "OK", "order_id": "ORD1"}
        if url.endswith("/Messages.json"):
            return 201, {"sid": "SM1"}
        if url.endswith(".json"):
            return 200, {"friendly_name": "ANCR", "status": "active"}
        if url.endswith("/messages"):
            return 200, {"messages": [{"id": "wamid.1"}]}
        if "fields=" in url:
            return 200, {"verified_name": "ANCR", "display_phone_number": "+39 333 000"}
        return 404, "non trovato"


@pytest.fixture
def fornitore(monkeypatch):
    finto = Fornitore()
    monkeypatch.setattr(messaggi, "_http", finto)
    return finto


def _servizio(tipo, **extra):
    s = ServizioMessaggi(nome=tipo, tipo=tipo, account="utente", attivo=True, **extra)
    s.imposta_segreto("segreta")
    s.save()
    return s


@pytest.fixture
def utente(crea_utente):
    return crea_utente("segr", ruoli=["Segretario"])


@pytest.fixture
def persone():
    return {
        "mario": Soggetto.objects.create(cognome="Rossi", nome="Mario", email="m@example.org",
                                         cellulare="333 123 4567",
                                         whatsapp_consenso_il=timezone.now()),
        "anna": Soggetto.objects.create(cognome="Verdi", nome="Anna", cellulare="+39 340-1112223"),
        "senza": Soggetto.objects.create(cognome="Bianchi", nome="Luigi", email="l@example.org"),
    }  # fmt: skip


def _crea(utente, soggetti, **extra):
    return servizi.crea_invio(utente, oggetto="Assemblea", corpo="Testo lungo dell'email.",
                              finalita=Finalita.ISTITUZIONALE, soggetti=soggetti, **extra)  # fmt: skip


@pytest.mark.parametrize("numero,atteso", [
    ("333 123 4567", "+393331234567"), ("+39 340-111.2223", "+393401112223"),
    ("0039 3331234567", "+393331234567"), ("(+41) 79 123 45 67", "+41791234567"),
    ("", ""), ("12", ""), ("abc", ""),
])  # fmt: skip
def test_numero_e164(numero, atteso):
    assert messaggi.numero_e164(numero) == atteso


class TestPreparazione:
    def test_consegne_per_canale(self, utente, persone):
        _servizio("skebby")
        _servizio("whatsapp", modello="comunicazione")
        invio = _crea(utente, persone.values(), sms=True, whatsapp=True,
                      testo_breve="{{ saluto }} {{ nome }}, assemblea il 12/12")  # fmt: skip
        consegne = {(c.destinatario.nome, c.canale): c.numero
                    for c in ConsegnaMessaggio.objects.select_related("destinatario")}  # fmt: skip
        assert consegne == {
            ("Rossi Mario", "sms"): "+393331234567",
            ("Rossi Mario", "whatsapp"): "+393331234567",  # ha dato il consenso
            ("Verdi Anna", "sms"): "+393401112223",  # senza email: solo SMS
        }
        servizi.conferma(invio, utente)

    def test_senza_servizio_attivo_ignorato(self, utente, persone):
        invio = _crea(utente, [persone["mario"]], sms=True)
        assert not invio.sms and not ConsegnaMessaggio.objects.exists()

    def test_solo_sms_si_conferma(self, utente, persone):
        _servizio("twilio", mittente="+15550001111")
        invio = servizi.conferma(_crea(utente, [persone["anna"]], sms=True), utente)
        assert invio.stato == "in_coda"

    def test_annullamento_toglie_le_consegne(self, utente, persone):
        _servizio("skebby")
        invio = _crea(utente, [persone["mario"]], sms=True)
        servizi.annulla(invio, utente)
        assert not ConsegnaMessaggio.objects.exists()


class TestFornitori:
    def test_skebby(self, utente, persone, fornitore):
        _servizio("skebby", mittente="ANCR")
        invio = servizi.conferma(_crea(utente, [persone["anna"]], sms=True,
                                       testo_breve="Ciao {{ nome }}"), utente)  # fmt: skip
        assert servizi.elabora_coda() == (1, 0)
        login, invia = fornitore.richieste
        assert login["url"].startswith("https://api.skebby.it/API/v1.0/REST/login?")
        assert invia["intestazioni"] == {"user_key": "UK123", "Session_key": "SK456"}
        assert invia["json"] == {"message_type": "GP", "message": "Ciao Anna - ANCR Avigliano",
                                 "recipient": ["+393401112223"], "returnCredits": False,
                                 "sender": "ANCR"}  # fmt: skip
        c = ConsegnaMessaggio.objects.get()
        assert (c.stato, c.riferimento) == ("inviato", "ORD1")
        invio.refresh_from_db()
        assert invio.stato == "inviato"

    def test_aruba_stessa_api_altro_indirizzo(self, fornitore):
        s = _servizio("aruba", tipo_messaggio="N")
        assert "credito SMS GP: 120" in messaggi.verifica(s)
        assert fornitore.richieste[0]["url"].startswith("https://smspanel.aruba.it/API/v1.0/REST/")

    def test_twilio(self, fornitore):
        s = _servizio("twilio", mittente="MGabc")
        assert "ANCR" in messaggi.verifica(s)
        assert messaggi.fornitore(s).invia("+393331234567", "Ciao") == "SM1"
        r = fornitore.richieste[-1]
        assert r["url"] == "https://api.twilio.com/2010-04-01/Accounts/utente/Messages.json"
        assert r["form"] == {"To": "+393331234567", "Body": "Ciao", "MessagingServiceSid": "MGabc"}
        assert r["utente"] == ("utente", "segreta")

    def test_whatsapp_modello(self, fornitore):
        s = _servizio("whatsapp", modello="comunicazione", lingua="it")
        assert "ANCR" in messaggi.verifica(s)
        assert messaggi.fornitore(s).invia("+393331234567", "Riga uno\n\nriga   due") == "wamid.1"
        r = fornitore.richieste[-1]
        assert r["url"] == "https://graph.facebook.com/v21.0/utente/messages"
        assert r["intestazioni"]["Authorization"] == "Bearer segreta"
        assert r["json"]["to"] == "393331234567" and r["json"]["type"] == "template"
        assert r["json"]["template"]["name"] == "comunicazione"
        parametro = r["json"]["template"]["components"][0]["parameters"][0]["text"]
        assert parametro == "Riga uno riga due"  # Meta non accetta a capo nei parametri

    def test_errori_e_tentativi(self, utente, persone, fornitore):
        _servizio("whatsapp", modello="x")
        invio = servizi.conferma(_crea(utente, [persone["mario"]], whatsapp=True), utente)
        fornitore.guasto = "Template name does not exist"
        servizi.elabora_coda()  # email inviata, WhatsApp in errore
        for _ in range(messaggi.MAX_TENTATIVI - 1):
            servizi.elabora_coda()
        c = ConsegnaMessaggio.objects.get()
        assert c.stato == "errore" and "Template name does not exist" in c.errore
        invio.refresh_from_db()
        assert invio.stato == "con_errori"

    def test_solo_https(self):
        with pytest.raises(messaggi.ErroreMessaggi, match="https"):
            messaggi._http("GET", "http://esempio.it")


class TestPagine:
    def test_configurazione(self, client_ruolo, fornitore):
        c = client_ruolo("Amministratore di sistema")
        assert "SMS e WhatsApp" in c.get("/sistema/posta/").content.decode()
        dati = {"nome": "WA", "tipo": "whatsapp", "account": "123", "lingua": "it",
                "nuovo_segreto": "tok"}  # fmt: skip
        r = c.post(reverse("core:messaggi_nuovo"), dati)
        assert "modello" in r.context["form"].errors
        assert (
            c.post(reverse("core:messaggi_nuovo"), {**dati, "modello": "avviso"}).status_code == 302
        )
        s = ServizioMessaggi.objects.get()
        assert s.segreto() == "tok" and not s.attivo
        c.post(reverse("core:messaggi_azione", args=[s.pk, "attivo"]), {"attivo": "on"})
        s.refresh_from_db()
        assert s.attivo
        r = c.post(reverse("core:messaggi_azione", args=[s.pk, "verifica"]), follow=True)
        assert "accesso riuscito" in r.content.decode()
        r = c.post(reverse("core:messaggi_nuovo"), {"nome": "S", "tipo": "skebby",
                   "account": "u", "mittente": "Associazione ANCR", "nuovo_segreto": "p"})  # fmt: skip
        assert "mittente" in r.context["form"].errors  # oltre 11 caratteri
        c.post(reverse("core:messaggi_azione", args=[s.pk, "elimina"]))
        assert not ServizioMessaggi.objects.exists()

    def test_modulo_e_consenso(self, client_ruolo, persone):
        _servizio("skebby")
        _servizio("whatsapp", modello="x")
        c = client_ruolo("Segretario")
        pagina = c.get(reverse("comunicazioni:nuovo")).content.decode()
        assert "Anche per SMS" in pagina and "Anche su WhatsApp" in pagina
        r = c.post(reverse("comunicazioni:nuovo"), {
            "oggetto": "Avviso", "corpo": "Testo", "finalita": "istituzionale",
            "soggetti": [persone["anna"].pk], "sms": "on", "testo_breve": "Ciao {{ ignoto }}",
        })  # fmt: skip
        assert "testo_breve" in r.context["form"].errors
        anna = persone["anna"]
        pagina = c.get(anna.get_absolute_url()).content.decode()
        assert "Nessun consenso per WhatsApp" in pagina
        c.post(reverse("comunicazioni:whatsapp_consenso", args=[anna.pk]), {"consenso": "on"})
        anna.refresh_from_db()
        assert anna.whatsapp_consenso_il is not None
        c.post(reverse("comunicazioni:whatsapp_consenso", args=[anna.pk]), {})
        anna.refresh_from_db()
        assert anna.whatsapp_consenso_il is None
