# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Utente dell'applicazione
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.contrib.auth.models import AbstractUser, Group
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
    sezioni = models.ManyToManyField(
        "soci.Sezione",
        blank=True,
        related_name="utenti",
        help_text="Limita soci e tessere visibili a queste sezioni. Vuoto = tutte le sezioni.",
    )
    deve_cambiare_password = models.BooleanField(
        "deve cambiare la password",
        default=False,
        help_text="Al prossimo accesso l'utente deve scegliere una nuova password.",
    )
    puo_cambiare_password = models.BooleanField(
        "può cambiare la propria password",
        default=True,
        help_text="Tolta la spunta, la password la imposta solo l'amministratore (niente cambio "
        "né recupero via email da parte dell'utente).",
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


class PoliticaRuolo(models.Model):
    """Regole di accesso legate a un ruolo (gruppo Django)."""

    ruolo = models.OneToOneField(Group, on_delete=models.CASCADE, related_name="politica")
    mfa_obbligatoria = models.BooleanField(
        "secondo fattore obbligatorio",
        default=False,
        help_text="Chi ha questo ruolo deve configurare un'app di autenticazione o una passkey.",
    )

    class Meta:
        verbose_name = "regola del ruolo"
        verbose_name_plural = "regole dei ruoli"

    def __str__(self):
        return f"Regole di {self.ruolo}"
