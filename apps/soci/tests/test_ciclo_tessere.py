# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test del ciclo delle tessere: richieste e integrazioni, ordine al nazionale,
# *              magazzino, consegne parziali con il lotto della sezione, pagamenti e storni nella
# *              quadratura, file della consegna importato dalla sezione (con anteprima).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from datetime import date
from decimal import Decimal

import pytest

from apps.soci import ciclo
from apps.soci.models import CartaTessera, ConsegnaTessere, ListinoTessere, LottoTessere, Sezione
from apps.soci.servizi import OperazioneNonValida
from apps.tesoreria import incassi
from apps.tesoreria import servizi as tesoreria

pytestmark = pytest.mark.django_db
ANNO = date.today().year
D = Decimal


@pytest.fixture(autouse=True)
def cartella_media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def utente(crea_utente):
    u = crea_utente("tesoriere", ruoli=["Amministratore di sistema", "Tesoriere"])
    tesoreria.apri_esercizio(ANNO, u)
    ListinoTessere.objects.update_or_create(
        anno=ANNO, defaults={"costo_acquisto": D("3.50"), "quota_federale": D("1.50")}
    )
    return u


@pytest.fixture
def sezioni():
    return (Sezione.objects.create(codice="PZ01", nome="Avigliano"),
            Sezione.objects.create(codice="PZ02", nome="Potenza"))  # fmt: skip


def test_prezzo_per_le_sezioni(utente):
    assert ciclo.prezzo_sezioni(ANNO) == D("5.00")


def test_richieste_integrazioni_e_ordini(utente, sezioni):
    a, b = sezioni
    ciclo.registra_richiesta(utente, anno=ANNO, sezione=a, quantita=100)
    ciclo.registra_richiesta(utente, anno=ANNO, sezione=b, quantita=40)
    primo = ciclo.crea_ordine(utente, anno=ANNO)
    assert primo.quantita == 140 and primo.numero == 1
    assert {r["codice"]: r["quantita"] for r in primo.dettaglio} == {"PZ01": 100, "PZ02": 40}
    with pytest.raises(OperazioneNonValida, match="Nessuna richiesta"):
        ciclo.crea_ordine(utente, anno=ANNO)
    ciclo.registra_richiesta(utente, anno=ANNO, sezione=a, quantita=20)  # integrazione
    secondo = ciclo.crea_ordine(utente, anno=ANNO)
    assert (secondo.numero, secondo.quantita) == (2, 20)
    assert secondo.dettaglio == [{"sezione": a.pk, "codice": "PZ01", "nome": "Avigliano",
                                  "quantita": 20}]  # fmt: skip


def test_magazzino_e_consegne_parziali(utente, sezioni):
    a, b = sezioni
    blocco = ciclo.carica_blocco(utente, anno=ANNO, numero_da=1001, numero_a=1200, serie="pz")
    assert (
        blocco.serie == "PZ" and not CartaTessera.objects.exists()
    )  # nessuna tessera in magazzino
    with pytest.raises(OperazioneNonValida, match="sovrappongono"):
        ciclo.carica_blocco(utente, anno=ANNO, numero_da=1150, numero_a=1300, serie="PZ")
    prima = ciclo.consegna(utente, blocco=blocco, sezione=a, numero_da=1001, numero_a=1100,
                           modalita="mano", note_distribuzione="Sabato in sede, ore 10")  # fmt: skip
    seconda = ciclo.consegna(utente, blocco=blocco, sezione=b, numero_da=1151, numero_a=1190)
    assert (prima.numero, seconda.numero) == (1, 2)
    assert prima.importo == D("500.00") and prima.prezzo_unitario == D("5.00")
    assert prima.lotto.sezione == a and prima.lotto.carte.count() == 100
    assert prima.lotto.riferimento == f"Consegna n. {ANNO}/1"
    assert CartaTessera.objects.filter(lotto__sezione=b, stato="disponibile").count() == 40
    assert ciclo.intervalli_liberi(blocco) == [(1101, 1150), (1191, 1200)]
    assert ciclo.in_magazzino(blocco) == 60
    with pytest.raises(OperazioneNonValida, match="già stata consegnata"):
        ciclo.consegna(utente, blocco=blocco, sezione=b, numero_da=1090, numero_a=1110)
    with pytest.raises(OperazioneNonValida, match="dentro il blocco"):
        ciclo.consegna(utente, blocco=blocco, sezione=b, numero_da=1195, numero_a=1205)
    riepilogo = ciclo.riepilogo_magazzino(ANNO)
    assert (riepilogo["ricevute"], riepilogo["consegnate"], riepilogo["disponibili"]) == (
        200,
        140,
        60,
    )


def test_quadratura_con_pagamenti_e_storni(utente, sezioni):
    a, b = sezioni
    ciclo.registra_richiesta(utente, anno=ANNO, sezione=a, quantita=120)
    ciclo.registra_richiesta(utente, anno=ANNO, sezione=b, quantita=10)
    blocco = ciclo.carica_blocco(utente, anno=ANNO, numero_da=1, numero_a=500)
    ciclo.consegna(utente, blocco=blocco, sezione=a, numero_da=1, numero_a=100)
    # versamento della sezione: incasso del tesoriere con ricevuta numerata
    incasso = incassi.registra_incasso({
        "data": date.today(), "tipo": "tessere", "nominativo": "Sezione di Avigliano",
        "importo": D("600"), "metodo": "bonifico", "causale": f"Tessere {ANNO}",
        "sezione": a, "anno_tessere": ANNO,
    }, utente)  # fmt: skip
    assert incasso.ricevuta_numero and incasso.movimento.importo == D("600")
    righe = {r.sezione.codice: r for r in ciclo.quadratura(ANNO)}
    ra = righe["PZ01"]
    assert (ra.richieste, ra.consegnate, ra.dovuto, ra.pagato) == (120, 100, D("500"), D("600"))
    assert ra.saldo == D("-100") and "versato in più € 100.00" in ra.avvisi
    assert "20 da consegnare" in ra.avvisi and "presa in carico da confermare" in ra.avvisi
    assert righe["PZ02"].avvisi == ["10 da consegnare"]
    incassi.storna(incasso, utente, data=date.today(), motivo="Importo errato", rimborso=False)
    assert ciclo.pagato_per_sezione(ANNO) == {a.pk: D("0")}
    assert "consegnate senza alcun pagamento" in ciclo.quadratura(ANNO)[0].avvisi


def test_presa_in_carico(utente, sezioni):
    blocco = ciclo.carica_blocco(utente, anno=ANNO, numero_da=1, numero_a=10)
    documento = ciclo.consegna(utente, blocco=blocco, sezione=sezioni[0], numero_da=1, numero_a=10)
    ciclo.prendi_in_carico(documento, utente, date.today())
    assert ConsegnaTessere.objects.get().presa_in_carico_il == date.today()


def test_file_della_consegna_importato_dalla_sezione(utente, sezioni):
    blocco = ciclo.carica_blocco(utente, anno=ANNO, numero_da=7, numero_a=9, serie="A", cifre=5)
    documento = ciclo.consegna(utente, blocco=blocco, sezione=sezioni[0], numero_da=7, numero_a=9)
    contenuto = ciclo.csv_consegna(documento)
    righe = ciclo.leggi_csv_consegna(contenuto)
    assert righe[0] | {"data": ""} == {
        "anno": ANNO,
        "serie": "A",
        "numero_da": 7,
        "numero_a": 9,
        "cifre": 5,
        "prezzo_unitario": D("5.00"),
        "consegna": f"{ANNO}/1",
        "data": "",
        "fornitore": righe[0]["fornitore"],
    }
    # nell'installazione della sezione gli stessi numeri (qui: un altro anno, stesso database)
    altro = contenuto.decode().replace(f"\n{ANNO};", f"\n{ANNO + 1};").encode()
    prima = LottoTessere.objects.count()
    _, lotti = ciclo.importa_consegna(utente, altro, sezione=sezioni[1])  # anteprima
    assert len(lotti) == 1 and LottoTessere.objects.count() == prima
    _, lotti = ciclo.importa_consegna(utente, altro, sezione=sezioni[1], esegui=True)
    lotto = LottoTessere.objects.get(pk=lotti[0].pk)
    assert (lotto.anno, lotto.sezione, lotto.costo_unitario) == (ANNO + 1, sezioni[1], D("5.00"))
    assert list(lotto.carte.values_list("codice", flat=True)) == ["A 00007", "A 00008", "A 00009"]
    with pytest.raises(OperazioneNonValida, match="già caricate"):
        ciclo.importa_consegna(utente, altro, sezione=sezioni[1], esegui=True)
    with pytest.raises(OperazioneNonValida, match="non è un file di consegna"):
        ciclo.leggi_csv_consegna(b"a;b\n1;2\n")
