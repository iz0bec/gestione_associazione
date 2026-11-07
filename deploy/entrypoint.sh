#!/bin/sh
# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Avvio del container: migrazioni e ruoli, poi il comando richiesto
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
set -e
# le migrazioni le esegue solo il servizio web (il pianificatore imposta SALTA_MIGRAZIONI=1)
if [ "${SALTA_MIGRAZIONI:-0}" != "1" ]; then
  python manage.py migrate --noinput
fi
exec "$@"
