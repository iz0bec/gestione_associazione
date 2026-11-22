# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test della stampa unica della composizione degli organi sociali: gruppi,
# *              ordine delle cariche, recapiti solo a chi li vede in anagrafica, sezioni.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from datetime import date

import pytest

from apps.anagrafica.models import Soggetto
from apps.core.models import EventoAudit
from apps.organi import servizi
from apps.organi.models import Carica, Organo
from apps.soci.models import Sezione

pytestmark = pytest.mark.django_db
URL = "/organi/composizione/"


def nomina(organo, cognome, ruolo, email="", dal=date(2025, 1, 1), al=None):
    s = Soggetto.objects.create(tipo="persona", cognome=cognome, nome="Mario", email=email,
                                cellulare="333 1234567")  # fmt: skip
    return Carica.objects.create(organo=organo, soggetto=s, ruolo=ruolo, dal=dal, al=al)


@pytest.fixture
def organi():
    cd = Organo.objects.get(sigla="CD")
    nomina(cd, "Consiglieri", "consigliere")
    nomina(cd, "Primo", "presidente", "primo@example.org")
    nomina(cd, "Uscito", "segretario", al=date(2025, 6, 1))  # non più in carica
    alfa = Sezione.objects.create(codice="A", nome="Alfa")
    Sezione.objects.create(codice="B", nome="Beta")
    locale = Organo.objects.create(
        nome="Consiglio di Alfa", sigla="CA", tipo="consiglio", sezione=alfa
    )
    nomina(locale, "Locale", "presidente", "locale@example.org")
    return cd, locale, alfa


def test_gruppi_e_ordine(organi, crea_utente):
    admin = crea_utente("capo", ruoli=["Amministratore di sistema"])
    gruppi = servizi.composizione_organi(admin, giorno=date(2026, 1, 1))
    titoli = [t for t, _ in gruppi]
    assert titoli == ["Associazione", "Sezione di Alfa"]
    cariche = dict(gruppi)["Associazione"]
    cd = next(c for o, c in cariche if o.sigla == "CD")
    assert [c.soggetto.cognome for c in cd] == [
        "Primo",
        "Consiglieri",
    ]  # presidente prima, uscito no
    solo = servizi.composizione_organi(admin, scelta=str(organi[2].pk), giorno=date(2026, 1, 1))
    assert [t for t, _ in solo] == ["Sezione di Alfa"]
    assert [t for t, _ in servizi.composizione_organi(admin, scelta="associazione")] == [
        "Associazione"
    ]


def test_pdf_con_recapiti_e_registro(organi, client_ruolo, monkeypatch):
    contesti = []
    monkeypatch.setattr("apps.core.pdf.genera_pdf", lambda t, c: contesti.append(c) or b"%PDF-1.7")
    c = client_ruolo("Segretario")
    pagina = c.get(URL).content.decode()
    assert "Sezione di Alfa" in pagina and "con email e telefono" in pagina
    r = c.get(URL, {"pdf": "1", "scelta": "tutti", "giorno": "2026-01-01"})
    assert (
        r["Content-Type"] == "application/pdf"
        and "organi_sociali_20260101.pdf" in r["Content-Disposition"]
    )
    assert contesti[-1]["contatti"] is True
    assert EventoAudit.objects.filter(
        oggetto_descrizione="Composizione degli organi sociali (PDF)"
    ).exists()


def test_recapiti_solo_a_chi_li_vede(organi, crea_utente):
    from django.contrib.auth.models import Permission

    u = crea_utente("lettore")
    u.user_permissions.add(Permission.objects.get(codename="view_organo"))
    html = []
    import apps.core.pdf as pdf

    originale = pdf.genera_pdf
    try:
        pdf.genera_pdf = lambda t, c: html.append(c) or b"%PDF"
        servizi.pdf_composizione_organi(u)
    finally:
        pdf.genera_pdf = originale
    assert html[0]["contatti"] is False


def test_pdf_reale(organi, crea_utente):
    admin = crea_utente("capo", ruoli=["Amministratore di sistema"])
    assert servizi.pdf_composizione_organi(admin).startswith(b"%PDF")


def test_sezione_limitata(organi, crea_utente):
    beta = Sezione.objects.get(nome="Beta")
    u = crea_utente("sezione", ruoli=["Presidente di sezione"])
    u.sezioni.add(beta)
    titoli = [t for t, _ in servizi.composizione_organi(u)]
    assert "Sezione di Alfa" not in titoli


def test_permesso(client_ruolo, client):
    assert client.get(URL).status_code == 302  # senza accesso: alla pagina di accesso
