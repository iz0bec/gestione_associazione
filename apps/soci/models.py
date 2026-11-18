# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Modelli del libro soci: tipologie, soci, tessere annuali con quota
# *              e ricevuta, domande di iscrizione (anche dal modulo pubblico).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import uuid as uuid_mod
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Exists, OuterRef, Q
from django.urls import reverse

from apps.anagrafica.models import Soggetto
from apps.anagrafica.validatori import valida_codice_fiscale
from apps.api.risorse import RisorsaApi
from apps.core.models import ModelloBase, validatore_cap, validatore_provincia

# chiavi delle sequenze di numerazione (apps.core.numerazione)
SEQ_LIBRO_SOCI = "libro_soci"  # progressivo unico, mai riavviato
SEQ_RICEVUTA = "ricevuta_quota"  # annuale, per anno di incasso
SEQ_CONSEGNA = "consegna_tessere"  # annuale: documenti di consegna alle sezioni
SEQ_ORDINE = "ordine_tessere"  # annuale: ordini alla sede nazionale


class Sezione(RisorsaApi):
    """Sezione territoriale a cui appartengono i soci e le tessere fisiche.

    Un'associazione singola ha una sola sezione (creata in automatico); una federazione ne ha
    molte e può limitare ogni utente alle proprie (Utente.sezioni).
    """

    FLUSSO = "sezioni"
    RISORSA = "sezione"

    codice = models.CharField(
        max_length=20, unique=True, help_text="Codice della sezione nel registro nazionale."
    )
    nome = models.CharField(max_length=150, unique=True)
    comune = models.CharField(max_length=100, blank=True)
    provincia = models.CharField(max_length=2, blank=True, validators=[validatore_provincia])
    email = models.EmailField(blank=True)
    attiva = models.BooleanField(default=True)
    ordine = models.PositiveSmallIntegerField(default=0)
    modificato_il = models.DateTimeField("modificato il", auto_now=True)

    class Meta:
        verbose_name = "sezione"
        verbose_name_plural = "sezioni"
        ordering = ["ordine", "nome"]

    def __str__(self):
        return self.nome

    @property
    def denominazione(self):
        """Come si scrive nei documenti: «Sezione di Ruoti» (o il nome, se lo dice già)."""
        nome = self.nome.strip()
        return nome if nome.lower().startswith("sezione") else f"Sezione di {nome}"

    @classmethod
    def predefinita(cls):
        per_ordine = cls.objects.order_by("ordine", "pk")
        sezione = per_ordine.filter(attiva=True).first() or per_ordine.first()
        if sezione is None:
            sezione = cls.objects.create(codice="001", nome="Sezione principale")
        return sezione


class TipologiaSocio(models.Model):
    """Categoria statutaria del socio (ordinario, sostenitore, onorario...) con quota annua."""

    nome = models.CharField(max_length=60, unique=True)
    descrizione = models.CharField(max_length=255, blank=True)
    quota_annua = models.DecimalField(
        "quota di riferimento",
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Proposta per i nuovi listini annuali; 0 = esente.",
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


def percorso_modulo(istanza, nome):
    from apps.core.immagini import nome_casuale

    return nome_casuale("soci/moduli", "pdf")


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
    sezione = models.ForeignKey(Sezione, on_delete=models.PROTECT, related_name="soci")
    matricola = models.CharField(
        "matricola nazionale",
        max_length=30,
        blank=True,
        help_text="Numero del socio nel registro nazionale, se assegnato.",
    )
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
    dichiarazione = models.BooleanField(
        "dichiarazione SI/NO del modulo di adesione",
        null=True,
        blank=True,
        help_text="La risposta alla dichiarazione richiesta nel modulo (es. decorato).",
    )
    modulo_adesione = models.FileField(
        "richiesta di adesione firmata",
        upload_to=percorso_modulo,
        blank=True,
        max_length=255,
        editable=False,
    )
    modulo_adesione_il = models.DateTimeField(null=True, blank=True, editable=False)
    note = models.TextField(blank=True)

    objects = SocioQuerySet.as_manager()

    class Meta:
        verbose_name = "socio"
        verbose_name_plural = "soci"
        ordering = ["numero"]
        permissions = [
            ("esporta_libro_soci", "Può stampare ed esportare il libro soci"),
            ("cessa_socio", "Può registrare la cessazione di un socio"),
            ("importa_soci", "Può importare i soci dal registro nazionale"),
            ("trasferisci_socio", "Può trasferire un socio in un'altra sezione"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(stato="cessato", data_cessazione__isnull=False) | ~Q(stato="cessato"),
                name="socio_cessato_con_data",
            ),
            models.UniqueConstraint(
                fields=["matricola"], condition=~Q(matricola=""), name="matricola_unica"
            ),
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


class ListinoTessere(ModelloBase):
    """Costi del tesseramento di un anno, fissati all'apertura dell'anno contabile.

    Costo d'acquisto: quanto si paga alla sede centrale per ogni tessera fisica.
    Prezzo di distribuzione: la quota chiesta al socio, diversa per tipologia (QuotaListino).
    """

    anno = models.PositiveIntegerField(unique=True)
    costo_acquisto = models.DecimalField(
        "costo d'acquisto per tessera",
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Prezzo pagato alla sede centrale per ogni tessera.",
    )
    quota_federale = models.DecimalField(
        "quota federale per tessera",
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Solo per chi distribuisce alle sezioni: si aggiunge al costo d'acquisto.",
    )
    delibera = models.ForeignKey(
        "organi.Delibera",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Delibera del consiglio direttivo che ha fissato la quota.",
    )
    scadenza_richieste = models.DateField("richieste delle tessere entro", null=True, blank=True)
    istruzioni_pagamento = models.TextField(
        "modalità di pagamento",
        blank=True,
        help_text="Testo per gli avvisi alle sezioni (es. IBAN, causale, termini).",
    )
    note = models.CharField(max_length=255, blank=True)

    @property
    def prezzo_sezioni(self):
        """Quanto paga una sezione per ogni tessera: costo d'acquisto più quota federale."""
        return self.costo_acquisto + self.quota_federale

    class Meta:
        verbose_name = "listino del tesseramento"
        verbose_name_plural = "listini del tesseramento"
        ordering = ["-anno"]

    def __str__(self):
        return f"Listino {self.anno}"


class QuotaListino(models.Model):
    listino = models.ForeignKey(ListinoTessere, on_delete=models.CASCADE, related_name="quote")
    tipologia = models.ForeignKey(TipologiaSocio, on_delete=models.PROTECT, related_name="+")
    importo = models.DecimalField(
        "prezzo di distribuzione",
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )

    class Meta:
        verbose_name = "quota del listino"
        verbose_name_plural = "quote del listino"
        ordering = ["tipologia__ordine", "tipologia__nome"]
        constraints = [
            models.UniqueConstraint(fields=["listino", "tipologia"], name="quota_unica_per_listino")
        ]

    def __str__(self):
        return f"{self.listino.anno} {self.tipologia}: {self.importo}"


class LottoTessere(ModelloBase):
    """Carico di tessere fisiche ricevute dalla sede centrale, con numerazione prestampata."""

    anno = models.PositiveIntegerField("anno di tesseramento", db_index=True)
    sezione = models.ForeignKey(
        Sezione,
        on_delete=models.PROTECT,
        related_name="lotti",
        help_text="Le tessere del lotto si attribuiscono ai soci di questa sezione.",
    )
    serie = models.CharField(
        max_length=10,
        blank=True,
        help_text="Lettere o prefisso stampati prima del numero, se presenti.",
    )
    numero_da = models.PositiveIntegerField("dal numero")
    numero_a = models.PositiveIntegerField("al numero")
    cifre = models.PositiveSmallIntegerField(
        default=0, help_text="Cifre del numero stampato (zeri iniziali), 0 = come scritto."
    )
    data_acquisizione = models.DateField("data di acquisizione", default=date.today)
    fornitore = models.CharField(max_length=100, default="Sede centrale")
    riferimento = models.CharField(
        max_length=200,
        blank=True,
        help_text="Es. ordine, protocollo di consegna, documento di trasporto.",
    )
    costo_unitario = models.DecimalField(
        "costo per tessera",
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Quota dovuta alla sede centrale per ogni tessera.",
    )
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "lotto di tessere"
        verbose_name_plural = "lotti di tessere"
        ordering = ["-anno", "data_acquisizione", "numero_da"]
        permissions = [("gestisci_tessere_fisiche", "Può caricare e gestire le tessere fisiche")]

    def __str__(self):
        return f"{self.anno}: {self.formatta(self.numero_da)} – {self.formatta(self.numero_a)}"

    @property
    def quantita(self):
        # le tessere registrate (i lotti dal registro nazionale non sono numerazioni continue)
        return self.carte.count()

    def formatta(self, numero):
        testo = f"{numero:0{self.cifre}d}" if self.cifre else str(numero)
        return f"{self.serie} {testo}".strip()


class CartaTesseraQuerySet(models.QuerySet):
    def disponibili(self):
        return self.filter(stato=CartaTessera.Stato.DISPONIBILE)


class CartaTessera(models.Model):
    """Singola tessera fisica di un lotto: disponibile, attribuita a un socio o fuori uso."""

    class Stato(models.TextChoices):
        DISPONIBILE = "disponibile", "Disponibile"
        ATTRIBUITA = "attribuita", "Attribuita"
        ANNULLATA = "annullata", "Annullata (deteriorata, errata)"
        SMARRITA = "smarrita", "Smarrita"
        RESTITUITA = "restituita", "Restituita alla sede centrale"

    lotto = models.ForeignKey(LottoTessere, on_delete=models.PROTECT, related_name="carte")
    anno = models.PositiveIntegerField(db_index=True)
    numero = models.PositiveIntegerField()
    codice = models.CharField("numero tessera", max_length=30)
    stato = models.CharField(
        max_length=12, choices=Stato.choices, default=Stato.DISPONIBILE, db_index=True
    )
    motivo = models.CharField(max_length=255, blank=True)
    modificata_il = models.DateTimeField(auto_now=True)

    objects = CartaTesseraQuerySet.as_manager()

    class Meta:
        verbose_name = "tessera fisica"
        verbose_name_plural = "tessere fisiche"
        ordering = ["anno", "lotto__serie", "numero"]
        constraints = [
            models.UniqueConstraint(fields=["anno", "codice"], name="carta_tessera_unica_per_anno")
        ]

    def __str__(self):
        return self.codice


class Tessera(ModelloBase):
    """Tesseramento annuale di un socio: tessera fisica attribuita e quota."""

    class Metodo(models.TextChoices):
        CONTANTI = "contanti", "Contanti"
        BONIFICO = "bonifico", "Bonifico"
        POS = "pos", "Carta / POS"
        ALTRO = "altro", "Altro"

    socio = models.ForeignKey(Socio, on_delete=models.PROTECT, related_name="tessere")
    anno = models.PositiveIntegerField(db_index=True)
    carta = models.OneToOneField(
        CartaTessera,
        verbose_name="tessera fisica",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="tessera",
        editable=False,
    )
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
    incasso_esterno = models.BooleanField(
        "incassata fuori dall'applicazione",
        default=False,
        editable=False,
        help_text="Quota già incassata prima dell'uso dell'applicazione (es. importata dal "
        "registro nazionale): senza ricevuta e senza registrazione in prima nota.",
    )
    annullata = models.BooleanField(default=False, editable=False)
    motivo_annullamento = models.CharField(max_length=255, blank=True, editable=False)
    note = models.CharField(max_length=255, blank=True)
    token_verifica = models.CharField(
        "codice di verifica", max_length=64, unique=True, null=True, blank=True, editable=False,
        help_text="Nel QR della tessera digitale: porta alla pagina pubblica di verifica.",
    )  # fmt: skip

    objects = TesseraQuerySet.as_manager()

    class Meta:
        verbose_name = "tessera"
        verbose_name_plural = "tessere"
        ordering = ["-anno", "socio__numero"]
        permissions = [
            ("incassa_quota", "Può registrare il pagamento delle quote ed emettere ricevute"),
            ("annulla_tessera", "Può annullare una tessera"),
        ]
        constraints = [
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
        return self.carta.codice if self.carta_id else "da attribuire"

    @property
    def attribuita(self):
        return self.carta_id is not None

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


class Trasferimento(models.Model):
    """Passaggio di un socio da una sezione a un'altra (storico)."""

    socio = models.ForeignKey(Socio, on_delete=models.CASCADE, related_name="trasferimenti")
    da = models.ForeignKey(Sezione, on_delete=models.PROTECT, related_name="+",
                           verbose_name="dalla sezione")  # fmt: skip
    a = models.ForeignKey(Sezione, on_delete=models.PROTECT, related_name="+",
                          verbose_name="alla sezione")  # fmt: skip
    data = models.DateField()
    motivo = models.CharField(max_length=255, blank=True)
    registrato_il = models.DateTimeField(auto_now_add=True)
    registrato_da = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        verbose_name = "trasferimento di sezione"
        verbose_name_plural = "trasferimenti di sezione"
        ordering = ["-data", "-registrato_il"]

    def __str__(self):
        return f"{self.socio}: {self.da} → {self.a} ({self.data:%d/%m/%Y})"


class DomandaIscrizione(models.Model):
    """Domanda di ammissione a socio, inserita dalla segreteria o dal modulo pubblico."""

    class Stato(models.TextChoices):
        IN_ATTESA = "in_attesa", "In attesa"
        ACCOLTA = "accolta", "Accolta"
        RESPINTA = "respinta", "Respinta"

    class Origine(models.TextChoices):
        PUBBLICA = "pubblica", "Modulo online"
        SEGRETERIA = "segreteria", "Segreteria"
        EMAIL = "email", "Email"
        INTEGRAZIONE = "integrazione", "Integrazione (API)"

    uuid = models.UUIDField(default=uuid_mod.uuid4, unique=True, editable=False)

    # dati del richiedente (copiati nell'anagrafica all'accoglimento)
    nome = models.CharField(max_length=100)
    cognome = models.CharField(max_length=100)
    codice_fiscale = models.CharField(
        "codice fiscale", max_length=16, validators=[valida_codice_fiscale]
    )
    data_nascita = models.DateField("data di nascita")
    luogo_nascita = models.CharField("luogo di nascita", max_length=100)
    email = models.EmailField(blank=True)
    telefono = models.CharField(max_length=30, blank=True)
    cellulare = models.CharField(max_length=30, blank=True)
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
    sezione = models.ForeignKey(
        Sezione,
        on_delete=models.PROTECT,
        verbose_name="sezione",
        null=True,
        blank=True,
        related_name="domande",
    )
    motivazione = models.TextField("presentazione", blank=True, max_length=2000)
    # dichiarazioni e consensi (come nel modulo di adesione e consenso)
    accetta_statuto = models.BooleanField(
        "ha preso visione dello statuto e del regolamento e li condivide", default=False
    )
    dichiarazione = models.BooleanField("dichiarazione SI/NO del modulo", null=True, blank=True)
    consenso_trattamento = models.BooleanField(
        "consenso al trattamento dei dati personali", default=False
    )
    consenso_particolari = models.BooleanField(
        "consenso al trattamento dei dati particolari", default=False
    )
    consenso_comunicazioni = models.BooleanField(default=False)  # compreso nel trattamento
    consenso_immagini = models.BooleanField("consenso all'uso dell'immagine", default=False)
    # gestione
    origine = models.CharField(max_length=12, choices=Origine.choices, default=Origine.SEGRETERIA)
    cliente_api = models.ForeignKey(
        "api.ClienteApi", null=True, blank=True, on_delete=models.SET_NULL, related_name="domande",
        verbose_name="inviata da", editable=False,
    )  # fmt: skip
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
    # documento di iscrizione: la richiesta firmata (passa al socio all'accoglimento)
    modulo_firmato = models.FileField(
        "richiesta di adesione firmata",
        upload_to=percorso_modulo,
        blank=True,
        max_length=255,
        editable=False,
    )
    protocollo = models.ForeignKey(
        "protocollo.Protocollo",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="domande_iscrizione",
        verbose_name="protocollo di arrivo",
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


# --- ciclo delle tessere fra federazione e sezioni (docs/analisi/ciclo-tessere.md) -----------


class RichiestaTessere(ModelloBase):
    """Fabbisogno di tessere di una sezione per un anno (anche più richieste nell'anno)."""

    anno = models.PositiveIntegerField("anno di tesseramento", db_index=True)
    sezione = models.ForeignKey(Sezione, on_delete=models.PROTECT, related_name="richieste_tessere")
    quantita = models.PositiveIntegerField("tessere richieste", validators=[MinValueValidator(1)])
    data = models.DateField(default=date.today)
    protocollo = models.ForeignKey(
        "protocollo.Protocollo", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "richiesta di tessere"
        verbose_name_plural = "richieste di tessere"
        ordering = ["-anno", "data", "pk"]
        permissions = [("gestisci_ciclo_tessere", "Gestire il ciclo delle tessere con le sezioni")]

    def __str__(self):
        return f"{self.sezione}: {self.quantita} tessere {self.anno}"


class BloccoTessere(ModelloBase):
    """Tessere numerate ricevute dalla sede nazionale e non ancora consegnate (magazzino):
    solo l'intervallo dei numeri. Le tessere vere nascono nel lotto della sezione alla consegna,
    così una tessera di magazzino non si può attribuire a un socio."""

    anno = models.PositiveIntegerField("anno di tesseramento", db_index=True)
    serie = models.CharField(max_length=10, blank=True)
    numero_da = models.PositiveIntegerField("dal numero")
    numero_a = models.PositiveIntegerField("al numero")
    cifre = models.PositiveSmallIntegerField(default=0)
    data_arrivo = models.DateField(default=date.today)
    fornitore = models.CharField(max_length=100, default="Sede nazionale")
    riferimento = models.CharField(max_length=200, blank=True)
    protocollo = models.ForeignKey(
        "protocollo.Protocollo", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        verbose_name = "blocco di tessere in magazzino"
        verbose_name_plural = "blocchi di tessere in magazzino"
        ordering = ["-anno", "serie", "numero_da"]

    def __str__(self):
        serie = f"{self.serie} " if self.serie else ""
        return f"{self.anno} {serie}{self.numero_da}–{self.numero_a}"

    @property
    def quantita(self):
        return self.numero_a - self.numero_da + 1


class ConsegnaTessere(ModelloBase):
    """Documento di consegna di un intervallo del magazzino a una sezione: crea il lotto della
    sezione. Numerato per anno (sequenza consegna_tessere)."""

    class Modalita(models.TextChoices):
        RITIRO = "ritiro", "Ritiro presso la sede"
        MANO = "mano", "Consegna a mano"
        SPEDIZIONE = "spedizione", "Spedizione"

    anno = models.PositiveIntegerField("anno di tesseramento", db_index=True)
    numero = models.PositiveIntegerField(editable=False)
    data = models.DateField(default=date.today)
    sezione = models.ForeignKey(Sezione, on_delete=models.PROTECT, related_name="consegne_tessere")
    blocco = models.ForeignKey(BloccoTessere, on_delete=models.PROTECT, related_name="consegne")
    numero_da = models.PositiveIntegerField("dal numero")
    numero_a = models.PositiveIntegerField("al numero")
    prezzo_unitario = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0"))
    lotto = models.OneToOneField(
        LottoTessere, on_delete=models.PROTECT, related_name="consegna", editable=False
    )
    modalita = models.CharField(
        "modalità di distribuzione",
        max_length=12,
        choices=Modalita.choices,
        default=Modalita.RITIRO,
    )
    note_distribuzione = models.TextField(
        "luogo, date e orari", blank=True, help_text="Riportate nell'avviso di attribuzione."
    )
    protocollo = models.ForeignKey(
        "protocollo.Protocollo", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    presa_in_carico_il = models.DateField("presa in carico il", null=True, blank=True)

    class Meta:
        verbose_name = "consegna di tessere"
        verbose_name_plural = "consegne di tessere"
        ordering = ["-anno", "-numero"]
        constraints = [
            models.UniqueConstraint(fields=["anno", "numero"], name="consegna_tessere_numero")
        ]

    def __str__(self):
        return f"Consegna {self.anno}/{self.numero} a {self.sezione}"

    @property
    def quantita(self):
        return self.numero_a - self.numero_da + 1

    @property
    def importo(self):
        return self.quantita * self.prezzo_unitario


class OrdineTessere(ModelloBase):
    """Ordine alla sede nazionale con il dettaglio per sezione (numerato per anno)."""

    anno = models.PositiveIntegerField("anno di tesseramento", db_index=True)
    numero = models.PositiveIntegerField(editable=False)
    data = models.DateField(default=date.today)
    quantita = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    dettaglio = models.JSONField(default=list, help_text="[{sezione, codice, quantita}]")
    note = models.TextField(blank=True)
    protocollo = models.ForeignKey(
        "protocollo.Protocollo", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        verbose_name = "ordine di tessere"
        verbose_name_plural = "ordini di tessere"
        ordering = ["-anno", "-numero"]
        constraints = [
            models.UniqueConstraint(fields=["anno", "numero"], name="ordine_tessere_numero")
        ]

    def __str__(self):
        return f"Ordine {self.anno}/{self.numero} ({self.quantita} tessere)"
