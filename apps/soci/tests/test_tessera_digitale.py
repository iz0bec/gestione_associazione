# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test della tessera digitale e della verifica pubblica
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from datetime import date
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.anagrafica.models import Soggetto
from apps.soci import servizi, tessera_digitale
from apps.soci.models import Sezione, TipologiaSocio

pytestmark = pytest.mark.django_db
ANNO = timezone.localdate().year


@pytest.fixture(autouse=True)
def ambiente(settings, tmp_path):
    from django.core.cache import cache

    settings.MEDIA_ROOT = tmp_path
    cache.clear()


@pytest.fixture
def tessera(crea_utente):
    u = crea_utente("segr", ruoli=["Segretario"])
    sez = Sezione.objects.create(codice="AV", nome="Avigliano", comune="Avigliano")
    tip = TipologiaSocio.objects.get(nome="Ordinario")
    tip.quota_annua = Decimal("25")
    tip.save()
    s = Soggetto.objects.create(cognome="Rossi", nome="Mario", email="rossi@example.org",
                                data_nascita=date(1950, 1, 1))  # fmt: skip
    socio = servizi.ammetti_socio(s, tip, u, sezione=sez)
    servizi.carica_lotto(u, anno=ANNO, numero_da=29000, numero_a=29010, cifre=6, sezione=sez)
    t = servizi.rilascia_tessera(socio, ANNO, u, pagata_il=timezone.localdate(), metodo="contanti")
    return servizi.attribuisci_carta(t, u, "029005")


def test_esito(tessera):
    e = tessera_digitale.esito(tessera)
    assert e.valida and e.nome == "Mario Rossi" and e.sezione == "Avigliano" and e.anno == ANNO
    tessera.pagata_il = None
    assert not tessera_digitale.esito(tessera).valida
    tessera.pagata_il, tessera.anno = timezone.localdate(), ANNO - 1
    assert "dell'anno" in tessera_digitale.esito(tessera).motivo


def test_pdf_e_codice_stabile(tessera, client_ruolo):
    c = client_ruolo("Segretario", username="s2")
    r = c.get(f"/soci/tessere/{tessera.pk}/tessera-digitale.pdf")
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
    tessera.refresh_from_db()
    codice = tessera.token_verifica
    assert len(codice) >= 30
    c.get(f"/soci/tessere/{tessera.pk}/tessera-digitale.pdf")
    tessera.refresh_from_db()
    assert tessera.token_verifica == codice  # sempre lo stesso QR
    assert "Tessera</a>" in c.get(f"/soci/{tessera.socio.pk}/").content.decode()


def test_invio_per_email_in_bozza(tessera, client_ruolo):
    from apps.comunicazioni.models import Invio

    c = client_ruolo("Segretario", username="s2")
    r = c.post(f"/comunicazioni/da/tessera-digitale/{tessera.pk}/")
    invio = Invio.objects.get(origine="tessera_digitale")
    assert r.status_code == 302 and invio.stato == "bozza"
    assert invio.allegati.get().nome == f"tessera_{ANNO}_{tessera.socio.numero}.pdf"
    assert invio.oggetto == "La tua tessera {{ anno_quota }}"


def test_verifica_pubblica(tessera, client):
    tessera_digitale.token_di(tessera)
    testo = client.get(f"/verifica-tessera/{tessera.token_verifica}/").content.decode()
    assert "Tessera valida" in testo and "Mario Rossi" in testo and "Avigliano" in testo
    assert "rossi@example.org" not in testo and "1950" not in testo  # nient'altro
    assert client.get("/verifica-tessera/inventato/").status_code == 404
    testo = client.get("/verifica-tessera/?numero=29005&cognome=ROSSI").content.decode()
    assert "Tessera valida" in testo
    testo = client.get("/verifica-tessera/?numero=29005&cognome=Bianchi").content.decode()
    assert "Nessuna tessera corrisponde" in testo
    assert "sia il numero" in client.get("/verifica-tessera/?numero=29005").content.decode()


def test_limite_tentativi(tessera, client):
    from apps.soci.pubblico import LIMITE_VERIFICHE

    for _ in range(LIMITE_VERIFICHE):
        client.get("/verifica-tessera/?numero=1&cognome=x")
    assert "Troppe verifiche" in client.get(
        "/verifica-tessera/?numero=29005&cognome=Rossi").content.decode()  # fmt: skip


def test_riquadro_nella_pagina_pubblica(client):
    from apps.core.models import Organizzazione

    Organizzazione.objects.update_or_create(pk=1, defaults={"pagina_pubblica": True})
    assert 'action="/verifica-tessera/"' in client.get("/").content.decode()
