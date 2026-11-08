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
