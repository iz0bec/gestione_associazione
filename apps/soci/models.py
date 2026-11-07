# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Modelli del libro soci: tipologie, soci, tessere annuali con quota
# *              e ricevuta, domande di iscrizione (anche dal modulo pubblico).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from datetime import date
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Exists, OuterRef, Q
from django.urls import reverse

from apps.anagrafica.models import Soggetto
from apps.anagrafica.validatori import valida_codice_fiscale
from apps.core.models import ModelloBase, validatore_cap, validatore_provincia

# chiavi delle sequenze di numerazione (apps.core.numerazione)
SEQ_LIBRO_SOCI = "libro_soci"  # progressivo unico, mai riavviato
SEQ_TESSERA = "tessera"  # annuale
SEQ_RICEVUTA = "ricevuta_quota"  # annuale, per anno di incasso


class TipologiaSocio(models.Model):
    """Categoria statutaria del socio (ordinario, sostenitore, onorario...) con quota annua."""

    nome = models.CharField(max_length=60, unique=True)
    descrizione = models.CharField(max_length=255, blank=True)
    quota_annua = models.DecimalField(
        "quota annua",
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Proposta al rilascio della tessera; 0 = esente.",
    )
    attiva = models.BooleanField(
        default=True, help_text="Le tipologie non attive non sono proposte."
    )
    ordine = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "tipologia di socio"
        verbose_name_plural = "tipologie di socio"
        ordering = ["ordine", "nome"]

    def __str__(self):
        return self.nome


class SocioQuerySet(models.QuerySet):
    def attivi(self):
        return self.filter(stato=Socio.Stato.ATTIVO)

    def con_tessera_pagata(self, anno):
        tessere = Tessera.objects.valide().filter(
            socio=OuterRef("pk"), anno=anno, pagata_il__isnull=False
        )
        return self.annotate(in_regola=Exists(tessere))

    def in_regola(self, anno):
        return self.con_tessera_pagata(anno).filter(in_regola=True)

    def morosi(self, anno):
        """Soci attivi senza una tessera pagata per l'anno (esclusi gli esenti con quota 0)."""
        return (
            self.attivi()
            .con_tessera_pagata(anno)
            .filter(in_regola=False)
            .exclude(
                Exists(Tessera.objects.valide().filter(socio=OuterRef("pk"), anno=anno, importo=0))
            )
        )


class Socio(ModelloBase):
    """Iscrizione di un soggetto al libro soci. Il numero non si riusa mai."""

    class Stato(models.TextChoices):
        ATTIVO = "attivo", "Attivo"
        SOSPESO = "sospeso", "Sospeso"
        CESSATO = "cessato", "Cessato"

    class Cessazione(models.TextChoices):
        DIMISSIONI = "dimissioni", "Dimissioni (recesso)"
        DECESSO = "decesso", "Decesso"
        ESCLUSIONE = "esclusione", "Esclusione"
        MOROSITA = "morosita", "Decadenza per morosità"
        ALTRO = "altro", "Altro"

    soggetto = models.OneToOneField(
        Soggetto,
        on_delete=models.PROTECT,
        related_name="socio",
        limit_choices_to={"tipo": "persona"},
    )
    numero = models.PositiveIntegerField("numero di iscrizione", unique=True, editable=False)
    tipologia = models.ForeignKey(TipologiaSocio, on_delete=models.PROTECT, related_name="soci")
    data_ammissione = models.DateField("data di ammissione", default=date.today)
    delibera_ammissione = models.CharField(
        "delibera di ammissione",
        max_length=200,
        blank=True,
        help_text="Es. «Consiglio direttivo del 12/01/2026, verbale n. 3».",
    )
    stato = models.CharField(
        max_length=10, choices=Stato.choices, default=Stato.ATTIVO, db_index=True
    )
    data_cessazione = models.DateField("data di cessazione", null=True, blank=True)
    causa_cessazione = models.CharField(
        "causa di cessazione", max_length=12, choices=Cessazione.choices, blank=True
    )
    note = models.TextField(blank=True)

    objects = SocioQuerySet.as_manager()

    class Meta:
        verbose_name = "socio"
        verbose_name_plural = "soci"
        ordering = ["numero"]
        permissions = [
            ("esporta_libro_soci", "Può stampare ed esportare il libro soci"),
            ("cessa_socio", "Può registrare la cessazione di un socio"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(stato="cessato", data_cessazione__isnull=False) | ~Q(stato="cessato"),
                name="socio_cessato_con_data",
            )
        ]

    def __str__(self):
        return f"n. {self.numero} {self.soggetto.nome_completo}"

    def get_absolute_url(self):
        return reverse("soci:dettaglio", args=[self.pk])

    @property
    def attivo(self):
        return self.stato == self.Stato.ATTIVO

    def tessera_anno(self, anno):
        return self.tessere.valide().filter(anno=anno).first()


class TesseraQuerySet(models.QuerySet):
    def valide(self):
        return self.filter(annullata=False)

    def pagate(self):
        return self.valide().filter(pagata_il__isnull=False)

    def da_pagare(self):
        return self.valide().filter(pagata_il__isnull=True, importo__gt=0)


class Tessera(ModelloBase):
    """Tessera annuale di un socio con la relativa quota."""

    class Metodo(models.TextChoices):
        CONTANTI = "contanti", "Contanti"
        BONIFICO = "bonifico", "Bonifico"
        POS = "pos", "Carta / POS"
        ALTRO = "altro", "Altro"

    socio = models.ForeignKey(Socio, on_delete=models.PROTECT, related_name="tessere")
    anno = models.PositiveIntegerField(db_index=True)
    numero = models.PositiveIntegerField(editable=False)
    data_rilascio = models.DateField("data di rilascio", default=date.today)
    importo = models.DecimalField(
        "quota", max_digits=8, decimal_places=2, validators=[MinValueValidator(Decimal("0"))]
    )
    pagata_il = models.DateField("pagata il", null=True, blank=True)
    metodo_pagamento = models.CharField(
        "metodo di pagamento", max_length=10, choices=Metodo.choices, blank=True
    )
    riferimento_pagamento = models.CharField(
        "riferimento", max_length=100, blank=True, help_text="Es. CRO del bonifico."
    )
    ricevuta_anno = models.PositiveIntegerField(null=True, blank=True, editable=False)
    ricevuta_numero = models.PositiveIntegerField(null=True, blank=True, editable=False)
    annullata = models.BooleanField(default=False, editable=False)
    motivo_annullamento = models.CharField(max_length=255, blank=True, editable=False)
    note = models.CharField(max_length=255, blank=True)

    objects = TesseraQuerySet.as_manager()

    class Meta:
        verbose_name = "tessera"
        verbose_name_plural = "tessere"
        ordering = ["-anno", "-numero"]
        permissions = [
            ("incassa_quota", "Può registrare il pagamento delle quote ed emettere ricevute"),
            ("annulla_tessera", "Può annullare una tessera"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["anno", "numero"], name="tessera_numero_unico_per_anno"
            ),
            models.UniqueConstraint(
                fields=["socio", "anno"],
                condition=Q(annullata=False),
                name="una_tessera_valida_per_socio_e_anno",
            ),
            models.UniqueConstraint(
                fields=["ricevuta_anno", "ricevuta_numero"], name="ricevuta_numero_unico"
            ),
        ]

    def __str__(self):
        return f"Tessera {self.codice} - {self.socio.soggetto.nome_completo}"

    @property
    def codice(self):
        return f"{self.anno}/{self.numero:04d}"

    @property
    def codice_ricevuta(self):
        if self.ricevuta_numero is None:
            return ""
        return f"{self.ricevuta_anno}/{self.ricevuta_numero:04d}"

    @property
    def pagata(self):
        return self.pagata_il is not None

    @property
    def stato(self):
        if self.annullata:
            return "annullata"
        if self.pagata:
            return "pagata"
        return "esente" if self.importo == 0 else "da pagare"


class DomandaIscrizione(models.Model):
    """Domanda di ammissione a socio, inserita dalla segreteria o dal modulo pubblico."""

    class Stato(models.TextChoices):
        IN_ATTESA = "in_attesa", "In attesa"
        ACCOLTA = "accolta", "Accolta"
        RESPINTA = "respinta", "Respinta"

    class Origine(models.TextChoices):
        PUBBLICA = "pubblica", "Modulo online"
        SEGRETERIA = "segreteria", "Segreteria"

    # dati del richiedente (copiati nell'anagrafica all'accoglimento)
    nome = models.CharField(max_length=100)
    cognome = models.CharField(max_length=100)
    codice_fiscale = models.CharField(
        "codice fiscale", max_length=16, validators=[valida_codice_fiscale]
    )
    data_nascita = models.DateField("data di nascita")
    luogo_nascita = models.CharField("luogo di nascita", max_length=100)
    email = models.EmailField()
    telefono = models.CharField(max_length=30, blank=True)
    indirizzo = models.CharField(max_length=255)
    cap = models.CharField("CAP", max_length=5, validators=[validatore_cap])
    comune = models.CharField(max_length=100)
    provincia = models.CharField(max_length=2, validators=[validatore_provincia])
    tipologia = models.ForeignKey(
        TipologiaSocio,
        on_delete=models.PROTECT,
        verbose_name="tipologia richiesta",
        null=True,
        blank=True,
    )
    motivazione = models.TextField("presentazione", blank=True, max_length=2000)
    # dichiarazioni
    accetta_statuto = models.BooleanField("dichiara di accettare lo statuto", default=False)
    consenso_comunicazioni = models.BooleanField(default=False)
    consenso_immagini = models.BooleanField(default=False)
    # gestione
    origine = models.CharField(max_length=10, choices=Origine.choices, default=Origine.SEGRETERIA)
    ricevuta_il = models.DateTimeField("ricevuta il", auto_now_add=True, db_index=True)
    indirizzo_ip = models.GenericIPAddressField(null=True, blank=True, editable=False)
    stato = models.CharField(
        max_length=10, choices=Stato.choices, default=Stato.IN_ATTESA, db_index=True
    )
    esito_il = models.DateField("data dell'esito", null=True, blank=True)
    esito_note = models.CharField("motivazione dell'esito", max_length=255, blank=True)
    esito_da = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    socio = models.ForeignKey(
        Socio, null=True, blank=True, on_delete=models.SET_NULL, related_name="domande"
    )

    class Meta:
        verbose_name = "domanda di iscrizione"
        verbose_name_plural = "domande di iscrizione"
        ordering = ["-ricevuta_il"]
        permissions = [("valuta_domanda", "Può accogliere o respingere le domande di iscrizione")]

    def __str__(self):
        return f"{self.cognome} {self.nome} ({self.ricevuta_il:%d/%m/%Y})"

    def save(self, *args, **kwargs):
        self.codice_fiscale = self.codice_fiscale.strip().upper()
        self.provincia = self.provincia.strip().upper()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("soci:domanda", args=[self.pk])
