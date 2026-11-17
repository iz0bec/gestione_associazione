# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test delle comunicazioni via PEC (canale per destinatario, servizio, ricevute)
# *              e su Telegram (collegamento con /start, invio, scollegamento).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from email.message import EmailMessage

import pytest
from django.core import mail
from django.urls import reverse

from apps.anagrafica.models import Soggetto
from apps.comunicazioni import servizi, telegram
from apps.comunicazioni.models import Finalita
from apps.core import invio as servizi_invio
from apps.core.cifratura import nuova_chiave
from apps.core.models import CanaleTelegram, Organizzazione, ServizioInvio
from apps.protocollo import posta
from apps.protocollo.models import CasellaPosta, MessaggioRicevuto

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def ambiente(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    settings.CHIAVE_CIFRATURA = nuova_chiave()
    settings.MAILERS = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}
    Organizzazione.objects.update_or_create(
        pk=1, defaults={"denominazione": "ANCR Avigliano", "invio_email": True}
    )


@pytest.fixture
def utente(crea_utente):
    return crea_utente("segr", ruoli=["Segretario"])


def _servizio(nome, tipo, indirizzo, **extra):
    s = ServizioInvio(nome=nome, tipo=tipo, indirizzo=indirizzo, server="smtps.example", **extra)
    s.imposta_password("x")
    s.save()
    return s


@pytest.fixture
def pec():
    return _servizio("PEC sezione", "pec", "sez@pec.example.it")


@pytest.fixture
def persone():
    return {
        "ente": Soggetto.objects.create(tipo="ente", denominazione="Comune",
                                        email="info@comune.it", pec="protocollo@pec.comune.it"),
        "solo_pec": Soggetto.objects.create(tipo="ente", denominazione="Prefettura",
                                            pec="prefettura@pec.interno.it"),
        "socio": Soggetto.objects.create(cognome="Rossi", nome="Mario", email="m@example.org"),
        "nessuno": Soggetto.objects.create(cognome="Verdi", nome="Anna"),
    }  # fmt: skip


def _crea(utente, soggetti, **extra):
    return servizi.crea_invio(utente, oggetto="Assemblea", corpo="Gentili, vi invitiamo.",
                              finalita=Finalita.ISTITUZIONALE, soggetti=soggetti, **extra)  # fmt: skip


def _per_nome(invio):
    return {d.nome: d for d in invio.destinatari.all()}


class TestPec:
    def test_canale_per_destinatario(self, utente, pec, persone):
        d = _per_nome(_crea(utente, persone.values(), servizio=pec))
        assert (d["Comune"].canale, d["Comune"].email) == ("pec", "protocollo@pec.comune.it")
        assert (d["Prefettura"].canale, d["Prefettura"].stato) == ("pec", "in_attesa")
        assert (d["Rossi Mario"].canale, d["Rossi Mario"].email) == ("email", "m@example.org")
        assert (d["Verdi Anna"].stato, d["Verdi Anna"].motivo) == ("escluso", "senza email")

    def test_senza_servizio_pec_solo_email(self, utente, persone):
        d = _per_nome(_crea(utente, persone.values()))
        assert d["Comune"].canale == "email" and d["Comune"].email == "info@comune.it"
        assert d["Prefettura"].stato == "escluso"  # ha solo la PEC: resta su carta

    def test_spedizione_dal_servizio_giusto(self, utente, pec, persone, monkeypatch):
        usati = []
        vero = servizi_invio.connessione
        monkeypatch.setattr(servizi_invio, "connessione",
                            lambda s=None: usati.append(s) or vero(s))  # fmt: skip
        invio = servizi.conferma(_crea(utente, [persone["ente"], persone["socio"]],
                                       servizio=pec), utente)  # fmt: skip
        assert servizi.elabora_coda() == (2, 0)
        assert set(usati) == {pec, None}  # la PEC per l'ente, il generale per il socio
        per_pec = next(m for m in mail.outbox if m.to[0].endswith("protocollo@pec.comune.it>"))
        assert "sez@pec.example.it" in per_pec.from_email and not per_pec.reply_to
        d = _per_nome(invio)["Comune"]
        assert d.message_id == per_pec.extra_headers["Message-ID"]
        assert d.message_id.endswith("@pec.example.it>")

    def test_servizio_email_non_generale(self, utente, persone):
        presidente = _servizio("Presidente", "email", "presidente@example.it")
        servizi.conferma(_crea(utente, [persone["socio"]], servizio=presidente), utente)
        servizi.elabora_coda()
        assert "presidente@example.it" in mail.outbox[0].from_email

    def test_ricevute_agganciate(self, utente, pec, persone):
        invio = servizi.conferma(_crea(utente, [persone["ente"]], servizio=pec), utente)
        servizi.elabora_coda()
        d = invio.destinatari.get()
        casella = CasellaPosta.objects.create(nome="PEC", pec=True, server="s", utente="u")

        def ricevuta(tipo, mid):
            m = EmailMessage()
            m["From"] = "posta-certificata@pec.example"
            m["Subject"] = f"{tipo.upper()}: Assemblea"
            m["Message-ID"] = mid
            m["X-Ricevuta"] = tipo
            m["X-Riferimento-Message-ID"] = d.message_id
            m.set_content("Ricevuta")
            return m.as_bytes()

        consegna = posta.salva_messaggio(casella, ricevuta("avvenuta-consegna", "<c@pec>"))
        posta.salva_messaggio(casella, ricevuta("accettazione", "<a@pec>"))
        d.refresh_from_db()
        assert d.esito_pec == "avvenuta-consegna" and d.esito_pec_testo == "consegnata"
        assert (
            consegna.stato == "scartato" and "comunicazione «Assemblea»" in consegna.motivo_scarto
        )
        assert consegna.spostare_in == "scartata"
        assert not MessaggioRicevuto.objects.da_esaminare().exists()

    def test_protocollata_come_pec(self, utente, pec, persone):
        invio = servizi.conferma(_crea(utente, [persone["ente"]], servizio=pec, protocolla=True),
                                 utente)  # fmt: skip
        servizi.elabora_coda()
        invio.refresh_from_db()
        assert invio.protocollo.mezzo == "pec"

    def test_modulo(self, client, utente, pec, persone):
        client.force_login(utente)
        pagina = client.get(reverse("comunicazioni:nuovo")).content.decode()
        assert "Spedisci da" in pagina and "PEC sezione" in pagina
        r = client.post(reverse("comunicazioni:nuovo"), {
            "oggetto": "Avviso", "corpo": "Testo", "finalita": "istituzionale",
            "soggetti": [persone["ente"].pk], "da": str(pec.pk),
        })  # fmt: skip
        assert r.status_code == 302
        assert persone["ente"].comunicazioni.get().canale == "pec"


class TestTelegram:
    @pytest.fixture
    def bot(self, monkeypatch):
        chiamate = []

        def finto(token, metodo, dati=None, documento=None):
            chiamate.append((metodo, dati, documento))
            if metodo == "getMe":
                return {"is_bot": True, "username": "ancr_bot"}
            if metodo == "getUpdates":
                return bot.aggiornamenti
            return {"message_id": 1}

        bot = type("Bot", (), {"aggiornamenti": [], "chiamate": chiamate})
        monkeypatch.setattr(telegram, "_chiama", finto)
        canale = CanaleTelegram.corrente()
        canale.imposta_token("123:abc")
        canale.nome_bot, canale.attivo = "ancr_bot", True
        canale.save()
        return bot

    def _start(self, bot, testo, chat=555):
        bot.aggiornamenti = [{"update_id": 10 + len(bot.chiamate), "message": {
            "chat": {"id": chat, "type": "private"}, "text": testo}}]  # fmt: skip
        telegram.leggi_comandi()

    def test_collegamento_e_scollegamento(self, bot, persone):
        socio = persone["socio"]
        link = telegram.link_invito(socio)
        socio.refresh_from_db()
        assert link == f"https://t.me/ancr_bot?start={socio.telegram_codice}"
        self._start(bot, f"/start {socio.telegram_codice}")
        socio.refresh_from_db()
        assert socio.telegram_chat_id == 555 and not socio.telegram_codice
        assert "Ciao Mario" in bot.chiamate[-1][1]["text"]
        assert CanaleTelegram.corrente().ultimo_update > 0
        self._start(bot, "/start codice-falso", chat=777)
        assert "link personale" in bot.chiamate[-1][1]["text"]
        self._start(bot, "/stop")
        socio.refresh_from_db()
        assert socio.telegram_chat_id is None

    def test_comunicazione_anche_su_telegram(self, bot, utente, persone):
        Soggetto.objects.filter(pk__in=[persone["socio"].pk, persone["nessuno"].pk]).update(
            telegram_chat_id=555)  # fmt: skip
        socio, nessuno = (Soggetto.objects.get(pk=persone[k].pk) for k in ("socio", "nessuno"))
        invio = _crea(utente, [socio, nessuno], telegram=True)
        d = _per_nome(invio)
        assert (
            d["Rossi Mario"].telegram_stato == "in_attesa" and d["Rossi Mario"].stato == "in_attesa"
        )
        assert d["Verdi Anna"].stato == "escluso" and d["Verdi Anna"].telegram_stato == "in_attesa"
        servizi._allega(invio, "invito.pdf", b"%PDF-1.4")
        servizi.conferma(invio, utente)
        assert servizi.elabora_coda() == (3, 0)  # un'email e due Telegram
        testi = [c[1]["text"] for c in bot.chiamate if c[0] == "sendMessage"]
        assert len(testi) == 2 and testi[0].startswith("Assemblea\n\nGentili")
        assert [c[2][0] for c in bot.chiamate if c[0] == "sendDocument"] == ["invito.pdf"] * 2
        invio.refresh_from_db()
        assert invio.stato == "inviato"
        assert all(x.telegram_stato == "inviato" for x in invio.destinatari.all())

    def test_solo_su_telegram_si_conferma(self, bot, utente, persone):
        Soggetto.objects.filter(pk=persone["nessuno"].pk).update(telegram_chat_id=9)
        nessuno = Soggetto.objects.get(pk=persone["nessuno"].pk)
        invio = servizi.conferma(_crea(utente, [nessuno], telegram=True), utente)
        assert invio.stato == "in_coda"

    def test_canale_spento_ignorato(self, bot, utente, persone):
        CanaleTelegram.objects.update(attivo=False)
        Soggetto.objects.filter(pk=persone["socio"].pk).update(telegram_chat_id=555)
        invio = _crea(utente, [persone["socio"]], telegram=True)
        assert not invio.telegram and invio.destinatari.get().telegram_stato == ""

    def test_pagine(self, bot, client_ruolo, persone):
        admin = client_ruolo("Amministratore di sistema")
        pagina = admin.get("/sistema/posta/").content.decode()
        assert "@ancr_bot" in pagina and "BotFather" in pagina
        r = admin.post("/sistema/posta/telegram/", {"azione": "token", "token": "999:nuovo"},
                       follow=True)  # fmt: skip
        assert "Bot @ancr_bot collegato" in r.content.decode()
        assert CanaleTelegram.corrente().token() == "999:nuovo"
        socio = persone["socio"]
        pagina = admin.get(socio.get_absolute_url()).content.decode()
        assert "Telegram non collegato" in pagina
        pagina = admin.get(reverse("comunicazioni:telegram_invito", args=[socio.pk])).content
        assert b"https://t.me/ancr_bot?start=" in pagina and b"<svg" in pagina
        Soggetto.objects.filter(pk=socio.pk).update(telegram_chat_id=1)
        admin.post(reverse("comunicazioni:telegram_scollega", args=[socio.pk]))
        socio.refresh_from_db()
        assert socio.telegram_chat_id is None
        pagina = admin.get(reverse("comunicazioni:nuovo")).content.decode()
        assert "Anche su Telegram" in pagina

    def test_anonimizzazione_toglie_telegram(self, persone, utente):
        from apps.anagrafica import gdpr

        s = persone["nessuno"]
        Soggetto.objects.filter(pk=s.pk).update(telegram_chat_id=42, telegram_codice="abc")
        s.refresh_from_db()
        gdpr.anonimizza(
            s, utente, motivo="richiesta dell'interessata", conferma=gdpr.PAROLA_CONFERMA
        )
        s.refresh_from_db()
        assert s.telegram_chat_id is None and s.telegram_codice == ""


def test_testo_lungo_diviso():
    pezzi = telegram._pezzi(("riga di prova\n" * 600).strip())
    assert len(pezzi) > 1 and all(len(p) <= telegram.LUNGHEZZA_MASSIMA for p in pezzi)
