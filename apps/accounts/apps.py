# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Configurazione dell'app accounts
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.apps import AppConfig
from django.db.models.signals import post_migrate


def _allinea_ruoli(sender, using="default", **kwargs):
    from django.apps import apps
    from django.contrib.auth.management import create_permissions

    from .ruoli import configura_ruoli

    # I permessi vengono creati app per app: li creo tutti prima di assegnarli ai ruoli
    for app_config in apps.get_app_configs():
        create_permissions(app_config, verbosity=0, using=using)
    configura_ruoli()


class AccountsConfig(AppConfig):
    name = "apps.accounts"
    verbose_name = "Utenti e accessi"

    def ready(self):
        post_migrate.connect(_allinea_ruoli, sender=self, dispatch_uid="allinea_ruoli")
