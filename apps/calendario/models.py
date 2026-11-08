# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Collegamento personale al calendario (iCal): se ne conserva solo l'impronta
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.conf import settings
from django.db import models


class FeedCalendario(models.Model):
    """Indirizzo segreto con cui il calendario del telefono o del computer legge gli impegni
    visibili all'utente. Il codice è mostrato una sola volta; nel database resta l'impronta."""

    utente = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="feed_calendario"
    )
    impronta = models.CharField(max_length=64, unique=True)
    compleanni = models.BooleanField(
        "compleanni dei soci", default=False, help_text="Aggiunge i compleanni dei soci attivi."
    )
    creato_il = models.DateTimeField(auto_now_add=True)
    ultimo_accesso = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "collegamento al calendario"
        verbose_name_plural = "collegamenti al calendario"

    def __str__(self):
        return f"Calendario di {self.utente}"
