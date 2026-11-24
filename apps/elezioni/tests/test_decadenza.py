# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test della decadenza anticipata degli organi e del commissariamento: cariche
# *              chiuse, commissario che firma, rinnovo straordinario, proroga, chiusura.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from datetime import date, timedelta

import pytest

from apps.elezioni import servizi
from apps.elezioni.models import Decadenza, Rinnovo
from apps.elezioni.tests.test_rinnovo import OGGI, lista_completa, persona, socio
from apps.organi.firme import firme, legale_rappresentante
from apps.organi.models import Carica, Organo
from apps.soci.models import Sezione

pytestmark = pytest.mark.django_db


@pytest.fixture
def segretario(crea_utente):
    return crea_utente("segretario", ruoli=["Segretario"])


@pytest.fixture
def sezione(segretario, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    alfa = Sezione.objects.create(codice="A", nome="Alfa")
    consiglio = Organo.objects.create(nome="Consiglio Alfa", sigla="CA", tipo="consiglio",
                                      sezione=alfa, durata_mandato=4)  # fmt: skip
    controllo = Organo.objects.create(nome="Sindaci Alfa", sigla="SA", tipo="controllo",
                                      sezione=alfa)  # fmt: skip
    iscritti = [socio(f"A{i}", segretario, sezione=alfa) for i in range(5)]
    for s, ruolo in zip(iscritti[:3], ["presidente", "vicepresidente", "segretario"],
                        strict=True):  # fmt: skip
        Carica.objects.create(organo=consiglio, soggetto=s.soggetto, ruolo=ruolo,
                              dal=date(2024, 1, 1))  # fmt: skip
    Carica.objects.create(organo=controllo, soggetto=iscritti[3].soggetto, ruolo="componente",
                          dal=date(2024, 1, 1))  # fmt: skip
    return alfa, consiglio, controllo, iscritti


def test_commissariamento_e_rinnovo_straordinario(sezione, segretario):
    alfa, consiglio, controllo, iscritti = sezione
    ordinario = servizi.nuovo_rinnovo(segretario, profilo=servizi.profilo_per(alfa), sezione=alfa)
    commissario = persona("Commissario")
    d = servizi.dichiara_decadenza(
        segretario, sezione=alfa, giorno=OGGI, motivo="scioglimento", commissario=commissario,
        disposto_da="Consiglio direttivo provinciale", atto="delibera n. 3",
    )  # fmt: skip
    assert d.cariche_chiuse == 4 and d.termine == servizi._piu_mesi(OGGI, 12) and not d.interim
    assert [c.ruolo for c in consiglio.cariche_al(OGGI)] == ["commissario"]
    assert not controllo.cariche_al(OGGI).exists()  # decadono sempre anche i sindaci
    # il commissario firma al posto del presidente e rappresenta la sezione
    firma = firme("presidente", giorno=OGGI, sezione=alfa, immagini=False)[0]
    assert firma.qualifica == "Il Commissario" and "Commissario" in firma.nome
    assert legale_rappresentante(OGGI, alfa).qualifica == "Il Commissario"
    ordinario.refresh_from_db()
    assert ordinario.fase == "annullato"
    r = d.rinnovo
    assert r.straordinario and r.scadenza == d.termine and r.chi_indice == "Il Commissario"
    assert "commissariamento" in servizi.termini(r)[0].nota
    with pytest.raises(servizi.OperazioneNonValida, match="già una decadenza"):
        servizi.dichiara_decadenza(segretario, sezione=alfa, giorno=OGGI, motivo="altro",
                                   termine=OGGI + timedelta(days=90))  # fmt: skip
    # proroga: al massimo dodici mesi oltre il termine
    with pytest.raises(servizi.OperazioneNonValida, match="al massimo"):
        servizi.proroga(d, segretario, fino=d.termine + timedelta(days=400))
    servizi.proroga(d, segretario, fino=d.termine + timedelta(days=180), atto="delibera n. 9")
    r.refresh_from_db()
    assert r.scadenza == d.termine + timedelta(days=180)
    # il congresso straordinario porta a normalità: commissario fuori, nuovi organi, chiusura
    r = avvia_esistente(r, segretario)
    servizi.convoca(r, segretario, comunicazione=False)
    lista = lista_completa(r, segretario, [s.soggetto for s in iscritti[:4]])
    servizi.presenta_lista(lista, segretario)
    servizi.esamina_lista(lista, segretario, ammessa=True)
    r = Rinnovo.objects.get(pk=r.pk)
    servizi.registra_esiti(r, segretario, {"votato_il": OGGI}, {lista.pk: 5})
    r.refresh_from_db()
    servizi.proclama(r, segretario)
    servizi.insedia(r, segretario, giorno=OGGI + timedelta(days=1))
    d.refresh_from_db()
    domani = OGGI + timedelta(days=1)
    assert d.chiusa_il == domani
    assert "commissario" not in [c.ruolo for c in consiglio.cariche_al(domani)]
    assert firme("presidente", giorno=domani, sezione=alfa, immagini=False)[0].qualifica == (
        "Il Presidente"
    )
    assert b"%PDF" in servizi.pdf("avviso", r)[:8]


def avvia_esistente(r, utente):
    """Indizione e assemblea di un rinnovo già aperto (come avvia() in test_rinnovo)."""
    from django.utils import timezone

    from apps.elezioni.forms import AssembleaForm

    servizi.indici(r, utente, giorno=OGGI, atto="decreto del commissario")
    momento = timezone.localtime() + timedelta(days=20)
    form = AssembleaForm(data={"quadriennio": r.quadriennio, "luogo": "Sede",
                               "data_assemblea": momento.strftime("%Y-%m-%dT%H:%M")},
                         instance=r)  # fmt: skip
    assert form.is_valid(), form.errors
    servizi.salva_assemblea(form, utente)
    r.refresh_from_db()
    return r


def test_senza_commissario_resta_ad_interim_il_presidente(sezione, segretario):
    alfa, consiglio, controllo, iscritti = sezione
    d = servizi.dichiara_decadenza(segretario, sezione=alfa, giorno=OGGI, motivo="dimissioni")
    presidente = iscritti[0].soggetto
    assert d.interim and d.commissario == presidente and d.cariche_chiuse == 4
    carica = consiglio.cariche_al(OGGI).get()
    assert carica.ruolo == "commissario" and carica.soggetto == presidente
    assert not controllo.cariche_al(OGGI).exists()
    firma = firme("presidente", giorno=OGGI, sezione=alfa, immagini=False)[0]
    assert firma.qualifica == "Il Commissario ad interim" and firma.soggetto_id == presidente.pk
    assert d.rinnovo.chi_indice == "Il Commissario ad interim"
    assert d.termine == servizi._piu_mesi(OGGI, 12)


def test_senza_presidente_serve_il_commissario(segretario, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    nuova = Sezione.objects.create(codice="N", nome="Nuova")
    with pytest.raises(servizi.OperazioneNonValida, match="indicare il commissario"):
        servizi.dichiara_decadenza(segretario, sezione=nuova, giorno=OGGI, motivo="costituzione")
    d = servizi.dichiara_decadenza(
        segretario,
        sezione=nuova,
        giorno=OGGI,
        motivo="costituzione",
        commissario=persona("Fondatore"),
    )
    assert d.cariche_chiuse == 0 and Organo.objects.get(sezione=nuova).cariche.get().ruolo == (
        "commissario"
    )


def test_pagina_decadenza(sezione, segretario, client):
    alfa, consiglio, _, _ = sezione
    client.force_login(segretario)
    assert "Commissario" in client.get("/organi/rinnovi/decadenza/").content.decode()
    commissario = persona("Rossi")
    trovati = client.get("/organi/rinnovi/decadenza/cerca/?cerca=Rossi").content.decode()
    assert f'value="{commissario.pk}"' in trovati
    r = client.post("/organi/rinnovi/decadenza/", {
        "sezione": alfa.pk, "motivo": "scioglimento", "giorno": OGGI.isoformat(),
        "commissario": commissario.pk, "atto": "delibera",
    })  # fmt: skip
    d = Decadenza.objects.get()
    assert r.status_code == 302 and r["Location"] == d.rinnovo.get_absolute_url()
    pagina = client.get(d.rinnovo.get_absolute_url()).content.decode()
    assert "Commissariamento" in pagina and "straordinario" in pagina.lower()
    fino = (d.termine + timedelta(days=30)).isoformat()
    client.post(f"/organi/rinnovi/{d.rinnovo.pk}/proroga/", {"fino": fino, "atto": "proroga"})
    d.refresh_from_db()
    assert d.prorogato_al.isoformat() == fino
