# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: URL del calendario
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.urls import path

from . import views

app_name = "calendario"

urlpatterns = [
    path("", views.CalendarioView.as_view(), name="calendario"),
    path("mese/", views.MeseView.as_view(), name="mese"),
    path("appuntamenti/nuovo/", views.AppuntamentoNuovoView.as_view(), name="appuntamento_nuovo"),
    path("appuntamenti/<int:pk>/", views.AppuntamentoView.as_view(), name="appuntamento"),
    path(
        "appuntamenti/<int:pk>/modifica/",
        views.AppuntamentoModificaView.as_view(),
        name="appuntamento_modifica",
    ),
    path(
        "appuntamenti/<int:pk>/azione/",
        views.AppuntamentoAzioneView.as_view(),
        name="appuntamento_azione",
    ),
    path("calendario.ics", views.ScaricaView.as_view(), name="scarica"),
    path("collegamento/", views.CollegamentoView.as_view(), name="collegamento"),
    path("feed/<str:codice>.ics", views.FeedPubblicoView.as_view(), name="feed_pubblico"),
]
