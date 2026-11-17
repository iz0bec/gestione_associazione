# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test della chat interna: conversazioni a due e di gruppo, non letti, ritiro,
# *              riservatezza (solo i partecipanti, nemmeno l'amministratore), pagine HTMX
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import pytest
from django.test import Client
from django.urls import reverse

from apps.chat import servizi
from apps.chat.models import Messaggio

pytestmark = pytest.mark.django_db


@pytest.fixture
def anna(crea_utente):
    return crea_utente("anna", ruoli=["Segretario"], first_name="Anna", last_name="Rossi")


@pytest.fixture
def bruno(crea_utente):
    return crea_utente("bruno", ruoli=["Tesoriere"], first_name="Bruno", last_name="Verdi")


@pytest.fixture
def carla(crea_utente):
    return crea_utente("carla", ruoli=["Consigliere"], first_name="Carla", last_name="Neri")


def _client(utente):
    c = Client()
    c.force_login(utente)
    return c


def test_tutti_i_ruoli_usano_la_chat_ma_non_chi_non_ha_ruolo(anna, bruno, crea_utente):
    senza = crea_utente("senza")
    assert set(servizi.utenti_chat()) == {anna, bruno}
    with pytest.raises(servizi.OperazioneNonValida, match="non può usare la chat"):
        servizi.conversazione_diretta(anna, senza)
    assert _client(senza).get(reverse("chat:elenco")).status_code == 403


def test_conversazione_diretta_unica_e_non_letti(anna, bruno):
    c = servizi.conversazione_diretta(anna, bruno)
    assert servizi.conversazione_diretta(bruno, anna) == c
    assert c.nome_per(anna) == "Bruno Verdi" and c.nome_per(bruno) == "Anna Rossi"
    servizi.invia(c, anna, "Ciao Bruno")
    m = servizi.invia(c, anna, "  ci sei?  ")
    assert m.testo == "ci sei?"
    assert servizi.non_letti(bruno) == 2 and servizi.non_letti(anna) == 0
    assert servizi.conversazioni_di(bruno).get().non_letti == 2
    servizi.segna_letti(c, bruno)
    assert servizi.non_letti(bruno) == 0
    servizi.segna_letti(c, bruno, 0)  # il segno non torna indietro
    assert servizi.non_letti(bruno) == 0
    with pytest.raises(servizi.OperazioneNonValida, match="vuoto"):
        servizi.invia(c, bruno, "   ")
    with pytest.raises(servizi.OperazioneNonValida, match="troppo lungo"):
        servizi.invia(c, bruno, "x" * 4001)


def test_gruppo_aggiungi_ed_esci(anna, bruno, carla):
    g = servizi.crea_gruppo(anna, "Consiglio", [bruno])
    servizi.invia(g, anna, "Prima dell'arrivo di Carla")
    assert servizi.aggiungi(g, bruno, [carla]) == [carla]
    assert servizi.non_letti(carla) == 0  # vede solo i messaggi da quando entra
    servizi.invia(g, bruno, "Benvenuta")
    assert servizi.non_letti(carla) == 1 and servizi.non_letti(anna) == 1
    servizi.esci(g, carla)
    assert not servizi.conversazioni_di(carla).exists()
    with pytest.raises(servizi.OperazioneNonValida, match="Non partecipi"):
        servizi.invia(g, carla, "ci sono ancora?")
    avvisi = list(g.messaggi.filter(sistema=True).values_list("testo", flat=True))
    assert avvisi == ["Anna Rossi ha creato il gruppo.", "Bruno Verdi ha aggiunto Carla Neri.",
                      "Carla Neri ha lasciato il gruppo."]  # fmt: skip
    with pytest.raises(servizi.OperazioneNonValida, match="nome"):
        servizi.crea_gruppo(anna, " ", [bruno])
    d = servizi.conversazione_diretta(anna, bruno)
    with pytest.raises(servizi.OperazioneNonValida, match="solo ai gruppi"):
        servizi.aggiungi(d, anna, [carla])


def test_ritiro_solo_dei_propri(anna, bruno):
    c = servizi.conversazione_diretta(anna, bruno)
    m = servizi.invia(c, anna, "Testo sbagliato")
    with pytest.raises(servizi.OperazioneNonValida, match="solo i tuoi"):
        servizi.ritira(m, bruno)
    servizi.ritira(m, anna)
    m.refresh_from_db()
    assert m.testo == "" and m.ritirato_il and servizi.non_letti(bruno) == 0


def test_riservatezza_anche_per_l_amministratore(anna, bruno, crea_utente):
    admin = crea_utente("capo", ruoli=["Amministratore di sistema"], is_superuser=True)
    c = servizi.conversazione_diretta(anna, bruno)
    m = servizi.invia(c, anna, "Riservato")
    a = _client(admin)
    assert a.get(reverse("chat:conversazione", args=[c.pk])).status_code == 404
    assert a.get(reverse("chat:messaggi", args=[c.pk])).status_code == 404
    assert a.post(reverse("chat:invia", args=[c.pk]), {"testo": "x"}).status_code == 404
    assert a.post(reverse("chat:ritira", args=[m.pk])).status_code == 404
    assert "Riservato" not in a.get(reverse("chat:elenco")).content.decode()


def test_pagine(anna, bruno, carla):
    a, b = _client(anna), _client(bruno)
    r = a.get(reverse("chat:con", args=[bruno.pk]))
    c = servizi.conversazioni_di(anna).get()
    assert r["Location"] == c.get_absolute_url()
    assert a.get(c.get_absolute_url()).status_code == 200
    # invio con HTMX: 204 e l'evento che fa chiedere subito i nuovi messaggi
    r = a.post(
        reverse("chat:invia", args=[c.pk]), {"testo": "Ciao <b>Bruno</b>"}, HTTP_HX_REQUEST="true"
    )
    assert r.status_code == 204 and r["HX-Trigger"] == "chat-nuovi"
    r = a.post(reverse("chat:invia", args=[c.pk]), {"testo": " "}, HTTP_HX_REQUEST="true")
    assert r.status_code == 422 and "vuoto" in r.content.decode()
    # il contatore della barra e la lettura con i messaggi nuovi
    assert ">1<" in b.get(reverse("chat:contatore")).content.decode()
    pezzo = b.get(reverse("chat:messaggi", args=[c.pk]), {"dopo": 0}).content.decode()
    assert "Ciao &lt;b&gt;Bruno&lt;/b&gt;" in pezzo and 'id="chat-coda"' in pezzo
    ultimo = Messaggio.objects.latest("pk").pk
    assert f"dopo={ultimo}" in pezzo
    assert b.get(reverse("chat:contatore")).content.decode().strip() == ""
    vuoto = b.get(reverse("chat:messaggi", args=[c.pk]), {"dopo": ultimo}).content.decode()
    assert "chat-fumetto" not in vuoto and f"dopo={ultimo}" in vuoto
    # nuovo gruppo dal modulo, aggiunta e uscita
    r = a.post(reverse("chat:nuova"), {"persone": [bruno.pk, carla.pk], "titolo": ""})
    assert r.status_code == 200 and "dai un nome al gruppo" in r.content.decode()
    r = a.post(reverse("chat:nuova"), {"persone": [bruno.pk], "titolo": "Direttivo"})
    g = servizi.conversazioni_di(anna).get(titolo="Direttivo")
    assert r["Location"] == g.get_absolute_url()
    a.post(reverse("chat:aggiungi", args=[g.pk]), {"persone": [carla.pk]})
    assert servizi.conversazioni_di(carla).filter(pk=g.pk).exists()
    assert "Direttivo" in a.get(reverse("chat:elenco")).content.decode()
    r = _client(carla).post(reverse("chat:esci", args=[g.pk]))
    assert r["Location"] == reverse("chat:elenco")


def test_contatore_consentito_con_password_da_cambiare(anna):
    anna.deve_cambiare_password = True
    anna.save()
    a = _client(anna)
    assert a.get(reverse("chat:contatore"), HTTP_HX_REQUEST="true").status_code == 200
    assert a.get(reverse("chat:elenco")).status_code == 302
