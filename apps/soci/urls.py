# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Indirizzi del modulo Soci e tesseramento
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.urls import path

from . import views

app_name = "soci"

urlpatterns = [
    path("", views.ElencoView.as_view(), name="elenco"),
    path("nuovo/", views.NuovoView.as_view(), name="nuovo"),
    path("ammissione/<int:soggetto>/", views.AmmissioneView.as_view(), name="ammissione"),
    path("libro-soci.pdf", views.LibroSociPdfView.as_view(), name="libro_pdf"),
    path("soci.csv", views.LibroSociCsvView.as_view(), name="esporta"),
    path("<int:pk>/", views.DettaglioView.as_view(), name="dettaglio"),
    path("<int:pk>/modifica/", views.ModificaView.as_view(), name="modifica"),
    path("<int:pk>/cessazione/", views.CessazioneView.as_view(), name="cessazione"),
    path("<int:pk>/stato/", views.StatoView.as_view(), name="stato"),
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
    path("domande/<int:pk>/respingi/", views.RespingiView.as_view(), name="respingi"),
    path("tessere/listino/", views.ListinoView.as_view(), name="listino"),
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
