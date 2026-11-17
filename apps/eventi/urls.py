# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Indirizzi degli eventi
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.urls import path

from . import views

app_name = "eventi"

urlpatterns = [
    path("", views.EventiView.as_view(), name="elenco"),
    path("nuovo/", views.EventoNuovoView.as_view(), name="nuovo"),
    path("<int:pk>/", views.EventoView.as_view(), name="evento"),
    path("<int:pk>/modifica/", views.EventoModificaView.as_view(), name="modifica"),
    path("<int:pk>/adesioni/", views.AdesioneNuovaView.as_view(), name="adesione_nuova"),
    path("<int:pk>/aderenti.<str:formato>", views.AderentiView.as_view(), name="aderenti"),
    path(
        "adesioni/<int:pk>/annulla/", views.AdesioneAnnullaView.as_view(), name="adesione_annulla"
    ),
]
