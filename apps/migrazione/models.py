# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Corrispondenza fra i record dei gestionali precedenti e quelli importati:
# *              rende le importazioni rieseguibili senza doppioni.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class Origine(models.Model):
    class Fonte(models.TextChoices):
        GESTIONE_SOCI = "gestione_soci", "Gestione Soci"
        ASSEMBLEE = "assemblee", "Gestione Assemblee"
        PROTOCOLLO = "protocollo", "Protocollo ANCR"

    fonte = models.CharField(max_length=20, choices=Fonte.choices)
    tabella = models.CharField(max_length=60)
    chiave = models.CharField("identificativo nella fonte", max_length=100)
    oggetto_tipo = models.ForeignKey(ContentType, on_delete=models.CASCADE, related_name="+")
    oggetto_id = models.CharField(max_length=40)
    oggetto = GenericForeignKey("oggetto_tipo", "oggetto_id")
    importato_il = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "origine importata"
        verbose_name_plural = "origini importate"
        constraints = [
            models.UniqueConstraint(fields=["fonte", "tabella", "chiave"], name="origine_unica")
        ]

    def __str__(self):
        return f"{self.get_fonte_display()} {self.tabella}#{self.chiave}"
