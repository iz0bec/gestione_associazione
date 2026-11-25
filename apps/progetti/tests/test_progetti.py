# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test del modulo Progetti (P1): idee (anche da protocollo e posta), valutazione
# *              pesata, stato e priorità, progetti con i passaggi di stato, gruppo, scadenze nel
# *              calendario, commenti, allegati, finalità, permessi e pagine.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from datetime import date, timedelta

import pytest
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.anagrafica.models import Soggetto
from apps.progetti import servizi
from apps.progetti.forms import IdeaForm, ProgettoForm
from apps.progetti.models import CriterioValutazione, FinalitaStatutaria, Idea, Progetto

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def utente(crea_utente):
    return crea_utente("presidente", ruoli=["Presidente"])


@pytest.fixture
def finalita():
    servizi.carica_finalita(
        "a) Il culto della Patria;\nb) La glorificazione dei Caduti;\n"
        "g) La promozione della cultura sul combattente italiano."
    )
    return FinalitaStatutaria.objects.order_by("ordine")


def _idea(utente, **extra):
    dati = {
        "titolo": "Mostra sui Caduti con le scuole",
        "descrizione": "Pannelli e incontri.",
        "fonte": "interna",
    } | extra
    form = IdeaForm(data=dati)
    assert form.is_valid(), form.errors
    return servizi.crea_idea(form, utente)


def _progetto(utente, idea=None, **extra):
    dati = {
        "titolo": "Memoria a scuola",
        "sintesi": "Incontri con le classi.",
        "responsabile": utente.pk,
    } | extra
    form = ProgettoForm(data=dati)
    assert form.is_valid(), form.errors
    return servizi.crea_progetto(form, utente, idea=idea)


class TestFinalita:
    def test_carica_dal_testo(self, finalita):
        assert [f.codice for f in finalita] == ["a", "b", "g"]
        assert finalita[0].titolo == "Il culto della Patria"
        assert servizi.carica_finalita("a) Il culto della Patria") == 0  # già presente

    def test_testo_senza_finalita(self):
        with pytest.raises(servizi.OperazioneNonValida):
            servizi.carica_finalita("nessuna riga valida")

    def test_comando(self, tmp_path, capsys):
        from django.core.management import call_command

        f = tmp_path / "art2.txt"
        f.write_text("a) Il culto della Patria;\nh) L'assistenza ai soci.\n", encoding="utf-8")
        call_command("importa_finalita", str(f))
        assert FinalitaStatutaria.objects.count() == 2


class TestIdee:
    def test_numerazione_e_finalita(self, utente, finalita):
        i1 = _idea(utente, finalita=[finalita[1].pk])
        i2 = _idea(utente, titolo="Restauro della lapide")
        assert (i1.numero, i2.numero) == (1, 2) and i1.codice == f"I-{date.today().year}-001"
        assert list(i1.finalita.all()) == [finalita[1]] and i1.proponente == utente

    def test_fonte_esterna_richiede_chi(self, utente):
        form = IdeaForm(data={"titolo": "X", "descrizione": "Y", "fonte": "esterna"})
        assert not form.is_valid() and "fonte_testo" in form.errors

    def test_da_protocollo(self, utente, crea_utente):
        from apps.protocollo import servizi as protocollo
        from apps.protocollo.models import Protocollo

        ente = Soggetto.objects.create(tipo="ente", denominazione="Istituto Comprensivo")
        p = protocollo.registra_protocollo(
            {
                "direzione": Protocollo.Direzione.ENTRATA,
                "mezzo": Protocollo.Mezzo.EMAIL,
                "oggetto": "Proposta di incontri sulla Grande Guerra",
                "testo": "Vi chiediamo...",
            },
            [{"ruolo": "mittente", "soggetto": ente, "descrizione": "Istituto Comprensivo"}],
            crea_utente("protocollista", ruoli=["Addetto protocollo"]),
        )
        iniziali = servizi.dati_da_protocollo(p)
        assert iniziali["fonte_soggetto"] == ente and iniziali["fonte"] == "esterna"
        form = IdeaForm(data={**iniziali, "fonte_soggetto": ente.pk})
        assert form.is_valid(), form.errors
        idea = servizi.crea_idea(form, utente, protocollo=p)
        assert idea.protocollo == p and idea.proposta_da == "Istituto Comprensivo"

    def test_valutazione_pesata(self, utente, crea_utente):
        idea = _idea(utente)
        criteri = list(CriterioValutazione.objects.order_by("ordine"))
        assert len(criteri) == 4  # quelli iniziali
        CriterioValutazione.objects.filter(pk=criteri[0].pk).update(peso=3)
        punti = {c.pk: 5 if i == 0 else 1 for i, c in enumerate(criteri)}
        v = servizi.valuta(idea, utente, punti, "Molto coerente")
        assert str(v.media) == "3.00"  # (5*3 + 1+1+1) / 6
        idea.refresh_from_db()
        assert idea.stato == Idea.Stato.IN_VALUTAZIONE
        servizi.valuta(idea, utente, {c.pk: 2 for c in criteri})  # aggiorna la propria
        assert idea.valutazioni.count() == 1
        altro = crea_utente("consigliere", ruoli=["Consigliere"])
        servizi.valuta(idea, altro, {c.pk: 4 for c in criteri})
        assert str(servizi.media_idea(idea)) == "3.00"
        with pytest.raises(servizi.OperazioneNonValida, match="va da 1 a 5"):
            servizi.valuta(idea, utente, {c.pk: 6 for c in criteri})

    def test_stato_e_priorita(self, utente):
        idea = _idea(utente)
        with pytest.raises(servizi.OperazioneNonValida, match="perché"):
            servizi.cambia_stato_idea(idea, Idea.Stato.ACCANTONATA, utente)
        servizi.imposta_priorita(idea, "alta", utente)
        servizi.cambia_stato_idea(idea, Idea.Stato.ACCANTONATA, utente, "Mancano volontari")
        idea.refresh_from_db()
        assert idea.priorita == "alta" and idea.stato == "accantonata"


class TestProgetti:
    def test_da_idea(self, utente, finalita):
        idea = _idea(utente, finalita=[finalita[0].pk])
        servizi.allega(idea, SimpleUploadedFile("bozza.pdf", b"%PDF-1.4"), utente)
        p = _progetto(utente, idea=idea, finalita=[finalita[0].pk])
        idea.refresh_from_db()
        assert idea.stato == Idea.Stato.APPROVATA and p.idea == idea
        assert p.codice == f"P-{date.today().year}-001" and p.stato == Progetto.Stato.PROGETTAZIONE
        assert p.passaggi.count() == 1 and p.membri.get().ruolo == "Responsabile"
        with pytest.raises(servizi.OperazioneNonValida, match="già diventata"):
            _progetto(utente, idea=idea)

    def test_passaggi_di_stato(self, utente):
        p = _progetto(utente)
        with pytest.raises(servizi.OperazioneNonValida, match="non si passa"):
            servizi.cambia_stato(p, Progetto.Stato.CHIUSO, utente)
        servizi.cambia_stato(p, Progetto.Stato.CANDIDATO, utente, motivo="Bando regionale")
        with pytest.raises(servizi.OperazioneNonValida, match="motivo"):
            servizi.cambia_stato(p, Progetto.Stato.NON_FINANZIATO, utente)
        servizi.cambia_stato(p, Progetto.Stato.FINANZIATO, utente)
        servizi.cambia_stato(p, Progetto.Stato.IN_CORSO, utente)
        servizi.cambia_stato(p, Progetto.Stato.CHIUSO, utente)
        p.refresh_from_db()
        assert p.stato == "chiuso" and p.passaggi.count() == 5 and not p.aperto
        with pytest.raises(servizi.OperazioneNonValida, match="chiuso"):
            servizi.aggiungi_scadenza(p, utente, titolo="X", data=date.today())

    def test_gruppo_scadenze_calendario(self, utente):
        from apps.calendario import servizi as calendario

        p = _progetto(utente)
        volontario = Soggetto.objects.create(tipo="persona", cognome="Verdi", nome="Anna")
        servizi.aggiungi_membro(
            p, utente, ruolo="Referente scuole", soggetto=volontario, volontario=True
        )
        s = servizi.aggiungi_scadenza(
            p, utente, titolo="Domanda al bando", data=date.today() + timedelta(days=5)
        )
        oggi = date.today()
        titoli = [
            e.titolo for e in calendario.eventi(utente, dal=oggi, al=oggi + timedelta(days=10))
        ]
        assert f"Domanda al bando ({p.codice})" in titoli
        servizi.segna_scadenza(s, utente)
        assert p.membri.count() == 2 and p.scadenze.get().fatta


class TestPagine:
    def test_ruolo_progettista_e_permessi(self, crea_utente):
        assert Group.objects.filter(name="Progettista").exists()
        progettista = crea_utente("prog", ruoli=["Progettista"])
        assert progettista.has_perm("progetti.gestisci_progetti")
        consigliere = crea_utente("cons", ruoli=["Consigliere"])
        assert consigliere.has_perm("progetti.add_idea") and consigliere.has_perm(
            "progetti.valuta_idea"
        )
        assert not consigliere.has_perm("progetti.gestisci_progetti")

    def test_percorso_completo(self, client_ruolo, finalita):
        c = client_ruolo("Segretario")
        r = c.post(
            reverse("progetti:idea_nuova"),
            {
                "titolo": "Viaggio della memoria",
                "descrizione": "A Redipuglia con i soci.",
                "fonte": "interna",
                "finalita": [finalita[1].pk],
            },
            follow=True,
        )
        assert "Viaggio della memoria" in r.content.decode()
        idea = Idea.objects.get()
        punti = {f"criterio_{x.pk}": "4" for x in CriterioValutazione.objects.all()}
        r = c.post(
            reverse("progetti:idea_azione", args=[idea.pk, "valuta"]),
            {**punti, "commento": "Bene"},
            follow=True,
        )
        assert "Valutazione registrata (media 4,00)" in r.content.decode()
        r = c.get(reverse("progetti:idee"))
        assert "<strong>4,00</strong>/5" in r.content.decode()
        r = c.post(
            reverse("progetti:progetto_nuovo") + f"?idea={idea.pk}",
            {
                "idea": idea.pk,
                "titolo": idea.titolo,
                "sintesi": "Viaggio",
                "finalita": [finalita[1].pk],
                "responsabile": c.utente.pk,
            },
            follow=True,
        )
        progetto = Progetto.objects.get()
        assert progetto.codice in r.content.decode()
        r = c.post(
            reverse("progetti:progetto_azione", args=[progetto.pk, "stato"]),
            {"stato": "candidato", "motivo": "Bando"},
            follow=True,
        )
        assert "Stato del progetto aggiornato" in r.content.decode()
        assert c.get(reverse("progetti:progetti")).status_code == 200
        assert c.get(reverse("progetti:finalita")).status_code == 200
        assert c.get(reverse("progetti:criteri")).status_code == 200

    def test_consigliere_non_gestisce(self, client_ruolo, crea_utente):
        presidente = crea_utente("pres", ruoli=["Presidente"])
        p = _progetto(presidente)
        c = client_ruolo("Consigliere")
        assert c.get(p.get_absolute_url()).status_code == 200
        r = c.post(
            reverse("progetti:progetto_azione", args=[p.pk, "stato"]), {"stato": "candidato"}
        )
        assert r.status_code == 404
        r = c.post(
            reverse("progetti:progetto_azione", args=[p.pk, "commenta"]),
            {"testo": "Posso aiutare"},
            follow=True,
        )
        assert "Posso aiutare" in r.content.decode()

    def test_allegato_scaricabile_solo_con_permesso(self, client_ruolo, utente, client):
        idea = _idea(utente)
        a = servizi.allega(idea, SimpleUploadedFile("nota.txt", b"testo"), utente)
        r = client_ruolo("Consigliere").get(reverse("progetti:allegato", args=[a.pk]))
        assert r.status_code == 200 and "sandbox" in r["Content-Security-Policy"]
        client.logout()
        assert client.get(reverse("progetti:allegato", args=[a.pk])).status_code == 302
