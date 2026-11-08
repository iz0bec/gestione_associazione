# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test degli interruttori dell'invio delle email e della lettura della posta
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
from apps.core.models import Organizzazione

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
