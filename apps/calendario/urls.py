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
    path("calendario.ics", views.ScaricaView.as_view(), name="scarica"),
    path("collegamento/", views.CollegamentoView.as_view(), name="collegamento"),
    path("feed/<str:codice>.ics", views.FeedPubblicoView.as_view(), name="feed_pubblico"),
]
