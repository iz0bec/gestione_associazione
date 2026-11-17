# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test degli incassi diversi dalle quote, delle note di storno e dei rimborsi,
# *              del registro degli incassi con i totali per metodo e per conto.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.anagrafica.models import Soggetto
from apps.soci import servizi as soci
from apps.soci.models import TipologiaSocio
from apps.tesoreria import incassi, servizi
from apps.tesoreria.models import Movimento

pytestmark = pytest.mark.django_db
OGGI = date.today()
D = Decimal


@pytest.fixture(autouse=True)
def cartella_media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def tesoriere(crea_utente):
    u = crea_utente("tesoriere", ruoli=["Tesoriere"])
    TipologiaSocio.objects.filter(nome="Ordinario").update(quota_annua=D("20"))
    servizi.apri_esercizio(OGGI.year, u)  # il listino dell'anno prende la quota
    return u


@pytest.fixture
def quota(tesoriere):
    ordinario = TipologiaSocio.objects.get(nome="Ordinario")
    s = soci.ammetti_socio(Soggetto.objects.create(cognome="Rossi", nome="Mario"), ordinario,
                           tesoriere)  # fmt: skip
    return soci.rilascia_tessera(s, OGGI.year, tesoriere, pagata_il=OGGI)  # contanti


def _incasso(utente, **extra):
    return incassi.registra_incasso({
        "data": OGGI, "tipo": "donazione", "nominativo": "Anna Verdi", "importo": D("50"),
        "metodo": "bonifico", "riferimento": "CRO123", "causale": "Offerta per il 4 novembre",
        **extra,
    }, utente)  # fmt: skip


def test_ricevuta_nella_numerazione_delle_quote(tesoriere, quota):
    i = _incasso(tesoriere)
    assert (i.ricevuta_anno, i.ricevuta_numero) == (OGGI.year, quota.ricevuta_numero + 1)
    m = i.movimento
    assert m.tipo == "entrata" and m.importo == D("50") and m.voce.codice == "E.A.4"
    assert m.conto.nome == "Banca" and f"ricevuta n. {i.codice_ricevuta}" in m.documento
    contributo = _incasso(tesoriere, tipo="contributo", metodo="contanti")
    assert contributo.movimento.voce.codice == "E.A.6"
    assert contributo.movimento.conto.nome == "Cassa"


def test_storno_per_errore_annulla_il_movimento(tesoriere):
    i = _incasso(tesoriere)
    s = incassi.storna(i, tesoriere, data=OGGI, motivo="Registrato due volte", rimborso=False)
    i.movimento.refresh_from_db()
    assert i.movimento.annullato and s.movimento is None and s.codice == f"{OGGI.year}/0001"
    with pytest.raises(servizi.OperazioneNonValida, match="già stata stornata"):
        incassi.storna(i, tesoriere, data=OGGI, motivo="x", rimborso=False)


def test_rimborso_della_quota_e_annullamento(tesoriere, quota):
    s = incassi.storna(quota, tesoriere, data=OGGI, motivo="Socio trasferito", rimborso=True,
                       annulla_tessera=True)  # fmt: skip
    m = s.movimento
    assert m.tipo == "uscita" and m.importo == D("20") and m.conto.nome == "Cassa"
    assert m.voce.codice == "U.A.5" and f"nota di storno n. {s.codice}" in m.documento
    quota.refresh_from_db()
    assert quota.annullata and not Movimento.objects.get(tessera=quota).annullato
    with pytest.raises(servizi.OperazioneNonValida, match="motivo"):
        incassi.storna(_incasso(tesoriere), tesoriere, data=OGGI, motivo=" ", rimborso=True)


def test_registro_e_quadratura(tesoriere, quota):
    _incasso(tesoriere)  # 50 bonifico
    errato = _incasso(tesoriere, importo=D("10"), metodo="contanti")
    incassi.storna(errato, tesoriere, data=OGGI, motivo="Errore", rimborso=False)
    r = incassi.registro(OGGI.replace(day=1), OGGI)
    assert r.ricevute == 3 and r.storni == 1
    assert r.totale == D("70")  # 20 quota + 50 + 10 - 10
    assert r.per_conto == {"Banca": D("50"), "Cassa": D("20")}
    assert r.per_metodo["Contanti"] == D("20") and r.per_metodo["Bonifico"] == D("50")
    assert incassi.registro_xlsx(r)[:2] == b"PK"


def test_pagine(client_ruolo, quota):
    c = client_ruolo("Tesoriere", username="t2")
    r = c.post(reverse("tesoreria:incasso_nuovo") + f"?soggetto={quota.socio.soggetto_id}", {
        "tipo": "partecipazione", "data": OGGI.isoformat(), "nominativo": "Mario Rossi",
        "importo": "15", "metodo": "pos", "causale": "Pranzo sociale",
        "soggetto": quota.socio.soggetto_id,
    })  # fmt: skip
    assert r.status_code == 302
    i = quota.socio.soggetto.incassi.get()
    assert i.voce.codice == "E.A.3"
    assert c.get(reverse("tesoreria:incassi")).status_code == 200
    pdf = c.get(reverse("tesoreria:ricevuta_incasso", args=[i.pk]))
    assert pdf.content.startswith(b"%PDF")
    r = c.post(reverse("tesoreria:storno"), {"incasso": i.pk, "data": OGGI.isoformat(),
                                              "motivo": "Annullato", "rimborso": "1"})  # fmt: skip
    assert r.status_code == 302 and c.get(r["Location"]).content.startswith(b"%PDF")
    assert c.get(reverse("tesoreria:storno") + f"?tessera={quota.pk}").status_code == 200
    pagina = c.get(reverse("tesoreria:registro_incassi")).content.decode()
    assert "Registro degli incassi" in pagina and "Rimborso" in pagina
    assert c.get(reverse("tesoreria:registro_incassi"), {"formato": "pdf"}).content[:4] == b"%PDF"
    assert "Stornata" not in c.get(quota.socio.get_absolute_url()).content.decode()


def test_permessi(client_ruolo):
    c = client_ruolo("Consigliere")
    assert c.get(reverse("tesoreria:incasso_nuovo")).status_code == 403
    assert c.get(reverse("tesoreria:storno") + "?incasso=1").status_code == 403
