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
    path("ente", endpoint.ente, name="ente"),
    path("chiavi", endpoint.chiavi_controparte, name="chiavi"),
    path("cambiamenti", endpoint.cambiamenti, name="cambiamenti"),
    path("riepiloghi/<str:flusso>", endpoint.riepilogo, name="riepilogo"),
    path("eventi", endpoint.eventi, name="eventi"),
    path("eventi/<uuid:uuid_risorsa>", endpoint.evento, name="evento"),
    path("sezioni", endpoint.sezioni, name="sezioni"),
    path("eventi/<uuid:uuid_risorsa>/adesioni", endpoint.adesioni_evento, name="adesioni_evento"),
    path("adesioni/<uuid:uuid_risorsa>", endpoint.adesione, name="adesione"),
    path("domande", endpoint.domande, name="domande"),
    path("contatti", endpoint.contatti, name="contatti"),
    path("documenti", endpoint.documenti, name="documenti"),
    path("documenti/<int:pk>/file", endpoint.documento_file, name="documento_file"),
    path("organigramma", endpoint.organigramma, name="organigramma"),
    path("soci", endpoint.soci, name="soci"),
    path("consegne", endpoint.consegne, name="consegne"),
    path("tesseramento", endpoint.tesseramento, name="tesseramento"),
    path("trasferimenti", endpoint.trasferimenti, name="trasferimenti"),
    path(
        "trasferimenti/<uuid:uuid_risorsa>/esito",
        endpoint.esito_trasferimento,
        name="esito_trasferimento",
    ),
    path("tessere/<str:codice>", endpoint.verifica_tessera, name="verifica_tessera"),
    path(
        "ciclo-tessere/<str:risorsa>/<uuid:uuid_risorsa>",
        endpoint.documento_tessere,
        name="documento_tessere",
    ),
]
