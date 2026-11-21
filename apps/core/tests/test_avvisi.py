# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test degli avvisi personali: domande di iscrizione (automatiche su Telegram,
# *              per sezione) e sicurezza (solo su scelta degli amministratori).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from datetime import date, timedelta

import pytest
from django.utils import timezone

from apps.anagrafica.models import Soggetto
from apps.comunicazioni import telegram
from apps.core import avvisi, sicurezza
from apps.core.audit import Azione, registra
from apps.core.cifratura import nuova_chiave
from apps.core.models import CanaleTelegram, EventoAudit, Organizzazione
from apps.soci.models import DomandaIscrizione, Sezione

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def ambiente(settings):
    settings.CHIAVE_CIFRATURA = nuova_chiave()
    settings.URL_PUBBLICO = "https://gestione.example.it"
    Organizzazione.objects.update_or_create(
        pk=1, defaults={"denominazione": "ANCR Avigliano", "invio_email": True}
    )


@pytest.fixture
def bot(monkeypatch):
    inviati = []

    def finto(token, metodo, dati=None, documento=None):
        inviati.append(dati)
        return {"is_bot": True, "username": "ancr_bot"} if metodo == "getMe" else {}

    monkeypatch.setattr(telegram, "_chiama", finto)
    canale = CanaleTelegram.corrente()
    canale.imposta_token("1:x")
    canale.nome_bot, canale.attivo = "ancr_bot", True
    canale.save()
    return inviati


@pytest.fixture
def con_telegram(crea_utente):
    def _crea(username, ruolo, chat, **extra):
        u = crea_utente(username, ruoli=[ruolo], **extra)
        u.soggetto = Soggetto.objects.create(cognome=username, nome="X", telegram_chat_id=chat)
        u.save()
        return u

    return _crea


def domanda(**extra):
    dati = {
        "nome": "Laura", "cognome": "Bianchi", "codice_fiscale": "BNCLRA80A41F205X",
        "data_nascita": date(1980, 1, 1), "luogo_nascita": "Milano", "indirizzo": "Via Roma 1",
        "cap": "20100", "comune": "Milano", "provincia": "MI", "accetta_statuto": True,
        "consenso_trattamento": True, "origine": "pubblica",
    }  # fmt: skip
    return DomandaIscrizione.objects.create(**{**dati, **extra})


class TestDomande:
    def test_a_chi_valuta_e_vede_la_sezione(
        self, bot, con_telegram, django_capture_on_commit_callbacks
    ):
        nord = Sezione.objects.create(nome="Nord", codice="N")
        sud = Sezione.objects.create(nome="Sud", codice="S")
        con_telegram("segretario", "Segretario", 1)
        con_telegram("presidente", "Presidente", 2)
        di_sud = con_telegram("pres_sud", "Presidente di sezione", 3)
        di_sud.sezioni.add(sud)
        con_telegram("addetto", "Addetto protocollo", 4)  # non valuta le domande
        rinuncia = con_telegram("rinuncia", "Segretario", 5)
        rinuncia.avvisi_domande = "no"
        rinuncia.save()
        with django_capture_on_commit_callbacks(execute=True):
            d = domanda(sezione=nord)
        assert sorted(x["chat_id"] for x in bot) == [1, 2]
        testo = bot[0]["text"]
        assert "nuova domanda di iscrizione" in testo and "Bianchi Laura, Milano (MI)" in testo
        assert "Modulo online · Nord" in testo
        assert testo.endswith(f"https://gestione.example.it/soci/domande/{d.pk}/")
        bot.clear()
        with django_capture_on_commit_callbacks(execute=True):
            d.email = "nuova@example.org"
            d.save()  # una modifica non è una domanda nuova
        assert bot == []

    def test_non_a_chi_la_registra(self, bot, con_telegram, django_capture_on_commit_callbacks):
        from apps.core.audit import contesto_richiesta

        autore = con_telegram("segretario", "Segretario", 1)
        con_telegram("presidente", "Presidente", 2)
        token = contesto_richiesta.set((autore, "127.0.0.1"))
        try:
            with django_capture_on_commit_callbacks(execute=True):
                domanda(origine="segreteria")
        finally:
            contesto_richiesta.reset(token)
        assert [x["chat_id"] for x in bot] == [2]

    def test_invio_spento(self, bot, con_telegram, django_capture_on_commit_callbacks):
        con_telegram("segretario", "Segretario", 1)
        Organizzazione.objects.update(invio_email=False)
        with django_capture_on_commit_callbacks(execute=True):
            domanda()
        assert bot == []


class TestSicurezza:
    @pytest.fixture
    def admin(self, con_telegram):
        u = con_telegram("capo", "Amministratore di sistema", 9)
        u.avvisi_sicurezza = "telegram"
        u.save()
        return u

    def test_solo_su_scelta(self, bot, con_telegram, admin):
        altro = con_telegram("altro", "Amministratore di sistema", 8)  # non ha scelto
        assert avvisi.canale_di(altro, "sicurezza") == ""
        assert [u for u, _ in avvisi.destinatari("sicurezza")] == [admin]

    def test_accessi_falliti_a_soglia(self, bot, admin, django_capture_on_commit_callbacks):
        with django_capture_on_commit_callbacks(execute=True):
            for _ in range(6):
                registra(Azione.ACCESSO_FALLITO, ip="203.0.113.9", descrizione="x")
                sicurezza.accesso_fallito("203.0.113.9", "mario")
        assert len(bot) == 1  # al quinto, non a ogni tentativo
        assert "5 accessi falliti in 15 minuti dall'indirizzo 203.0.113.9" in bot[0]["text"]

    def test_amministratore_da_indirizzo_nuovo(
        self, bot, admin, crea_utente, django_capture_on_commit_callbacks
    ):
        registra(Azione.ACCESSO, utente=admin, ip="198.51.100.1")
        with django_capture_on_commit_callbacks(execute=True):
            sicurezza.accesso(admin, "198.51.100.1")  # già noto
            sicurezza.accesso(crea_utente("cons", ruoli=["Consigliere"]), "192.0.2.7")
        assert bot == []
        EventoAudit.objects.update(momento=timezone.now() - timedelta(days=100))
        with django_capture_on_commit_callbacks(execute=True):
            sicurezza.accesso(admin, "198.51.100.1")  # non usato da 90 giorni
        assert "da un indirizzo nuovo: 198.51.100.1" in bot[0]["text"]

    def test_operazioni_sugli_utenti(
        self, bot, admin, con_telegram, crea_utente, django_capture_on_commit_callbacks
    ):
        from apps.accounts import servizi as utenti

        altro_admin = con_telegram("vice", "Amministratore di sistema", 7)
        altro_admin.avvisi_sicurezza = "telegram"
        altro_admin.save()
        mario = crea_utente("mario", ruoli=["Consigliere"])
        with django_capture_on_commit_callbacks(execute=True):
            utenti.reimposta_password(mario, admin)
        # chi ha fatto l'operazione non riceve l'avviso
        assert [x["chat_id"] for x in bot] == [7]
        assert "Password temporanea per mario (da capo" in bot[0]["text"]

    def test_lavoro_non_riuscito(self, bot, admin):
        sicurezza.lavoro_non_riuscito("backup", RuntimeError("disco pieno"))
        assert "Lavoro periodico «backup» non riuscito: disco pieno" in bot[0]["text"]

    def test_pagina_per_amministratore(self, client, bot, admin):
        client.force_login(admin)
        pagina = client.get("/avvisi/").content.decode()
        for tipo in ("Posta da protocollare", "Domande di iscrizione", "Sicurezza"):
            assert tipo in pagina
        client.post("/avvisi/", {"azione": "salva", "posta": "", "domande": "no",
                                 "sicurezza": ""})  # fmt: skip
        admin.refresh_from_db()
        assert (admin.avvisi_domande, admin.avvisi_sicurezza) == ("no", "")
        # «Nessuno» esplicito non esiste per la sicurezza: vuoto è già nessuno
        client.post("/avvisi/", {"azione": "salva", "sicurezza": "no"})
        admin.refresh_from_db()
        assert admin.avvisi_sicurezza == ""
