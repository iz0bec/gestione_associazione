# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test degli avvisi della posta da protocollare per Telegram, SMS e WhatsApp:
# *              chi li riceve, testo, interruttore, pagina personale.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from email.message import EmailMessage

import pytest
from django.utils import timezone

from apps.anagrafica.models import Soggetto
from apps.comunicazioni import messaggi, telegram
from apps.core.cifratura import nuova_chiave
from apps.core.models import CanaleTelegram, Organizzazione, ServizioMessaggi
from apps.protocollo import avvisi, posta
from apps.protocollo.models import CasellaPosta

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def ambiente(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    settings.CHIAVE_CIFRATURA = nuova_chiave()
    settings.URL_PUBBLICO = "https://gestione.example.it"
    Organizzazione.objects.update_or_create(
        pk=1, defaults={"denominazione": "ANCR Avigliano", "invio_email": True}
    )


@pytest.fixture
def bot(monkeypatch):
    inviati = []

    def finto(token, metodo, dati=None, documento=None):
        inviati.append((metodo, dati))
        return {"is_bot": True, "username": "ancr_bot"} if metodo == "getMe" else {}

    monkeypatch.setattr(telegram, "_chiama", finto)
    canale = CanaleTelegram.corrente()
    canale.imposta_token("1:x")
    canale.nome_bot, canale.attivo = "ancr_bot", True
    canale.save()
    return inviati


@pytest.fixture
def addetto(crea_utente):
    u = crea_utente("addetto", ruoli=["Addetto protocollo"])
    u.soggetto = Soggetto.objects.create(cognome="Rossi", nome="Mario", telegram_chat_id=77,
                                         cellulare="333 1234567")  # fmt: skip
    u.avvisi_posta = "telegram"
    u.save()
    return u


def _arriva(oggetto, casella=None):
    casella = (
        casella
        or CasellaPosta.objects.get_or_create(
            nome="PEC", defaults={"pec": True, "server": "s", "utente": "u"}
        )[0]
    )
    m = EmailMessage()
    m["From"] = "Comune <protocollo@pec.comune.it>"
    m["Subject"] = oggetto
    m["Message-ID"] = f"<{oggetto}@pec>"
    m.set_content("Testo")
    return posta.salva_messaggio(casella, m.as_bytes())


def test_riepilogo_su_telegram(bot, addetto):
    dal = timezone.now()
    for i in range(7):
        _arriva(f"Invito-{i}")
    assert avvisi.avvisa_nuova_posta(dal) == 1
    ((metodo, dati),) = bot
    assert metodo == "sendMessage" and dati["chat_id"] == 77
    testo = dati["text"]
    assert testo.startswith("ANCR Avigliano: 7 nuovi messaggi da protocollare")
    assert "- PEC Invito-6 (protocollo@pec.comune.it)" in testo and "e altri 2" in testo
    assert testo.endswith("https://gestione.example.it/protocollo/posta/")


def test_solo_chi_gestisce_la_posta_e_ha_scelto(bot, addetto, crea_utente):
    consigliere = crea_utente("cons", ruoli=["Consigliere"])
    consigliere.soggetto = Soggetto.objects.create(cognome="B", nome="C", telegram_chat_id=88)
    consigliere.avvisi_posta = "telegram"
    consigliere.save()
    nessuno = crea_utente("altro", ruoli=["Addetto protocollo"])  # non ha scelto
    assert nessuno.avvisi_posta == ""
    dal = timezone.now()
    _arriva("Uno")
    assert avvisi.avvisa_nuova_posta(dal) == 1
    assert [d["chat_id"] for _, d in bot] == [77]


def test_niente_avvisi(bot, addetto):
    dal = timezone.now()
    assert avvisi.avvisa_nuova_posta(dal) == 0  # nessun messaggio nuovo
    _arriva("Uno")
    Organizzazione.objects.update(invio_email=False)
    assert avvisi.avvisa_nuova_posta(dal) == 0 and bot == []  # invio dei messaggi spento


def test_per_sms(addetto, monkeypatch):
    s = ServizioMessaggi(nome="SMS", tipo="twilio", account="AC", mittente="+1555", attivo=True)
    s.imposta_segreto("t")
    s.save()
    mandati = []
    monkeypatch.setattr(messaggi._Twilio, "invia", lambda self, n, t: mandati.append((n, t)) or "")
    addetto.avvisi_posta = "sms"
    addetto.save()
    dal = timezone.now()
    _arriva("Convocazione")
    assert avvisi.avvisa_nuova_posta(dal) == 1
    numero, testo = mandati[0]
    assert numero == "+393331234567" and "\n" not in testo and "Convocazione" in testo


def test_problemi(bot, addetto, crea_utente):
    u = crea_utente("senza", ruoli=["Addetto protocollo"])
    assert "scheda anagrafica" in avvisi.problema(u, "telegram")
    assert "non è attivo" in avvisi.problema(u, "sms")  # nessun servizio SMS attivo
    addetto.soggetto.telegram_chat_id = None
    addetto.soggetto.save()
    assert avvisi.problema(addetto) == "Telegram non ancora collegato"


def test_dopo_lo_scaricamento(monkeypatch, addetto):
    chiamate = []
    monkeypatch.setattr(posta, "scarica_casella", lambda c: 0)
    monkeypatch.setattr(avvisi, "avvisa_nuova_posta", lambda dal: chiamate.append(dal))
    CasellaPosta.objects.create(nome="E", server="s", utente="u")
    Organizzazione.objects.update(ricezione_posta=True)
    posta.scarica_tutte()
    assert len(chiamate) == 1


def test_pagina_personale(client, bot, addetto, crea_utente):
    client.force_login(addetto)
    pagina = client.get("/protocollo/posta/avvisi/").content.decode()
    assert "Telegram" in pagina and "Collegato dal" in pagina
    assert "Avvisi della posta" in client.get("/protocollo/posta/").content.decode()
    r = client.post("/protocollo/posta/avvisi/", {"azione": "prova"}, follow=True)
    assert "Avviso di prova inviato" in r.content.decode() and bot[-1][1]["chat_id"] == 77
    client.post("/protocollo/posta/avvisi/", {"azione": "salva", "canale": ""})
    addetto.refresh_from_db()
    assert addetto.avvisi_posta == ""
    # senza Telegram collegato: si genera il link personale
    nuovo = crea_utente("nuovo", ruoli=["Addetto protocollo"])
    nuovo.soggetto = Soggetto.objects.create(cognome="Verdi", nome="Anna")
    nuovo.save()
    client.force_login(nuovo)
    r = client.post("/protocollo/posta/avvisi/", {"azione": "salva", "canale": "telegram"},
                    follow=True)  # fmt: skip
    assert "non partono: Telegram non ancora collegato" in r.content.decode()
    r = client.post("/protocollo/posta/avvisi/", {"azione": "telegram"}, follow=True)
    assert "https://t.me/ancr_bot?start=" in r.content.decode()


def test_senza_permesso(client_ruolo):
    assert client_ruolo("Consigliere").get("/protocollo/posta/avvisi/").status_code == 403
