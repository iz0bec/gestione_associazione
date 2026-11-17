# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Accessi all'area personale (collegamenti monouso) e richieste di correzione
# *              dei dati
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.conf import settings
from django.db import models

from apps.anagrafica.models import Soggetto


class AccessoArea(models.Model):
    """Collegamento di accesso inviato per email: si conserva solo l'impronta del codice."""

    soggetto = models.ForeignKey(Soggetto, on_delete=models.CASCADE, related_name="accessi_area")
    impronta = models.CharField(max_length=64, unique=True)
    creato_il = models.DateTimeField(auto_now_add=True, db_index=True)
    usato_il = models.DateTimeField(null=True, blank=True)
    indirizzo_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name = "accesso all'area personale"
        verbose_name_plural = "accessi all'area personale"

    def __str__(self):
        return f"Accesso di {self.soggetto} del {self.creato_il:%d/%m/%Y %H:%M}"


class RichiestaArea(models.Model):
    """Richiesta del socio (es. correzione dei dati), da gestire dalla segreteria."""

    soggetto = models.ForeignKey(Soggetto, on_delete=models.CASCADE, related_name="richieste_area")
    testo = models.TextField()
    creata_il = models.DateTimeField(auto_now_add=True)
    gestita_il = models.DateTimeField(null=True, blank=True)
    gestita_da = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        verbose_name = "richiesta dall'area personale"
        verbose_name_plural = "richieste dall'area personale"
        ordering = ["-creata_il"]

    def __str__(self):
        return f"{self.soggetto}: {self.testo[:40]}"
