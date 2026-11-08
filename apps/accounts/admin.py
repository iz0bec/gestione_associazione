# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Amministrazione tecnica degli utenti
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Utente


@admin.register(Utente)
class UtenteAdmin(UserAdmin):
    fieldsets = (
        *UserAdmin.fieldsets,
        ("Associazione", {"fields": ("telefono", "soggetto", "sezioni", "deve_cambiare_password")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("username", "email", "password1", "password2")}),
    )
    list_display = ["username", "email", "first_name", "last_name", "is_active", "is_staff"]
    raw_id_fields = ["soggetto"]
    filter_horizontal = [*UserAdmin.filter_horizontal, "sezioni"]
