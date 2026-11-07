# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Modelli del patrimonio: inventario dei beni, valutazioni, prestiti e
# *              uscite definitive, passaggi di consegne con fotografia immutabile.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import secrets
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse

from apps.anagrafica.models import Soggetto
from apps.core.models import ModelloBase

SEQ_INVENTARIO = "inventario"  # unica, mai riavviata


def nuovo_token():
    return secrets.token_urlsafe(12)


class CategoriaBene(models.Model):
    nome = models.CharField(max_length=100, unique=True)
    ordine = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "categoria di beni"
        verbose_name_plural = "categorie di beni"
        ordering = ["ordine", "nome"]

    def __str__(self):
        return self.nome


def percorso_foto(istanza, nome):
    return f"patrimonio/foto/{istanza.token}.jpg"


class Bene(ModelloBase):
    class Acquisizione(models.TextChoices):
        ACQUISTO = "acquisto", "Acquisto"
        DONAZIONE = "donazione", "Donazione"
        LASCITO = "lascito", "Lascito"
        COMODATO = "comodato", "Ricevuto in comodato"
        RINVENIMENTO = "rinvenimento", "Rinvenimento"
        ALTRO = "altro", "Altro"

    class Conservazione(models.TextChoices):
        OTTIMO = "ottimo", "Ottimo"
        BUONO = "buono", "Buono"
        DISCRETO = "discreto", "Discreto"
        CATTIVO = "cattivo", "Cattivo"
        DA_RESTAURARE = "restauro", "Da restaurare"

    class Stato(models.TextChoices):
        IN_DOTAZIONE = "dotazione", "In dotazione"
        IN_PRESTITO = "prestito", "In prestito"
        USCITO = "uscito", "Uscito dal patrimonio"

    numero = models.PositiveIntegerField("numero di inventario", unique=True, editable=False)
    codice_precedente = models.CharField(
        "numero di inventario precedente",
        max_length=50,
        blank=True,
        help_text="Da registri cartacei.",
    )
    nome = models.CharField(max_length=200)
    categoria = models.ForeignKey(CategoriaBene, on_delete=models.PROTECT, related_name="beni")
    descrizione = models.TextField(blank=True)
    quantita = models.PositiveIntegerField("quantità", default=1, validators=[MinValueValidator(1)])
    ubicazione = models.CharField(
        max_length=200, blank=True, help_text="Es. sede, sala riunioni, armadio 2."
    )
    conservazione = models.CharField(
        "stato di conservazione",
        max_length=10,
        choices=Conservazione.choices,
        default=Conservazione.BUONO,
    )
    acquisizione = models.CharField(
        "modalità di acquisizione",
        max_length=12,
        choices=Acquisizione.choices,
        default=Acquisizione.ACQUISTO,
    )
    data_acquisizione = models.DateField("data di acquisizione", null=True, blank=True)
    provenienza = models.ForeignKey(
        Soggetto,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="beni_donati",
        verbose_name="donatore / fornitore",
    )
    provenienza_testo = models.CharField("donatore / fornitore", max_length=200, blank=True)
    documento = models.CharField(
        "documento di acquisizione",
        max_length=200,
        blank=True,
        help_text="Fattura, atto di donazione, verbale.",
    )
    movimento = models.ForeignKey(
        "tesoreria.Movimento",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="beni",
        verbose_name="movimento di tesoreria",
    )
    valore_acquisizione = models.DecimalField(
        "valore di acquisizione", max_digits=12, decimal_places=2, default=Decimal("0")
    )
    valore = models.DecimalField(
        "valore attuale", max_digits=12, decimal_places=2, default=Decimal("0")
    )
    foto = models.ImageField(upload_to=percorso_foto, blank=True, max_length=255)
    note = models.TextField(blank=True)
    stato = models.CharField(
        max_length=10, choices=Stato.choices, default=Stato.IN_DOTAZIONE, db_index=True
    )
    # scheda pubblica (QR): dati minimi, nessun valore né ubicazione
    token = models.CharField(max_length=32, unique=True, default=nuovo_token, editable=False)
    pubblico = models.BooleanField(
        "scheda pubblica", default=False, help_text="Visibile a chi inquadra il QR, senza accesso."
    )
    descrizione_pubblica = models.TextField(
        "testo della scheda pubblica",
        blank=True,
        help_text="Storia del cimelio, provenienza, significato.",
    )
    foto_pubblica = models.BooleanField("mostra la foto nella scheda pubblica", default=False)

    class Meta:
        verbose_name = "bene"
        verbose_name_plural = "inventario"
        ordering = ["numero"]
        permissions = [
            ("movimenta_bene", "Può registrare prestiti, restituzioni e uscite dei beni"),
            ("valuta_bene", "Può registrare le valutazioni dei beni"),
        ]

    def __str__(self):
        return f"{self.codice} {self.nome}"

    def get_absolute_url(self):
        return reverse("patrimonio:bene", args=[self.pk])

    @property
    def codice(self):
        return f"INV {self.numero:05d}"

    @property
    def in_patrimonio(self):
        return self.stato != self.Stato.USCITO

    @property
    def valore_totale(self):
        return self.valore * self.quantita


class Valutazione(models.Model):
    class Metodo(models.TextChoices):
        STIMA = "stima", "Stima interna"
        PERIZIA = "perizia", "Perizia di un esperto"
        ASSICURAZIONE = "assicurazione", "Valore assicurato"
        MERCATO = "mercato", "Valore di mercato"

    bene = models.ForeignKey(Bene, on_delete=models.CASCADE, related_name="valutazioni")
    data = models.DateField()
    valore = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0"))]
    )
    metodo = models.CharField(max_length=15, choices=Metodo.choices, default=Metodo.STIMA)
    note = models.CharField(max_length=255, blank=True)
    registrata_il = models.DateTimeField(auto_now_add=True)
    registrata_da = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        verbose_name = "valutazione"
        verbose_name_plural = "valutazioni"
        ordering = ["-data", "-registrata_il"]

    def __str__(self):
        return f"{self.bene.codice} {self.data:%d/%m/%Y}: {self.valore}"


class Uscita(ModelloBase):
    """Prestito (temporaneo) o uscita definitiva di un bene dal patrimonio."""

    class Tipo(models.TextChoices):
        PRESTITO = "prestito", "Prestito"
        DONAZIONE = "donazione", "Donazione ad altri"
        VENDITA = "vendita", "Vendita"
        RESTITUZIONE = "restituzione", "Restituzione al proprietario (comodato)"
        DISMISSIONE = "dismissione", "Dismissione / distruzione"
        SMARRIMENTO = "smarrimento", "Smarrimento o furto"

    class Rientro(models.TextChoices):
        INTEGRO = "integro", "Integro"
        DANNEGGIATO = "danneggiato", "Danneggiato"

    bene = models.ForeignKey(Bene, on_delete=models.PROTECT, related_name="uscite")
    tipo = models.CharField(max_length=12, choices=Tipo.choices)
    data = models.DateField()
    controparte = models.ForeignKey(
        Soggetto, null=True, blank=True, on_delete=models.SET_NULL, related_name="beni_ricevuti"
    )
    controparte_testo = models.CharField("a chi", max_length=200, blank=True)
    motivo = models.CharField(max_length=255, help_text="Es. mostra al Comune per il 4 Novembre.")
    condizioni = models.TextField(
        blank=True, help_text="Per i prestiti: cura, assicurazione, riconsegna."
    )
    restituzione_prevista = models.DateField("restituzione prevista", null=True, blank=True)
    restituito_il = models.DateField("restituito il", null=True, blank=True)
    rientro = models.CharField(
        "condizioni al rientro", max_length=12, choices=Rientro.choices, blank=True
    )
    note_rientro = models.CharField(max_length=255, blank=True)
    importo = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0"), help_text="Per le vendite."
    )

    class Meta:
        verbose_name = "uscita del bene"
        verbose_name_plural = "prestiti e uscite"
        ordering = ["-data", "-pk"]

    def __str__(self):
        return f"{self.get_tipo_display()} {self.bene.codice} del {self.data:%d/%m/%Y}"

    @property
    def definitiva(self):
        return self.tipo != self.Tipo.PRESTITO

    @property
    def in_corso(self):
        return self.tipo == self.Tipo.PRESTITO and self.restituito_il is None


class PassaggioConsegne(models.Model):
    """Fotografia immutabile dell'inventario consegnata da un responsabile al successivo."""

    data = models.DateField()
    consegnante = models.CharField("consegna", max_length=200)
    consegnante_ruolo = models.CharField("ruolo di chi consegna", max_length=100)
    ricevente = models.CharField("riceve", max_length=200)
    ricevente_ruolo = models.CharField("ruolo di chi riceve", max_length=100)
    note = models.TextField(
        blank=True, help_text="Osservazioni, beni mancanti o danneggiati riscontrati."
    )
    beni = models.JSONField(default=list, editable=False)
    numero_beni = models.PositiveIntegerField(editable=False)
    valore_totale = models.DecimalField(max_digits=14, decimal_places=2, editable=False)
    file = models.FileField(upload_to="patrimonio/passaggi/", max_length=255, editable=False)
    impronta = models.CharField(max_length=64, editable=False)
    protocollo = models.ForeignKey(
        "protocollo.Protocollo", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    creato_il = models.DateTimeField(auto_now_add=True)
    creato_da = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        verbose_name = "passaggio di consegne"
        verbose_name_plural = "passaggi di consegne"
        ordering = ["-data", "-pk"]

    def __str__(self):
        return f"Passaggio di consegne del {self.data:%d/%m/%Y}"

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("Un passaggio di consegne non si modifica.")
        super().save(*args, **kwargs)
