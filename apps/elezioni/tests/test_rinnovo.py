# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test del rinnovo degli organi: termini, convocazione con gli aventi diritto,
# *              compilazione e controllo delle liste, esiti, proclamazione, insediamento con le
# *              nomine, documenti PDF, congresso provinciale (voto ponderato), viste e permessi.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.anagrafica.models import Soggetto
from apps.elezioni import servizi
from apps.elezioni.forms import AssembleaForm
from apps.elezioni.models import Lista, ProfiloElettorale, Rinnovo
from apps.organi.models import Carica, Organo
from apps.soci import servizi as soci
from apps.soci.models import Sezione, TipologiaSocio

pytestmark = pytest.mark.django_db
OGGI = timezone.localdate()


@pytest.fixture
def segretario(crea_utente):
    return crea_utente("segretario", ruoli=["Segretario"])


def persona(cognome, email=True):
    return Soggetto.objects.create(cognome=cognome, nome="Prova",
                                   email=f"{cognome.lower()}@example.org" if email else "")  # fmt: skip


def socio(cognome, utente, *, in_regola=True, sezione=None):
    ordinario = TipologiaSocio.objects.get(nome="Ordinario")
    if not ordinario.quota_annua:
        ordinario.quota_annua = Decimal("20")
        ordinario.save()
    s = soci.ammetti_socio(persona(cognome), ordinario, utente,
                           data_ammissione=date(2020, 1, 1), sezione=sezione)  # fmt: skip
    if in_regola:
        soci.rilascia_tessera(s, OGGI.year, utente, pagata_il=OGGI)
    return s


@pytest.fixture
def sezionale():
    return ProfiloElettorale.objects.get(nome="ANCR - Congresso sezionale")


@pytest.fixture
def ambiente(segretario, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    consiglio = Organo.objects.get(sigla="CD")
    consiglio.durata_mandato = 4
    consiglio.save()
    iscritti = [socio(f"S{i}", segretario) for i in range(6)]
    socio("Moroso", segretario, in_regola=False)
    inizio = OGGI - timedelta(days=4 * 365 - 90)  # mandato in scadenza fra circa 3 mesi
    Carica.objects.create(organo=consiglio, soggetto=iscritti[0].soggetto, ruolo="presidente",
                          dal=inizio)  # fmt: skip
    return consiglio, iscritti


def avvia(segretario, profilo, quando=None):
    r = servizi.nuovo_rinnovo(segretario, profilo=profilo)
    servizi.indici(r, segretario, giorno=OGGI, atto="delibera del consiglio")
    assemblea = timezone.localtime() + timedelta(days=30)
    form = AssembleaForm(data={
        "quadriennio": r.quadriennio, "luogo": "Sede sociale", "seggio": "Sala riunioni",
        "data_assemblea": assemblea.strftime("%Y-%m-%dT%H:%M"),
        "seconda_convocazione": (assemblea + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"),
        "apertura_seggio": "10:00", "chiusura_seggio": "12:00",
    }, instance=r)  # fmt: skip
    assert form.is_valid(), form.errors
    assert servizi.salva_assemblea(form, segretario) == []
    r.refresh_from_db()
    return r


def lista_completa(r, utente, persone, accettazione=True):
    lista = servizi.nuova_lista(r, utente)
    for p, incarico in zip(persone, ["presidente", "vicepresidente", "segretario", "sindaco"],
                           strict=True):  # fmt: skip
        servizi.aggiungi_candidato(lista, utente, soggetto=p, incarico=incarico,
                                   accettazione=accettazione)  # fmt: skip
    return lista


def test_procedura_completa_della_sezione(ambiente, segretario, sezionale):
    consiglio, iscritti = ambiente
    r = avvia(segretario, sezionale)
    presidente_uscente = consiglio.cariche_al().get(ruolo="presidente")
    assert r.scadenza == presidente_uscente.scadenza_mandato and r.fase == "indetto"
    assert r.termine_liste == timezone.localtime(r.data_assemblea).date() - timedelta(days=15)
    assert "Elezione delle cariche sociali" in r.ordine_del_giorno
    # convocazione: aventi diritto fissati (il moroso non vota) e avviso in bozza
    assert servizi.convoca(r, segretario, giorno=OGGI) == []
    r.refresh_from_db()
    assert r.fase == "convocato" and len(r.aventi_diritto) == 6 and r.soci_alla_soglia == 6
    assert r.invio_avviso.stato == "bozza" and r.invio_avviso.destinatari.count() == 6
    assert "Moroso" not in str(r.aventi_diritto)
    # composizione fino a 100 soci: presidente, vice, segretario, un sindaco; niente consiglieri
    regole = servizi.composizione(r)
    assert regole["consigliere"] == (0, 0) and regole["sindaco"] == (1, 1)
    assert regole["supplente"] == (0, 4)
    lista = lista_completa(r, segretario, [s.soggetto for s in iscritti[:4]], accettazione=False)
    assert any("accettazione" in p for p in servizi.problemi_lista(lista))
    with pytest.raises(servizi.OperazioneNonValida, match="massimo"):
        servizi.aggiungi_candidato(lista, segretario, soggetto=iscritti[4].soggetto,
                                   incarico="consigliere")  # fmt: skip
    for c in lista.candidati.all():
        servizi.imposta_accettazione(c, segretario, True)
    servizi.aggiungi_candidato(lista, segretario, soggetto=iscritti[5].soggetto,
                               incarico="supplente", accettazione=True)  # fmt: skip
    assert servizi.problemi_lista(lista) == []
    assert servizi.presenta_lista(lista, segretario, protocolla=True) == []
    lista.refresh_from_db()
    assert lista.numero == 1 and lista.stato == "presentata" and lista.protocollo is not None
    with pytest.raises(servizi.OperazioneNonValida, match="presentata"):
        servizi.aggiungi_candidato(lista, segretario, soggetto=iscritti[4].soggetto,
                                   incarico="supplente")  # fmt: skip
    # una seconda lista con un candidato già presente e un socio non in regola
    moroso = Soggetto.objects.get(cognome="Moroso")
    seconda = servizi.nuova_lista(r, segretario)
    servizi.aggiungi_candidato(seconda, segretario, soggetto=iscritti[1].soggetto,
                               incarico="presidente", accettazione=True)  # fmt: skip
    servizi.aggiungi_candidato(seconda, segretario, soggetto=moroso, incarico="vicepresidente",
                               accettazione=True)  # fmt: skip
    problemi = " ".join(servizi.problemi_lista(seconda))
    assert "altra lista" in problemi and "non è un socio in regola" in problemi
    servizi.presenta_lista(seconda, segretario)
    servizi.esamina_lista(lista, segretario, ammessa=True)
    with pytest.raises(servizi.OperazioneNonValida, match="motivi"):
        servizi.esamina_lista(seconda, segretario, ammessa=False)
    servizi.esamina_lista(seconda, segretario, ammessa=False, motivo="Lista incompleta")
    r.refresh_from_db()
    assert r.fase == "liste" and servizi.modalita_voto(r) == "alzata"
    # esiti, proclamazione, rinuncia, insediamento
    avvisi = servizi.registra_esiti(r, segretario, {"votato_il": OGGI, "presenti": 4,
                                                    "deleghe": 2}, {lista.pk: 6})  # fmt: skip
    r.refresh_from_db()
    assert avvisi == [] and r.alzata_di_mano and r.lista_eletta == lista
    servizi.proclama(r, segretario)
    vice = lista.candidati.get(incarico="vicepresidente")
    servizi.registra_rinuncia(vice, segretario)
    nominati = servizi.insedia(r, segretario, giorno=OGGI)
    assert nominati == 4  # presidente, segretario, sindaco, supplente (il vice non accetta)
    presidente_uscente.refresh_from_db()
    assert presidente_uscente.al == OGGI
    in_carica = {c.ruolo: c.soggetto for c in consiglio.cariche_al(OGGI)}
    assert in_carica["presidente"] == iscritti[0].soggetto and "vicepresidente" not in in_carica
    assert in_carica["supplente"] == iscritti[5].soggetto
    controllo = Organo.objects.get(tipo="controllo", sezione=None)
    assert controllo.cariche_al(OGGI).get().soggetto == iscritti[3].soggetto
    # documenti e trasmissione protocollata con i verbali
    for codice in servizi.DOCUMENTI:
        extra = {"lista": lista} if codice == "lista" else {}
        assert servizi.pdf(codice, r, **extra).startswith(b"%PDF")
    servizi.trasmetti(r, segretario, protocolla=True)
    r.refresh_from_db()
    assert r.protocollo_trasmissione.allegati.count() == 3  # ammissione, elezione (C3), D2
    assert servizi.sigla_modello(r, "elezione") == "C3"
    servizi.registra_consegne(r, segretario, {"consegnante": "Uscente"}, giorno=OGGI)
    servizi.concludi(r, segretario)
    r.refresh_from_db()
    assert r.fase == "concluso" and all(t.fatto for t in servizi.termini(r) if t.codice in (
        "indizione", "avviso", "trasmissione", "consegne"))  # fmt: skip


def test_scrutinio_parita_e_controlli(ambiente, segretario, sezionale):
    _, iscritti = ambiente
    r = avvia(segretario, sezionale)
    servizi.convoca(r, segretario, comunicazione=False)
    a = lista_completa(r, segretario, [s.soggetto for s in iscritti[:4]])
    servizi.presenta_lista(a, segretario)
    b = servizi.nuova_lista(r, segretario)
    servizi.aggiungi_candidato(b, segretario, soggetto=iscritti[4].soggetto,
                               incarico="presidente", accettazione=True)  # fmt: skip
    servizi.presenta_lista(b, segretario)
    servizi.esamina_lista(a, segretario, ammessa=True)
    servizi.esamina_lista(b, segretario, ammessa=True)
    r.refresh_from_db()
    assert servizi.modalita_voto(r) == "scrutinio"
    with pytest.raises(servizi.OperazioneNonValida, match="schede votate"):
        servizi.registra_esiti(r, segretario, {"votato_il": OGGI, "schede_votate": 5},
                               {a.pk: 3, b.pk: 3})  # fmt: skip
    with pytest.raises(servizi.OperazioneNonValida, match="aventi diritto"):
        servizi.registra_esiti(r, segretario, {"votato_il": OGGI}, {a.pk: 5, b.pk: 5})
    with pytest.raises(servizi.OperazioneNonValida, match="delega"):
        servizi.registra_esiti(r, segretario, {"votato_il": OGGI, "presenti": 1, "deleghe": 3},
                               {a.pk: 1, b.pk: 0})  # fmt: skip
    r = Rinnovo.objects.get(pk=r.pk)
    avvisi = servizi.registra_esiti(r, segretario, {"votato_il": OGGI, "schede_votate": 6},
                                    {a.pk: 3, b.pk: 3})  # fmt: skip
    assert "Parità" in avvisi[0]
    with pytest.raises(servizi.OperazioneNonValida):
        servizi.proclama(Rinnovo.objects.get(pk=r.pk), segretario)
    r = Rinnovo.objects.get(pk=r.pk)
    servizi.registra_esiti(r, segretario, {"votato_il": OGGI, "schede_votate": 6},
                           {a.pk: 4, b.pk: 2})  # fmt: skip
    r.refresh_from_db()
    assert r.lista_eletta == a and servizi.sigla_modello(r, "elezione") == "C2"
    servizi.proclama(r, segretario)
    servizi.aggiungi_ricorso(r, segretario, presentato_il=OGGI, presentato_da="Socio",
                             motivi="Scheda contestata")  # fmt: skip
    with pytest.raises(servizi.OperazioneNonValida, match="ricorsi"):
        servizi.insedia(r, segretario)


def test_congresso_provinciale(segretario, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    provinciale = ProfiloElettorale.objects.get(nome="ANCR - Congresso provinciale")
    alfa = Sezione.objects.create(codice="A", nome="Alfa")
    beta = Sezione.objects.create(codice="B", nome="Beta")
    for i in range(3):
        socio(f"A{i}", segretario, sezione=alfa)
    socio("B0", segretario, sezione=beta)
    socio("B1", segretario, sezione=beta, in_regola=False)
    consiglio_alfa = Organo.objects.create(nome="Consiglio Alfa", sigla="CA", tipo="consiglio",
                                           sezione=alfa)  # fmt: skip
    presidente = Soggetto.objects.get(cognome="A0")
    Carica.objects.create(organo=consiglio_alfa, soggetto=presidente, ruolo="presidente",
                          dal=date(2024, 1, 1))  # fmt: skip
    r = avvia(segretario, provinciale)
    servizi.convoca(r, segretario)
    r.refresh_from_db()
    voti = {riga["nome"]: (riga["voti"], riga["delegato"]) for riga in r.aventi_diritto}
    assert voti["Alfa"] == (3, presidente.nome_completo) and voti["Beta"] == (1, "")
    assert servizi.voti_totali(r) >= 4
    assert r.invio_avviso.destinatari.get().soggetto == presidente  # ai presidenti di sezione
    # federazione: consiglieri facoltativi fino a 100 soci, poi 4, oltre 400 uno ogni 100
    assert servizi.composizione(r)["consigliere"] == (0, 4)
    r.soci_alla_soglia = 450
    assert servizi.composizione(r)["consigliere"] == (5, 5)
    r.soci_alla_soglia = 2000
    assert servizi.composizione(r)["consigliere"] == (10, 10)
    assert servizi.composizione(r)["garante"] == (3, 3)
    assert servizi.sigla_modello(r, "commissione") == "B1"
    assert servizi.pdf("commissione", r).startswith(b"%PDF")


def test_termini_e_calendario(ambiente, segretario, sezionale, crea_utente):
    r = avvia(segretario, sezionale)
    codici = [t.codice for t in servizi.termini(r)]
    assert codici == ["indizione", "avviso", "liste", "assemblea", "ricorsi", "trasmissione",
                      "consegne"]  # fmt: skip
    assert servizi.termini(r)[0].fatto == OGGI
    from apps.calendario import servizi as calendario

    eventi = calendario.eventi(segretario, dal=OGGI, al=OGGI + timedelta(days=60))
    assert any(e.uid.startswith(f"rinnovo-{r.pk}-avviso") for e in eventi)
    with pytest.raises(servizi.OperazioneNonValida, match="già un rinnovo"):
        servizi.nuovo_rinnovo(segretario, profilo=sezionale)
    assert servizi.da_avviare() == []  # il rinnovo c'è già


def test_mandato_da_avviare(ambiente):
    assert servizi.da_avviare()[0]["sezione"] is None


def test_pagine(ambiente, segretario, sezionale, client):
    client.force_login(segretario)
    assert "Mandati in scadenza senza un rinnovo" in client.get("/organi/rinnovi/").content.decode()
    r = client.post("/organi/rinnovi/nuovo/", {"profilo": sezionale.pk})
    rinnovo = Rinnovo.objects.get()
    assert r.status_code == 302 and r["Location"] == rinnovo.get_absolute_url()
    client.post(f"/organi/rinnovi/{rinnovo.pk}/indici/", {"giorno": OGGI.isoformat()})
    pagina = client.get(rinnovo.get_absolute_url()).content.decode()
    assert "Imposta l&#x27;assemblea" in pagina or "Imposta l'assemblea" in pagina
    client.post(f"/organi/rinnovi/{rinnovo.pk}/liste/nuova/")
    lista = Lista.objects.get()
    trovati = client.get(f"/organi/rinnovi/liste/{lista.pk}/cerca/?cerca=S1").content.decode()
    assert "S1" in trovati and "Aggiungi" in trovati
    presidente = Soggetto.objects.get(cognome="S1")
    client.post(
        f"/organi/rinnovi/liste/{lista.pk}/candidati/",
        {"soggetto": presidente.pk, "incarico": "presidente", "accettazione": "on"},
    )
    assert lista.candidati.get().soggetto == presidente
    assert "Composizione" in client.get(lista.get_absolute_url()).content.decode()
    pdf = client.get(f"/organi/rinnovi/{rinnovo.pk}/documenti/lista/?lista={lista.pk}")
    assert pdf["Content-Type"] == "application/pdf"
    assert client.get(f"/organi/rinnovi/{rinnovo.pk}/documenti/inesistente/").status_code == 404
    assert client.get("/organi/rinnovi/profili/").status_code == 200
    assert "Rinnovo degli organi" in client.get("/").content.decode()


def test_permessi_e_sezioni(ambiente, segretario, sezionale, client_ruolo, crea_utente, client):
    servizi.nuovo_rinnovo(segretario, profilo=sezionale)
    consigliere = client_ruolo("Consigliere")
    assert consigliere.get("/organi/rinnovi/nuovo/").status_code == 403
    assert consigliere.get("/organi/rinnovi/").status_code == 200
    altra = Sezione.objects.create(codice="Z", nome="Zeta")
    responsabile = crea_utente("zeta", ruoli=["Presidente di sezione"])
    responsabile.sezioni.add(altra)
    client.force_login(responsabile)
    rinnovo = Rinnovo.objects.get()
    assert client.get(rinnovo.get_absolute_url()).status_code == 404  # organi dell'ente
    assert client.get("/organi/rinnovi/").status_code == 200
