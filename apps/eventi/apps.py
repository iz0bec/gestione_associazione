# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Configurazione dell'applicazione eventi
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.apps import AppConfig


class EventiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.eventi"
    verbose_name = "Eventi e cerimonie"
