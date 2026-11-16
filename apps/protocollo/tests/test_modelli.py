# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test dei modelli di registrazione del protocollo («Parti da un modello»).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
from datetime import date

import pytest
from django.urls import reverse

from apps.comunicazioni.models import Lista
from apps.core.models import Organizzazione
from apps.protocollo.models import Classificazione, ModelloProtocollo

pytestmark = pytest.mark.django_db


@pytest.fixture
def utente(crea_utente):
    return crea_utente("addetto", ruoli=["Addetto protocollo"])


def test_modelli_di_base():
    nomi = set(ModelloProtocollo.objects.values_list("nome", flat=True))
    assert "Richiesta di patrocinio" in nomi and len(nomi) >= 7
    m = ModelloProtocollo.objects.get(nome="Trasmissione del rendiconto")
    assert m.classificazione.codice == "04"


def test_valori_con_segnaposto():
    org = Organizzazione.corrente()
    org.denominazione = "Amici del Paese"
    org.save()
    lista = Lista.objects.create(nome="Autorità")
    m = ModelloProtocollo.objects.create(
        nome="Prova", direzione="uscita", mezzo="raccomandata",
        oggetto="Bilancio {{ anno_precedente }} - {{ data }}",
        testo="{{ organizzazione }} comunica... {{ sconosciuto }}",
    )  # fmt: skip
    m.liste.set([lista])
    v = m.valori(date(2026, 11, 16))
    assert v["oggetto"] == "Bilancio 2025 - 16/11/2026"
    assert v["testo"] == "Amici del Paese comunica... {{ sconosciuto }}"
    assert v["mezzo"] == "raccomandata" and v["liste"] == [lista.pk]
    m.direzione = "entrata"
    assert "liste" not in m.valori()


def test_parti_da_un_modello(client, utente):
    client.force_login(utente)
    m = ModelloProtocollo.objects.get(nome="Richiesta di patrocinio")
    r = client.get(reverse("protocollo:nuovo"))
    assert "Parti da un modello" in r.text and m.nome in r.text
    r = client.get(reverse("protocollo:nuovo"), {"modello": m.pk})
    form = r.context["form"]
    assert form.initial["oggetto"] == "Richiesta di patrocinio per ..."
    assert form.initial["direzione"] == "uscita" and form.initial["mezzo"] == "pec"
    assert form.initial["classificazione"] == Classificazione.objects.get(codice="07").pk
    m.attivo = False
    m.save()
    r = client.get(reverse("protocollo:nuovo"), {"modello": m.pk})
    assert r.context["form"].initial.get("oggetto") is None


def test_gestione_e_permessi(client, client_ruolo, crea_utente, utente):
    client.force_login(utente)  # l'addetto consulta e usa i modelli, non li modifica
    assert client.get(reverse("protocollo:modelli")).status_code == 200
    assert client.get(reverse("protocollo:modello_nuovo")).status_code == 403
    responsabile = crea_utente("segr", ruoli=["Segretario"])
    client.force_login(responsabile)
    assert responsabile.has_perm("protocollo.add_modelloprotocollo")
    r = client.post(
        reverse("protocollo:modello_nuovo"),
        {"nome": "Auguri", "direzione": "uscita", "mezzo": "email", "oggetto": "Auguri {{ anno }}",
         "ordine": 0, "attivo": "on"},
    )  # fmt: skip
    assert r.status_code == 302 and ModelloProtocollo.objects.filter(nome="Auguri").exists()
