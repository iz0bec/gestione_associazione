# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Cifratura dei segreti salvati nel database (es. password delle caselle
# *              di posta) con chiavi Fernet da CHIAVE_CIFRATURA (più chiavi = rotazione).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class ChiaveNonConfigurata(ImproperlyConfigured):
    pass


def _fernet():
    from cryptography.fernet import Fernet, MultiFernet

    chiavi = [c.strip() for c in (settings.CHIAVE_CIFRATURA or "").split(",") if c.strip()]
    if not chiavi:
        raise ChiaveNonConfigurata(
            "CHIAVE_CIFRATURA non impostata: generarla con "
            "`uv run python manage.py genera_chiave_cifratura` e inserirla nel file .env."
        )
    return MultiFernet([Fernet(c.encode()) for c in chiavi])


def cifratura_disponibile():
    return bool((settings.CHIAVE_CIFRATURA or "").strip())


def cifra(testo: str) -> str:
    return _fernet().encrypt(testo.encode()).decode()


def decifra(cifrato: str) -> str:
    return _fernet().decrypt(cifrato.encode()).decode()


def nuova_chiave() -> str:
    from cryptography.fernet import Fernet

    return Fernet.generate_key().decode()
