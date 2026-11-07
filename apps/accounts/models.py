# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Utente dell'applicazione
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.contrib.auth.models import AbstractUser
from django.db import models


class Utente(AbstractUser):
    """Account di accesso. I ruoli sono gruppi Django (vedi ruoli.py)."""

    email = models.EmailField("email", unique=True)
    telefono = models.CharField(max_length=30, blank=True)
    soggetto = models.OneToOneField(
        "anagrafica.Soggetto",
        verbose_name="scheda anagrafica",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="utente",
        help_text="Collega l'account alla persona in anagrafica (facoltativo).",
    )

    class Meta:
        verbose_name = "utente"
        verbose_name_plural = "utenti"
        ordering = ["last_name", "first_name", "username"]

    def __str__(self):
        return self.get_full_name() or self.username

    @property
    def ruoli(self):
        return [g.name for g in self.groups.all()]
