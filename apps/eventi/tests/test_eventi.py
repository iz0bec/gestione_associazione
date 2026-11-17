# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test degli eventi: adesioni, posti, scadenze, doppioni, modulo pubblico, pagine, calendario
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.anagrafica.models import Soggetto
from apps.calendario import servizi as calendario
from apps.eventi import forms, servizi
from apps.eventi.models import Adesione, Evento

pytestmark = pytest.mark.django_db
SEG = Adesione.Origine.SEGRETERIA


@pytest.fixture(autouse=True)
def cartella_media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def evento():
    return Evento.objects.create(titolo="Cerimonia del 4 novembre", luogo="Monumento ai caduti",
                                 inizio=timezone.now() + timedelta(days=10), posti=5,
                                 accompagnatori=2, pubblico=True)  # fmt: skip


def test_posti_accompagnatori_e_doppioni(evento):
    mario = Soggetto.objects.create(cognome="Rossi", nome="Mario", email="mario@example.org")
    a = servizi.aderisci(evento, {"cognome": "Rossi", "nome": "Mario", "accompagnatori": 2},
                         origine=SEG)  # fmt: skip
    assert a.soggetto == mario and evento.partecipanti == 3  # riconosciuto per nome e cognome
    with pytest.raises(servizi.OperazioneNonValida, match="già aderito"):
        servizi.aderisci(evento, {"cognome": "X", "email": "MARIO@example.org"}, origine=SEG)
    with pytest.raises(servizi.OperazioneNonValida, match="Al massimo 2"):
        servizi.aderisci(evento, {"cognome": "Verdi", "accompagnatori": 3}, origine=SEG)
    servizi.aderisci(evento, {"cognome": "Verdi", "accompagnatori": 1}, origine=SEG)
    with pytest.raises(servizi.OperazioneNonValida, match="Posti esauriti"):
        servizi.aderisci(evento, {"cognome": "Bianchi"}, origine=SEG)
    servizi.annulla_adesione(a)
    evento.refresh_from_db()
    assert evento.posti_liberi == 3 and evento.si_puo_aderire


def test_chiusura_vale_per_il_pubblico_non_per_la_segreteria(evento):
    evento.chiusura_adesioni = timezone.now() - timedelta(hours=1)
    evento.save()
    with pytest.raises(servizi.OperazioneNonValida, match="chiuse"):
        servizi.aderisci(evento, {"cognome": "Neri"}, origine=Adesione.Origine.PUBBLICO)
    servizi.aderisci(evento, {"cognome": "Neri"}, origine=SEG)  # la segreteria può ancora
    evento.annullato = True
    evento.save()
    with pytest.raises(servizi.OperazioneNonValida, match="annullato"):
        servizi.aderisci(evento, {"cognome": "Gialli"}, origine=SEG)


def test_modulo_pubblico(client, evento, monkeypatch):
    url = reverse("evento_pubblico", args=[evento.token])
    pagina = client.get(url).content.decode()
    assert "Cerimonia del 4 novembre" in pagina and "Aderisco" in pagina
    token = client.get(url).context["form"].initial["token"]
    dati = {"cognome": "Verdi", "nome": "Anna", "email": "anna@example.org", "accompagnatori": 1,
            "token": token}  # fmt: skip
    r = client.post(url, dati)  # troppo rapido
    assert "troppo rapido" in r.content.decode()
    monkeypatch.setattr(forms, "_adesso", lambda: 10**10)
    r = client.post(url, {**dati, "token": forms.signing.dumps(10**10 - 60, salt=forms.SALE)})
    assert r.status_code == 302
    a = evento.adesioni.get()
    assert a.origine == "pubblico" and a.indirizzo_ip and a.accompagnatori == 1
    r = client.post(url, {**dati, "token": forms.signing.dumps(10**10 - 60, salt=forms.SALE),
                          "sito": "spam"})  # fmt: skip
    assert "Invio non accettato" in r.content.decode() and evento.adesioni.count() == 1
    evento.pubblico = False
    evento.save()
    assert client.get(url).status_code == 404


def test_pagine_ed_esportazioni(client_ruolo, evento):
    c = client_ruolo("Segretario")
    assert "Cerimonia del 4 novembre" in c.get(reverse("eventi:elenco")).content.decode()
    r = c.post(reverse("eventi:nuovo"), {"titolo": "Gita a Matera", "tipo": "gita",
               "inizio": "2027-05-01T08:00", "posti": "40", "accompagnatori": "1",
               "adesioni_aperte": "on"})  # fmt: skip
    gita = Evento.objects.get(titolo="Gita a Matera")
    assert r.status_code == 302 and gita.creato_da == c.utente
    r = c.post(reverse("eventi:adesione_nuova", args=[evento.pk]),
               {"cognome": "Rossi", "nome": "Luca", "accompagnatori": "0"}, follow=True)  # fmt: skip
    assert "Adesione di Rossi Luca registrata" in r.content.decode()
    pagina = c.get(evento.get_absolute_url()).content.decode()
    assert f"/adesione/{evento.token}/" in pagina and "Rossi Luca" in pagina
    assert c.get(reverse("eventi:aderenti", args=[evento.pk, "xlsx"])).content[:2] == b"PK"
    assert c.get(reverse("eventi:aderenti", args=[evento.pk, "pdf"])).content[:4] == b"%PDF"
    a = evento.adesioni.get()
    c.post(reverse("eventi:adesione_annulla", args=[a.pk]))
    a.refresh_from_db()
    assert a.annullata


def test_calendario_e_permessi(client_ruolo, evento):
    c = client_ruolo("Consigliere")
    oggi = timezone.localdate()
    eventi = calendario.eventi(c.utente, dal=oggi, al=oggi + timedelta(days=30))
    assert any(e.categoria == "Eventi" and e.titolo == evento.titolo for e in eventi)
    assert c.get(evento.get_absolute_url()).status_code == 200
    assert c.get(reverse("eventi:nuovo")).status_code == 403
    assert c.post(reverse("eventi:adesione_nuova", args=[evento.pk]),
                  {"cognome": "X"}).status_code == 403  # fmt: skip
