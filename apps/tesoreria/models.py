# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Modelli della tesoreria per cassa: esercizi, conti e saldi, piano dei
# *              conti del rendiconto per cassa ETS (Modello D) con sottovoci, prima nota,
# *              preventivo.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.urls import reverse

from apps.anagrafica.models import Soggetto
from apps.core.models import ModelloBase

SEQ_PRIMA_NOTA = "prima_nota"  # annuale, per esercizio


class Esercizio(models.Model):
    class Stato(models.TextChoices):
        APERTO = "aperto", "Aperto"
        CHIUSO = "chiuso", "Chiuso"

    anno = models.PositiveIntegerField(unique=True)
    stato = models.CharField(max_length=6, choices=Stato.choices, default=Stato.APERTO)
    chiuso_il = models.DateTimeField(null=True, blank=True, editable=False)
    chiuso_da = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    approvazione = models.CharField(
        "approvazione del rendiconto",
        max_length=200,
        blank=True,
        help_text="Es. «Assemblea dei soci del 20/04/2027, delibera ASS 2/2027».",
    )
    note = models.TextField(blank=True)

    class Meta:
        verbose_name = "esercizio"
        verbose_name_plural = "esercizi"
        ordering = ["-anno"]
        permissions = [("chiudi_esercizio", "Può chiudere e riaprire gli esercizi")]

    def __str__(self):
        return f"Esercizio {self.anno}"

    def get_absolute_url(self):
        return reverse("tesoreria:cruscotto") + f"?anno={self.anno}"

    @property
    def aperto(self):
        return self.stato == self.Stato.APERTO


class Conto(models.Model):
    class Tipo(models.TextChoices):
        CASSA = "cassa", "Cassa contanti"
        BANCA = "banca", "Conto corrente bancario"
        POSTALE = "postale", "Conto corrente postale"
        ALTRO = "altro", "Altro (carta prepagata, ...)"

    nome = models.CharField(max_length=100, unique=True)
    tipo = models.CharField(max_length=8, choices=Tipo.choices, default=Tipo.BANCA)
    iban = models.CharField("IBAN", max_length=34, blank=True)
    per_contanti = models.BooleanField(
        "usato per le quote in contanti", default=False, help_text="Un solo conto."
    )
    per_pagamenti_elettronici = models.BooleanField(
        "usato per le quote con bonifico o POS", default=False, help_text="Un solo conto."
    )
    attivo = models.BooleanField(default=True)
    ordine = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "conto"
        verbose_name_plural = "conti"
        ordering = ["ordine", "nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["per_contanti"],
                condition=Q(per_contanti=True),
                name="un_conto_per_contanti",
            ),
            models.UniqueConstraint(
                fields=["per_pagamenti_elettronici"],
                condition=Q(per_pagamenti_elettronici=True),
                name="un_conto_per_elettronici",
            ),
        ]

    def __str__(self):
        return self.nome

    @property
    def e_cassa(self):
        return self.tipo == self.Tipo.CASSA


class SaldoConto(models.Model):
    """Saldo di apertura (e di chiusura, a esercizio chiuso) di un conto in un esercizio."""

    esercizio = models.ForeignKey(Esercizio, on_delete=models.CASCADE, related_name="saldi")
    conto = models.ForeignKey(Conto, on_delete=models.PROTECT, related_name="saldi")
    iniziale = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    finale = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    class Meta:
        verbose_name = "saldo del conto"
        verbose_name_plural = "saldi dei conti"
        constraints = [models.UniqueConstraint(fields=["esercizio", "conto"], name="saldo_unico")]

    def __str__(self):
        return f"{self.conto} {self.esercizio.anno}"


class Voce(models.Model):
    """Voce del rendiconto per cassa (Modello D) o sottovoce di dettaglio dell'associazione."""

    class Tipo(models.TextChoices):
        ENTRATA = "entrata", "Entrata"
        USCITA = "uscita", "Uscita"

    class Sezione(models.TextChoices):
        A = "A", "A) Attività di interesse generale"
        B = "B", "B) Attività diverse"
        C = "C", "C) Attività di raccolta fondi"
        D = "D", "D) Attività finanziarie e patrimoniali"
        E = "E", "E) Supporto generale"
        INV = "INV", "Investimenti e disinvestimenti"
        IMP = "IMP", "Imposte"

    codice = models.CharField(max_length=20, unique=True)
    tipo = models.CharField(max_length=7, choices=Tipo.choices)
    sezione = models.CharField(max_length=3, choices=Sezione.choices)
    numero = models.PositiveSmallIntegerField(
        default=0, help_text="Numero della voce nella sezione."
    )
    descrizione = models.CharField(max_length=200)
    padre = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="sottovoci",
        verbose_name="voce del rendiconto",
        limit_choices_to={"padre__isnull": True},
    )
    attiva = models.BooleanField(default=True)

    class Meta:
        verbose_name = "voce"
        verbose_name_plural = "piano dei conti"
        ordering = ["tipo", "sezione", "numero", "padre_id", "descrizione"]

    def __str__(self):
        if self.padre_id:
            return f"{self.padre.etichetta} › {self.descrizione}"
        return self.etichetta

    @property
    def etichetta(self):
        n = f"{self.numero}) " if self.numero else ""
        return f"{self.sezione} {n}{self.descrizione}"

    @property
    def ufficiale(self):
        return self.padre_id is None

    @property
    def voce_rendiconto(self):
        return self.padre if self.padre_id else self


def percorso_giustificativo(istanza, nome):
    estensione = "".join(c for c in Path(nome).suffix.lower() if c.isalnum())[:10] or "bin"
    return f"tesoreria/{istanza.esercizio.anno}/{istanza.impronta[:20]}.{estensione}"


class MovimentoQuerySet(models.QuerySet):
    def validi(self):
        return self.filter(annullato=False)


class Movimento(ModelloBase):
    class Tipo(models.TextChoices):
        ENTRATA = "entrata", "Entrata"
        USCITA = "uscita", "Uscita"
        GIROCONTO = "giroconto", "Giroconto"

    esercizio = models.ForeignKey(Esercizio, on_delete=models.PROTECT, related_name="movimenti")
    numero = models.PositiveIntegerField(editable=False)
    data = models.DateField()
    tipo = models.CharField(max_length=9, choices=Tipo.choices)
    conto = models.ForeignKey(Conto, on_delete=models.PROTECT, related_name="movimenti")
    conto_destinazione = models.ForeignKey(
        Conto,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="giroconti_ricevuti",
        verbose_name="verso il conto",
    )
    importo = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    voce = models.ForeignKey(
        Voce, null=True, blank=True, on_delete=models.PROTECT, related_name="movimenti"
    )
    descrizione = models.CharField(max_length=255)
    controparte = models.ForeignKey(
        Soggetto, null=True, blank=True, on_delete=models.SET_NULL, related_name="movimenti"
    )
    controparte_testo = models.CharField("controparte", max_length=200, blank=True)
    documento = models.CharField(
        "documento", max_length=100, blank=True, help_text="Es. fattura n. 12/2026, ricevuta n. ..."
    )
    giustificativo = models.FileField(upload_to=percorso_giustificativo, max_length=255, blank=True)
    giustificativo_nome = models.CharField(max_length=255, blank=True)
    impronta = models.CharField(max_length=64, blank=True)
    tessera = models.OneToOneField(
        "soci.Tessera", null=True, blank=True, on_delete=models.PROTECT, related_name="movimento"
    )
    annullato = models.BooleanField(default=False, editable=False)
    motivo_annullamento = models.CharField(max_length=255, blank=True, editable=False)

    objects = MovimentoQuerySet.as_manager()

    class Meta:
        verbose_name = "movimento"
        verbose_name_plural = "prima nota"
        ordering = ["-data", "-numero"]
        permissions = [("annulla_movimento", "Può annullare i movimenti di prima nota")]
        constraints = [
            models.UniqueConstraint(fields=["esercizio", "numero"], name="movimento_numero_unico"),
            models.CheckConstraint(
                condition=Q(tipo="giroconto", conto_destinazione__isnull=False, voce__isnull=True)
                | (~Q(tipo="giroconto") & Q(conto_destinazione__isnull=True, voce__isnull=False)),
                name="movimento_coerente",
            ),
        ]

    def __str__(self):
        return f"{self.esercizio.anno}/{self.numero} {self.descrizione}"

    def get_absolute_url(self):
        return reverse("tesoreria:movimento", args=[self.pk])

    @property
    def codice(self):
        return f"{self.esercizio.anno}/{self.numero:04d}"

    @property
    def segno(self):
        return -1 if self.tipo == self.Tipo.USCITA else 1


class Previsione(models.Model):
    esercizio = models.ForeignKey(Esercizio, on_delete=models.CASCADE, related_name="previsioni")
    voce = models.ForeignKey(Voce, on_delete=models.PROTECT, related_name="previsioni")
    importo = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))

    class Meta:
        verbose_name = "previsione"
        verbose_name_plural = "preventivo"
        constraints = [
            models.UniqueConstraint(fields=["esercizio", "voce"], name="previsione_unica")
        ]

    def __str__(self):
        return f"{self.voce} {self.esercizio.anno}: {self.importo}"
