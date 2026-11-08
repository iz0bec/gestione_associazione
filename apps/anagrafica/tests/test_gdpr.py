# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test dell'esportazione dei dati personali e dell'anonimizzazione (GDPR)
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import io
import json
import zipfile
from datetime import date

import pytest

from apps.anagrafica import gdpr
from apps.anagrafica.models import Consenso, Soggetto
from apps.core.models import EventoAudit

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def cartella_media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def persona(crea_utente):
    from apps.comunicazioni import servizi as comunicazioni
    from apps.protocollo import servizi as protocollo
    from apps.protocollo.servizi import corrispondente_da_soggetto
    from apps.soci import servizi as soci
    from apps.soci.models import TipologiaSocio

    u = crea_utente("segr", ruoli=["Segretario"])
    s = Soggetto.objects.create(cognome="Verdi", nome="Ugo", email="ugo@example.org",
                                codice_fiscale="VRDGUO50A01G942X", data_nascita=date(1950, 1, 1),
                                cellulare="3331234567", note="nota riservata")  # fmt: skip
    Consenso.objects.create(soggetto=s, finalita="comunicazioni", modalita="modulo cartaceo")
    socio = soci.ammetti_socio(s, TipologiaSocio.objects.get(nome="Ordinario"), u)
    p = protocollo.registra_protocollo({"direzione": "entrata", "oggetto": "Lettera di Ugo Verdi"},
                                       [corrispondente_da_soggetto(s, "mittente")], u)  # fmt: skip
    invio = comunicazioni.crea_invio(u, oggetto="Avviso", corpo="Testo", finalita="istituzionale",
                                     soggetti=[s])  # fmt: skip
    return {"soggetto": s, "socio": socio, "protocollo": p, "invio": invio, "utente": u}


def test_esportazione_completa(persona):
    s = persona["soggetto"]
    contenuto = gdpr.dati(s)
    assert contenuto["scheda"]["codice_fiscale"] == "VRDGUO50A01G942X"
    assert contenuto["socio"]["numero"] == persona["socio"].numero
    assert contenuto["protocolli"][0]["oggetto"] == "Lettera di Ugo Verdi"
    assert contenuto["comunicazioni_ricevute"][0]["oggetto"] == "Avviso"
    assert contenuto["consensi"][0]["modalita"] == "modulo cartaceo"
    archivio = zipfile.ZipFile(io.BytesIO(gdpr.esporta(s, persona["utente"])))
    assert set(archivio.namelist()) == {"dati-personali.json", "riepilogo.pdf"}
    assert json.loads(archivio.read("dati-personali.json"))["dati"]["scheda"]["cognome"] == "Verdi"
    assert archivio.read("riepilogo.pdf").startswith(b"%PDF")


def test_impedimenti_e_anonimizzazione(persona, crea_utente):
    from apps.comunicazioni.models import Destinatario
    from apps.soci import servizi as soci

    s, admin = persona["soggetto"], crea_utente("capo", ruoli=["Amministratore di sistema"])
    assert any("socio attivo" in m for m in gdpr.impedimenti(s))
    soci.cessa_socio(persona["socio"], admin, data_cessazione=date.today(), causa="dimissioni")
    s.refresh_from_db()
    assert gdpr.impedimenti(s) == []
    with pytest.raises(gdpr.OperazioneNonValida, match="ANONIMIZZA"):
        gdpr.anonimizza(s, admin, motivo="richiesta", conferma="si")
    with pytest.raises(gdpr.OperazioneNonValida, match="motivo"):
        gdpr.anonimizza(s, admin, motivo=" ", conferma="anonimizza")
    gdpr.anonimizza(s, admin, motivo="Richiesta dell'interessato", conferma="anonimizza")
    s.refresh_from_db()
    assert s.cognome == gdpr.ANONIMO and s.nome == "" and s.codice_fiscale is None
    assert s.email == "" and s.cellulare == "" and s.data_nascita is None and s.note == ""
    assert s.anonimizzato_il and not s.attivo
    d = Destinatario.objects.get(soggetto=s)
    assert d.nome == gdpr.ANONIMO and d.email == ""
    persona["protocollo"].refresh_from_db()
    assert persona["protocollo"].oggetto == "Lettera di Ugo Verdi"  # documento ufficiale intatto
    evento = EventoAudit.objects.filter(dettagli__operazione="anonimizzazione (GDPR)").get()
    assert "Verdi" not in json.dumps(evento.dettagli)
    assert "già anonimizzata" in " ".join(gdpr.impedimenti(s))


def test_utente_ed_ente_non_anonimizzabili(crea_utente):
    ente = Soggetto.objects.create(tipo="ente", denominazione="Comune")
    assert any("persone" in m for m in gdpr.impedimenti(ente))
    s = Soggetto.objects.create(cognome="Neri", nome="Ada")
    u = crea_utente("ada")
    u.soggetto = s
    u.save()
    s.refresh_from_db()
    assert any("utente" in m for m in gdpr.impedimenti(s))


def test_viste_e_permessi(persona, client_ruolo):
    s = persona["soggetto"]
    segretario = client_ruolo("Segretario", username="s2")
    pagina = segretario.get(f"/anagrafica/{s.pk}/").content.decode()
    assert "Esporta tutti i dati" in pagina and 'data-bs-target="#anonimizza"' not in pagina
    r = segretario.get(f"/anagrafica/{s.pk}/dati-personali.zip")
    assert r.status_code == 200 and r["Content-Type"] == "application/zip"
    assert segretario.post(f"/anagrafica/{s.pk}/anonimizza/").status_code == 403
    assert client_ruolo("Consigliere", username="c").get(
        f"/anagrafica/{s.pk}/dati-personali.zip").status_code == 403  # fmt: skip
    admin = client_ruolo("Amministratore di sistema", username="a")
    assert "è socio attivo" in admin.get(f"/anagrafica/{s.pk}/").content.decode()


def test_scheda_anonimizzata_non_si_modifica(persona, client_ruolo, crea_utente):
    from apps.soci import servizi as soci

    s, admin = persona["soggetto"], crea_utente("capo", ruoli=["Amministratore di sistema"])
    soci.cessa_socio(persona["socio"], admin, data_cessazione=date.today(), causa="dimissioni")
    gdpr.anonimizza(Soggetto.objects.get(pk=s.pk), admin, motivo="x", conferma="ANONIMIZZA")
    c = client_ruolo("Segretario", username="s3")
    assert c.get(f"/anagrafica/{s.pk}/modifica/").status_code == 404
    assert "anonimizzata" in c.get(f"/anagrafica/{s.pk}/").content.decode()
