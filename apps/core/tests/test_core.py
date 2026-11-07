# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test di numerazione, organizzazione, registro attività, sicurezza HTTP
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import threading

import pytest
from django.core.exceptions import PermissionDenied
from django.db import connection, transaction

from apps.core import audit
from apps.core.models import EventoAudit, Organizzazione, Sequenza
from apps.core.numerazione import TransazioneRichiesta, numero_formattato, prossimo_numero


@pytest.mark.django_db
class TestNumerazione:
    def test_progressiva_per_chiave_e_anno(self):
        with transaction.atomic():
            assert prossimo_numero("protocollo", 2026) == 1
            assert prossimo_numero("protocollo", 2026) == 2
            assert prossimo_numero("protocollo", 2027) == 1
            assert prossimo_numero("tessera", 2026) == 1

    def test_formato(self):
        with transaction.atomic():
            assert numero_formattato("protocollo", 2026) == "2026-00001"

    @pytest.mark.django_db(transaction=True)
    def test_fuori_transazione_errore(self):
        with pytest.raises(TransazioneRichiesta):
            prossimo_numero("protocollo", 2026)

    def test_rollback_non_consuma_il_numero(self):
        with pytest.raises(RuntimeError), transaction.atomic():
            prossimo_numero("protocollo", 2026)
            raise RuntimeError("salvataggio fallito")
        with transaction.atomic():
            assert prossimo_numero("protocollo", 2026) == 1


@pytest.mark.django_db(transaction=True)
def test_numerazione_concorrente_senza_duplicati():
    numeri, errori = [], []
    lock = threading.Lock()

    def lavoro():
        try:
            for _ in range(10):
                with transaction.atomic():
                    n = prossimo_numero("concorrenza", 2026)
                with lock:
                    numeri.append(n)
        except Exception as e:  # noqa: BLE001
            errori.append(e)
        finally:
            connection.close()

    threads = [threading.Thread(target=lavoro) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errori
    assert sorted(numeri) == list(range(1, 81))
    assert Sequenza.objects.get(chiave="concorrenza", anno=2026).ultimo_numero == 80


@pytest.mark.django_db
class TestOrganizzazione:
    def test_unica_riga(self):
        a = Organizzazione.corrente()
        Organizzazione(denominazione="Altra").save()
        assert Organizzazione.objects.count() == 1
        assert Organizzazione.corrente().pk == a.pk == 1

    def test_non_eliminabile(self):
        with pytest.raises(PermissionDenied):
            Organizzazione.corrente().delete()

    def test_modifica_solo_con_permesso(self, client_ruolo):
        assert client_ruolo("Consigliere").get("/organizzazione/").status_code == 403

    def test_modifica_registrata(self, client_ruolo):
        c = client_ruolo("Segretario")
        r = c.post(
            "/organizzazione/", {"denominazione": "ANCR Sezione di Prova", "provincia": "PZ"}
        )
        assert r.status_code == 302
        assert Organizzazione.corrente().denominazione == "ANCR Sezione di Prova"
        evento = EventoAudit.objects.get(azione="modifica")
        assert "denominazione" in evento.dettagli["campi"]


@pytest.mark.django_db
class TestRegistroAttivita:
    def test_evento_immutabile(self):
        e = audit.registra(audit.Azione.CREAZIONE, descrizione="prova")
        e.oggetto_descrizione = "alterato"
        with pytest.raises(PermissionDenied):
            e.save()
        with pytest.raises(PermissionDenied):
            e.delete()

    def test_accesso_registrato(self, client, crea_utente):
        crea_utente("anna")
        client.post("/account/login/", {"login": "anna", "password": "Password-di-prova-123"})
        assert EventoAudit.objects.filter(azione="accesso", utente_descrizione="anna").exists()

    def test_registro_visibile_solo_con_permesso(self, client_ruolo):
        assert client_ruolo("Tesoriere").get("/registro-attivita/").status_code == 403


@pytest.mark.django_db
class TestSicurezzaHttp:
    def test_salute(self, client):
        r = client.get("/salute/")
        assert r.status_code == 200 and r.content == b"ok"

    def test_pagine_richiedono_login(self, client):
        r = client.get("/")
        assert r.status_code == 302 and "/account/login/" in r["Location"]

    def test_intestazioni_di_sicurezza(self, client_ruolo):
        r = client_ruolo("Consigliere").get("/")
        csp = r["Content-Security-Policy"]
        assert "default-src 'self'" in csp and "script-src 'self'" in csp
        assert "unsafe-inline" not in csp and "unsafe-eval" not in csp
        assert "frame-ancestors 'none'" in csp
        assert r["X-Frame-Options"] == "DENY"
        assert r["X-Content-Type-Options"] == "nosniff"

    def test_nessuno_script_inline(self, client_ruolo):
        html = client_ruolo("Segretario").get("/").content.decode()
        assert "<script>" not in html and "onclick=" not in html
