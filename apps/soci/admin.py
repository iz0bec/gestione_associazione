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

from apps.core.admin import SolaLettura

from .models import (
    CartaTessera,
    DomandaIscrizione,
    ListinoTessere,
    LottoTessere,
    Sezione,
    Socio,
    Tessera,
    TipologiaSocio,
)


@admin.register(Sezione)
class SezioneAdmin(admin.ModelAdmin):
    list_display = ["codice", "nome", "comune", "provincia", "attiva", "ordine"]
    search_fields = ["codice", "nome", "comune"]


@admin.register(ListinoTessere)
class ListinoTessereAdmin(SolaLettura):
    list_display = ["anno", "costo_acquisto"]


@admin.register(TipologiaSocio)
class TipologiaSocioAdmin(admin.ModelAdmin):
    list_display = ["nome", "quota_annua", "attiva", "ordine"]


@admin.register(Socio)
class SocioAdmin(SolaLettura):
    list_display = ["numero", "soggetto", "sezione", "tipologia", "stato", "data_ammissione"]
    list_filter = ["stato", "sezione", "tipologia"]
    search_fields = ["soggetto__cognome", "soggetto__nome", "soggetto__codice_fiscale"]


@admin.register(Tessera)
class TesseraAdmin(SolaLettura):
    list_display = ["codice", "socio", "importo", "pagata_il", "annullata"]
    list_filter = ["anno", "annullata"]


@admin.register(DomandaIscrizione)
class DomandaIscrizioneAdmin(SolaLettura):
    list_display = ["cognome", "nome", "ricevuta_il", "origine", "stato"]
    list_filter = ["stato", "origine"]


@admin.register(LottoTessere)
class LottoTessereAdmin(SolaLettura):
    list_display = ["__str__", "anno", "data_acquisizione", "fornitore", "costo_unitario"]
    list_filter = ["anno"]


@admin.register(CartaTessera)
class CartaTesseraAdmin(SolaLettura):
    list_display = ["codice", "anno", "stato", "lotto"]
    list_filter = ["anno", "stato"]
    search_fields = ["codice"]
