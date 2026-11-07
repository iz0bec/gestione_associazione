# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Indirizzi del modulo Patrimonio
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.urls import path

from . import views

app_name = "patrimonio"

urlpatterns = [
    path("", views.InventarioView.as_view(), name="inventario"),
    path("nuovo/", views.BeneNuovoView.as_view(), name="nuovo"),
    path("stampa/", views.StampaInventarioView.as_view(), name="stampa"),
    path("etichette.pdf", views.EtichetteView.as_view(), name="etichette"),
    path("<int:pk>/", views.BeneView.as_view(), name="bene"),
    path("<int:pk>/modifica/", views.BeneModificaView.as_view(), name="modifica"),
    path("<int:pk>/foto/", views.FotoView.as_view(), name="foto"),
    path("<int:pk>/valutazione/", views.ValutazioneView.as_view(), name="valutazione"),
    path("<int:pk>/uscita/", views.UscitaView.as_view(), name="uscita"),
    path("<int:pk>/restituzione/", views.RestituzioneView.as_view(), name="restituzione"),
    path("passaggi/", views.PassaggiView.as_view(), name="passaggi"),
    path("passaggi/nuovo/", views.PassaggioNuovoView.as_view(), name="passaggio_nuovo"),
    path("passaggi/<int:pk>.pdf", views.PassaggioPdfView.as_view(), name="passaggio_pdf"),
    path("categorie/", views.CategorieView.as_view(), name="categorie"),
    path("categorie/nuova/", views.CategoriaNuovaView.as_view(), name="categoria_nuova"),
    path("categorie/<int:pk>/", views.CategoriaModificaView.as_view(), name="categoria"),
]
