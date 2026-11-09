# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test dei modelli di convocazione (casi tipici e precompilazione)
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
from datetime import date

import pytest
from django.urls import reverse

from apps.organi.models import ModelloConvocazione

pytestmark = pytest.mark.django_db


def test_modelli_tipici_presenti():
    assert ModelloConvocazione.objects.filter(tipo_organo="assemblea").count() >= 3
    assert ModelloConvocazione.objects.filter(straordinaria=True).exists()


def test_anni_sostituiti():
    m = ModelloConvocazione.objects.get(nome="Assemblea ordinaria - rendiconto annuale")
    valori = m.valori(date(2027, 3, 1))
    assert "rendiconto dell'esercizio 2026" in valori["punti"]
    assert "{{" not in valori["punti"] + valori["premessa"]
    assert len(valori["punti"].splitlines()) == 6


def test_nuova_riunione_dal_modello(client_ruolo):
    client = client_ruolo("Segretario")
    m = ModelloConvocazione.objects.get(nome__startswith="Assemblea straordinaria")
    r = client.get(reverse("organi:riunione_nuova") + f"?modello={m.pk}")
    assert r.status_code == 200
    form = r.context["form"]
    assert form.initial["straordinaria"] is True
    assert "statuto" in form.initial["punti"]
    assert "Parti da un modello" in r.content.decode() or m.nome in r.content.decode()


def test_gestione_modelli(client_ruolo):
    client = client_ruolo("Segretario")
    assert client.get(reverse("organi:modelli_convocazione")).status_code == 200
    r = client.post(
        reverse("organi:modello_convocazione_nuovo"),
        {"nome": "Prova", "tipo_organo": "", "punti": "Uno\nDue", "ordine": 0, "attivo": "on"},
    )
    assert r.status_code == 302
    m = ModelloConvocazione.objects.get(nome="Prova")
    r = client.post(
        reverse("organi:modello_convocazione", args=[m.pk]),
        {"nome": "Prova", "tipo_organo": "consiglio", "punti": "Uno", "ordine": 0},
    )
    m.refresh_from_db()
    assert m.tipo_organo == "consiglio" and not m.attivo


def test_permessi(client_ruolo):
    client = client_ruolo("Tesoriere")
    assert client.get(reverse("organi:modelli_convocazione")).status_code == 200
    assert client.get(reverse("organi:modello_convocazione_nuovo")).status_code == 403
