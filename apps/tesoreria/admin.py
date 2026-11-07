# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Amministrazione tecnica della tesoreria (sola consultazione)
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.contrib import admin

from apps.core.admin import SolaLettura

from .models import Conto, Esercizio, Movimento, SaldoConto, Voce


@admin.register(Movimento)
class MovimentoAdmin(SolaLettura):
    list_display = ["codice", "data", "tipo", "importo", "conto", "voce", "annullato"]
    list_filter = ["esercizio", "tipo", "conto"]
    search_fields = ["descrizione", "controparte_testo"]


@admin.register(Esercizio)
class EsercizioAdmin(SolaLettura):
    list_display = ["anno", "stato", "chiuso_il"]


@admin.register(SaldoConto)
class SaldoContoAdmin(SolaLettura):
    list_display = ["esercizio", "conto", "iniziale", "finale"]


@admin.register(Voce)
class VoceAdmin(SolaLettura):
    list_display = ["codice", "tipo", "sezione", "descrizione"]
    list_filter = ["tipo", "sezione"]


admin.site.register(Conto)
