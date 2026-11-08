# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: URL principali
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from apps.core.aspetto import aspetto_css, logo
from apps.core.configurazione import ConfigurazioneView
from apps.core.views import (
    DocumentiPubbliciView,
    DocumentoPubblicoView,
    PresentazioneView,
    salute,
)
from apps.core.viste_backup import StatoRipristinoView
from apps.patrimonio.views import BenePubblicoView, FotoPubblicaView
from apps.soci.pubblico import DomandaInviataView, DomandaPubblicaView

admin.site.site_header = settings.APP_NOME
admin.site.site_title = settings.APP_NOME
admin.site.index_title = "Amministrazione tecnica"

urlpatterns = [
    path("salute/", salute, name="salute"),
    path("aspetto.css", aspetto_css, name="aspetto_css"),
    path("logo.png", logo, name="logo"),
    path("ripristino/", StatoRipristinoView.as_view(), name="stato_ripristino"),
    path("account/", include("allauth.urls")),
    path("amministrazione-tecnica/", admin.site.urls),
    path("sistema/utenti/", include("apps.accounts.urls")),
    path("anagrafica/", include("apps.anagrafica.urls")),
    path("soci/", include("apps.soci.urls")),
    path("protocollo/", include("apps.protocollo.urls")),
    path("organi/", include("apps.organi.urls")),
    path("comunicazioni/", include("apps.comunicazioni.urls")),
    path("tesoreria/", include("apps.tesoreria.urls")),
    path("patrimonio/", include("apps.patrimonio.urls")),
    path("documenti/", include("apps.documenti.urls")),
    path("calendario/", include("apps.calendario.urls")),
    path("beni/<str:token>/", BenePubblicoView.as_view(), name="bene_pubblico"),
    path("beni/<str:token>/foto/", FotoPubblicaView.as_view(), name="bene_pubblico_foto"),
    path("iscrizione/", DomandaPubblicaView.as_view(), name="iscrizione"),
    path("documenti-pubblici/", DocumentiPubbliciView.as_view(), name="documenti_pubblici"),
    path("presentazione/", PresentazioneView.as_view(), name="presentazione"),
    path(
        "documenti-pubblici/<int:pk>/<slug:slug>.pdf",
        DocumentoPubblicoView.as_view(),
        name="documento_pubblico",
    ),
    path("iscrizione/inviata/", DomandaInviataView.as_view(), name="iscrizione_inviata"),
    path("configurazione-iniziale/", ConfigurazioneView.as_view(), name="configurazione_inizio"),
    path(
        "configurazione-iniziale/<str:passo>/", ConfigurazioneView.as_view(), name="configurazione"
    ),
    path("", include("apps.core.urls")),
]

handler403 = "django.views.defaults.permission_denied"
handler404 = "django.views.defaults.page_not_found"
handler500 = "django.views.defaults.server_error"
