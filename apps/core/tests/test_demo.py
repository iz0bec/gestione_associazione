# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test dell'ambiente dimostrativo: rifiuto senza DEMO=true, fascia e credenziali
# *              pubbliche, azzeramento mensile dal pianificatore, logo generato.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import io
from datetime import datetime

import pytest
from django.core.management import CommandError, call_command
from django.utils import timezone
from PIL import Image

from apps.core import demo
from apps.core.audit import Azione, registra

pytestmark = pytest.mark.django_db


def test_rifiuta_senza_demo(settings, monkeypatch):
    settings.DEMO = False
    chiamato = []
    monkeypatch.setattr(demo, "azzera", lambda **k: chiamato.append(1))
    with pytest.raises(CommandError, match="DEMO=true"):
        call_command("demo", "--conferma")
    assert chiamato == []


def test_serve_la_conferma(settings, monkeypatch):
    settings.DEMO = True
    chiamato = []
    monkeypatch.setattr(demo, "azzera", lambda **k: chiamato.append(1) or "x")
    with pytest.raises(CommandError, match="--conferma"):
        call_command("demo")
    call_command("demo", "--conferma", stdout=io.StringIO())
    assert chiamato == [1]


def test_azzera_rifiuta_senza_demo(settings):
    settings.DEMO = False
    with pytest.raises(demo.DemoNonAttiva):
        demo.azzera("x")


def test_azzeramento_il_primo_del_mese(settings):
    settings.DEMO = True
    primo = timezone.make_aware(datetime(2026, 12, 1, 2, 0))
    assert not demo.azzeramento_dovuto(primo.replace(day=2))
    assert demo.azzeramento_dovuto(primo)
    registra(Azione.MODIFICA, None, descrizione=demo.DESCRIZIONE_AZZERAMENTO)
    from apps.core.models import EventoAudit

    EventoAudit.objects.update(momento=primo.replace(hour=1))
    assert not demo.azzeramento_dovuto(primo)  # già fatto oggi
    settings.DEMO = False
    assert not demo.azzeramento_dovuto(primo.replace(month=11))


def test_fascia_e_credenziali_pubbliche(settings, client, client_ruolo):
    settings.DEMO = True
    pagina = client.get("/account/login/").content.decode()
    assert "Ambiente dimostrativo" in pagina and settings.DEMO_PASSWORD in pagina
    assert ">presidente</code>" in pagina and ">admin</code>" not in pagina
    assert "Ambiente dimostrativo" in client_ruolo("Segretario").get("/").content.decode()
    settings.DEMO = False
    assert "Ambiente dimostrativo" not in client.get("/account/login/").content.decode()


def test_logo_generato():
    img = Image.open(io.BytesIO(demo.logo_generato()))
    assert img.size == (512, 512) and img.mode == "RGBA"
