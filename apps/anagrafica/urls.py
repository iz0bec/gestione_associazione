# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: URL dell'anagrafica
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.urls import path

from . import views

app_name = "anagrafica"

urlpatterns = [
    path("", views.ElencoView.as_view(), name="elenco"),
    path("nuovo/", views.CreaView.as_view(), name="nuovo"),
    path("esporta.csv", views.EsportaView.as_view(), name="esporta"),
    path("rubrica.vcf", views.EsportaVCardView.as_view(), name="esporta_vcard"),
    path("importa/", views.ImportaVCardView.as_view(), name="importa_vcard"),
    path("<int:pk>/vcard.vcf", views.VCardSoggettoView.as_view(), name="vcard"),
    path("<int:pk>/", views.DettaglioView.as_view(), name="dettaglio"),
    path("<int:pk>/modifica/", views.ModificaView.as_view(), name="modifica"),
    path("<int:pk>/foto/", views.FotoView.as_view(), name="foto"),
    path("<int:pk>/archivia/", views.ArchiviaView.as_view(), name="archivia"),
    path("<int:pk>/consenso/", views.ConsensoView.as_view(), name="consenso"),
]
