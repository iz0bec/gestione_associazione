# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test dell'allineamento automatico dei soci fra federazione e sezione (F4):
# *              attivazione dopo la prima verifica, ordine di tempo rispetto all'ultimo
# *              allineamento, incongruenze, avvisi email, modalità a spinta (POST /consegne).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from datetime import timedelta

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from apps.api.models import ClienteApi, VerificaSoci
from apps.collegamenti import soci as allineamento_soci
from apps.soci.models import Socio, Tessera

from . import test_verifica_soci as base
from .test_verifica_soci import ANNO, CF_BIANCHI, CF_ROSSI, _controparte, _remota, _socio

pytestmark = pytest.mark.django_db
# stesse fixture della verifica soci
_ambiente, admin, avigliano = base._ambiente, base.admin, base.avigliano


def _ore(n):
    return timezone.now() + timedelta(hours=n)


@pytest.fixture
def federazione_con_sezione(admin, avigliano, monkeypatch):
    """Siamo la federazione, collegata alla sezione di Avigliano con una prima verifica applicata
    (riferimento: un'ora fa)."""
    rossi = _socio(admin, avigliano, "Rossi", "Mario", CF_ROSSI, email="mario@example.org")
    _, sezione = _controparte("sezione", avigliano, ambiti=("soci:lettura", "consegne:scrittura"))
    VerificaSoci.objects.create(cliente=sezione, sezione=avigliano, da_sezione=True,
                                applicata_il=_ore(-1))  # fmt: skip
    allineamento_soci.attiva_automatico(sezione, admin)
    Socio.objects.filter(pk=rossi.pk).update(modificato_il=_ore(-2))
    rossi.soggetto.__class__.objects.filter(pk=rossi.soggetto_id).update(modificato_il=_ore(-2))
    righe = []
    monkeypatch.setattr(allineamento_soci, "scarica", lambda c: righe)
    return sezione, rossi, righe


def test_si_attiva_solo_dopo_una_verifica_applicata(admin, avigliano):
    _, sezione = _controparte("sezione", avigliano)
    with pytest.raises(allineamento_soci.OperazioneNonValida, match="Verifica soci"):
        allineamento_soci.attiva_automatico(sezione, admin)
    VerificaSoci.objects.create(cliente=sezione, sezione=avigliano, da_sezione=True,
                                applicata_il=_ore(-3))  # fmt: skip
    allineamento_soci.attiva_automatico(sezione, admin)
    sezione.refresh_from_db()
    assert sezione.allineamento_automatico
    assert abs((sezione.allineato_il - _ore(-3)).total_seconds()) < 5


def test_rinnovo_dalla_sezione_applicato_e_segnalato(federazione_con_sezione, admin):
    sezione, rossi, righe = federazione_con_sezione
    righe[:] = [
        _remota("Rossi", "Mario", CF_ROSSI, modificato=_ore(-0.5), email="mario@example.org",
                tessere=[{"anno": ANNO, "codice": "321", "pagata": True}]),
        _remota("Bianchi", "Laura", CF_BIANCHI, modificato=_ore(-0.5)),
    ]  # fmt: skip
    v = allineamento_soci.allinea(sezione)
    assert v.automatica and v.applicata_il
    assert v.proposta["conteggi"]["aggiornato"] == 1 and v.proposta["conteggi"]["creato"] == 1
    assert Tessera.objects.get(socio=rossi, anno=ANNO).carta.codice == "321"
    assert Socio.objects.filter(soggetto__codice_fiscale=CF_BIANCHI, sezione=sezione.sezione)
    # la federazione supervisiona: email a chi gestisce i soci
    assert [m.to for m in mail.outbox] == [[admin.email]]
    assert "Rossi Mario" in mail.outbox[0].body and "nuovo socio" in mail.outbox[0].body
    # giro successivo con gli stessi dati: nulla di nuovo, nessuna verifica né email
    assert allineamento_soci.allinea(sezione) is None
    assert len(mail.outbox) == 1


def test_cambiato_solo_qui_non_si_tocca(federazione_con_sezione):
    sezione, rossi, righe = federazione_con_sezione
    rossi.soggetto.email = "nuova-qui@example.org"
    rossi.soggetto.save()
    # la sezione ha ancora il valore vecchio, modificato prima dell'ultimo allineamento
    righe[:] = [_remota("Rossi", "Mario", CF_ROSSI, modificato=_ore(-2),
                        email="mario@example.org")]  # fmt: skip
    assert allineamento_soci.allinea(sezione) is None
    rossi.soggetto.refresh_from_db()
    assert rossi.soggetto.email == "nuova-qui@example.org"
    assert not mail.outbox


@pytest.mark.parametrize("remoto_piu_recente", [True, False])
def test_incongruenza_vale_la_modifica_piu_recente(federazione_con_sezione, remoto_piu_recente):
    sezione, rossi, righe = federazione_con_sezione
    rossi.soggetto.email = "qui@example.org"
    rossi.soggetto.save()  # modificato adesso
    momento = _ore(0.5) if remoto_piu_recente else _ore(-0.5)
    righe[:] = [_remota("Rossi", "Mario", CF_ROSSI, modificato=momento,
                        email="sezione@example.org")]  # fmt: skip
    v = allineamento_soci.allinea(sezione)
    voce = v.proposta["voci"][0]
    assert voce["allineamento"] == "conflitto" and v.proposta["conteggi"]["incongruenze"] == 1
    rossi.soggetto.refresh_from_db()
    if remoto_piu_recente:
        assert voce["vince"] == "controparte" and rossi.soggetto.email == "sezione@example.org"
    else:
        assert voce["vince"] == "qui" and rossi.soggetto.email == "qui@example.org"
    assert mail.outbox[0].subject.startswith("Incongruenze nell'allineamento")


def test_escluso_segnalato_una_volta(federazione_con_sezione, admin):
    sezione, _, righe = federazione_con_sezione
    altra = sezione.sezione.__class__.objects.create(codice="009", nome="Ruoti")
    _socio(admin, altra, "Bianchi", "Laura", CF_BIANCHI)
    righe[:] = [_remota("Bianchi", "Laura", CF_BIANCHI, modificato=_ore(-0.5))]
    v = allineamento_soci.allinea(sezione)
    assert v.proposta["conteggi"]["da_verificare"] == 1 and "Ruoti" in mail.outbox[0].body
    assert allineamento_soci.allinea(sezione) is None  # nulla di nuovo dalla sezione


def test_errore_di_lettura_resta_sulla_controparte(federazione_con_sezione, monkeypatch):
    sezione, _, _ = federazione_con_sezione

    def guasto(c):
        raise allineamento_soci.OperazioneNonValida("Controparte non raggiungibile: prova")

    monkeypatch.setattr(allineamento_soci, "scarica", guasto)
    esiti = allineamento_soci.allinea_tutti()
    assert esiti[sezione.nome].startswith("errore")
    sezione.refresh_from_db()
    assert "non raggiungibile" in sezione.allineamento_errore


class TestSpinta:
    def test_senza_automatico_resta_da_decidere(self, admin, avigliano):
        _socio(admin, avigliano, "Rossi", "Mario", CF_ROSSI)
        _, sezione = _controparte("sezione", avigliano, ambiti=("consegne:scrittura",))
        dati = {"flusso": "soci", "soci": [_remota("Bianchi", "Laura", CF_BIANCHI)]}
        esito = allineamento_soci.ricevi_consegna(sezione, dati)
        assert esito["applicazione"] == "in_anteprima" and esito["conteggi"]["nuovo"] == 1
        assert len(mail.outbox) == 1 and "da verificare" in mail.outbox[0].subject
        allineamento_soci.ricevi_consegna(sezione, dati)  # nuovo invio: sostituisce, senza email
        v = VerificaSoci.objects.get(cliente=sezione)
        assert v.origine == "spinta" and v.righe and not v.applicata_il
        assert len(mail.outbox) == 1
        # applicata a mano: poi si può accendere l'automatico
        allineamento_soci.applica(v, [0], admin)
        allineamento_soci.attiva_automatico(sezione, admin)

    def test_endpoint_con_automatico(self, client, admin, avigliano):
        ctp, sezione = _controparte("sezione", avigliano, ambiti=("consegne:scrittura",))
        VerificaSoci.objects.create(cliente=sezione, sezione=avigliano, da_sezione=True,
                                    applicata_il=_ore(-1))  # fmt: skip
        allineamento_soci.attiva_automatico(sezione, admin)
        dati = {"flusso": "soci", "soci": [_remota("Bianchi", "Laura", CF_BIANCHI)]}
        r = ctp.cifrato(client, "POST", "/api/v1/consegne", dati,
                        extra={"Idempotency-Key": "spinta-di-prova-0001"})  # fmt: skip
        assert r.status_code == 200, r.content
        assert r.json()["applicazione"] == "automatica" and r.json()["conteggi"]["creato"] == 1
        assert Socio.objects.get(soggetto__codice_fiscale=CF_BIANCHI).sezione == avigliano

    def test_endpoint_rifiuta_chi_non_e_sezione(self, client, avigliano):
        ctp, _ = _controparte("federazione", ambiti=("consegne:scrittura",))
        r = ctp.cifrato(client, "POST", "/api/v1/consegne", {"flusso": "soci", "soci": []},
                        extra={"Idempotency-Key": "spinta-di-prova-0002"})  # fmt: skip
        assert r.status_code == 422

    def test_la_sezione_invia_solo_se_cambia(self, admin, monkeypatch):
        from apps.soci.models import Sezione

        _socio(admin, Sezione.predefinita(), "Rossi", "Mario", CF_ROSSI)
        _, federazione = _controparte("federazione")
        ClienteApi.objects.filter(pk=federazione.pk).update(allineamento_spinta=True)
        federazione.refresh_from_db()
        inviati = []

        class Risposta:
            stato = 200

        def chiama(cliente, metodo, percorso, corpo=None, **opzioni):
            inviati.append(corpo)
            return Risposta(), None, []

        monkeypatch.setattr(allineamento_soci.client, "chiama", chiama)
        monkeypatch.setattr(allineamento_soci.client, "json_risposta",
                            lambda r: {"flusso": "soci", "applicazione": "automatica"})  # fmt: skip
        assert allineamento_soci.spingi(federazione)["applicazione"] == "automatica"
        assert allineamento_soci.spingi(federazione) is None  # nulla di cambiato
        assert len(inviati) == 1 and inviati[0]["soci"][0]["codice_fiscale"] == CF_ROSSI
        assert "(spinta)" not in str(allineamento_soci.allinea_tutti())  # già inviato


def test_viste(client_ruolo, avigliano, monkeypatch):
    admin = client_ruolo("Amministratore di sistema")
    _, sezione = _controparte("sezione", avigliano)
    pagina = admin.get(reverse("api:controparte", args=[sezione.pk])).content.decode()
    assert "Attiva l'allineamento automatico" in pagina
    r = admin.post(reverse("api:allineamento", args=[sezione.pk, "attiva"]), follow=True)
    assert "Fare prima una Verifica soci" in r.content.decode()
    VerificaSoci.objects.create(cliente=sezione, sezione=avigliano, da_sezione=True,
                                applicata_il=_ore(-1))  # fmt: skip
    r = admin.post(reverse("api:allineamento", args=[sezione.pk, "attiva"]), follow=True)
    assert "Allineamento automatico attivato" in r.content.decode()
    monkeypatch.setattr(allineamento_soci, "scarica",
                        lambda c: [_remota("Bianchi", "Laura", CF_BIANCHI)])  # fmt: skip
    r = admin.post(reverse("api:allineamento", args=[sezione.pk, "ora"]), follow=True)
    contenuto = r.content.decode()
    assert "allineamento automatico" in contenuto and "creati: 1" in contenuto
    r = admin.post(reverse("api:allineamento", args=[sezione.pk, "disattiva"]), follow=True)
    sezione.refresh_from_db()
    assert not sezione.allineamento_automatico
