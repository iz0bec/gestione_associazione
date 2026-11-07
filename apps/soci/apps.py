# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Configurazione del modulo Soci e tesseramento
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.apps import AppConfig


class SociConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.soci"
    verbose_name = "Soci e tesseramento"
