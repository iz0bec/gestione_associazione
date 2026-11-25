# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Indirizzi del modulo Progetti
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.urls import path

from . import views

app_name = "progetti"

urlpatterns = [
    path("", views.ProgettiView.as_view(), name="progetti"),
    path("nuovo/", views.ProgettoNuovoView.as_view(), name="progetto_nuovo"),
    path("<int:pk>/", views.ProgettoView.as_view(), name="progetto"),
    path("<int:pk>/modifica/", views.ProgettoModificaView.as_view(), name="progetto_modifica"),
    path("<int:pk>/<str:azione>/", views.ProgettoAzioneView.as_view(), name="progetto_azione"),
    path("idee/", views.IdeeView.as_view(), name="idee"),
    path("idee/nuova/", views.IdeaNuovaView.as_view(), name="idea_nuova"),
    path("idee/<int:pk>/", views.IdeaView.as_view(), name="idea"),
    path("idee/<int:pk>/modifica/", views.IdeaModificaView.as_view(), name="idea_modifica"),
    path("idee/<int:pk>/<str:azione>/", views.IdeaAzioneView.as_view(), name="idea_azione"),
    path("allegati/<int:pk>/", views.AllegatoView.as_view(), name="allegato"),
    path("finalita/", views.FinalitaView.as_view(), name="finalita"),
    path("criteri/", views.CriteriView.as_view(), name="criteri"),
]
