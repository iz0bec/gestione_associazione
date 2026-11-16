# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test delle liste in Excel: esportazione, modifica fuori linea e
# *              reimportazione con anteprima, abbinamento all'anagrafica, schede nuove.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from openpyxl import load_workbook

from apps.anagrafica.models import Categoria, Soggetto
from apps.comunicazioni import scambio_liste
from apps.comunicazioni.models import Lista
from apps.core.models import EventoAudit

pytestmark = pytest.mark.django_db


@pytest.fixture
def utente(crea_utente):
    return crea_utente("segr", ruoli=["Segretario"])


def persona(cognome, email=None, **extra):
    return Soggetto.objects.create(
        cognome=cognome, nome="Mario", email=email or f"{cognome.lower()}@example.org", **extra
    )


def _file(contenuto):
    return load_workbook(io.BytesIO(contenuto))


def _salva(wb):
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


@pytest.fixture
def lista():
    cat, _ = Categoria.objects.get_or_create(nome="Autorità")
    lista = Lista.objects.create(nome="Cerimonia", descrizione="4 novembre", soci_attivi=True)
    lista.categorie.add(cat)
    lista.soggetti.add(persona("Rossi"), persona("Bianchi"))
    return lista


class TestEsportazione:
    def test_fogli_e_valori(self, lista, utente):
        wb = _file(scambio_liste.esporta(lista, utente))
        assert wb.sheetnames == ["Lista", "Persone", "Destinatari", "Istruzioni"]
        valori = {r[0]: r[1] for r in wb["Lista"].iter_rows(min_row=2, values_only=True)}
        assert valori["Codice lista"] == lista.pk and valori["Nome"] == "Cerimonia"
        assert (
            valori["Tutti i soci attivi"] == "sì"
            and valori["Categorie dell'anagrafica"] == "Autorità"
        )
        cognomi = [r[2] for r in wb["Persone"].iter_rows(min_row=2, values_only=True)]
        assert cognomi == ["Bianchi", "Rossi"]
        assert EventoAudit.objects.filter(azione="esportazione").exists()

    def test_nessuna_formula(self, utente):
        lista = Lista.objects.create(nome="=SOMMA(A1)")
        wb = _file(scambio_liste.esporta(lista, utente))
        assert wb["Lista"]["B3"].data_type == "s"


class TestImportazione:
    def test_modifica_fuori_linea(self, lista, utente):
        verdi = persona("Verdi", codice_fiscale="RSSMRA80A01H501U")
        wb = _file(scambio_liste.esporta(lista, utente))
        ws = wb["Lista"]
        ws["B3"] = "Cerimonia 2026"
        ws["B5"] = "no"
        ws["B8"] = "Autorità; Inesistente"
        wp = wb["Persone"]
        wp.delete_rows(3)  # Rossi
        wp.append([None, None, None, None, "rssmra80a01h501u", None])  # Verdi per codice fiscale
        wp.append([None, None, "Ignoto", "Ugo", None, "ignoto@example.org"])
        piano = scambio_liste.prepara(scambio_liste.leggi(_salva(wb)))
        assert piano.lista == lista and piano.nome == "Cerimonia 2026"
        assert piano.riepilogo()["non_trovata"] == 1
        assert [s.cognome for s in piano.tolte] == ["Rossi"]
        assert any("Inesistente" in a for a in piano.avvisi)
        lista.refresh_from_db()
        assert lista.nome == "Cerimonia"  # l'anteprima non salva

        scambio_liste.applica(piano, utente)
        lista.refresh_from_db()
        assert lista.nome == "Cerimonia 2026" and not lista.soci_attivi
        assert set(lista.soggetti.values_list("cognome", flat=True)) == {"Bianchi", "Verdi"}
        assert verdi in lista.soggetti.all()
        assert not Soggetto.objects.filter(cognome="Ignoto").exists()

    def test_crea_schede_e_lista_nuova(self, lista, utente):
        wb = _file(scambio_liste.esporta(lista, utente))
        wb["Lista"]["B2"] = None  # senza codice: lista nuova
        wb["Lista"]["B3"] = "Autorità locali"
        wb["Persone"].append([None, "ente", "Comune di Prova", None, None, "comune@example.org"])
        wb["Persone"].append([None, "persona", "", "Senza cognome", None, None])
        piano = scambio_liste.prepara(scambio_liste.leggi(_salva(wb)), crea_schede=True)
        assert piano.nuova
        assert piano.riepilogo()["nuova"] == 1 and piano.riepilogo()["scartata"] == 1
        nuova, creati = scambio_liste.applica(piano, utente)
        assert creati == 1 and nuova.pk != lista.pk
        ente = Soggetto.objects.get(denominazione="Comune di Prova")
        assert ente.tipo == "ente" and ente in nuova.soggetti.all()

    def test_nome_di_un_altra_lista(self, lista, utente):
        Lista.objects.create(nome="Altra")
        wb = _file(scambio_liste.esporta(lista, utente))
        wb["Lista"]["B3"] = "altra"
        with pytest.raises(scambio_liste.FileNonValido, match="Altra"):
            scambio_liste.prepara(scambio_liste.leggi(_salva(wb)))

    def test_email_ambigua(self, lista, utente):
        persona("Uno", email="casa@example.org")
        persona("Due", email="casa@example.org")
        wb = _file(scambio_liste.esporta(lista, utente))
        wb["Persone"].append([None, None, "Chi", None, None, "casa@example.org"])
        piano = scambio_liste.prepara(scambio_liste.leggi(_salva(wb)))
        assert piano.riepilogo()["ambigua"] == 1

    def test_file_non_valido(self):
        with pytest.raises(scambio_liste.FileNonValido):
            scambio_liste.leggi(b"non un excel")


class TestViste:
    def test_esporta_anteprima_conferma(self, client, lista, utente):
        client.force_login(utente)
        risposta = client.get(reverse("comunicazioni:lista_esporta", args=[lista.pk]))
        assert risposta.status_code == 200
        assert "attachment" in risposta["Content-Disposition"]
        wb = _file(risposta.content)
        wb["Lista"]["B4"] = "Nuova descrizione"
        url = reverse("comunicazioni:lista_importa")
        file = SimpleUploadedFile("lista.xlsx", _salva(wb))
        risposta = client.post(url, {"file": file})
        assert risposta.status_code == 200 and "Anteprima" in risposta.content.decode()
        lista.refresh_from_db()
        assert lista.descrizione == "4 novembre"
        risposta = client.post(url, {"azione": "esegui"})
        assert risposta.status_code == 302
        lista.refresh_from_db()
        assert lista.descrizione == "Nuova descrizione"
        # anteprima già usata
        risposta = client.post(url, {"azione": "esegui"})
        assert risposta.status_code == 302 and risposta.url == url

    def test_pagine(self, client, lista, utente):
        client.force_login(utente)
        assert client.get(reverse("comunicazioni:lista_importa")).status_code == 200
        pagina = client.get(reverse("comunicazioni:lista", args=[lista.pk])).content.decode()
        assert reverse("comunicazioni:lista_esporta", args=[lista.pk]) in pagina
