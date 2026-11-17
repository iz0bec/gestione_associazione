# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test degli interruttori, dei servizi di invio (SMTP) e della lettura della posta
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from unittest import mock

import pytest
from django.core import mail
from django.utils import timezone

from apps.anagrafica.models import Soggetto
from apps.comunicazioni import servizi as comunicazioni
from apps.comunicazioni.models import Automazione, PromemoriaRinnovo
from apps.core import invio
from apps.core.cifratura import nuova_chiave
from apps.core.models import EventoAudit, Organizzazione, ServizioInvio

pytestmark = pytest.mark.django_db


def _imposta(**valori):
    Organizzazione.objects.update_or_create(pk=1, defaults=valori)


@pytest.fixture(autouse=True)
def ambiente(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    settings.MAILERS = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}


def test_coda_ferma_e_poi_riparte(crea_utente):
    s = Soggetto.objects.create(cognome="Rossi", nome="Mario", email="r@example.org")
    u = crea_utente("u", ruoli=["Segretario"])
    invio = comunicazioni.crea_invio(u, oggetto="O", corpo="C", finalita="istituzionale",
                                     soggetti=[s])  # fmt: skip
    comunicazioni.conferma(invio, u)
    _imposta(invio_email=False)
    assert comunicazioni.elabora_coda() == (0, 0) and mail.outbox == []
    invio.refresh_from_db()
    assert invio.stato == "in_coda"
    _imposta(invio_email=True)
    assert comunicazioni.elabora_coda() == (1, 0) and len(mail.outbox) == 1


def test_automazioni_non_preparate(crea_utente):
    _imposta(invio_email=False)
    Automazione.objects.update(attiva=True, ora=0)
    PromemoriaRinnovo.objects.filter(pk=1).update(
        attivo=True, ora=0, date_invio=f"{timezone.localdate():%d/%m}"
    )
    assert comunicazioni.auguri_del_giorno() == []
    assert comunicazioni.promemoria_rinnovo() is None


def test_email_dell_accesso_non_spedite(client, crea_utente):
    crea_utente("mario")
    _imposta(invio_email=False)
    client.post("/account/password/reset/", {"email": "mario@example.org"})
    assert mail.outbox == []
    _imposta(invio_email=True)
    client.post("/account/password/reset/", {"email": "mario@example.org"})
    assert len(mail.outbox) == 1


def test_lettura_posta_ferma():
    from apps.protocollo import posta
    from apps.protocollo.models import CasellaPosta

    CasellaPosta.objects.create(nome="PEC", attiva=True)
    with mock.patch.object(posta, "scarica_casella", return_value=3) as scarica:
        _imposta(ricezione_posta=False)
        assert posta.scarica_tutte() == {} and not scarica.called
        _imposta(ricezione_posta=True)
        assert posta.scarica_tutte() == {"PEC": 3}


def test_pagina_solo_amministratore(client_ruolo):
    assert client_ruolo("Segretario", username="s").get("/sistema/posta/").status_code == 403
    c = client_ruolo("Amministratore di sistema")
    pagina = c.get("/sistema/posta/").content.decode()
    assert "Servizi di posta" in pagina and "Messaggi in coda" in pagina
    r = c.post("/sistema/posta/", {"ricezione_posta": "on"})  # invio spento
    org = Organizzazione.corrente()
    assert r.status_code == 302 and not org.invio_email and org.ricezione_posta
    assert "Invio delle email disattivato" in c.get("/comunicazioni/").content.decode()


class _ImapFinto:
    def __init__(self, cartella_ok=True):
        self.cartella_ok, self.uscito = cartella_ok, False

    def select(self, cartella, readonly=False):
        assert readonly  # mai in scrittura
        return ("OK", [b"42"]) if self.cartella_ok else ("NO", [b""])

    def uid(self, comando, *args):
        assert comando == "SEARCH"  # nessun FETCH: niente viene scaricato
        return "OK", [b"1 2 3"]

    def status(self, cartella, cosa):
        return "NO", [b"cartella inesistente"]  # nessuna CREATE: la verifica non modifica nulla

    def capability(self):
        return "OK", [b"IMAP4rev1 MOVE"]

    def logout(self):
        self.uscito = True


def test_verifica_casella(client_ruolo):
    from apps.protocollo import posta
    from apps.protocollo.models import CasellaPosta, MessaggioRicevuto

    _imposta(ricezione_posta=False)  # la verifica funziona anche con la lettura spenta
    casella = CasellaPosta.objects.create(nome="Federazione", server="imaps.example.it",
                                          utente="f@example.it", giorni=30)  # fmt: skip
    c = client_ruolo("Amministratore di sistema")
    finto = _ImapFinto()
    with mock.patch.object(posta, "_connetti", return_value=finto):
        r = c.post(f"/sistema/posta/verifica/{casella.pk}/", follow=True)
    testo = r.content.decode()
    assert "accesso a imaps.example.it riuscito" in testo and "42 messaggi in tutto" in testo
    assert "3 negli ultimi 30 giorni" in testo and finto.uscito
    assert "cartella «PROCESSATA» (sarà creata al primo scaricamento)" in testo
    assert not MessaggioRicevuto.objects.exists()
    with mock.patch.object(posta, "_connetti", return_value=_ImapFinto(cartella_ok=False)):
        testo = c.post(f"/sistema/posta/verifica/{casella.pk}/", follow=True).content.decode()
    assert "non esiste" in testo
    errore = posta.ErroreCasella("Connessione a imaps.example.it non riuscita: password errata")
    with mock.patch.object(posta, "_connetti", side_effect=errore):
        testo = c.post(f"/sistema/posta/verifica/{casella.pk}/", follow=True).content.decode()
    assert "password errata" in testo
    assert client_ruolo("Segretario", username="s").post(
        f"/sistema/posta/verifica/{casella.pk}/").status_code == 403  # fmt: skip


def test_verifica_invio(client_ruolo, settings):
    settings.MAILERS = {"default": {"BACKEND": "django.core.mail.backends.smtp.EmailBackend",
                                    "OPTIONS": {"host": "smtp.example.it", "port": 465}}}  # fmt: skip
    c = client_ruolo("Amministratore di sistema")
    with mock.patch("django.core.mail.backends.smtp.EmailBackend.open") as apri, \
         mock.patch("django.core.mail.backends.smtp.EmailBackend.close"):  # fmt: skip
        testo = c.post("/sistema/posta/verifica-invio/", follow=True).content.decode()
    assert apri.called and "smtp.example.it:465: accesso riuscito" in testo
    with mock.patch("django.core.mail.backends.smtp.EmailBackend.open",
                    side_effect=OSError("rifiutato")):  # fmt: skip
        testo = c.post("/sistema/posta/verifica-invio/", follow=True).content.decode()
    assert "accesso non riuscito" in testo and "rifiutato" in testo
    assert mail.outbox == []


def _servizio(**valori):
    s = ServizioInvio(**{"nome": "Email sezione", "indirizzo": "sez@example.it",
                         "server": "smtps.example.it", **valori})  # fmt: skip
    s.imposta_password("segreta")
    s.save()
    return s


class _SmtpFinto:
    """Al posto di smtplib: registra a quale server ci si collega e cosa si spedisce."""

    ultimo = None

    def __init__(self, host, port, **kwargs):
        self.host, self.port, self.spediti, self.accesso = host, port, [], None
        _SmtpFinto.ultimo = self

    def login(self, utente, password):
        self.accesso = (utente, password)

    def sendmail(self, mittente, destinatari, messaggio):
        self.spediti.append((mittente, destinatari, messaggio))

    def quit(self):
        pass

    def close(self):
        pass


@pytest.fixture
def smtp_finto(settings, monkeypatch):
    settings.CHIAVE_CIFRATURA = nuova_chiave()
    settings.MAILERS = {"default": {"BACKEND": invio.BACKEND, "OPTIONS": {
        "host": "smtp.env.example", "port": 587, "username": "env", "password": "x",
        "use_tls": True}}}  # fmt: skip
    settings.DEFAULT_FROM_EMAIL = "noreply@env.example"
    monkeypatch.setattr("smtplib.SMTP_SSL", _SmtpFinto)
    monkeypatch.setattr("smtplib.SMTP", _SmtpFinto)
    monkeypatch.setattr(_SmtpFinto, "starttls", lambda self, **k: None, raising=False)
    return _SmtpFinto


def test_backend_usa_il_servizio_generale(smtp_finto):
    _imposta(denominazione="ANCR Avigliano")
    mail.EmailMessage("Oggetto", "Testo", to=["a@example.org"]).send()
    assert smtp_finto.ultimo.host == "smtp.env.example"  # senza servizio: il .env
    assert smtp_finto.ultimo.spediti[0][0] == "noreply@env.example"
    _servizio(generale=True, utente="utente-smtp")
    mail.EmailMessage("Oggetto", "Testo", to=["a@example.org"]).send()
    finto = smtp_finto.ultimo
    assert (finto.host, finto.port, finto.accesso) == ("smtps.example.it", 465,
                                                       ("utente-smtp", "segreta"))  # fmt: skip
    mittente, _, grezzo = finto.spediti[0]
    assert mittente == "sez@example.it" and b"ANCR Avigliano <sez@example.it>" in grezzo
    mail.EmailMessage("O", "T", from_email="altro@example.it", to=["a@example.org"]).send()
    assert smtp_finto.ultimo.spediti[0][0] == "altro@example.it"  # mittente esplicito: resta


def test_pagina_e_modulo_dei_servizi(client_ruolo, settings):
    settings.CHIAVE_CIFRATURA = nuova_chiave()
    c = client_ruolo("Amministratore di sistema")
    pagina = c.get("/sistema/posta/").content.decode()
    assert "Servizi di invio" in pagina and "riserva" in pagina
    dati = {"nome": "PEC federazione", "tipo": "pec", "indirizzo": "fed@pec.example.it",
            "server": "smtps.pec.example.it", "porta": 465, "ssl": "on", "attivo": "on",
            "nuova_password": "segreta"}  # fmt: skip
    r = c.post("/sistema/posta/invio/nuovo/", {**dati, "generale": "on"})
    assert "un servizio email" in str(r.context["form"].errors["generale"])
    assert c.post("/sistema/posta/invio/nuovo/", dati).status_code == 302
    s = ServizioInvio.objects.get()
    assert s.password() == "segreta" and s.pec and not s.generale
    evento = EventoAudit.objects.filter(azione="creazione").latest("pk")
    assert "segreta" not in str(evento.dettagli)
    r = c.post(f"/sistema/posta/invio/{s.pk}/", {**dati, "nuova_password": "", "porta": 587})
    s.refresh_from_db()
    assert r.status_code == 302 and s.porta == 587 and s.password() == "segreta"
    assert "PEC federazione" in c.get("/sistema/posta/").content.decode()
    assert client_ruolo("Segretario", username="s").get(
        "/sistema/posta/invio/nuovo/").status_code == 403  # fmt: skip


def test_un_solo_server_generale(settings):
    from apps.core.forms import ServizioInvioForm

    settings.CHIAVE_CIFRATURA = nuova_chiave()
    _servizio(generale=True)
    form = ServizioInvioForm(data={"nome": "Altro", "tipo": "email", "indirizzo": "b@example.it",
                                   "server": "s", "porta": 465, "attivo": "on", "generale": "on",
                                   "nuova_password": "x"})  # fmt: skip
    assert not form.is_valid() and "già" in str(form.errors["generale"])


def test_verifica_ed_eliminazione(client_ruolo, settings, crea_utente):
    from apps.protocollo import servizi as protocollo
    from apps.protocollo import spedizioni

    settings.CHIAVE_CIFRATURA = nuova_chiave()
    c = client_ruolo("Amministratore di sistema")
    s = _servizio()
    with mock.patch("django.core.mail.backends.smtp.EmailBackend.open") as apri, \
         mock.patch("django.core.mail.backends.smtp.EmailBackend.close"):  # fmt: skip
        testo = c.post(f"/sistema/posta/invio/{s.pk}/verifica/", follow=True).content.decode()
    assert apri.called and "smtps.example.it:465 riuscito" in testo
    with mock.patch("django.core.mail.backends.smtp.EmailBackend.open",
                    side_effect=OSError("rifiutato")):  # fmt: skip
        testo = c.post(f"/sistema/posta/invio/{s.pk}/verifica/", follow=True).content.decode()
    assert "non riuscito" in testo and "rifiutato" in testo
    u = crea_utente("addetto", ruoli=["Addetto protocollo"])
    p = protocollo.registra_protocollo(
        {"direzione": "uscita", "mezzo": "email", "oggetto": "Lettera"},
        [{"ruolo": "destinatario", "descrizione": "Ente", "indirizzo": "ente@example.org"}], u,
    )  # fmt: skip
    spedizioni.prepara_spedizione(p, u, servizio=s, destinatari=[(None, "Ente", "ente@example.org")],
                                  testo="T", allegati=[])  # fmt: skip
    testo = c.post(f"/sistema/posta/invio/{s.pk}/elimina/", follow=True).content.decode()
    assert "non si elimina" in testo and ServizioInvio.objects.filter(pk=s.pk).exists()
    nuovo = _servizio(nome="Mai usato")
    c.post(f"/sistema/posta/invio/{nuovo.pk}/elimina/")
    assert not ServizioInvio.objects.filter(pk=nuovo.pk).exists()


def test_migrazione_dal_file_env(settings):
    """Il server SMTP del .env diventa il servizio generale (una volta sola)."""
    import importlib

    from django.apps import apps

    migrazione = importlib.import_module("apps.core.migrations.0012_servizi_invio")
    settings.CHIAVE_CIFRATURA = nuova_chiave()
    settings.MAILERS = {"default": {"BACKEND": invio.BACKEND, "OPTIONS": {
        "host": "smtps.aruba.it", "port": 465, "username": "sez@example.it",
        "password": "segreta", "use_ssl": True}}}  # fmt: skip
    settings.DEFAULT_FROM_EMAIL = "ANCR Sezione <sez@example.it>"
    migrazione.servizio_da_env(apps, None)
    migrazione.servizio_da_env(apps, None)
    s = ServizioInvio.objects.get()
    assert (s.server, s.porta, s.ssl, s.indirizzo, s.nome_mittente, s.utente, s.generale) == (
        "smtps.aruba.it", 465, True, "sez@example.it", "ANCR Sezione", "", True)  # fmt: skip
    assert s.password() == "segreta" and invio.servizio_generale() == s
