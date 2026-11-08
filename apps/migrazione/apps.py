# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Configurazione dell'app di importazione dai gestionali precedenti
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.apps import AppConfig


class MigrazioneConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.migrazione"
    verbose_name = "Importazione dai gestionali precedenti"
