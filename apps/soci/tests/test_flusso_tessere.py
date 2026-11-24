# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test del flusso delle tessere: dal rinnovo alla richiesta in preparazione (per
# *              differenza, accumulata, mai inviata da sola), invio sul canale previsto (API,
# *              email, fabbisogno della federazione), ordine al nazionale per email, pagamenti
# *              al livello superiore sulla voce «Acquisto delle tessere» con il da pagare.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from datetime import date
from decimal import Decimal

import pytest
from django.core import mail
from django.urls import reverse

from apps.anagrafica.models import Soggetto
from apps.api.models import Cambiamento, ClienteApi
from apps.comunicazioni import servizi as comunicazioni
from apps.core.cifratura import nuova_chiave
from apps.core.models import Organizzazione
from apps.soci import ciclo, servizi
from apps.soci.models import ListinoTessere, RichiestaTessere, Sezione, TipologiaSocio
from apps.tesoreria import servizi as tesoreria
from apps.tesoreria.models import Conto, Movimento

pytestmark = pytest.mark.django_db
ANNO = date.today().year + 1


@pytest.fixture(autouse=True)
def _ambiente(settings, tmp_path):
    settings.CHIAVE_CIFRATURA = nuova_chiave()
    settings.MEDIA_ROOT = tmp_path
    ListinoTessere.objects.update_or_create(
        anno=ANNO, defaults={"costo_acquisto": Decimal("3.50"), "quota_federale": Decimal("1.50")}
    )


@pytest.fixture
def capo(crea_utente):
    return crea_utente("capo", ruoli=["Amministratore di sistema"])


def _soci(utente, n, sezione=None):
    ordinario = TipologiaSocio.objects.get(nome="Ordinario")
    return [servizi.ammetti_socio(Soggetto.objects.create(cognome=f"S{i}", nome="X"), ordinario,
                                  utente, sezione=sezione) for i in range(n)]  # fmt: skip


def _federazione_collegata():
    return ClienteApi.objects.create(
        nome="Federazione", tipo="installazione", origine="invito_nostro", stato="attiva",
        ruolo="federazione", ambiti=["tessere:scambio"],
    )  # fmt: skip


def _rinnova(client, soci):
    return client.post(reverse("soci:rinnovo"), {"anno": ANNO, "conferma": "1",
                                                 "soci": [s.pk for s in soci]}, follow=True)  # fmt: skip


class TestRichiestaInPreparazione:
    def test_si_accumula_per_differenza_e_non_parte_da_sola(self, client, capo):
        _federazione_collegata()
        sezione = Sezione.predefinita()
        soci = _soci(capo, 5)
        servizi.carica_lotto(capo, anno=ANNO, numero_da=1, numero_a=2, sezione=sezione)
        client.force_login(capo)
        _rinnova(client, soci[:3])  # prima sessione: 3 rinnovati, ma 2 tessere già in carico
        bozza = ciclo.in_preparazione(ANNO, sezione)
        assert bozza.quantita == 1 and bozza.in_preparazione  # attribuite le 2 disponibili
        r = _rinnova(client, soci[3:])  # seconda sessione: si accumula
        bozza.refresh_from_db()
        assert bozza.quantita == 3 and "portata a 3" in r.content.decode()
        assert not Cambiamento.objects.filter(soggetto=bozza.uuid).exists()  # non è partita
        assert ciclo.quadratura(ANNO) == [] and ciclo.da_ordinare(ANNO) == []
        pagina = client.get(reverse("soci:campagna", args=[ANNO])).content.decode()
        assert "Richieste in preparazione" in pagina and "Invia alla federazione" in pagina

    def test_invio_via_collegamento(self, client, capo):
        _federazione_collegata()
        sezione = Sezione.predefinita()
        client.force_login(capo)
        _rinnova(client, _soci(capo, 4))
        bozza = ciclo.in_preparazione(ANNO, sezione)
        r = client.post(reverse("soci:richiesta_preparazione", args=[bozza.pk]),
                        {"azione": "invia", "quantita": "6", "note": "con scorta"}, follow=True)  # fmt: skip
        assert "tramite il collegamento" in r.content.decode()
        bozza.refresh_from_db()
        assert not bozza.in_preparazione and bozza.quantita == 6 and bozza.note == "con scorta"
        assert Cambiamento.objects.filter(soggetto=bozza.uuid,
                                          flusso=f"tessere:{sezione.codice}").exists()  # fmt: skip
        # chieste e non ancora arrivate: non si richiedono di nuovo
        assert ciclo.fabbisogno(ANNO, sezione)["proposta"] == 0

    def test_invio_per_email_senza_collegamento(self, capo):
        Organizzazione.objects.update(federazione_email="federazione@example.org",
                                      federazione="Potenza Matera")  # fmt: skip
        sezione = Sezione.predefinita()
        for s in _soci(capo, 2):
            servizi.rilascia_tessera(s, ANNO, capo)
        bozza, _ = ciclo.aggiorna_in_preparazione(capo, ANNO, sezione)
        canale, invio = ciclo.invia_richiesta(capo, bozza)
        assert canale == "email" and invio.stato == "bozza" and invio.allegati.count() == 1
        bozza.refresh_from_db()
        assert bozza.in_preparazione  # in bozza finché l'email non parte
        with pytest.raises(servizi.OperazioneNonValida, match="già in bozza"):
            ciclo.invia_richiesta(capo, bozza)
        with pytest.raises(servizi.OperazioneNonValida, match="annullare"):
            ciclo.modifica_in_preparazione(capo, bozza, quantita=9)
        servizi.rilascia_tessera(_soci(capo, 1)[0], ANNO, capo)
        assert ciclo.aggiorna_in_preparazione(capo, ANNO, sezione)[0].quantita == 2  # bloccata
        comunicazioni.annulla(invio, capo)
        ciclo.modifica_in_preparazione(capo, bozza, quantita=3)  # di nuovo modificabile
        _, invio = ciclo.invia_richiesta(capo, bozza)
        comunicazioni.conferma(invio, capo)
        comunicazioni.elabora_coda(invio=invio)
        invio.refresh_from_db()
        bozza.refresh_from_db()
        assert invio.stato == "inviato" and not bozza.in_preparazione
        assert bozza.protocollo_id == invio.protocollo_id
        assert len(mail.outbox) == 1 and ciclo.da_ordinare(ANNO)[0]["quantita"] == 3

    def test_nella_federazione_entra_nel_fabbisogno(self, capo):
        nord = Sezione.objects.create(codice="N1", nome="Nord")
        for s in _soci(capo, 3, sezione=nord):
            servizi.rilascia_tessera(s, ANNO, capo)
        bozza, calcolo = ciclo.aggiorna_in_preparazione(capo, ANNO, nord)
        assert calcolo["proposta"] == 3 and ciclo.canale_richiesta() == "registro"
        assert ciclo.da_ordinare(ANNO) == []
        ciclo.invia_richiesta(capo, bozza)
        assert ciclo.da_ordinare(ANNO)[0]["quantita"] == 3

    def test_senza_fabbisogno_la_bozza_resta_e_ricalcola_la_toglie(self, capo):
        sezione = Sezione.predefinita()
        socio = _soci(capo, 1)[0]
        tessera = servizi.rilascia_tessera(socio, ANNO, capo)
        bozza, _ = ciclo.aggiorna_in_preparazione(capo, ANNO, sezione)
        assert bozza.quantita == 1
        servizi.annulla_tessera(tessera, capo, motivo="non rinnova")
        # l'aggiornamento automatico non toglie una richiesta (anche preparata a mano)
        assert ciclo.aggiorna_in_preparazione(capo, ANNO, sezione)[0] == bozza
        assert ciclo.aggiorna_in_preparazione(capo, ANNO, sezione, togli=True)[0] is None
        assert not RichiestaTessere.objects.exists()

    def test_sezione_senza_soci_nel_gestionale_prepara_a_mano(self, capo, client):
        """Una sezione che non tiene i soci nel gestionale (fabbisogno zero) prepara la
        richiesta a mano con «Registra» e poi la invia alla federazione."""
        sezione = Sezione.predefinita()
        assert ciclo.canale_richiesta() != "registro"
        client.force_login(capo)
        r = client.post(f"/soci/tessere/campagna/{ANNO}/richiesta/", {
            "sezione": sezione.pk, "quantita": 90, "data": date.today().isoformat(),
        }, follow=True)  # fmt: skip
        assert "Richiesta preparata: 90 tessere" in r.content.decode()
        bozza = RichiestaTessere.objects.get()
        assert bozza.inviata_il is None and ciclo.in_preparazione(ANNO, sezione) == bozza
        assert (
            "Invia alla federazione" in r.content.decode()
            or "Prepara l&#x27;email" in (r.content.decode())
            or "Prepara l'email" in r.content.decode()
        )
        ciclo.aggiorna_in_preparazione(capo, ANNO, sezione)  # un rinnovo: resta
        assert RichiestaTessere.objects.get().quantita == 90


class TestOrdineEPagamenti:
    def _federazione(self, capo):
        nord = Sezione.objects.create(codice="N1", nome="Nord")
        ciclo.registra_richiesta(capo, anno=ANNO, sezione=nord, quantita=10)
        return ciclo.crea_ordine(capo, anno=ANNO)

    def test_ordine_in_bozza_email(self, capo):
        ordine = self._federazione(capo)
        with pytest.raises(servizi.OperazioneNonValida, match="sede nazionale"):
            ciclo.prepara_ordine_email(capo, ordine)
        Organizzazione.objects.update(nazionale_email="nazionale@example.org")
        invio = ciclo.prepara_ordine_email(capo, ordine)
        assert invio.stato == "bozza" and invio.allegati.count() == 1
        assert invio.contesto["numero"] == f"{ANNO}/{ordine.numero}"

    def test_pagamenti_in_piu_volte_verso_il_nazionale(self, capo):
        ordine = self._federazione(capo)
        tesoreria.apri_esercizio(date.today().year, capo)
        conto = Conto.objects.get(nome="Banca")
        assert ciclo.quadratura_superiore(ANNO)["dovuto"] == Decimal("35.00")
        ciclo.registra_pagamento(capo, anno=ANNO, data=date.today(), importo=Decimal("20"),
                                 conto=conto, ordine=ordine, riferimento="bonifico 1")  # fmt: skip
        q = ciclo.quadratura_superiore(ANNO)
        assert q["destinatario"] == "Sede nazionale"
        assert (q["pagato"], q["da_pagare"]) == (Decimal("20"), Decimal("15.00"))
        m = Movimento.objects.get()
        assert m.tipo == "uscita" and m.voce.codice == ciclo.VOCE_TESSERE
        assert (
            m.voce.descrizione.startswith("Acquisto delle tessere") and m.ordine_tessere == ordine
        )
        ciclo.registra_pagamento(capo, anno=ANNO, data=date.today(), importo=Decimal("15"),
                                 conto=conto, ordine=ordine)  # fmt: skip
        assert ciclo.quadratura_superiore(ANNO)["da_pagare"] == 0

    def test_pagina_del_pagamento(self, client, capo):
        ordine = self._federazione(capo)
        tesoreria.apri_esercizio(date.today().year, capo)
        client.force_login(capo)
        url = reverse("soci:pagamento_tessere", args=[ANNO]) + f"?ordine={ordine.pk}"
        assert "da pagare € 35.00" in client.get(url).content.decode()
        conto = Conto.objects.get(nome="Banca")
        r = client.post(url, {"data": date.today().isoformat(), "importo": "10",
                              "conto": conto.pk, "ordine": ordine.pk}, follow=True)  # fmt: skip
        assert "Pagamento registrato in prima nota" in r.content.decode()
        assert Movimento.objects.get().ordine_tessere == ordine
