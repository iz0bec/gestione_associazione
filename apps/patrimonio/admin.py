# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Amministrazione tecnica del patrimonio (sola consultazione)
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.contrib import admin

from apps.core.admin import SolaLettura

from .models import Bene, CategoriaBene, PassaggioConsegne, Uscita


@admin.register(Bene)
class BeneAdmin(SolaLettura):
    list_display = ["codice", "nome", "categoria", "stato", "valore"]
    list_filter = ["categoria", "stato"]
    search_fields = ["nome"]


@admin.register(Uscita)
class UscitaAdmin(SolaLettura):
    list_display = ["bene", "tipo", "data", "restituito_il"]


@admin.register(PassaggioConsegne)
class PassaggioConsegneAdmin(SolaLettura):
    list_display = ["data", "consegnante", "ricevente", "numero_beni"]


admin.site.register(CategoriaBene)
