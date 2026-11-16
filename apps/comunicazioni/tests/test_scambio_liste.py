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

    def test_destinatari_con_indirizzi_e_motivo(self, lista, utente):
        verdi = persona("Verdi", indirizzo="Via Roma 1", cap="85021", comune="Avigliano",
                        provincia="PZ")  # fmt: skip
        verdi.categorie.add(Categoria.objects.get(nome="Autorità"))
        lista.soggetti.add(verdi)
        wd = _file(scambio_liste.esporta(lista, utente))["Destinatari"]
        assert [c.value for c in wd[2]] == scambio_liste.COLONNE_DESTINATARI
        righe = {r[1]: r for r in wd.iter_rows(min_row=3, values_only=True)}
        assert righe["Verdi Mario"][3:8] == ("Via Roma 1", "85021", "Avigliano", "PZ", "IT")
        assert righe["Verdi Mario"][8] == "scelto, categoria Autorità"

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
        ws["B9"] = "Autorità; Inesistente"
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

    def test_indirizzi_postali(self, lista, utente):
        rossi = Soggetto.objects.get(cognome="Rossi")
        rossi.comune = "Avigliano"
        rossi.save()
        wb = _file(scambio_liste.esporta(lista, utente))
        wp = wb["Persone"]
        assert [c.value for c in wp[1]][6:] == [
            "Indirizzo",
            "CAP",
            "Comune",
            "Provincia",
            "Nazione",
        ]
        for riga in wp.iter_rows(min_row=2):
            if riga[2].value == "Rossi":
                riga[6].value, riga[7].value, riga[8].value = "Via Roma 1", 85021, "Potenza"
                riga[9].value = "pz"
            else:  # Bianchi
                riga[7].value = "123456"
        wp.append([None, "ente", "Prefettura", None, None, "pref@example.org",
                   "Piazza Mario Pagano", "85100", "Potenza", "PZ", "IT"])  # fmt: skip
        piano = scambio_liste.prepara(scambio_liste.leggi(_salva(wb)), crea_schede=True)
        esiti = {r.descrizione: r.dettaglio for r in piano.righe}
        assert "completerà: indirizzo, CAP, provincia" in esiti["Rossi Mario"]
        assert "diverso in anagrafica, non modificato: comune" in esiti["Rossi Mario"]
        assert "CAP «123456» non valido" in esiti["Bianchi Mario"]
        scambio_liste.applica(piano, utente)
        rossi.refresh_from_db()
        assert (rossi.indirizzo, rossi.cap, rossi.comune, rossi.provincia) == (
            "Via Roma 1", "85021", "Avigliano", "PZ")  # fmt: skip
        assert Soggetto.objects.get(cognome="Bianchi").cap == ""
        pref = Soggetto.objects.get(denominazione="Prefettura")
        assert (pref.cap, pref.comune, pref.provincia) == ("85100", "Potenza", "PZ")

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


@pytest.fixture
def due_sezioni(utente):
    from apps.soci import servizi as soci
    from apps.soci.models import Sezione, TipologiaSocio

    nord = Sezione.objects.create(codice="N", nome="Nord")
    sud = Sezione.objects.create(codice="S", nome="Sud")
    ordinario = TipologiaSocio.objects.get(nome="Ordinario")
    soci.ammetti_socio(persona("Alto"), ordinario, utente, sezione=nord)
    soci.ammetti_socio(persona("Basso"), ordinario, utente, sezione=sud)
    return nord, sud


class TestSezioni:
    def test_soci_di_una_sezione(self, utente, due_sezioni):
        from apps.comunicazioni import servizi

        nord, _ = due_sezioni
        lista = Lista.objects.create(nome="Nord", soci_attivi=True)
        assert {"Alto", "Basso"} <= set(
            servizi.soggetti_lista(lista).values_list("cognome", flat=True)
        )
        lista.sezioni.add(nord)
        assert list(servizi.soggetti_lista(lista).values_list("cognome", flat=True)) == ["Alto"]
        motivi = servizi.motivi_lista(lista)
        assert list(motivi.values()) == [["socio (Nord)"]]

    def test_excel_con_sezioni(self, utente, due_sezioni):
        nord, sud = due_sezioni
        lista = Lista.objects.create(nome="Nord", soci_attivi=True)
        lista.sezioni.add(nord)
        wb = _file(scambio_liste.esporta(lista, utente))
        valori = {r[0]: r for r in wb["Lista"].iter_rows(min_row=2, values_only=True)}
        assert valori["Sezioni dei soci"][1] == "Nord"
        wb["Lista"]["B7"] = "S; Ovest"  # per codice; Ovest non esiste
        piano = scambio_liste.prepara(scambio_liste.leggi(_salva(wb)))
        assert piano.sezioni == [sud] and any("Ovest" in a for a in piano.avvisi)
        scambio_liste.applica(piano, utente)
        assert list(lista.sezioni.all()) == [sud]

    def test_utente_limitato(self, client, crea_utente, due_sezioni):
        from apps.comunicazioni.forms import ListaForm

        nord, sud = due_sezioni
        limitato = crea_utente("nord", ruoli=["Segretario"])
        limitato.sezioni.add(nord)
        dati = {"nome": "Soci", "soci_attivi": "on"}
        form = ListaForm(dati, utente=limitato)
        assert list(form.fields["sezioni"].queryset) == [nord]
        assert not form.is_valid() and "sezioni" in form.errors  # sezione obbligatoria
        assert not ListaForm({**dati, "sezioni": [sud.pk]}, utente=limitato).is_valid()
        assert ListaForm({**dati, "sezioni": [nord.pk]}, utente=limitato).is_valid()
        # dal file: senza sezioni non si importa, quelle altrui sono ignorate
        lista = Lista.objects.create(nome="Tutti", soci_attivi=True)
        wb = _file(scambio_liste.esporta(lista, limitato))
        with pytest.raises(scambio_liste.FileNonValido, match="sezioni"):
            scambio_liste.prepara(scambio_liste.leggi(_salva(wb)), utente=limitato)
        wb["Lista"]["B7"] = "Nord; Sud"
        piano = scambio_liste.prepara(scambio_liste.leggi(_salva(wb)), utente=limitato)
        assert piano.sezioni == [nord] and any("Sud" in a for a in piano.avvisi)

    def test_modulo(self, client, utente, due_sezioni):
        client.force_login(utente)
        nord, _ = due_sezioni
        r = client.post(reverse("comunicazioni:lista_nuova"),
                        {"nome": "Nord", "soci_attivi": "on", "sezioni": [nord.pk]})  # fmt: skip
        assert r.status_code == 302
        lista = Lista.objects.get(nome="Nord")
        assert list(lista.sezioni.all()) == [nord]
        pagina = client.get(lista.get_absolute_url()).content.decode()
        assert "Tutti i soci attivi di Nord" in pagina


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
