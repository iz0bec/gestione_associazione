# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Amministrazione tecnica del libro soci (sola consultazione: le
# *              operazioni passano dall'interfaccia, che numera e registra).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.contrib import admin

from .models import DomandaIscrizione, Socio, Tessera, TipologiaSocio


class SolaLettura(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TipologiaSocio)
class TipologiaSocioAdmin(admin.ModelAdmin):
    list_display = ["nome", "quota_annua", "attiva", "ordine"]


@admin.register(Socio)
class SocioAdmin(SolaLettura):
    list_display = ["numero", "soggetto", "tipologia", "stato", "data_ammissione"]
    list_filter = ["stato", "tipologia"]
    search_fields = ["soggetto__cognome", "soggetto__nome", "soggetto__codice_fiscale"]


@admin.register(Tessera)
class TesseraAdmin(SolaLettura):
    list_display = ["codice", "socio", "importo", "pagata_il", "annullata"]
    list_filter = ["anno", "annullata"]


@admin.register(DomandaIscrizione)
class DomandaIscrizioneAdmin(SolaLettura):
    list_display = ["cognome", "nome", "ricevuta_il", "origine", "stato"]
    list_filter = ["stato", "origine"]
