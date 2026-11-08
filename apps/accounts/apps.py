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


def _password_scelta(sender, request=None, user=None, **kwargs):
    """L'utente ha scelto una password propria: non è più temporanea."""
    if user is not None and user.deve_cambiare_password:
        user.deve_cambiare_password = False
        user.save(update_fields=["deve_cambiare_password"])


class AccountsConfig(AppConfig):
    name = "apps.accounts"
    verbose_name = "Utenti e accessi"

    def ready(self):
        post_migrate.connect(_allinea_ruoli, sender=self, dispatch_uid="allinea_ruoli")

        from allauth.account import signals

        for segnale in (signals.password_changed, signals.password_set, signals.password_reset):
            segnale.connect(_password_scelta, dispatch_uid=f"password_scelta_{id(segnale)}")
