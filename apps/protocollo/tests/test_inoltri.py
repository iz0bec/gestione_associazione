# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test dell'inoltro dei messaggi di una casella: destinatari scelti, riservati solo
# *              all'incaricato, reindirizzo trasparente e ripiego con l'originale allegato, coda.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import smtplib
from datetime import timedelta

import pytest
from django.core import mail
from django.utils import timezone

from apps.anagrafica.models import Soggetto
from apps.core.models import EventoAudit, Organizzazione
from apps.protocollo import inoltri
from apps.protocollo.models import CasellaPosta, InoltroMessaggio, MessaggioRicevuto
from apps.protocollo.posta import salva_messaggio

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def ambiente(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    settings.MAILERS = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}
    Organizzazione.objects.update_or_create(pk=1, defaults={"invio_email": True})


def eml(oggetto="Convocazione", mittente="federazione@example.org", extra="", n=1):
    return (f"From: Federazione <{mittente}>\r\nTo: sezione@example.org\r\nSubject: {oggetto}\r\n"
            f"Message-ID: <m{n}-{oggetto[:5].replace(' ', '')}@example.org>\r\n{extra}"
            "Date: Mon, 23 Nov 2026 10:00:00 +0100\r\n\r\nTesto del messaggio.\r\n").encode()  # fmt: skip


@pytest.fixture
def casella():
    presidente = Soggetto.objects.create(tipo="persona", cognome="Rossi", nome="Mario",
                                         email="presidente@example.org")  # fmt: skip
    segretario = Soggetto.objects.create(tipo="persona", cognome="Verdi", nome="Anna",
                                         email="segretario@example.org")  # fmt: skip
    c = CasellaPosta.objects.create(nome="Sezione", server="imap.example.org",
                                    utente="sezione@example.org",
                                    inoltro_indirizzi="altro@example.org\nsezione@example.org",
                                    inoltro_incaricato=presidente)  # fmt: skip
    c.inoltro_destinatari.set([presidente, segretario])
    inoltri.attiva(c, True)
    c.save()
    return c


def test_destinatari_e_riservati(casella):
    vecchio = salva_messaggio(casella, eml("Prima dell'attivazione", n=0))
    MessaggioRicevuto.objects.filter(pk=vecchio.pk).update(
        scaricato_il=casella.inoltro_dal - timedelta(minutes=1)
    )
    salva_messaggio(casella, eml("Circolare"))
    salva_messaggio(casella, eml("Accesso al gestionale per conto di Luca Gialli - ANCR"))
    salva_messaggio(casella, eml("Credenziali", extra="X-Gestione-Riservato: per-conto\r\n"))
    assert inoltri.prepara(casella) == 3 + 1 + 1
    circolare = {i.email for i in InoltroMessaggio.objects.filter(messaggio__oggetto="Circolare")}
    # mai alla casella stessa; gli indirizzi scritti a mano si aggiungono
    assert circolare == {"presidente@example.org", "segretario@example.org", "altro@example.org"}
    riservati = InoltroMessaggio.objects.filter(riservato=True)
    assert riservati.count() == 2 and {i.email for i in riservati} == {"presidente@example.org"}
    assert not InoltroMessaggio.objects.filter(messaggio=vecchio).exists()
    assert inoltri.prepara(casella) == 0  # rieseguibile


def test_senza_incaricato_i_riservati_restano(casella):
    casella.inoltro_incaricato = None
    casella.save()
    salva_messaggio(casella, eml("Credenziali per conto di Luca"))
    assert inoltri.prepara(casella) == 0
    assert MessaggioRicevuto.objects.get().inoltro_esaminato


def test_reindirizzo_trasparente(casella):
    salva_messaggio(casella, eml("Circolare"))
    inoltri.prepara(casella)
    assert inoltri.invia_coda() == 3
    m = next(x for x in mail.outbox if x.to == ["segretario@example.org"])
    assert m.subject == "Circolare" and "federazione@example.org" in m.from_email
    assert m.extra_headers["Resent-From"] and "Testo del messaggio" in m.body
    assert set(InoltroMessaggio.objects.values_list("modo", flat=True)) == {"trasparente"}


def test_ripiego_con_originale_allegato(casella, monkeypatch):
    def rifiuta(*args):
        raise smtplib.SMTPSenderRefused(553, b"sender not owned", "federazione@example.org")

    monkeypatch.setattr(inoltri, "_reindirizza", rifiuta)
    salva_messaggio(casella, eml("Circolare"))
    inoltri.prepara(casella)
    inoltri.invia_coda()
    m = mail.outbox[0]
    assert m.subject == "Inoltro: Circolare" and m.reply_to == ["federazione@example.org"]
    assert m.attachments[0][0] == "messaggio-originale.eml"
    assert b"Testo del messaggio" in m.message().as_bytes()  # serializzabile per l'SMTP
    assert InoltroMessaggio.objects.filter(modo="allegato", stato="inoltrato").count() == 3


def test_errori_e_invio_spento(casella, monkeypatch):
    salva_messaggio(casella, eml("Circolare"))
    inoltri.prepara(casella)
    Organizzazione.objects.update(invio_email=False)
    assert inoltri.invia_coda() == 0 and mail.outbox == []
    Organizzazione.objects.update(invio_email=True)

    def guasto(*args):
        raise OSError("rete assente")

    monkeypatch.setattr(inoltri, "_reindirizza", guasto)
    for _ in range(inoltri.TENTATIVI_MASSIMI):
        inoltri.invia_coda()
    i = InoltroMessaggio.objects.first()
    assert i.stato == "errore" and "rete assente" in i.errore


def test_comunicazione_per_conto_riservata(crea_utente):
    from apps.comunicazioni import servizi as comunicazioni
    from apps.comunicazioni.models import Invio

    u = crea_utente("capo")
    invio = comunicazioni.crea_invio(u, oggetto="Prova", corpo="x", finalita="istituzionale",
                                     indirizzi=[("Sezione", "sezione@example.org")])  # fmt: skip
    Invio.objects.filter(pk=invio.pk).update(riservato=True)
    invio.refresh_from_db()
    email = comunicazioni.messaggio(invio, invio.destinatari.get())
    assert email.extra_headers["X-Gestione-Riservato"] == "per-conto"


def test_pagina_inoltro(client_ruolo, casella):
    c = client_ruolo("Amministratore di sistema")
    url = f"/sistema/posta/caselle/{casella.pk}/inoltro/"
    assert "Incaricato della trattazione" in c.get(url).content.decode()
    trovati = c.get("/sistema/posta/inoltro/cerca/?nome=inoltro_incaricato&cerca=Rossi")
    assert "Mario" in trovati.content.decode() and "innerHTML" in trovati.content.decode()
    senza = Soggetto.objects.create(tipo="persona", cognome="Bianchi", nome="Luca")
    r = c.post(url, {"inoltro_attivo": "on", "inoltro_destinatari": [senza.pk]})
    assert "Senza email" in r.content.decode()
    r = c.post(url, {"inoltro_attivo": "on", "inoltro_indirizzi": "non-valido"})
    assert "Indirizzi non validi" in r.content.decode()
    casella.inoltro_attivo = False
    casella.inoltro_dal = None
    casella.save()
    pres = Soggetto.objects.get(cognome="Rossi")
    r = c.post(url, {"inoltro_attivo": "on", "inoltro_destinatari": [pres.pk],
                     "inoltro_incaricato": pres.pk})  # fmt: skip
    assert r.status_code == 302
    casella.refresh_from_db()
    assert casella.inoltro_attivo and casella.inoltro_dal >= timezone.now() - timedelta(minutes=1)
    assert list(casella.inoltro_destinatari.all()) == [pres]
    assert EventoAudit.objects.filter(oggetto_id=str(casella.pk)).exists()
    assert "inoltra a 1 indirizzo" in c.get("/sistema/posta/").content.decode()


def test_permesso(client_ruolo, casella):
    assert (
        client_ruolo("Segretario").get(f"/sistema/posta/caselle/{casella.pk}/inoltro/").status_code
        == 403
    )
