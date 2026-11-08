# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Indirizzi del modulo Organi sociali
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.urls import path

from . import views

app_name = "organi"

urlpatterns = [
    path("", views.OrganiView.as_view(), name="organi"),
    path("nuovo/", views.OrganoNuovoView.as_view(), name="organo_nuovo"),
    path("<int:pk>/", views.OrganoView.as_view(), name="organo"),
    path("<int:pk>/organigramma/", views.OrganigrammaView.as_view(), name="organigramma"),
    path("<int:pk>/regole/", views.OrganoModificaView.as_view(), name="organo_modifica"),
    path("<int:pk>/nomina/", views.NominaView.as_view(), name="nomina"),
    path("cariche/<int:pk>/fine/", views.FineCaricaView.as_view(), name="fine_carica"),
    path("cariche/<int:pk>/modifica/", views.ModificaCaricaView.as_view(), name="modifica_carica"),
    path("riunioni/", views.RiunioniView.as_view(), name="riunioni"),
    path("riunioni/nuova/", views.RiunioneNuovaView.as_view(), name="riunione_nuova"),
    path("riunioni/<int:pk>/", views.RiunioneView.as_view(), name="riunione"),
    path(
        "riunioni/<int:pk>/modifica/",
        views.RiunioneModificaView.as_view(),
        name="riunione_modifica",
    ),
    path("riunioni/<int:pk>/convoca/", views.ConvocaView.as_view(), name="convoca"),
    path("riunioni/<int:pk>/annulla/", views.AnnullaRiunioneView.as_view(), name="annulla"),
    path(
        "riunioni/<int:pk>/convocazione.pdf",
        views.ConvocazionePdfView.as_view(),
        name="convocazione",
    ),
    path("riunioni/<int:pk>/presenze/", views.PresenzeView.as_view(), name="presenze"),
    path("presenze/<int:pk>/", views.PresenzaView.as_view(), name="presenza"),
    path("riunioni/<int:pk>/verbale/", views.VerbaleView.as_view(), name="verbale"),
    path(
        "riunioni/<int:pk>/verbale/delibere/", views.DeliberaView.as_view(), name="delibera_nuova"
    ),
    path(
        "riunioni/<int:pk>/verbale/delibere/<int:delibera>/",
        views.DeliberaView.as_view(),
        name="delibera",
    ),
    path("riunioni/<int:pk>/verbale/chiudi/", views.ChiudiVerbaleView.as_view(), name="chiudi"),
    path("riunioni/<int:pk>/verbale.pdf", views.VerbalePdfView.as_view(), name="verbale_pdf"),
    path("delibere/", views.DelibereView.as_view(), name="delibere"),
]
