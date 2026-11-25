# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Indirizzi del modulo Soci e tesseramento
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.urls import path

from . import views, viste_ciclo, viste_trasferimenti

app_name = "soci"

urlpatterns = [
    path("", views.ElencoView.as_view(), name="elenco"),
    path("nuovo/", views.NuovoView.as_view(), name="nuovo"),
    path("ammissione/<int:soggetto>/", views.AmmissioneView.as_view(), name="ammissione"),
    path("libro-soci.pdf", views.LibroSociPdfView.as_view(), name="libro_pdf"),
    path("soci.csv", views.LibroSociCsvView.as_view(), name="esporta"),
    path("soci-scambio.xlsx", views.SociScambioView.as_view(), name="esporta_scambio"),
    path("archivio-centrale/", views.PromemoriaArchivioView.as_view(), name="promemoria_archivio"),
    path("<int:pk>/", views.DettaglioView.as_view(), name="dettaglio"),
    path("<int:pk>/modifica/", views.ModificaView.as_view(), name="modifica"),
    path("<int:pk>/cessazione/", views.CessazioneView.as_view(), name="cessazione"),
    path("<int:pk>/stato/", views.StatoView.as_view(), name="stato"),
    path("<int:pk>/trasferisci/", views.TrasferimentoView.as_view(), name="trasferisci"),
    path(
        "<int:pk>/trasferisci-collegata/",
        viste_trasferimenti.RichiestaView.as_view(),
        name="trasferisci_collegata",
    ),
    path("trasferimenti/", viste_trasferimenti.ElencoView.as_view(), name="trasferimenti_esterni"),
    path(
        "trasferimenti/<int:pk>/",
        viste_trasferimenti.DettaglioView.as_view(),
        name="trasferimento_esterno",
    ),
    path(
        "verifica-tessera/",
        viste_trasferimenti.VerificaTesseraView.as_view(),
        name="verifica_tessera_collegata",
    ),
    path("<int:pk>/modulo.pdf", views.ModuloSocioPdfView.as_view(), name="modulo_socio"),
    path("<int:pk>/modulo-firmato.pdf", views.ModuloFirmatoView.as_view(), name="modulo_firmato"),
    path("<int:pk>/modulo-firmato/", views.CaricaModuloView.as_view(), name="carica_modulo"),
    path("<int:pk>/tessera/", views.TesseraNuovaView.as_view(), name="tessera_nuova"),
    path("tessere/", views.TessereView.as_view(), name="tessere"),
    path("tessere/rinnovo/", views.RinnovoView.as_view(), name="rinnovo"),
    path("tessere/incasso/", views.IncassoMassivoView.as_view(), name="incasso_massivo"),
    path("tessere/<int:pk>/pagamento/", views.PagamentoView.as_view(), name="pagamento"),
    path("tessere/<int:pk>/annulla/", views.AnnullaTesseraView.as_view(), name="annulla_tessera"),
    path("tessere/<int:pk>/attribuisci/", views.AttribuisciView.as_view(), name="attribuisci"),
    path("tessere/attribuzione/", views.AttribuzioneMassivaView.as_view(), name="attribuzione"),
    path("tessere/fisiche/", views.TessereFisicheView.as_view(), name="tessere_fisiche"),
    path("tessere/fisiche/carico/", views.LottoNuovoView.as_view(), name="lotto_nuovo"),
    path("tessere/fisiche/<int:pk>/stato/", views.StatoCartaView.as_view(), name="stato_carta"),
    path("tessere/tesserati.csv", views.EsportaTesseratiView.as_view(), name="esporta_tesserati"),
    path("tessere/<int:pk>/ricevuta.pdf", views.RicevutaView.as_view(), name="ricevuta"),
    path(
        "tessere/<int:pk>/tessera-digitale.pdf",
        views.TesseraDigitaleView.as_view(),
        name="tessera_digitale",
    ),
    path("domande/", views.DomandeView.as_view(), name="domande"),
    path("domande/modulo.pdf", views.ModuloVuotoView.as_view(), name="modulo_vuoto"),
    path("domande/<int:pk>/modulo.pdf", views.DomandaPdfView.as_view(), name="domanda_pdf"),
    path("domande/nuova/", views.NuovaDomandaView.as_view(), name="domanda_nuova"),
    path("domande/<int:pk>/", views.DomandaView.as_view(), name="domanda"),
    path("domande/<int:pk>/accogli/", views.AccogliView.as_view(), name="accogli"),
    path(
        "domande/<int:pk>/modulo-firmato.pdf",
        views.ModuloDomandaView.as_view(),
        name="domanda_modulo_firmato",
    ),
    path(
        "domande/da-messaggio/<int:messaggio>/",
        views.DomandaDaMessaggioView.as_view(),
        name="domanda_da_messaggio",
    ),
    path("domande/<int:pk>/respingi/", views.RespingiView.as_view(), name="respingi"),
    path("tessere/listino/", views.ListinoView.as_view(), name="listino"),
    # ciclo delle tessere con le sezioni
    path("tessere/campagna/", viste_ciclo.CampagnaView.as_view(), name="campagna_corrente"),
    path("tessere/campagna/<int:anno>/", viste_ciclo.CampagnaView.as_view(), name="campagna"),
    path(
        "tessere/campagna/<int:anno>/richiesta/",
        viste_ciclo.RichiestaNuovaView.as_view(),
        name="richiesta_tessere",
    ),
    path(
        "tessere/campagna/<int:anno>/blocco/",
        viste_ciclo.BloccoNuovoView.as_view(),
        name="blocco_tessere",
    ),
    path(
        "tessere/campagna/<int:anno>/consegna/",
        viste_ciclo.ConsegnaNuovaView.as_view(),
        name="consegna_tessere",
    ),
    path(
        "tessere/campagna/<int:anno>/ordine/",
        viste_ciclo.OrdineNuovoView.as_view(),
        name="ordine_tessere",
    ),
    path(
        "tessere/campagna/<int:anno>/avvisi/<str:tipo>/",
        viste_ciclo.AvvisiView.as_view(),
        name="avvisi_tessere",
    ),
    path(
        "tessere/consegne/<int:pk>/pdf/", viste_ciclo.ConsegnaPdfView.as_view(), name="consegna_pdf"
    ),
    path(
        "tessere/consegne/<int:pk>/numeri.csv",
        viste_ciclo.ConsegnaCsvView.as_view(),
        name="consegna_csv",
    ),
    path(
        "tessere/consegne/<int:pk>/presa-in-carico/",
        viste_ciclo.PresaInCaricoView.as_view(),
        name="consegna_presa",
    ),
    path("tessere/ordini/<int:pk>/pdf/", viste_ciclo.OrdinePdfView.as_view(), name="ordine_pdf"),
    path(
        "tessere/ordini/<int:pk>/email/", viste_ciclo.OrdineEmailView.as_view(), name="ordine_email"
    ),
    path(
        "tessere/richieste/<int:pk>/preparazione/",
        viste_ciclo.RichiestaPreparazioneView.as_view(),
        name="richiesta_preparazione",
    ),
    path(
        "tessere/campagna/<int:anno>/pagamento/",
        viste_ciclo.PagamentoTessereView.as_view(),
        name="pagamento_tessere",
    ),
    path(
        "tessere/richieste/<int:pk>/modifica/",
        viste_ciclo.RichiestaModificaView.as_view(),
        name="richiesta_modifica",
    ),
    path(
        "tessere/richieste/<int:pk>/annulla/",
        viste_ciclo.RichiestaAnnullaView.as_view(),
        name="richiesta_annulla",
    ),
    path(
        "tessere/richieste/<int:pk>/pdf/",
        viste_ciclo.RichiestaPdfView.as_view(),
        name="richiesta_pdf",
    ),
    path(
        "tessere/campagna/<int:anno>/invito/",
        viste_ciclo.InvitoView.as_view(),
        name="invito_tessere",
    ),
    path(
        "tessere/richieste/<int:pk>/conferma/",
        viste_ciclo.ConfermaRichiestaView.as_view(),
        name="richiesta_conferma",
    ),
    path(
        "tessere/richieste/<int:pk>/rispondi/",
        viste_ciclo.RispostaRichiestaView.as_view(),
        name="richiesta_rispondi",
    ),
    path(
        "tessere/arrivi/<int:pk>/conferma/",
        viste_ciclo.ArrivoConfermaView.as_view(),
        name="arrivo_conferma",
    ),
    path(
        "tessere/arrivi/<int:pk>/scarta/",
        viste_ciclo.ArrivoScartaView.as_view(),
        name="arrivo_scarta",
    ),
    path("tessere/arrivi/<int:pk>/pdf/", viste_ciclo.ArrivoPdfView.as_view(), name="arrivo_pdf"),
    path("tessere/sincronizza/", viste_ciclo.SincronizzaView.as_view(), name="sincronizza"),
    path(
        "tessere/modulo-richiesta.xlsx",
        viste_ciclo.ModuloRichiestaView.as_view(),
        name="modulo_richiesta",
    ),
    path("tessere/importa-modulo/", viste_ciclo.ImportaModuloView.as_view(), name="importa_modulo"),
    path(
        "tessere/da-messaggio/<int:pk>/<int:indice>/",
        viste_ciclo.RichiestaDaMessaggioView.as_view(),
        name="richiesta_da_messaggio",
    ),
    path(
        "tessere/importa-consegna/",
        viste_ciclo.ImportaConsegnaView.as_view(),
        name="importa_consegna",
    ),
    path("importa/", views.ImportaView.as_view(), name="importa"),
    path(
        "importa/<str:lavoro>/avanzamento/",
        views.AvanzamentoImportazioneView.as_view(),
        name="importa_avanzamento",
    ),
    path("sezioni/", views.SezioniView.as_view(), name="sezioni"),
    path(
        "sezioni/<int:pk>/organigramma/",
        views.SezioneOrganigrammaView.as_view(),
        name="sezione_organigramma",
    ),
    path(
        "sezioni/<int:pk>/crea-organi/",
        views.CreaOrganiSezioneView.as_view(),
        name="sezione_crea_organi",
    ),
    path("sezioni/nuova/", views.SezioneNuovaView.as_view(), name="sezione_nuova"),
    path("sezioni/<int:pk>/", views.SezioneModificaView.as_view(), name="sezione_modifica"),
    path("tipologie/", views.TipologieView.as_view(), name="tipologie"),
    path("tipologie/nuova/", views.TipologiaNuovaView.as_view(), name="tipologia_nuova"),
    path("tipologie/<int:pk>/", views.TipologiaModificaView.as_view(), name="tipologia_modifica"),
]
