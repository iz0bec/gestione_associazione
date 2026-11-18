# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test delle azioni massive sull'elenco delle comunicazioni: conferma e invio,
# *              annullamento ed eliminazione delle bozze (mai di quelle già confermate).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import pytest
from django.core import mail

from apps.comunicazioni import servizi
from apps.comunicazioni.models import Invio
from apps.core.models import EventoAudit

pytestmark = pytest.mark.django_db


def _bozza(utente, n):
    return servizi.crea_invio(utente, oggetto=f"Avviso {n}", corpo="Testo", finalita="istituzionale",
                              indirizzi=[(f"Sezione {n}", f"sezione{n}@example.org")])  # fmt: skip


@pytest.fixture
def segreteria(client_ruolo):
    return client_ruolo("Amministratore di sistema")


def test_conferma_massiva(segreteria):
    bozze = [_bozza(segreteria.utente, n) for n in range(3)]
    r = segreteria.post("/comunicazioni/azione-massiva/",
                        {"azione": "conferma", "invii": [b.pk for b in bozze[:2]]})  # fmt: skip
    assert r.status_code == 302
    stati = dict(Invio.objects.values_list("oggetto", "stato"))
    assert stati["Avviso 2"] == "bozza" and stati["Avviso 0"] != "bozza"
    assert {m.to[0].split("<")[-1].rstrip(">") for m in mail.outbox} == {
        "sezione0@example.org",
        "sezione1@example.org",
    }


def test_annulla_ed_elimina(segreteria):
    a, b, c = (_bozza(segreteria.utente, n) for n in range(3))
    servizi.conferma(c, segreteria.utente)
    segreteria.post("/comunicazioni/azione-massiva/", {"azione": "annulla", "invii": [a.pk]})
    assert Invio.objects.get(pk=a.pk).stato == "annullato"
    r = segreteria.post("/comunicazioni/azione-massiva/",
                        {"azione": "elimina", "invii": [b.pk, c.pk]}, follow=True)  # fmt: skip
    assert not Invio.objects.filter(pk=b.pk).exists()
    assert Invio.objects.filter(pk=c.pk).exists()  # già confermata: non si elimina
    assert "Si eliminano solo le bozze" in r.content.decode()
    assert EventoAudit.objects.filter(
        azione="eliminazione", oggetto_descrizione="Bozza «Avviso 1»"
    ).exists()


def test_senza_permesso(client_ruolo):
    client = client_ruolo("Consigliere")
    bozza = _bozza(client.utente, 1)
    r = client.post("/comunicazioni/azione-massiva/", {"azione": "elimina", "invii": [bozza.pk]})
    assert r.status_code == 403 and Invio.objects.filter(pk=bozza.pk).exists()


def test_modifica_della_bozza(segreteria):
    bozza = _bozza(segreteria.utente, 1)
    destinatario = bozza.destinatari.get()
    r = segreteria.post(f"/comunicazioni/{bozza.pk}/modifica/", {
        "oggetto": "Avviso corretto", "corpo": "Gentile {{ nome_completo }}, testo nuovo",
        "togli": [destinatario.pk], "indirizzi": "Nuova sezione <nuova@example.org>",
    })  # fmt: skip
    assert r.status_code == 302
    bozza.refresh_from_db()
    assert bozza.oggetto == "Avviso corretto" and "testo nuovo" in bozza.corpo
    assert list(bozza.destinatari.values_list("email", flat=True)) == ["nuova@example.org"]
    assert EventoAudit.objects.filter(azione="modifica", oggetto_id=str(bozza.pk)).exists()
    r = segreteria.post(f"/comunicazioni/{bozza.pk}/modifica/",
                        {"oggetto": "X", "corpo": "{{ sconosciuto }}"})  # fmt: skip
    assert "Segnaposto sconosciuti" in r.content.decode()
    servizi.conferma(bozza, segreteria.utente)
    r = segreteria.get(f"/comunicazioni/{bozza.pk}/modifica/")
    assert r.status_code == 302  # confermata: non si modifica più


def test_seleziona_tutte_trova_le_caselle_collegate_al_modulo():
    """Le caselle dell'elenco stanno fuori dal <form> (attributo form=): lo script le deve
    cercare in tutta la pagina, non solo dentro il modulo."""
    from pathlib import Path

    from django.conf import settings

    script = (Path(settings.BASE_DIR) / "static/js/app.js").read_text()
    blocco = script[script.index("data-seleziona-tutte") : script.index("data-copia")]
    assert "document.querySelectorAll" in blocco and "c.form === modulo" in blocco


@pytest.mark.django_db(transaction=True)
def test_servizi_fuori_da_una_transazione(crea_utente):
    """Come in produzione (ATOMIC_REQUESTS spento): i servizi aprono da soli la transazione che
    serve a select_for_update. I test normali girano già dentro una transazione e non lo vedono."""
    from django.contrib.auth.models import Group

    from apps.accounts.ruoli import configura_ruoli

    if not Group.objects.exists():
        configura_ruoli()
    utente = crea_utente("fuori", ruoli=["Amministratore di sistema"])
    a, b, c = (_bozza(utente, n) for n in range(3))
    servizi.modifica_bozza(a, utente, oggetto="Nuovo", corpo="Testo")
    servizi.annulla(b, utente)
    servizi.elimina_bozza(c, utente)
    assert Invio.objects.get(pk=a.pk).oggetto == "Nuovo"
    assert Invio.objects.get(pk=b.pk).stato == "annullato"
    assert not Invio.objects.filter(pk=c.pk).exists()
