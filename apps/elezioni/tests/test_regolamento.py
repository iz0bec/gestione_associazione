# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test della conformità al Regolamento: registro dei votanti e deleghe, schede di
# *              peso diverso, adempimenti, prima riunione e cooptazione, determinazioni e
# *              relazione del commissario, commissario amministrativo.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from datetime import time, timedelta

import pytest
from django.utils import timezone

from apps.elezioni import servizi
from apps.elezioni.models import Rinnovo
from apps.elezioni.tests.test_decadenza import sezione  # noqa: F401 (fixture)
from apps.elezioni.tests.test_rinnovo import (  # noqa: F401 (fixture)
    OGGI,
    ambiente,
    avvia,
    lista_completa,
    persona,
    sezionale,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def segretario(crea_utente):
    return crea_utente("segretario", ruoli=["Segretario"])


def convocato(segretario, profilo, iscritti):
    r = avvia(segretario, profilo)
    servizi.convoca(r, segretario, comunicazione=False)
    r.refresh_from_db()
    lista = lista_completa(r, segretario, [s.soggetto for s in iscritti[:4]])
    servizi.presenta_lista(lista, segretario)
    servizi.esamina_lista(lista, segretario, ammessa=True)
    return Rinnovo.objects.get(pk=r.pk), lista


def test_registro_dei_votanti(ambiente, segretario, sezionale):  # noqa: F811
    _, iscritti = ambiente
    r, lista = convocato(segretario, sezionale, iscritti)
    soci = [riga["socio"] for riga in r.aventi_diritto]
    a, b, c, d, e, f = soci
    with pytest.raises(servizi.OperazioneNonValida, match="non è presente"):
        servizi.registra_votanti(r, segretario, {a: ("delega", b)})
    with pytest.raises(servizi.OperazioneNonValida, match="Più di 2 deleghe"):
        servizi.registra_votanti(r, segretario, {a: ("presente", None), b: ("delega", a),
                                                 c: ("delega", a), d: ("delega", a)})  # fmt: skip
    r.refresh_from_db()
    assert servizi.registra_votanti(r, segretario, {
        a: ("presente", None), b: ("delega", a), c: ("delega", a), d: ("presente", None),
    }) == (2, 2)  # fmt: skip
    r.refresh_from_db()
    assert servizi.registro_usato(r)
    with pytest.raises(servizi.OperazioneNonValida, match="votanti del registro"):
        servizi.registra_esiti(r, segretario, {"votato_il": OGGI}, {lista.pk: 5})
    r = Rinnovo.objects.get(pk=r.pk)
    avvisi = servizi.registra_esiti(
        r,
        segretario,
        {"votato_il": OGGI, "voto_aperto": time(9), "voto_chiuso": time(13)},
        {lista.pk: 4},
    )
    r.refresh_from_db()
    assert (r.presenti, r.deleghe) == (2, 2) and "tre ore" in avvisi[0]
    assert b"%PDF" in servizi.pdf("aventi", r)[:8]
    assert e and f


def test_schede_di_peso_diverso():
    assert servizi.schede_per_peso(178) == [(100, 1), (50, 1), (10, 2), (5, 1), (1, 3)]
    assert servizi.descrivi_schede(0) == "-"


def test_adempimenti_prima_riunione_e_cooptazione(ambiente, segretario, sezionale):  # noqa: F811
    consiglio, iscritti = ambiente
    r, lista = convocato(segretario, sezionale, iscritti)
    servizi.segna_adempimento(r, segretario, "elenco_inviato_il", OGGI)
    with pytest.raises(servizi.OperazioneNonValida):
        servizi.segna_adempimento(r, segretario, "inventato", OGGI)
    assert {c: g for c, _, g in servizi.adempimenti(r)}["elenco_inviato_il"] == OGGI
    servizi.registra_esiti(r, segretario, {"votato_il": OGGI}, {lista.pk: 5})
    r.refresh_from_db()
    servizi.proclama(r, segretario)
    servizi.insedia(r, segretario, giorno=OGGI)
    r.refresh_from_db()
    quando = timezone.now() + timedelta(days=7)
    riunione = servizi.prepara_prima_riunione(r, segretario, quando=quando, luogo="Sede")
    assert riunione.organo == consiglio and riunione.punti.count() == 4
    assert "Insediamento" in riunione.punti.first().titolo
    with pytest.raises(servizi.OperazioneNonValida, match="già stata preparata"):
        servizi.prepara_prima_riunione(r, segretario, quando=quando, luogo="Sede")
    # cooptazione di un supplente (nominato a mano per la prova)
    from apps.organi.servizi import nomina

    supplente = nomina(consiglio, iscritti[5].soggetto, "supplente", OGGI, segretario)
    assert servizi.supplenti_in_carica(r) == [supplente]
    with pytest.raises(servizi.OperazioneNonValida, match="delibera"):
        servizi.coopta(supplente, segretario, giorno=OGGI, atto=" ")
    nuova = servizi.coopta(supplente, segretario, giorno=OGGI, atto="delibera n. 1")
    assert nuova.ruolo == "consigliere" and servizi.supplenti_in_carica(r) == []


def test_determinazioni_e_relazione(sezione, segretario, settings, tmp_path):  # noqa: F811
    alfa, consiglio, _, _ = sezione
    d = servizi.dichiara_decadenza(segretario, sezione=alfa, giorno=OGGI, motivo="scioglimento",
                                   commissario=persona("Commissario"))  # fmt: skip
    prima = servizi.nuova_determinazione(
        d,
        segretario,
        giorno=OGGI,
        oggetto="Apertura conto",
        testo="Determina di aprire il conto.",
        protocolla=True,
    )
    seconda = servizi.nuova_determinazione(
        d,
        segretario,
        giorno=OGGI,
        oggetto="Convocazione",
        testo="Determina di indire il congresso.",
    )
    assert (prima.numero, seconda.numero) == (1, 2) and prima.protocollo is not None
    assert servizi.pdf_determinazione(prima).startswith(b"%PDF")
    with pytest.raises(servizi.OperazioneNonValida, match="obbligatori"):
        servizi.nuova_determinazione(d, segretario, giorno=OGGI, oggetto="", testo="x")
    servizi.salva_relazione(d, segretario, testo="Ho riorganizzato la sezione.", giorno=OGGI,
                            protocolla=True)  # fmt: skip
    d.refresh_from_db()
    assert d.relazione_protocollo is not None
    assert servizi.destinatario_relazione(d) == "Presidente di Federazione"


def test_commissario_amministrativo(sezione, segretario):  # noqa: F811
    alfa, consiglio, _, _ = sezione
    ca = servizi.nomina_commissario_amministrativo(
        segretario, sezione=alfa, commissario=persona("Revisore"), dal=OGGI,
        nominato_da="Consiglio direttivo di Federazione")  # fmt: skip
    assert ca.termine == servizi._piu_mesi(OGGI, 12)
    assert consiglio.cariche_al(OGGI).count() == 3  # gli organi restano in carica
    with pytest.raises(servizi.OperazioneNonValida, match="già un commissario"):
        servizi.nomina_commissario_amministrativo(
            segretario, sezione=alfa, commissario=persona("Altro"), dal=OGGI, nominato_da="x"
        )
    with pytest.raises(servizi.OperazioneNonValida, match="dodici mesi"):
        servizi.aggiorna_commissario_amministrativo(
            ca, segretario, rinnova_al=ca.termine + timedelta(days=400)
        )
    servizi.aggiorna_commissario_amministrativo(ca, segretario, relazione="Conti in ordine.",
                                                chiudi=True)  # fmt: skip
    ca.refresh_from_db()
    assert ca.chiuso_il == timezone.localdate() and ca.relazione == "Conti in ordine."


def test_pagine(ambiente, segretario, sezionale, client):  # noqa: F811
    _, iscritti = ambiente
    r, _ = convocato(segretario, sezionale, iscritti)
    client.force_login(segretario)
    pagina = client.get(f"/organi/rinnovi/{r.pk}/votanti/").content.decode()
    assert "per delega" in pagina
    socio = r.aventi_diritto[0]["socio"]
    risposta = client.post(f"/organi/rinnovi/{r.pk}/votanti/", {f"presenza_{socio}": "presente"})
    assert risposta.status_code == 302
    assert "Adempimenti del Regolamento" in client.get(r.get_absolute_url()).content.decode()
    assert client.get("/organi/rinnovi/amministrativi/").status_code == 200
