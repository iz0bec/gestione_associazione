# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test dell'esenzione dal secondo fattore per singolo utente: accesso senza
# *              secondo fattore, scadenza, revoca, mai per l'Amministratore di sistema.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from datetime import timedelta

import pytest
from allauth.mfa.models import Authenticator
from django.contrib.auth.models import Group
from django.utils import timezone

from apps.accounts import servizi
from apps.accounts.models import PoliticaRuolo
from apps.core.models import EventoAudit

pytestmark = pytest.mark.django_db


@pytest.fixture
def tesoriere(crea_utente):
    for nome in ("Tesoriere", "Amministratore di sistema"):
        PoliticaRuolo.objects.create(ruolo=Group.objects.get(name=nome), mfa_obbligatoria=True)
    return crea_utente("tes", ruoli=["Tesoriere"])


@pytest.fixture
def admin(crea_utente):
    u = crea_utente("capo", ruoli=["Amministratore di sistema"])
    Authenticator.objects.create(user=u, type=Authenticator.Type.TOTP, data={})
    return u


def test_esentato_entra_senza_secondo_fattore(client, tesoriere, admin):
    client.force_login(tesoriere)
    assert client.get("/")["Location"] == "/account/2fa/"
    servizi.esenta_secondo_fattore(tesoriere, admin, "Non ha uno smartphone")
    assert client.get("/").status_code == 200
    evento = EventoAudit.objects.filter(oggetto_id=str(tesoriere.pk)).latest("momento")
    assert evento.dettagli["motivo"] == "Non ha uno smartphone"


def test_scadenza_e_revoca(tesoriere, admin):
    oggi = timezone.localdate()
    servizi.esenta_secondo_fattore(tesoriere, admin, "Temporanea", oggi + timedelta(days=3))
    assert not servizi.mfa_richiesta(tesoriere)
    assert servizi.esenzione_mfa_attiva(tesoriere, oggi + timedelta(days=3))
    assert not servizi.esenzione_mfa_attiva(tesoriere, oggi + timedelta(days=4))
    servizi.revoca_esenzione_mfa(tesoriere, admin)
    tesoriere.refresh_from_db()
    assert servizi.mfa_richiesta(tesoriere) and not tesoriere.mfa_esenzione_motivo


def test_mai_per_l_amministratore_ne_se_stessi(tesoriere, admin, crea_utente):
    altro = crea_utente("altro", ruoli=["Amministratore di sistema"])
    with pytest.raises(servizi.OperazioneNonValida, match="Amministratore"):
        servizi.esenta_secondo_fattore(altro, admin, "motivo")
    with pytest.raises(servizi.OperazioneNonValida, match="te stesso"):
        servizi.esenta_secondo_fattore(admin, admin, "motivo")
    with pytest.raises(servizi.OperazioneNonValida, match="motivo"):
        servizi.esenta_secondo_fattore(tesoriere, admin, "  ")
    with pytest.raises(servizi.OperazioneNonValida, match="passata"):
        servizi.esenta_secondo_fattore(tesoriere, admin, "x", timezone.localdate() - timedelta(1))
    # un'esenzione rimasta a chi diventa amministratore non vale
    servizi.esenta_secondo_fattore(tesoriere, admin, "x")
    tesoriere.groups.add(Group.objects.get(name="Amministratore di sistema"))
    assert servizi.mfa_richiesta(tesoriere)


def test_dalla_scheda_e_nell_elenco(client, tesoriere, admin):
    client.force_login(admin)
    scheda = client.get(f"/sistema/utenti/{tesoriere.pk}/").content.decode()
    assert "Esenta dal secondo fattore" in scheda
    fino = (timezone.localdate() + timedelta(days=30)).isoformat()
    r = client.post(f"/sistema/utenti/{tesoriere.pk}/esenzione-mfa/",
                    {"motivo": "Nessun telefono", "fino": fino})  # fmt: skip
    assert r.status_code == 302
    elenco = client.get("/sistema/utenti/").content.decode()
    assert "esentato fino al" in elenco and "Nessun telefono" in elenco
    assert "Revoca l'esenzione" in client.get(f"/sistema/utenti/{tesoriere.pk}/").content.decode()
    client.post(f"/sistema/utenti/{tesoriere.pk}/esenzione-mfa/", {"revoca": "1"})
    tesoriere.refresh_from_db()
    assert not tesoriere.mfa_esenzione_motivo
    # l'amministratore non mostra il modulo
    altro = client.get(f"/sistema/utenti/{admin.pk}/").content.decode()
    assert "Esenta dal secondo fattore" not in altro
