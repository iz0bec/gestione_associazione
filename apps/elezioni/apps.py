# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Configurazione del modulo Rinnovo degli organi (procedura elettorale guidata).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.apps import AppConfig


class ElezioniConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.elezioni"
    verbose_name = "Rinnovo degli organi"
