# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test degli spostamenti sulla casella IMAP dei messaggi scartati (cartella
# *              SCARTATA), ripristinati e ripuliti (cestino, mai per le PEC).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import email
import re
from email import policy
from email.message import EmailMessage

import pytest

from apps.protocollo import posta, servizi
from apps.protocollo.models import CasellaPosta, MessaggioRicevuto

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def cartella_media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def _email(n):
    m = EmailMessage()
    m["From"] = "Pubblicità <promo@example.org>"
    m["Subject"] = f"Offerta {n}"
    m["Message-ID"] = f"<offerta-{n}@example.org>"
    m["Date"] = "Mon, 16 Nov 2026 10:00:00 +0100"
    m.set_content("Compra subito.")
    return m.as_bytes()


class Imap:
    """Server finto: cartelle con UID, ricerca per Message-ID, MOVE dalla cartella scelta."""

    def __init__(self, messaggi, prefisso="INBOX.", cestino="INBOX.Trash", attributo_trash=True):
        self.prefisso, self.cestino, self.attributo_trash = prefisso, cestino, attributo_trash
        self.cartelle = {"INBOX": dict(messaggi)}
        if cestino:
            self.cartelle[cestino] = {}
        self.scelta = None

    def capability(self):
        return "OK", [b"IMAP4rev1 MOVE"]

    def namespace(self):
        return "OK", [f'(("{self.prefisso}" ".")) NIL NIL'.encode()]

    def list(self):
        righe = []
        for c in self.cartelle:
            attributi = "\\HasNoChildren" + (
                " \\Trash" if c == self.cestino and self.attributo_trash else ""
            )
            righe.append(f'({attributi}) "." "{c}"'.encode())
        return "OK", righe

    def select(self, cartella, readonly=False):
        nome = cartella.strip('"')
        if nome not in self.cartelle:
            return "NO", [b"inesistente"]
        self.scelta = nome
        return "OK", [str(len(self.cartelle[nome])).encode()]

    def status(self, cartella, cosa):
        return ("OK", [b"x"]) if cartella.strip('"') in self.cartelle else ("NO", [b"no"])

    def create(self, cartella):
        self.cartelle[cartella.strip('"')] = {}
        return "OK", [b""]

    def subscribe(self, cartella):
        return "OK", [b""]

    def uid(self, comando, *argomenti):
        cartella = self.cartelle[self.scelta]
        if comando == "SEARCH":
            if argomenti[1:3] == ("HEADER", "Message-ID"):
                cercato = argomenti[3].strip('"')
                trovati = [u for u, g in cartella.items()
                           if email.message_from_bytes(g, policy=policy.default)["Message-ID"]
                           == cercato]  # fmt: skip
                return "OK", [b" ".join(trovati)]
            return "OK", [b" ".join(cartella)]
        if comando == "FETCH":
            uid, cosa = argomenti
            if "SIZE" in cosa:
                return "OK", [f"1 (UID {uid.decode()} RFC822.SIZE 1000)".encode()]
            return "OK", [(b"1", cartella[uid])]
        if comando == "MOVE":
            insieme, destinazione = argomenti
            for u in insieme.split(","):
                self.cartelle[destinazione.strip('"')][u.encode()] = cartella.pop(u.encode())
            return "OK", [b""]
        raise AssertionError(comando)

    def logout(self):
        pass

    def oggetti(self, cartella):
        return sorted(
            email.message_from_bytes(g, policy=policy.default)["Subject"]
            for g in self.cartelle.get(cartella, {}).values()
        )


@pytest.fixture
def casella():
    return CasellaPosta.objects.create(nome="Email", server="imap.example.org", utente="u@x.it")


@pytest.fixture
def imap(monkeypatch):
    server = Imap({b"1": _email(1), b"2": _email(2), b"3": _email(3)})
    monkeypatch.setattr(posta, "_connetti", lambda c: server)
    return server


@pytest.fixture
def segretario(crea_utente):
    return crea_utente("segr", ruoli=["Segretario"])


def _messaggio(n):
    return MessaggioRicevuto.objects.get(oggetto=f"Offerta {n}")


def test_scartati_in_scartata_e_ritorno(casella, imap, segretario):
    assert posta.scarica_casella(casella) == 3
    assert imap.oggetti("INBOX.PROCESSATA") == ["Offerta 1", "Offerta 2", "Offerta 3"]
    servizi.scarta_messaggi(MessaggioRicevuto.objects.filter(oggetto__in=["Offerta 1",
                            "Offerta 2"]), segretario, "Pubblicità")  # fmt: skip
    assert _messaggio(1).spostare_in == "scartata"
    posta.scarica_casella(casella)  # lo spostamento avviene con lo scaricamento
    assert imap.oggetti("INBOX.SCARTATA") == ["Offerta 1", "Offerta 2"]
    assert imap.oggetti("INBOX.PROCESSATA") == ["Offerta 3"]
    m = _messaggio(1)
    assert (m.cartella_server, m.spostare_in, m.errore_server) == ("scartata", "", "")
    servizi.ripristina_messaggio(m, segretario)
    assert _messaggio(1).spostare_in == "processata"
    posta.scarica_casella(casella)
    assert imap.oggetti("INBOX.PROCESSATA") == ["Offerta 1", "Offerta 3"]
    assert _messaggio(1).cartella_server == ""


def test_ripristino_prima_dello_spostamento(casella, imap, segretario):
    posta.scarica_casella(casella)
    m = _messaggio(1)
    servizi.scarta_messaggio(m, segretario, "Pubblicità")
    servizi.ripristina_messaggio(m, segretario)
    assert _messaggio(1).spostare_in == ""  # era ancora in PROCESSATA: nulla da fare
    posta.scarica_casella(casella)
    assert "INBOX.SCARTATA" not in imap.cartelle


def test_ripulito_nel_cestino(casella, imap, segretario, django_capture_on_commit_callbacks):
    posta.scarica_casella(casella)
    servizi.scarta_messaggio(_messaggio(1), segretario, "Pubblicità")
    servizi.scarta_messaggio(_messaggio(2), segretario, "Pubblicità")
    posta.scarica_casella(casella)
    with django_capture_on_commit_callbacks(execute=True):
        servizi.ripulisci_messaggio(_messaggio(1), segretario, dal_server=True)
        servizi.ripulisci_messaggio(_messaggio(2), segretario)  # solo nel programma
    posta.scarica_casella(casella)
    assert imap.oggetti("INBOX.Trash") == ["Offerta 1"]
    assert imap.oggetti("INBOX.SCARTATA") == ["Offerta 2"]
    assert _messaggio(1).cartella_server == "cestino"


def test_cestino_riconosciuto_per_nome(casella, monkeypatch, segretario):
    server = Imap({b"1": _email(1)}, cestino="INBOX.Cestino", attributo_trash=False)
    monkeypatch.setattr(posta, "_connetti", lambda c: server)
    posta.scarica_casella(casella)
    servizi.scarta_messaggio(_messaggio(1), segretario, "x")
    servizi.ripulisci_messaggio(_messaggio(1), segretario, dal_server=True)
    posta.scarica_casella(casella)
    assert server.oggetti("INBOX.Cestino") == ["Offerta 1"]


def test_senza_cestino_resta_e_lo_dice(casella, monkeypatch, segretario):
    server = Imap({b"1": _email(1)}, cestino=None)
    monkeypatch.setattr(posta, "_connetti", lambda c: server)
    posta.scarica_casella(casella)
    servizi.scarta_messaggio(_messaggio(1), segretario, "x")
    servizi.ripulisci_messaggio(_messaggio(1), segretario, dal_server=True)
    posta.scarica_casella(casella)
    m = _messaggio(1)
    assert m.spostare_in == "cestino" and "cestino" in m.errore_server  # si riprova
    assert server.oggetti("INBOX.PROCESSATA") == ["Offerta 1"]  # resta dov'era


def test_pec_mai_nel_cestino(monkeypatch, segretario):
    pec = CasellaPosta.objects.create(nome="PEC", pec=True, server="imap.pec.it", utente="p@pec.it")
    server = Imap({b"1": _email(1)})
    monkeypatch.setattr(posta, "_connetti", lambda c: server)
    posta.scarica_casella(pec)
    servizi.scarta_messaggio(_messaggio(1), segretario, "x")
    servizi.ripulisci_messaggio(_messaggio(1), segretario, dal_server=True)
    posta.scarica_casella(pec)
    assert server.oggetti("INBOX.SCARTATA") == ["Offerta 1"] and not server.oggetti("INBOX.Trash")


def test_messaggio_sparito_dal_server(casella, imap, segretario):
    posta.scarica_casella(casella)
    servizi.scarta_messaggio(_messaggio(1), segretario, "x")
    imap.cartelle["INBOX.PROCESSATA"].pop(b"1")  # cancellato a mano dalla webmail
    posta.scarica_casella(casella)
    m = _messaggio(1)
    assert m.spostare_in == "" and re.search("non trovato", m.errore_server)


def test_cartella_vuota_niente_spostamento(imap, segretario):
    c = CasellaPosta.objects.create(nome="E", server="s", utente="u", cartella_scartata="")
    posta.scarica_casella(c)
    servizi.scarta_messaggio(_messaggio(1), segretario, "x")
    assert _messaggio(1).spostare_in == ""


def test_spunta_anche_dalla_casella(casella, imap, client_ruolo):
    client = client_ruolo("Segretario", username="s2")
    posta.scarica_casella(casella)
    servizi.scarta_messaggio(_messaggio(1), client.utente, "x")
    pagina = client.get("/protocollo/posta/?stato=scartato").content.decode()
    assert 'name="dal_server"' in pagina
    r = client.post("/protocollo/posta/azione/", {"azione": "ripulisci", "dal_server": "on",
                    "messaggi": [_messaggio(1).pk], "stato": "scartato"}, follow=True)  # fmt: skip
    assert "nel cestino al prossimo scaricamento" in r.content.decode()
    assert _messaggio(1).spostare_in == "cestino"
