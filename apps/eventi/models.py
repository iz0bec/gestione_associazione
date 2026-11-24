# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Eventi e cerimonie (date, luogo, posti) e adesioni (segreteria, modulo
# *              pubblico, area del socio)
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import secrets
import uuid

from django.db import models
from django.db.models import Q, Sum
from django.urls import reverse
from django.utils import timezone

from apps.anagrafica.models import Soggetto
from apps.api.risorse import RisorsaApi
from apps.core.models import ModelloBase


def _token():
    return secrets.token_urlsafe(18)


class Evento(RisorsaApi, ModelloBase):
    FLUSSO = "eventi"
    RISORSA = "evento"

    class Tipo(models.TextChoices):
        CERIMONIA = "cerimonia", "Cerimonia o commemorazione"
        INCONTRO = "incontro", "Incontro o conferenza"
        GITA = "gita", "Gita o viaggio"
        CONVIVIALE = "conviviale", "Pranzo o cena"
        ALTRO = "altro", "Altro"

    titolo = models.CharField(max_length=200)
    tipo = models.CharField(max_length=12, choices=Tipo.choices, default=Tipo.CERIMONIA)
    inizio = models.DateTimeField()
    fine = models.DateTimeField(null=True, blank=True)
    luogo = models.CharField(max_length=200, blank=True)
    descrizione = models.TextField(blank=True, help_text="Programma, appuntamento, indicazioni.")
    quota = models.CharField(
        "quota di partecipazione", max_length=100, blank=True,
        help_text="Solo indicativa (es. «25 € a persona»); gli incassi si registrano in Tesoreria.",
    )  # fmt: skip
    posti = models.PositiveIntegerField(
        "posti disponibili", null=True, blank=True, help_text="Vuoto: senza limite."
    )
    accompagnatori = models.PositiveSmallIntegerField(
        "accompagnatori per adesione", default=0, help_text="Quanti accompagnatori può indicare."
    )
    adesioni_aperte = models.BooleanField(default=True)
    chiusura_adesioni = models.DateTimeField(
        "adesioni fino al", null=True, blank=True, help_text="Vuoto: fino all'inizio."
    )
    pubblico = models.BooleanField(
        "modulo pubblico di adesione", default=False,
        help_text="Chiunque abbia il collegamento può aderire (anche i non soci).",
    )  # fmt: skip
    sito = models.BooleanField(
        "pubblica sui siti collegati", default=False,
        help_text="I siti collegati (es. WordPress con il connettore) ne fanno un articolo, in "
        "bozza da rivedere. Vale solo con il modulo pubblico.",
    )  # fmt: skip
    token = models.CharField(max_length=32, unique=True, default=_token, editable=False)
    annullato = models.BooleanField(default=False)

    class Meta:
        verbose_name = "evento"
        verbose_name_plural = "eventi"
        ordering = ["-inizio"]

    def __str__(self):
        return self.titolo

    def get_absolute_url(self):
        return reverse("eventi:evento", args=[self.pk])

    def azione_api(self, nuovo):
        if not nuovo and self.annullato:
            precedente = type(self).objects.filter(pk=self.pk)
            prima = precedente.values_list("annullato", flat=True).first()
            if prima is False:
                return "annullato"
        return super().azione_api(nuovo)

    def adesioni_valide(self):
        return self.adesioni.filter(annullata=False)

    @property
    def partecipanti(self):
        """Persone attese: aderenti più accompagnatori."""
        r = self.adesioni_valide().aggregate(n=models.Count("pk"), a=Sum("accompagnatori"))
        return (r["n"] or 0) + (r["a"] or 0)

    @property
    def posti_liberi(self):
        return None if self.posti is None else max(self.posti - self.partecipanti, 0)

    @property
    def scadenza_adesioni(self):
        return self.chiusura_adesioni or self.inizio

    @property
    def si_puo_aderire(self):
        return (
            self.adesioni_aperte
            and not self.annullato
            and timezone.now() < self.scadenza_adesioni
            and (self.posti is None or self.posti_liberi > 0)
        )


class Adesione(models.Model):
    class Origine(models.TextChoices):
        SEGRETERIA = "segreteria", "Segreteria"
        PUBBLICO = "pubblico", "Modulo pubblico"
        AREA = "area", "Area del socio"
        INTEGRAZIONE = "integrazione", "Integrazione (API)"

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    versione = models.PositiveIntegerField(default=1, editable=False)

    evento = models.ForeignKey(Evento, on_delete=models.CASCADE, related_name="adesioni")
    soggetto = models.ForeignKey(
        Soggetto, null=True, blank=True, on_delete=models.SET_NULL, related_name="adesioni"
    )
    cognome = models.CharField(max_length=100)
    nome = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    telefono = models.CharField(max_length=30, blank=True)
    accompagnatori = models.PositiveSmallIntegerField(default=0)
    note = models.CharField(max_length=255, blank=True)
    origine = models.CharField(max_length=12, choices=Origine.choices)
    cliente_api = models.ForeignKey(
        "api.ClienteApi", null=True, blank=True, on_delete=models.SET_NULL, related_name="adesioni",
        verbose_name="inviata da",
    )  # fmt: skip
    riferimento_esterno = models.CharField(max_length=100, blank=True, editable=False)
    annullata = models.BooleanField(default=False)
    creata_il = models.DateTimeField(auto_now_add=True)
    modificata_il = models.DateTimeField(auto_now=True)
    indirizzo_ip = models.GenericIPAddressField(null=True, blank=True, editable=False)

    class Meta:
        verbose_name = "adesione"
        verbose_name_plural = "adesioni"
        ordering = ["cognome", "nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["evento", "soggetto"],
                condition=Q(soggetto__isnull=False, annullata=False),
                name="una_adesione_per_persona",
            )
        ]

    def __str__(self):
        return f"{self.cognome} {self.nome}".strip()
