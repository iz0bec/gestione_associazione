# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: URL della gestione utenti
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.urls import path

from . import views

app_name = "utenti"

urlpatterns = [
    path("", views.UtentiView.as_view(), name="elenco"),
    path("nuovo/", views.UtenteNuovoView.as_view(), name="nuovo"),
    path("ruoli/", views.RuoliView.as_view(), name="ruoli"),
    path("<int:pk>/", views.UtenteView.as_view(), name="utente"),
    path("<int:pk>/password/", views.ReimpostaPasswordView.as_view(), name="password"),
    path(
        "<int:pk>/imposta-password/", views.ImpostaPasswordView.as_view(), name="imposta_password"
    ),
    path(
        "<int:pk>/secondo-fattore/",
        views.AzzeraSecondoFattoreView.as_view(),
        name="azzera_mfa",
    ),
    path("<int:pk>/attivo/", views.AttivaView.as_view(), name="attivo"),
]
