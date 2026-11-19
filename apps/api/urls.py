# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: URL di Sistema → Collegamenti API
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.urls import path

from . import views

app_name = "api"

urlpatterns = [
    path("", views.ControparteElencoView.as_view(), name="elenco"),
    path("invito/", views.InvitoNuovoView.as_view(), name="invito_nuovo"),
    path("usa-invito/", views.UsaInvitoView.as_view(), name="usa_invito"),
    path("chiavi/ruota/", views.RuotaChiaviView.as_view(), name="ruota_chiavi"),
    path("<int:pk>/", views.ControparteView.as_view(), name="controparte"),
    path(
        "<int:pk>/verifica-soci/",
        views.VerificaSociNuovaView.as_view(),
        name="verifica_soci_nuova",
    ),
    path("verifiche-soci/<int:pk>/", views.VerificaSociView.as_view(), name="verifica_soci"),
    path("<int:pk>/modifica/", views.ControparteModificaView.as_view(), name="modifica"),
    path("<int:pk>/<str:azione>/", views.ControparteAzioneView.as_view(), name="azione"),
]
