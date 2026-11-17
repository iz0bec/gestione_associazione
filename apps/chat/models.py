# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Chat interna fra gli utenti del gestionale (non i soci): conversazioni dirette o
# *              di gruppo, partecipanti con l'ultimo messaggio letto, messaggi ritirabili
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.conf import settings
from django.db import models
from django.urls import reverse

MAX_TESTO = 4000


class Conversazione(models.Model):
    titolo = models.CharField(max_length=120, blank=True)
    gruppo = models.BooleanField(default=False)
    creata_da = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    creata_il = models.DateTimeField(auto_now_add=True)
    ultimo_messaggio_il = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        verbose_name = "conversazione"
        verbose_name_plural = "conversazioni"
        ordering = [models.F("ultimo_messaggio_il").desc(nulls_last=True), "-pk"]
        default_permissions = ()
        permissions = [("usa_chat", "Può usare la chat interna")]

    def __str__(self):
        return self.titolo or f"Conversazione n. {self.pk}"

    def get_absolute_url(self):
        return reverse("chat:conversazione", args=[self.pk])

    def presenti(self):
        """Partecipanti attivi (sfrutta il prefetch di «partecipazioni__utente»)."""
        return [p for p in self.partecipazioni.all() if p.uscito_il is None]

    def nome_per(self, utente):
        if self.titolo:
            return self.titolo
        altri = [p.utente for p in self.presenti() if p.utente_id != utente.pk]
        if not altri:
            return "Solo tu"
        return ", ".join(u.get_full_name() or u.get_username() for u in altri)


class Partecipazione(models.Model):
    conversazione = models.ForeignKey(
        Conversazione, on_delete=models.CASCADE, related_name="partecipazioni"
    )
    utente = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="partecipazioni_chat"
    )
    letto_fino = models.BigIntegerField(default=0, help_text="Ultimo messaggio letto.")
    aggiunto_il = models.DateTimeField(auto_now_add=True)
    uscito_il = models.DateTimeField(null=True, blank=True)

    class Meta:
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(fields=["conversazione", "utente"], name="partecipazione_unica")
        ]

    def __str__(self):
        return f"{self.utente} in {self.conversazione}"


class Messaggio(models.Model):
    conversazione = models.ForeignKey(
        Conversazione, on_delete=models.CASCADE, related_name="messaggi"
    )
    autore = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    testo = models.TextField(blank=True)
    sistema = models.BooleanField(default=False, help_text="Avviso automatico (ingressi, uscite).")
    inviato_il = models.DateTimeField(auto_now_add=True)
    ritirato_il = models.DateTimeField(null=True, blank=True)

    class Meta:
        default_permissions = ()
        ordering = ["pk"]

    def __str__(self):
        return f"Messaggio n. {self.pk}"
