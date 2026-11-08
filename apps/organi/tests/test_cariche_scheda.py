# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Cariche sociali mostrate nella scheda del socio e in anagrafica
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from datetime import date

import pytest

from apps.anagrafica.models import Soggetto
from apps.organi.models import Carica, Organo, cariche_di
from apps.soci import servizi
from apps.soci.models import TipologiaSocio


@pytest.fixture
def socio_presidente(crea_utente):
    utente = crea_utente("seg", ruoli=["Segretario"])
    s = Soggetto.objects.create(tipo="persona", cognome="Rossi", nome="Mario")
    socio = servizi.ammetti_socio(s, TipologiaSocio.objects.get(nome="Ordinario"), utente)
    organo, _ = Organo.objects.get_or_create(nome="Consiglio di prova", defaults={"sigla": "CP"})
    Carica.objects.create(organo=organo, soggetto=s, ruolo="consigliere",
                          dal=date(2018, 1, 1), al=date(2021, 12, 31))  # fmt: skip
    Carica.objects.create(organo=organo, soggetto=s, ruolo="presidente", dal=date(2022, 1, 1))
    return socio


@pytest.mark.django_db
class TestCaricheNellaScheda:
    def test_ordine_in_corso_prima(self, socio_presidente):
        cariche = cariche_di(socio_presidente.soggetto)
        assert [c.ruolo for c in cariche] == ["presidente", "consigliere"]

    def test_scheda_socio(self, client_ruolo, socio_presidente):
        testo = client_ruolo("Consigliere").get(f"/soci/{socio_presidente.pk}/").content.decode()
        assert "Presidente · CP" in testo  # etichetta in testa
        assert "Cariche sociali" in testo and "conclusa" in testo and "dal 01/01/2018" in testo

    def test_scheda_anagrafica(self, client_ruolo, socio_presidente):
        r = client_ruolo("Consigliere").get(f"/anagrafica/{socio_presidente.soggetto.pk}/")
        assert "Cariche sociali" in r.content.decode()

    def test_senza_cariche_nessuna_sezione(self, client_ruolo, crea_utente):
        s = Soggetto.objects.create(tipo="persona", cognome="Bianchi")
        socio = servizi.ammetti_socio(s, TipologiaSocio.objects.get(nome="Ordinario"),
                                      crea_utente("x"))  # fmt: skip
        assert (
            "Cariche sociali"
            not in client_ruolo("Consigliere").get(f"/soci/{socio.pk}/").content.decode()
        )


@pytest.mark.django_db
class TestOrganigramma:
    def test_livelli(self, socio_presidente):
        from apps.organi.servizi import organigramma

        organo = Organo.objects.get(nome="Consiglio di prova")
        s = Soggetto.objects.create(tipo="persona", cognome="Verdi")
        Carica.objects.create(organo=organo, soggetto=s, ruolo="tesoriere", dal=date(2022, 1, 1))
        livelli = organigramma(organo)
        assert [[c.ruolo for c in riga] for riga in livelli] == [["presidente"], ["tesoriere"]]

    def test_pdf(self, client_ruolo, socio_presidente, settings, tmp_path):
        settings.MEDIA_ROOT = tmp_path
        organo = Organo.objects.get(nome="Consiglio di prova")
        client = client_ruolo("Consigliere")
        assert "Organigramma PDF" in client.get(f"/organi/{organo.pk}/").content.decode()
        r = client.get(f"/organi/{organo.pk}/organigramma/")
        assert r.status_code == 200 and r.content.startswith(b"%PDF")
        assert "organigramma_cp.pdf" in r["Content-Disposition"]

    def test_permesso(self, client_ruolo, socio_presidente):
        organo = Organo.objects.get(nome="Consiglio di prova")
        r = client_ruolo(username="senza_ruoli").get(f"/organi/{organo.pk}/organigramma/")
        assert r.status_code == 403


@pytest.mark.django_db
class TestFineCarica:
    def _carica(self):
        organo, _ = Organo.objects.get_or_create(nome="Consiglio fine", defaults={"sigla": "CF"})
        s = Soggetto.objects.create(tipo="persona", cognome="Bianchi", nome="Anna")
        return Carica.objects.create(organo=organo, soggetto=s, ruolo="presidente",
                                     dal=date(2025, 4, 20))  # fmt: skip

    def test_fine_oggi_esce_subito_dai_componenti(self, client_ruolo):
        from django.utils import timezone

        c = self._carica()
        client = client_ruolo("Segretario")
        oggi = timezone.localdate()
        r = client.post(f"/organi/cariche/{c.pk}/fine/", {"al": oggi.isoformat(), "motivo": "dimissioni"},
                        follow=True)  # fmt: skip
        assert "Fine della carica registrata" in r.content.decode()
        c.refresh_from_db()
        assert c.al == oggi and not c.in_carica
        assert c not in c.organo.cariche_al()
        assert "Bianchi Anna" not in cariche_di_testo(c.organo)
        # una seconda volta non si registra
        r = client.post(f"/organi/cariche/{c.pk}/fine/", {"al": oggi.isoformat(), "motivo": "x"},
                        follow=True)  # fmt: skip
        assert "già terminata" in r.content.decode()
        c.refresh_from_db()
        assert c.note == "dimissioni"

    def test_data_non_valida_segnalata(self, client_ruolo):
        c = self._carica()
        r = client_ruolo("Segretario").post(f"/organi/cariche/{c.pk}/fine/", {"al": "boh"},
                                            follow=True)  # fmt: skip
        assert "Fine carica non registrata" in r.content.decode()
        c.refresh_from_db()
        assert c.al is None


def cariche_di_testo(organo):
    from apps.organi.servizi import organigramma

    return " ".join(c.soggetto.nome_completo for riga in organigramma(organo) for c in riga)
