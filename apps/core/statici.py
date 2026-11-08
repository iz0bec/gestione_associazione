# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: File statici in sviluppo: indirizzo con la data di modifica (?v=...) così il
# *              browser non usa una copia vecchia di app.js o app.css dopo una modifica.
# *              In produzione i nomi contengono già l'impronta (CompressedManifest...).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import os

from django.contrib.staticfiles import finders
from django.contrib.staticfiles.storage import StaticFilesStorage


class StaticiSviluppo(StaticFilesStorage):
    def url(self, name):
        indirizzo = super().url(name)
        percorso = finders.find(name)
        if isinstance(percorso, str) and os.path.exists(percorso):
            indirizzo += f"?v={int(os.path.getmtime(percorso))}"
        return indirizzo
