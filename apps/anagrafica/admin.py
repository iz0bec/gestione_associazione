# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Amministrazione tecnica dell'anagrafica
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.contrib import admin

from .models import Categoria, Consenso, Soggetto


class ConsensoInline(admin.TabularInline):
    model = Consenso
    extra = 0


@admin.register(Soggetto)
class SoggettoAdmin(admin.ModelAdmin):
    list_display = ["__str__", "tipo", "email", "comune", "attivo"]
    list_filter = ["tipo", "attivo", "categorie"]
    search_fields = ["cognome", "nome", "denominazione", "email", "codice_fiscale"]
    filter_horizontal = ["categorie"]
    inlines = [ConsensoInline]


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ["nome", "descrizione", "colore"]
