# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Pannello di amministrazione per i modelli di sistema
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.contrib import admin

from .models import EventoAudit, Organizzazione, Sequenza


@admin.register(Organizzazione)
class OrganizzazioneAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not Organizzazione.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Sequenza)
class SequenzaAdmin(admin.ModelAdmin):
    list_display = ["chiave", "anno", "ultimo_numero"]
    readonly_fields = ["chiave", "anno", "ultimo_numero"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(EventoAudit)
class EventoAuditAdmin(admin.ModelAdmin):
    list_display = [
        "momento",
        "utente_descrizione",
        "azione",
        "oggetto_descrizione",
        "indirizzo_ip",
    ]
    list_filter = ["azione"]
    search_fields = ["utente_descrizione", "oggetto_descrizione"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
