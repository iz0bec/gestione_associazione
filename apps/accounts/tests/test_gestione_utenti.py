# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test della gestione utenti dall'interfaccia
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import re

import pytest
from allauth.mfa.models import Authenticator
from django.contrib.auth.models import Group

from apps.accounts import servizi
from apps.accounts.models import PoliticaRuolo, Utente
from apps.core.models import EventoAudit

ADMIN = "Amministratore di sistema"


def _password_mostrata(risposta):
    return re.search(r'value="([A-Za-z0-9-]{19})" readonly', risposta.content.decode()).group(1)


def _dati(**extra):
    dati = {
        "username": "nuovo",
        "first_name": "Anna",
        "last_name": "Rossi",
        "email": "Anna@Example.org",
        "telefono": "",
        "groups": [Group.objects.get(name="Segretario").pk],
        "crea_scheda": "on",
    }
    dati.update(extra)
    return dati


@pytest.mark.django_db
class TestPermessi:
    def test_elenco_solo_con_permesso(self, client_ruolo):
        assert client_ruolo("Segretario").get("/sistema/utenti/").status_code == 403

    def test_elenco_e_ricerca(self, client_ruolo, crea_utente):
        client = client_ruolo(ADMIN)
        crea_utente("giulia", first_name="Giulia")
        crea_utente("pietro")
        r = client.get("/sistema/utenti/?q=giul", headers={"HX-Request": "true"})
        testo = r.content.decode()
        assert "giulia@example.org" in testo and "pietro@" not in testo
        assert "<html" not in testo  # solo il partial

    def test_pagine(self, client_ruolo, crea_utente):
        client = client_ruolo(ADMIN)
        u = crea_utente("scheda", ruoli=["Tesoriere"])
        Authenticator.objects.create(user=u, type=Authenticator.Type.WEBAUTHN, data={})
        testo = client.get(f"/sistema/utenti/{u.pk}/").content.decode()
        assert "passkey" in testo and "Azzera il secondo fattore" in testo
        assert client.get(f"/sistema/utenti/{client.utente.pk}/").status_code == 200
        assert client.get("/sistema/utenti/nuovo/").status_code == 200
        assert "Tesoriere" in client.get("/sistema/utenti/ruoli/").content.decode()

    def test_voce_di_menu(self, client_ruolo):
        assert "Utenti e ruoli" in client_ruolo(ADMIN).get("/").content.decode()


@pytest.mark.django_db
class TestCreazione:
    def test_crea_con_password_temporanea(self, client_ruolo):
        admin = client_ruolo(ADMIN)
        r = admin.post("/sistema/utenti/nuovo/", _dati())
        assert r.status_code == 200 and r["Cache-Control"] == "no-store"
        password = _password_mostrata(r)
        u = Utente.objects.get(username="nuovo")
        assert u.email == "anna@example.org"
        assert u.deve_cambiare_password and u.check_password(password)
        assert not u.is_staff and not u.is_superuser
        assert list(u.groups.values_list("name", flat=True)) == ["Segretario"]
        evento = EventoAudit.objects.filter(oggetto_id=str(u.pk)).latest("momento")
        assert password not in str(evento.dettagli)

    def test_crea_la_scheda_in_anagrafica(self, client_ruolo):
        client_ruolo(ADMIN).post("/sistema/utenti/nuovo/", _dati(telefono="333 1234567"))
        u = Utente.objects.get(username="nuovo")
        assert u.soggetto.cognome == "Rossi" and u.soggetto.email == "anna@example.org"
        assert u.soggetto.cellulare == "333 1234567"

    def test_scheda_obbligatoria(self, client_ruolo):
        dati = _dati()
        del dati["crea_scheda"]
        r = client_ruolo(ADMIN).post("/sistema/utenti/nuovo/", dati)
        assert "Scegliere la scheda" in r.content.decode()
        assert not Utente.objects.filter(username="nuovo").exists()

    def test_collega_un_socio_esistente(self, client_ruolo):
        from apps.anagrafica.models import Soggetto
        from apps.soci import servizi as soci
        from apps.soci.models import TipologiaSocio

        admin = client_ruolo(ADMIN)
        s = Soggetto.objects.create(tipo=Soggetto.Tipo.PERSONA, cognome="Verdi", nome="Ugo")
        socio = soci.ammetti_socio(s, TipologiaSocio.objects.get(nome="Ordinario"), admin.utente)
        dati = _dati(first_name="", last_name="", soggetto=s.pk)
        del dati["crea_scheda"]
        admin.post("/sistema/utenti/nuovo/", dati)
        u = Utente.objects.get(username="nuovo")
        assert u.soggetto == s and u.last_name == "Verdi"  # completato dalla scheda
        testo = admin.get("/sistema/utenti/").content.decode()
        assert f"socio n. {socio.numero}" in testo

    def test_email_duplicata(self, client_ruolo, crea_utente):
        crea_utente("esistente")
        r = client_ruolo(ADMIN).post("/sistema/utenti/nuovo/", _dati(email="ESISTENTE@example.org"))
        assert "già usata" in r.content.decode()


@pytest.mark.django_db
class TestObblighiAccesso:
    def test_password_temporanea_obbliga_al_cambio(self, client, crea_utente):
        u = crea_utente("temp", ruoli=["Consigliere"], deve_cambiare_password=True)
        client.force_login(u)
        r = client.get("/anagrafica/")
        assert r.status_code == 302 and r["Location"] == "/account/password/change/"
        assert client.get("/account/password/change/").status_code == 200
        r = client.post(
            "/account/password/change/",
            {
                "oldpassword": "Password-di-prova-123",
                "password1": "Una-nuova-Password-9",
                "password2": "Una-nuova-Password-9",
            },
        )
        assert r.status_code == 302
        u.refresh_from_db()
        assert not u.deve_cambiare_password

    def test_htmx_riceve_hx_redirect(self, client, crea_utente):
        client.force_login(crea_utente("temp", deve_cambiare_password=True))
        r = client.get("/anagrafica/", headers={"HX-Request": "true"})
        assert r.status_code == 204 and r["HX-Redirect"] == "/account/password/change/"

    def test_mfa_obbligatoria_per_ruolo(self, client, crea_utente):
        gruppo = Group.objects.get(name="Tesoriere")
        PoliticaRuolo.objects.create(ruolo=gruppo, mfa_obbligatoria=True)
        u = crea_utente("tes", ruoli=["Tesoriere"])
        client.force_login(u)
        r = client.get("/")
        assert r.status_code == 302 and r["Location"] == "/account/2fa/"
        Authenticator.objects.create(user=u, type=Authenticator.Type.TOTP, data={})
        assert client.get("/").status_code == 200

    def test_mfa_non_richiesta_ad_altri_ruoli(self, client, crea_utente):
        PoliticaRuolo.objects.create(
            ruolo=Group.objects.get(name="Tesoriere"), mfa_obbligatoria=True
        )
        client.force_login(crea_utente("cons", ruoli=["Consigliere"]))
        assert client.get("/").status_code == 200


@pytest.mark.django_db
class TestAzioni:
    def test_modifica_ruoli(self, client_ruolo, crea_utente):
        u = crea_utente("cambia", ruoli=["Consigliere"])
        admin = client_ruolo(ADMIN)
        r = admin.post(
            f"/sistema/utenti/{u.pk}/",
            _dati(username="cambia", email="cambia@example.org",
                  groups=[Group.objects.get(name="Revisore").pk]),
        )  # fmt: skip
        assert r.status_code == 302
        assert list(u.groups.values_list("name", flat=True)) == ["Revisore"]
        evento = EventoAudit.objects.filter(oggetto_id=str(u.pk), azione="modifica").get()
        assert "groups" in evento.dettagli["campi"]

    def test_non_si_toglie_la_gestione_utenti(self, client_ruolo):
        admin = client_ruolo(ADMIN)
        io = admin.utente
        r = admin.post(
            f"/sistema/utenti/{io.pk}/",
            _dati(username=io.username, email=io.email,
                  groups=[Group.objects.get(name="Consigliere").pk]),
        )  # fmt: skip
        assert r.status_code == 200 and "Non puoi toglierti" in r.content.decode()
        assert io.groups.filter(name=ADMIN).exists()

    def test_reimposta_password(self, client_ruolo, crea_utente):
        u = crea_utente("dimentica")
        r = client_ruolo(ADMIN).post(f"/sistema/utenti/{u.pk}/password/")
        password = _password_mostrata(r)
        u.refresh_from_db()
        assert u.check_password(password) and u.deve_cambiare_password

    def test_azzera_secondo_fattore(self, client_ruolo, crea_utente):
        u = crea_utente("telefono_perso")
        Authenticator.objects.create(user=u, type=Authenticator.Type.TOTP, data={})
        Authenticator.objects.create(user=u, type=Authenticator.Type.RECOVERY_CODES, data={})
        client_ruolo(ADMIN).post(f"/sistema/utenti/{u.pk}/secondo-fattore/")
        assert not Authenticator.objects.filter(user=u).exists()

    def test_disattiva_e_riattiva(self, client_ruolo, crea_utente):
        u = crea_utente("uscente")
        admin = client_ruolo(ADMIN)
        admin.post(f"/sistema/utenti/{u.pk}/attivo/", {"attivo": "0"})
        u.refresh_from_db()
        assert not u.is_active
        admin.post(f"/sistema/utenti/{u.pk}/attivo/", {"attivo": "1"})
        u.refresh_from_db()
        assert u.is_active

    def test_non_disattiva_se_stesso(self, client_ruolo):
        admin = client_ruolo(ADMIN)
        admin.post(f"/sistema/utenti/{admin.utente.pk}/attivo/", {"attivo": "0"})
        admin.utente.refresh_from_db()
        assert admin.utente.is_active

    def test_superutente_intoccabile_per_chi_non_lo_e(self, client_ruolo, django_user_model):
        su = django_user_model.objects.create_superuser("root", "root@example.org", "x-Y-z-123456")
        admin = client_ruolo(ADMIN)
        admin.post(f"/sistema/utenti/{su.pk}/attivo/", {"attivo": "0"})
        admin.post(f"/sistema/utenti/{su.pk}/password/")
        su.refresh_from_db()
        assert su.is_active and su.check_password("x-Y-z-123456")
        with pytest.raises(servizi.OperazioneNonValida):
            servizi.reimposta_password(su, admin.utente)


@pytest.mark.django_db
class TestRuoli:
    def test_imposta_mfa_obbligatoria(self, client_ruolo):
        admin = client_ruolo(ADMIN)
        tes = Group.objects.get(name="Tesoriere")
        admin.post("/sistema/utenti/ruoli/", {"ruoli": [tes.pk]})
        assert servizi.ruoli_con_mfa() == {tes.pk}
        admin.post("/sistema/utenti/ruoli/", {})
        assert servizi.ruoli_con_mfa() == set()
        assert (
            EventoAudit.objects.filter(oggetto_descrizione__startswith="Secondo fattore").count()
            == 2
        )

    def test_password_temporanea_robusta(self):
        p = servizi.password_temporanea()
        assert len(p) == 19 and p.count("-") == 3
        assert not set(p) & set("0O1lI")


@pytest.mark.django_db
class TestPasswordDallAmministratore:
    def test_imposta_password(self, client_ruolo, crea_utente):
        bianchi = crea_utente("bianchi", ruoli=["Segretario"])
        admin = client_ruolo(ADMIN, username="capo")
        assert "Imposta password" in admin.get(f"/sistema/utenti/{bianchi.pk}/").content.decode()
        r = admin.post(f"/sistema/utenti/{bianchi.pk}/imposta-password/",
                       {"password1": "Sezione-Avigliano-2026", "password2": "Diversa-2026-xyz"})  # fmt: skip
        assert r.status_code == 200 and "non coincidono" in r.content.decode()
        r = admin.post(f"/sistema/utenti/{bianchi.pk}/imposta-password/",
                       {"password1": "12345678", "password2": "12345678"})  # fmt: skip
        assert r.status_code == 200 and "password" in r.content.decode().lower()  # troppo debole
        r = admin.post(f"/sistema/utenti/{bianchi.pk}/imposta-password/", {
            "password1": "Sezione-Avigliano-2026", "password2": "Sezione-Avigliano-2026",
            "obbligo_cambio": "on"})  # fmt: skip
        assert r.status_code == 302
        bianchi.refresh_from_db()
        assert bianchi.check_password("Sezione-Avigliano-2026") and bianchi.deve_cambiare_password
        evento = EventoAudit.objects.filter(oggetto_id=str(bianchi.pk)).latest("pk")
        assert "Sezione-Avigliano-2026" not in str(evento.dettagli)

    def test_utente_che_non_puo_cambiarla(self, client, crea_utente, settings):
        from django.core import mail

        settings.MAILERS = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}
        u = crea_utente("rossi", ruoli=["Consigliere"])
        u.puo_cambiare_password = False
        u.save()
        client.force_login(u)
        assert "Cambia password" not in client.get("/").content.decode()
        r = client.get("/account/password/change/")
        assert r.status_code == 302 and r["Location"] == "/"
        client.logout()
        client.post("/account/password/reset/", {"email": u.email})
        assert mail.outbox == []  # niente recupero via email

    def test_obbligo_incompatibile_e_scheda(self, client_ruolo, crea_utente):
        u = crea_utente("verdi", ruoli=["Consigliere"])
        servizi.imposta_password(u, crea_utente("capo2", ruoli=[ADMIN]), "Password-Lunga-2026",
                                 obbligo_cambio=True)  # fmt: skip
        u.refresh_from_db()
        assert u.deve_cambiare_password
        u.puo_cambiare_password = False
        u.deve_cambiare_password = False
        u.save()
        servizi.imposta_password(u, Utente.objects.get(username="capo2"), "Password-Lunga-2027",
                                 obbligo_cambio=True)  # fmt: skip
        u.refresh_from_db()
        assert not u.deve_cambiare_password  # ignorato per chi non può cambiarla
