# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test dell'area personale: collegamento monouso, sessione, dati e ricevute solo propri, eventi, richieste
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import re
import time
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core import mail, signing
from django.urls import reverse
from django.utils import timezone

from apps.anagrafica.models import Soggetto
from apps.area import servizi, views
from apps.area.models import RichiestaArea
from apps.core.models import Organizzazione
from apps.eventi.models import Evento
from apps.soci import servizi as soci
from apps.soci.models import TipologiaSocio

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def ambiente(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    settings.URL_PUBBLICO = "https://gestione.example.it"
    settings.MAILERS = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}
    Organizzazione.objects.update_or_create(pk=1, defaults={
        "denominazione": "ANCR Avigliano", "invio_email": True, "area_soci": True})  # fmt: skip


@pytest.fixture
def socio(crea_utente):
    u = crea_utente("segr", ruoli=["Segretario"])
    tipo = TipologiaSocio.objects.get(nome="Ordinario")
    s = soci.ammetti_socio(Soggetto.objects.create(cognome="Rossi", nome="Mario",
                                                   email="mario@example.org"), tipo, u)  # fmt: skip
    t = soci.rilascia_tessera(s, date.today().year, u, importo=Decimal("20"))
    soci.registra_pagamento(t, u, pagata_il=date.today(), metodo="contanti")
    return s


def _modulo(client):
    return {"token": signing.dumps(time.time() - 10, salt=views.SALE_MODULO)}


def _entra(client, email="mario@example.org"):
    client.post(reverse("area:accesso"), {"email": email, **_modulo(client)})
    (link,) = re.findall(r"https://gestione\.example\.it(/area/entra/\S+/)", mail.outbox[-1].body)
    return link


def test_collegamento_monouso_e_area(client, socio):
    r = client.post(reverse("area:accesso"), {"email": "mario@example.org", **_modulo(client)})
    assert r.status_code == 302 and len(mail.outbox) == 1
    assert "30 minuti" in mail.outbox[0].body
    link = re.findall(r"https://gestione\.example\.it(/area/entra/\S+/)", mail.outbox[0].body)[0]
    r = client.get(link, follow=True)
    pagina = r.content.decode()
    assert "Ciao Mario" in pagina and f"n. {socio.numero}" in pagina and "Ricevuta" in pagina
    client.post(reverse("area:esci"))
    r = client.get(link, follow=True)  # usato: non vale più
    assert "non è valido" in r.content.decode()
    assert client.get(reverse("area:area")).status_code == 302


def test_email_sconosciuta_stessa_risposta(client, socio):
    r = client.post(reverse("area:accesso"), {"email": "altro@example.org", **_modulo(client)})
    assert r.status_code == 302 and r["Location"] == reverse("area:inviato") and not mail.outbox


def test_collegamento_scaduto(client, socio, monkeypatch):
    link = _entra(client)
    monkeypatch.setattr(servizi, "VALIDITA", -1)
    assert "non è valido" in client.get(link, follow=True).content.decode()


def test_ricevute_solo_proprie(client, socio, crea_utente):
    u = crea_utente("altro_segr", ruoli=["Segretario"])
    tipo = TipologiaSocio.objects.get(nome="Ordinario")
    altro = soci.ammetti_socio(Soggetto.objects.create(cognome="Verdi", email="v@example.org"),
                               tipo, u)  # fmt: skip
    t_altro = soci.rilascia_tessera(altro, date.today().year, u, importo=Decimal("20"))
    soci.registra_pagamento(t_altro, u, pagata_il=date.today(), metodo="contanti")
    client.get(_entra(client))
    mia = socio.tessere.get()
    assert client.get(reverse("area:ricevuta", args=[mia.pk])).content[:4] == b"%PDF"
    assert client.get(reverse("area:ricevuta", args=[t_altro.pk])).status_code == 404


def test_eventi_e_richieste(client, socio):
    evento = Evento.objects.create(titolo="Pranzo sociale", inizio=timezone.now() + timedelta(days=5),
                                   accompagnatori=1)  # fmt: skip
    client.get(_entra(client))
    assert "Pranzo sociale" in client.get(reverse("area:area")).content.decode()
    client.post(reverse("area:aderisci", args=[evento.pk]), {"accompagnatori": "1"})
    a = evento.adesioni.get()
    assert a.soggetto == socio.soggetto and a.origine == "area" and a.accompagnatori == 1
    assert "hai aderito" in client.get(reverse("area:area")).content.decode()
    client.post(reverse("area:rinuncia", args=[evento.pk]))
    a.refresh_from_db()
    assert a.annullata
    client.post(reverse("area:richiesta"), {"testo": "Il mio indirizzo è cambiato: via Roma 2"})
    r = RichiestaArea.objects.get()
    assert r.soggetto == socio.soggetto and r.gestita_il is None


def test_segreteria_vede_e_gestisce(client_ruolo, socio):
    r = servizi.chiedi_correzione(socio.soggetto, "Telefono nuovo 333 1234567")
    c = client_ruolo("Segretario", username="s2")
    assert "Richieste dall'area soci" in c.get("/").content.decode()
    assert "Telefono nuovo" in c.get(socio.soggetto.get_absolute_url()).content.decode()
    c.post(reverse("area:gestita", args=[r.pk]))
    r.refresh_from_db()
    assert r.gestita_il is not None


def test_area_spenta_e_invio_spento(client, socio):
    Organizzazione.objects.update(invio_email=False)
    client.post(reverse("area:accesso"), {"email": "mario@example.org", **_modulo(client)})
    assert not mail.outbox  # rispetta l'interruttore dell'invio
    Organizzazione.objects.update(area_soci=False)
    assert client.get(reverse("area:accesso")).status_code == 404


def test_limite_e_antispam(client, socio):
    r = client.post(reverse("area:accesso"), {"email": "mario@example.org", "sito": "x",
                                               **_modulo(client)})  # fmt: skip
    assert "Invio non accettato" in r.content.decode()
    for _ in range(servizi.LIMITE_PERSONA + 1):
        client.post(reverse("area:accesso"), {"email": "mario@example.org", **_modulo(client)})
    assert len(mail.outbox) == servizi.LIMITE_PERSONA
