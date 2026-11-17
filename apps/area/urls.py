# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Indirizzi dell'area personale dei soci
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.urls import path

from . import views

app_name = "area"

urlpatterns = [
    path("", views.AreaView.as_view(), name="area"),
    path("accesso/", views.AccessoView.as_view(), name="accesso"),
    path("accesso/inviato/", views.InviatoView.as_view(), name="inviato"),
    path("entra/<str:firmato>/", views.EntraView.as_view(), name="entra"),
    path("ricevute/<int:pk>.pdf", views.RicevutaView.as_view(), name="ricevuta"),
    path("eventi/<int:pk>/aderisci/", views.AderisciView.as_view(), name="aderisci"),
    path("eventi/<int:pk>/rinuncia/", views.RinunciaView.as_view(), name="rinuncia"),
    path("richiesta/", views.RichiestaView.as_view(), name="richiesta"),
    path("telegram/", views.TelegramView.as_view(), name="telegram"),
    path("esci/", views.EsciView.as_view(), name="esci"),
    path("richieste/<int:pk>/gestita/", views.RichiestaGestitaView.as_view(), name="gestita"),
]
