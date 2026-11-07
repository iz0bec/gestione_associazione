# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Configurazione del modulo Comunicazioni e anniversari
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.apps import AppConfig


class ComunicazioniConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.comunicazioni"
    verbose_name = "Comunicazioni e anniversari"
