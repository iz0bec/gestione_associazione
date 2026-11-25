# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Indirizzi del modulo Progetti
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.urls import path

from . import mcp, views

app_name = "progetti"

urlpatterns = [
    path("", views.ProgettiView.as_view(), name="progetti"),
    path("nuovo/", views.ProgettoNuovoView.as_view(), name="progetto_nuovo"),
    path("<int:pk>/", views.ProgettoView.as_view(), name="progetto"),
    path("<int:pk>/modifica/", views.ProgettoModificaView.as_view(), name="progetto_modifica"),
    path("<int:pk>/proposta/", views.PropostaView.as_view(), name="proposta"),
    path("<int:pk>/candidatura/", views.CandidaturaView.as_view(), name="candidatura"),
    path("<int:pk>/esecuzione/", views.EsecuzioneView.as_view(), name="esecuzione"),
    path(
        "<int:pk>/candidatura/scarica/<str:tipo>",
        views.DocumentoCandidaturaView.as_view(),
        name="documento_candidatura",
    ),
    path(
        "<int:pk>/candidatura/azione/<str:azione>/",
        views.AzioneCandidaturaView.as_view(),
        name="azione_candidatura",
    ),
    path(
        "<int:pk>/progettazione/<str:sezione>/",
        views.ProgettazioneView.as_view(),
        name="progettazione",
    ),
    path("<int:pk>/<str:azione>/", views.ProgettoAzioneView.as_view(), name="progetto_azione"),
    path("idee/", views.IdeeView.as_view(), name="idee"),
    path("idee/nuova/", views.IdeaNuovaView.as_view(), name="idea_nuova"),
    path("idee/<int:pk>/", views.IdeaView.as_view(), name="idea"),
    path("idee/<int:pk>/modifica/", views.IdeaModificaView.as_view(), name="idea_modifica"),
    path("idee/<int:pk>/<str:azione>/", views.IdeaAzioneView.as_view(), name="idea_azione"),
    path("bandi/", views.BandiView.as_view(), name="bandi"),
    path("bandi/da-vagliare/", views.ProposteView.as_view(), name="proposte"),
    path("bandi/fonti/", views.FontiView.as_view(), name="fonti"),
    path("bandi/nuovo/", views.BandoNuovoView.as_view(), name="bando_nuovo"),
    path("bandi/<int:pk>/", views.BandoView.as_view(), name="bando"),
    path("bandi/<int:pk>/modifica/", views.BandoModificaView.as_view(), name="bando_modifica"),
    path("bandi/<int:pk>/<str:azione>/", views.BandoAzioneView.as_view(), name="bando_azione"),
    path("assistente/", views.AssistenteView.as_view(), name="assistente"),
    path("mcp/", mcp.endpoint, name="mcp"),
    path("allegati/<int:pk>/", views.AllegatoView.as_view(), name="allegato"),
    path("finalita/", views.FinalitaView.as_view(), name="finalita"),
    path("criteri/", views.CriteriView.as_view(), name="criteri"),
]
