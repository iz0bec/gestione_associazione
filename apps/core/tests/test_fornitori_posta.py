# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test delle preimpostazioni dei fornitori di posta: elenco del programma, fornitori
# *              personalizzati, compilazione di caselle e servizi di invio, verifica dopo il salvataggio.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import json
from unittest import mock

import pytest

from apps.core import fornitori_posta
from apps.core.cifratura import nuova_chiave
from apps.core.models import EventoAudit, FornitorePosta, ServizioInvio
from apps.protocollo.models import CasellaPosta

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin(client_ruolo, settings):
    settings.CHIAVE_CIFRATURA = nuova_chiave()
    return client_ruolo("Amministratore di sistema")


def test_elenco_del_programma():
    nomi = {f["id"] for f in fornitori_posta.predefiniti()}
    assert {"aruba", "aruba-pec", "legalmail", "poste-pec", "gmail", "microsoft"} <= nomi
    aruba = fornitori_posta.trova("smtp", "aruba-pec")
    assert aruba["smtp"]["server"] == "smtps.pec.aruba.it" and aruba["pec"]
    for f in fornitori_posta.predefiniti():  # ogni voce ha almeno IMAP o SMTP con porta
        assert any(isinstance(f.get(r), dict) and f[r]["porta"] for r in fornitori_posta.RUOLI)


def test_personalizzati_in_cima_e_solo_per_il_ruolo():
    FornitorePosta.objects.create(nome="Posta del dominio", smtp_server="mail.esempio.it",
                                  smtp_porta=587, smtp_ssl=False)  # fmt: skip
    FornitorePosta.objects.create(nome="Spento", imap_server="x.it", attivo=False)
    smtp = fornitori_posta.scelte("smtp")
    assert smtp[0] == ("", "Altro (valori a mano)") and smtp[1][1] == "Posta del dominio"
    assert "Posta del dominio" not in dict(fornitori_posta.scelte("imap")).values()
    assert "Spento" not in json.dumps(fornitori_posta.scelte("imap"))
    dati = json.loads(fornitori_posta.per_il_modulo("smtp"))
    assert dati[smtp[1][0]] == {"server": "mail.esempio.it", "porta": 587, "ssl": False,
                                "pec": False, "nota": ""}  # fmt: skip


def test_servizio_compilato_dal_fornitore_senza_javascript(admin):
    with mock.patch("apps.core.invio.verifica", return_value="accesso riuscito") as verifica:
        r = admin.post("/sistema/posta/invio/nuovo/", {
            "fornitore": "aruba-pec", "nome": "PEC", "tipo": "email",
            "indirizzo": "sezione@pec.esempio.it", "porta": 25, "nuova_password": "segreta",
            "attivo": "on", "verifica": "on",
        })  # fmt: skip
    assert r.status_code == 302
    s = ServizioInvio.objects.get()
    assert (s.server, s.porta, s.ssl, s.tipo) == ("smtps.pec.aruba.it", 465, True, "pec")
    assert verifica.called  # verifica subito dopo il salvataggio


def test_server_scritto_a_mano_prevale(admin):
    admin.post("/sistema/posta/invio/nuovo/", {
        "fornitore": "aruba", "nome": "Altro", "tipo": "email", "indirizzo": "a@esempio.it",
        "server": "smtp.mio.it", "porta": 587, "nuova_password": "segreta", "attivo": "on",
    })  # fmt: skip
    assert ServizioInvio.objects.get().server == "smtp.mio.it"


def test_senza_server_ne_fornitore(admin):
    r = admin.post("/sistema/posta/invio/nuovo/", {
        "nome": "X", "tipo": "email", "indirizzo": "a@esempio.it", "porta": 465,
        "nuova_password": "segreta", "attivo": "on",
    })  # fmt: skip
    assert r.status_code == 200 and "scegliere un fornitore" in r.content.decode()


def test_casella_pec_dal_fornitore(admin):
    pagina = admin.get("/sistema/posta/caselle/nuova/").content.decode()
    assert "data-fornitore-posta" in pagina and "Legalmail" in pagina
    with mock.patch("apps.protocollo.posta.verifica_casella", return_value="ok") as verifica:
        admin.post("/sistema/posta/caselle/nuova/", {
            "fornitore": "legalmail", "nome": "PEC", "porta": 143, "utente": "a@legalmail.it",
            "cartella": "INBOX", "giorni": 30, "nuova_password": "segreta",
        })  # fmt: skip
    c = CasellaPosta.objects.get()
    assert (c.server, c.porta, c.ssl, c.pec) == ("mbox.cert.legalmail.it", 993, True, True)
    assert not verifica.called  # senza la spunta niente verifica


def test_gestione_dei_fornitori(admin):
    r = admin.post("/sistema/posta/fornitori/nuovo/", {"nome": "Vuoto", "imap_porta": 993,
                                                       "smtp_porta": 465, "attivo": "on"})  # fmt: skip
    assert "almeno il server" in r.content.decode()
    admin.post("/sistema/posta/fornitori/nuovo/", {
        "nome": "Comune", "imap_server": "imap.comune.it", "imap_porta": 993, "imap_ssl": "on",
        "smtp_porta": 465, "nota": "Chiedere all'ufficio CED", "attivo": "on",
    })  # fmt: skip
    f = FornitorePosta.objects.get()
    assert "Comune" in admin.get("/sistema/posta/").content.decode()
    assert "Chiedere all" in admin.get("/sistema/posta/caselle/nuova/").content.decode()
    assert EventoAudit.objects.filter(oggetto_id=str(f.pk), azione="creazione").exists()
    admin.post(f"/sistema/posta/fornitori/{f.pk}/elimina/")
    assert not FornitorePosta.objects.exists()


def test_permesso(client_ruolo):
    assert client_ruolo("Segretario").get("/sistema/posta/fornitori/nuovo/").status_code == 403
