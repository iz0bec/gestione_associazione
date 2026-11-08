# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: URL dei modelli di stampa
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.urls import path

from . import views

app_name = "documenti"

urlpatterns = [
    path("", views.ModelliView.as_view(), name="modelli"),
    path("nuovo/", views.ModelloNuovoView.as_view(), name="nuovo"),
    path("<int:pk>/", views.ModelloModificaView.as_view(), name="modifica"),
    path("<int:pk>/anteprima/", views.AnteprimaView.as_view(), name="anteprima"),
    path("stampa/", views.StampaView.as_view(), name="stampa"),
]
