# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Indirizzi del rinnovo degli organi (sotto /organi/rinnovi/).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.urls import path

from . import views

app_name = "elezioni"

urlpatterns = [
    path("", views.RinnoviView.as_view(), name="rinnovi"),
    path("nuovo/", views.RinnovoNuovoView.as_view(), name="nuovo"),
    path("profili/", views.ProfiliView.as_view(), name="profili"),
    path("profili/nuovo/", views.ProfiloNuovoView.as_view(), name="profilo_nuovo"),
    path("profili/<int:pk>/", views.ProfiloModificaView.as_view(), name="profilo"),
    path("<int:pk>/", views.RinnovoView.as_view(), name="rinnovo"),
    path("<int:pk>/indici/", views.IndiciView.as_view(), name="indici"),
    path("<int:pk>/assemblea/", views.AssembleaView.as_view(), name="assemblea"),
    path("<int:pk>/convoca/", views.ConvocaView.as_view(), name="convoca"),
    path("<int:pk>/liste/nuova/", views.ListaNuovaView.as_view(), name="lista_nuova"),
    path("<int:pk>/esiti/", views.EsitiView.as_view(), name="esiti"),
    path("<int:pk>/proclama/", views.ProclamaView.as_view(), name="proclama"),
    path("<int:pk>/ricorsi/", views.RicorsoView.as_view(), name="ricorsi"),
    path("<int:pk>/insedia/", views.InsediaView.as_view(), name="insedia"),
    path("<int:pk>/consegne/", views.ConsegneView.as_view(), name="consegne"),
    path("<int:pk>/trasmetti/", views.TrasmettiView.as_view(), name="trasmetti"),
    path("<int:pk>/concludi/", views.ConcludiView.as_view(), name="concludi"),
    path("<int:pk>/annulla/", views.AnnullaView.as_view(), name="annulla"),
    path("<int:pk>/documenti/<str:codice>/", views.DocumentoView.as_view(), name="documento"),
    path("liste/<int:pk>/", views.ListaView.as_view(), name="lista"),
    path("liste/<int:pk>/cerca/", views.CercaCandidatiView.as_view(), name="cerca"),
    path("liste/<int:pk>/candidati/", views.CandidatoAggiungiView.as_view(), name="candidato"),
    path(
        "liste/<int:pk>/candidati/<int:candidato>/<str:azione>/",
        views.CandidatoAzioneView.as_view(),
        name="candidato_azione",
    ),
    path("liste/<int:pk>/<str:azione>/", views.ListaAzioneView.as_view(), name="lista_azione"),
]
