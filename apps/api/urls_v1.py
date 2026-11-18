# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: URL dell'API v1 (contratto in docs/api/openapi.yaml)
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.urls import path

from . import endpoint

app_name = "api_v1"

urlpatterns = [
    path("abbinamenti", endpoint.abbinamenti, name="abbinamenti"),
    path("prova", endpoint.prova, name="prova"),
    path("chiavi", endpoint.chiavi_controparte, name="chiavi"),
    path("cambiamenti", endpoint.cambiamenti, name="cambiamenti"),
    path("riepiloghi/<str:flusso>", endpoint.riepilogo, name="riepilogo"),
    path("eventi", endpoint.eventi, name="eventi"),
    path("eventi/<uuid:uuid_risorsa>", endpoint.evento, name="evento"),
    path("sezioni", endpoint.sezioni, name="sezioni"),
]
