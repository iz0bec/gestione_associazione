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

from apps.core.views import salute

admin.site.site_header = settings.APP_NOME
admin.site.site_title = settings.APP_NOME
admin.site.index_title = "Amministrazione tecnica"

urlpatterns = [
    path("salute/", salute, name="salute"),
    path("account/", include("allauth.urls")),
    path("amministrazione-tecnica/", admin.site.urls),
    path("anagrafica/", include("apps.anagrafica.urls")),
    path("", include("apps.core.urls")),
]

handler403 = "django.views.defaults.permission_denied"
handler404 = "django.views.defaults.page_not_found"
handler500 = "django.views.defaults.server_error"
