# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test di «manage.py utenti»: elenco, reimpostazione alla password predefinita
# *              (carica o iniziale dell'amministratore), email di notifica come ultimo passo.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import io
import json
from datetime import date

import pytest
from django.core import mail
from django.core.management import CommandError, call_command

from apps.accounts import servizi
from apps.anagrafica.models import Soggetto
from apps.comunicazioni.models import Invio
from apps.core.models import EventoAudit, Organizzazione
from apps.organi.models import Carica, Organo

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def ambiente(settings, tmp_path):
    settings.MAILERS = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}
    settings.URL_PUBBLICO = "https://gestione.example.org"
    file = tmp_path / "password-predefinite.json"
    file.write_text(
        json.dumps({"admin": "Iniziale-Admin-2026", "presidente": "Presidenti-2027-ok"})
    )
    settings.PASSWORD_PREDEFINITE = str(file)
    Organizzazione.objects.update(denominazione="ANCR Sezione di Prova", invio_email=True)


def presidente(crea_utente, email="rossi@example.org"):
    s = Soggetto.objects.create(tipo="persona", cognome="Rossi", nome="Mario", email=email)
    Carica.objects.create(organo=Organo.objects.get(sigla="CD"), soggetto=s, ruolo="presidente",
                          dal=date(2025, 1, 1))  # fmt: skip
    return crea_utente("mario.rossi", ruoli=["Presidente"], soggetto=s)


def esegui(*argomenti):
    uscita = io.StringIO()
    call_command("utenti", *argomenti, stdout=uscita)
    return uscita.getvalue()


def test_elenco(crea_utente):
    presidente(crea_utente)
    crea_utente("spento", is_active=False)
    testo = esegui()
    assert "mario.rossi" in testo and "presidente ✓" in testo and "spento" not in testo
    assert "spento" in esegui("--tutti")


def test_reimposta_alla_predefinita_e_invia(crea_utente):
    u = presidente(crea_utente)
    testo = esegui("--reimposta", "Mario.Rossi", "--invia")
    u.refresh_from_db()
    assert u.check_password("Presidenti-2027-ok") and not u.deve_cambiare_password
    assert (
        "predefinita della categoria «presidente»" in testo
        and "inviata a rossi@example.org" in testo
    )
    assert len(mail.outbox) == 1 and "Presidenti-2027-ok" in mail.outbox[0].body
    evento = EventoAudit.objects.filter(oggetto_id=str(u.pk)).latest("momento")
    assert "Presidenti-2027-ok" not in json.dumps(evento.dettagli)  # mai nel registro


def test_senza_terminale_resta_in_bozza(crea_utente):
    presidente(crea_utente)
    testo = esegui(
        "--reimposta", "mario.rossi"
    )  # nei test stdin non è un terminale: niente domanda
    assert "bozza pronta" in testo and Invio.objects.get().stato == "bozza" and mail.outbox == []


def test_senza_email_e_obbligo_cambio(crea_utente):
    u = presidente(crea_utente)
    esegui("--reimposta", "mario.rossi", "--senza-email", "--obbligo-cambio")
    u.refresh_from_db()
    assert u.deve_cambiare_password and not Invio.objects.exists()


def test_amministratore_alla_password_iniziale(crea_utente):
    admin = crea_utente("admin", ruoli=["Amministratore di sistema"])
    assert servizi.categoria_utente(admin) == "admin"
    esegui("--reimposta", "admin", "--senza-email")
    admin.refresh_from_db()
    assert admin.check_password("Iniziale-Admin-2026")


def test_generata_se_manca_la_predefinita(crea_utente):
    crea_utente("cons", ruoli=["Consigliere"])
    testo = esegui("--reimposta", "cons", "--senza-email")
    assert "generata" in testo and "mostrata solo ora" in testo


def test_senza_email_per_conto_alla_casella(crea_utente):
    Organizzazione.objects.update(email="sezione@example.org")
    presidente(crea_utente, email="")
    testo = esegui("--reimposta", "mario.rossi", "--invia")
    assert "inviata a sezione@example.org" in testo
    assert "per conto di" in mail.outbox[0].subject


def test_errori(crea_utente):
    with pytest.raises(CommandError, match="inesistente"):
        esegui("--reimposta", "nessuno")
    presidente(crea_utente)
    with pytest.raises(CommandError):
        esegui("--reimposta", "mario.rossi", "--password", "corta")
