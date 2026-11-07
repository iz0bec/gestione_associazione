# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Amministrazione tecnica degli organi sociali (sola consultazione)
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.contrib import admin

from apps.core.admin import SolaLettura

from .models import Carica, Delibera, Organo, Riunione, Verbale


@admin.register(Organo)
class OrganoAdmin(admin.ModelAdmin):
    list_display = ["nome", "sigla", "tipo", "quorum_prima", "quorum_seconda", "max_deleghe"]


@admin.register(Carica)
class CaricaAdmin(SolaLettura):
    list_display = ["organo", "ruolo", "soggetto", "dal", "al"]
    list_filter = ["organo"]


@admin.register(Riunione)
class RiunioneAdmin(SolaLettura):
    list_display = ["__str__", "stato"]
    list_filter = ["organo", "stato"]


@admin.register(Verbale)
class VerbaleAdmin(SolaLettura):
    list_display = ["__str__", "chiuso", "numero"]


@admin.register(Delibera)
class DeliberaAdmin(SolaLettura):
    list_display = ["codice", "oggetto", "esito"]
