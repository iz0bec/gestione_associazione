# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: URL dell'app core
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.CruscottoView.as_view(), name="cruscotto"),
    path("organizzazione/", views.OrganizzazioneView.as_view(), name="organizzazione"),
    path("organizzazione/aspetto/", views.AspettoView.as_view(), name="aspetto"),
    path("organizzazione/logo-modulo/", views.LogoModuloView.as_view(), name="logo_modulo"),
    path("registro-attivita/", views.RegistroAttivitaView.as_view(), name="registro_attivita"),
]
