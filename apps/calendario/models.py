# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Appuntamenti e scadenze inseriti a mano; collegamento personale al calendario
# *              (iCal), di cui si conserva solo l'impronta.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.urls import reverse
from django.utils import timezone

from apps.core.models import ModelloBase


class Appuntamento(ModelloBase):
    """Evento, cerimonia, scadenza o promemoria inserito a mano. Non si cancella: si annulla."""

    class Tipo(models.TextChoices):
        EVENTO = "evento", "Evento"
        CERIMONIA = "cerimonia", "Cerimonia o commemorazione"
        SCADENZA = "scadenza", "Scadenza"
        PROMEMORIA = "promemoria", "Promemoria"

    ICONE = {"evento": "calendar-event", "cerimonia": "flag-3", "scadenza": "alarm",
             "promemoria": "bell"}  # fmt: skip

    titolo = models.CharField(max_length=200)
    tipo = models.CharField(max_length=12, choices=Tipo.choices, default=Tipo.EVENTO)
    giorno = models.DateField()
    ora = models.TimeField(null=True, blank=True, help_text="Vuota = tutto il giorno.")
    fine_giorno = models.DateField(
        "fino al", null=True, blank=True, help_text="Per gli impegni di più giorni."
    )
    ora_fine = models.TimeField("ora di fine", null=True, blank=True)
    luogo = models.CharField(max_length=200, blank=True)
    descrizione = models.TextField(blank=True)
    annuale = models.BooleanField(
        "ogni anno", default=False, help_text="Si ripete ogni anno nello stesso giorno."
    )
    completato_il = models.DateField("fatto il", null=True, blank=True, editable=False)
    annullato = models.BooleanField(default=False, editable=False)

    class Meta:
        verbose_name = "appuntamento"
        verbose_name_plural = "appuntamenti"
        ordering = ["giorno", "ora", "titolo"]
        constraints = [
            models.CheckConstraint(
                condition=Q(fine_giorno__isnull=True) | Q(fine_giorno__gte=F("giorno")),
                name="appuntamento_fine_dopo_inizio",
            )
        ]

    def __str__(self):
        return f"{self.titolo} ({self.giorno:%d/%m/%Y})"

    def get_absolute_url(self):
        return reverse("calendario:appuntamento", args=[self.pk])

    @property
    def icona(self):
        return self.ICONE.get(self.tipo, "calendar")

    @property
    def scadenza(self):
        return self.tipo == self.Tipo.SCADENZA

    def nel(self, anno):
        try:
            return self.giorno.replace(year=anno)
        except ValueError:  # 29 febbraio
            return self.giorno.replace(year=anno, day=28)

    def fatto_per(self, giorno):
        """Una scadenza annuale è fatta per l'anno dell'occorrenza, le altre una volta per tutte."""
        if not self.completato_il:
            return False
        return self.completato_il.year == giorno.year if self.annuale else True

    @property
    def prossima(self):
        """Data della scadenza da rispettare (per le annuali, quella dell'anno in corso)."""
        return self.nel(timezone.localdate().year) if self.annuale else self.giorno

    @property
    def fatto(self):
        return self.fatto_per(self.prossima)

    @property
    def scaduto(self):
        """Scadenza non ancora fatta la cui data è passata."""
        if not self.scadenza or self.annullato:
            return False
        return self.prossima < timezone.localdate() and not self.fatto


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
