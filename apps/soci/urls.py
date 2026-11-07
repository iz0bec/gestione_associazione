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
    path("<int:pk>/tessera/", views.TesseraNuovaView.as_view(), name="tessera_nuova"),
    path("tessere/", views.TessereView.as_view(), name="tessere"),
    path("tessere/rinnovo/", views.RinnovoView.as_view(), name="rinnovo"),
    path("tessere/<int:pk>/pagamento/", views.PagamentoView.as_view(), name="pagamento"),
    path("tessere/<int:pk>/annulla/", views.AnnullaTesseraView.as_view(), name="annulla_tessera"),
    path("tessere/<int:pk>/ricevuta.pdf", views.RicevutaView.as_view(), name="ricevuta"),
    path("domande/", views.DomandeView.as_view(), name="domande"),
    path("domande/nuova/", views.NuovaDomandaView.as_view(), name="domanda_nuova"),
    path("domande/<int:pk>/", views.DomandaView.as_view(), name="domanda"),
    path("domande/<int:pk>/accogli/", views.AccogliView.as_view(), name="accogli"),
    path("domande/<int:pk>/respingi/", views.RespingiView.as_view(), name="respingi"),
    path("tipologie/", views.TipologieView.as_view(), name="tipologie"),
    path("tipologie/nuova/", views.TipologiaNuovaView.as_view(), name="tipologia_nuova"),
    path("tipologie/<int:pk>/", views.TipologiaModificaView.as_view(), name="tipologia_modifica"),
]
