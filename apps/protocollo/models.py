# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Modelli del registro di protocollo: registrazioni in entrata, uscita e
# *              interne, corrispondenti, allegati con impronta, registro giornaliero,
# *              caselle di posta e messaggi ricevuti da protocollare.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from pathlib import Path

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from apps.anagrafica.models import Soggetto
from apps.core.models import ModelloBase

SEQ_PROTOCOLLO = "protocollo"  # annuale


class Classificazione(models.Model):
    """Voce del titolario di classificazione (es. 01.02 - Soci / Ammissioni)."""

    codice = models.CharField(max_length=20, unique=True)
    descrizione = models.CharField(max_length=200)
    attiva = models.BooleanField(default=True)

    class Meta:
        verbose_name = "classificazione"
        verbose_name_plural = "titolario di classificazione"
        ordering = ["codice"]

    def __str__(self):
        return f"{self.codice} - {self.descrizione}"


class ProtocolloQuerySet(models.QuerySet):
    def visibili_a(self, utente):
        """I documenti riservati solo a chi ha il permesso specifico."""
        if utente.has_perm("protocollo.vedi_riservati"):
            return self
        return self.filter(riservato=False)

    def validi(self):
        return self.filter(annullato=False)


class Protocollo(ModelloBase):
    """Registrazione di protocollo. Numero, data, oggetto e corrispondenti non si modificano:
    un errore si corregge annullando la registrazione e registrandone una nuova."""

    class Direzione(models.TextChoices):
        ENTRATA = "entrata", "In entrata"
        USCITA = "uscita", "In uscita"
        INTERNO = "interno", "Interno"

    class Mezzo(models.TextChoices):
        EMAIL = "email", "Email"
        PEC = "pec", "PEC"
        POSTA = "posta", "Posta ordinaria"
        RACCOMANDATA = "raccomandata", "Raccomandata"
        MANO = "mano", "Consegna a mano"
        MESSAGGISTICA = "messaggistica", "Messaggistica"
        ALTRO = "altro", "Altro"

    anno = models.PositiveIntegerField(editable=False)
    numero = models.PositiveIntegerField(editable=False)
    registrato_il = models.DateTimeField(
        "data di registrazione", default=timezone.now, editable=False
    )
    direzione = models.CharField(max_length=8, choices=Direzione.choices)
    mezzo = models.CharField(max_length=15, choices=Mezzo.choices, default=Mezzo.EMAIL)
    oggetto = models.CharField(max_length=500)
    data_documento = models.DateField("data del documento", null=True, blank=True)
    riferimento_mittente = models.CharField(
        "protocollo del mittente",
        max_length=100,
        blank=True,
        help_text="Numero e data assegnati dal mittente, se presenti.",
    )
    data_ricezione = models.DateField(
        "data di ricezione", null=True, blank=True, help_text="Se diversa dalla registrazione."
    )
    classificazione = models.ForeignKey(
        Classificazione, null=True, blank=True, on_delete=models.PROTECT, related_name="protocolli"
    )
    risposta_a = models.ForeignKey(
        "self",
        verbose_name="in risposta a",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="risposte",
    )
    riservato = models.BooleanField(
        default=False, help_text="Visibile solo a chi è autorizzato ai documenti riservati."
    )
    note = models.TextField(blank=True)
    annullato = models.BooleanField(default=False, editable=False)
    motivo_annullamento = models.CharField(max_length=500, blank=True, editable=False)
    annullato_il = models.DateTimeField(null=True, blank=True, editable=False)
    annullato_da = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        editable=False,
    )

    objects = ProtocolloQuerySet.as_manager()

    class Meta:
        verbose_name = "protocollo"
        verbose_name_plural = "protocolli"
        ordering = ["-anno", "-numero"]
        permissions = [
            ("annulla_protocollo", "Può annullare una registrazione di protocollo"),
            ("vedi_riservati", "Può vedere i protocolli riservati"),
            ("esporta_protocollo", "Può esportare e stampare il registro di protocollo"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["anno", "numero"], name="protocollo_numero_unico")
        ]
        indexes = [models.Index(fields=["registrato_il"])]

    def __str__(self):
        return f"Prot. {self.segnatura} - {self.oggetto[:60]}"

    def get_absolute_url(self):
        return reverse("protocollo:dettaglio", args=[self.pk])

    @property
    def segnatura(self):
        return f"{self.anno}-{self.numero:05d}"

    @property
    def mittenti(self):
        return [c for c in self.corrispondenti.all() if c.ruolo == Corrispondente.Ruolo.MITTENTE]

    @property
    def destinatari(self):
        return [
            c for c in self.corrispondenti.all() if c.ruolo == Corrispondente.Ruolo.DESTINATARIO
        ]


class Corrispondente(models.Model):
    """Mittente o destinatario: legato all'anagrafica, con il testo fissato alla registrazione."""

    class Ruolo(models.TextChoices):
        MITTENTE = "mittente", "Mittente"
        DESTINATARIO = "destinatario", "Destinatario"

    protocollo = models.ForeignKey(
        Protocollo, on_delete=models.CASCADE, related_name="corrispondenti"
    )
    ruolo = models.CharField(max_length=12, choices=Ruolo.choices)
    soggetto = models.ForeignKey(
        Soggetto, null=True, blank=True, on_delete=models.SET_NULL, related_name="protocolli"
    )
    descrizione = models.CharField(max_length=300)
    indirizzo = models.CharField(
        max_length=300, blank=True, help_text="Email, PEC o indirizzo postale usato."
    )

    class Meta:
        verbose_name = "corrispondente"
        verbose_name_plural = "corrispondenti"
        ordering = ["ruolo", "id"]

    def __str__(self):
        return self.descrizione


def percorso_allegato(istanza, nome):
    """Nome su disco ricavato dall'impronta: mai dal nome scelto da chi carica il file."""
    estensione = "".join(c for c in Path(nome).suffix.lower() if c.isalnum())[:10]
    p = istanza.protocollo
    return f"protocollo/{p.anno}/{p.numero:05d}/{istanza.impronta[:20]}.{estensione or 'bin'}"


class Allegato(models.Model):
    """File del documento protocollato. Non si sostituisce né si cancella dall'interfaccia."""

    protocollo = models.ForeignKey(Protocollo, on_delete=models.PROTECT, related_name="allegati")
    file = models.FileField(upload_to=percorso_allegato, max_length=255)
    nome = models.CharField("nome del file", max_length=255)
    tipo = models.CharField(max_length=100, blank=True)
    dimensione = models.PositiveBigIntegerField()
    impronta = models.CharField("impronta SHA-256", max_length=64)
    principale = models.BooleanField(default=False, help_text="Documento principale.")
    caricato_il = models.DateTimeField(auto_now_add=True)
    caricato_da = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        verbose_name = "allegato"
        verbose_name_plural = "allegati"
        ordering = ["-principale", "id"]

    def __str__(self):
        return self.nome


class RegistroGiornaliero(models.Model):
    """PDF del registro di protocollo di un giorno, generato una volta e conservato con impronta."""

    data = models.DateField(unique=True)
    file = models.FileField(upload_to="protocollo/registri/", max_length=255)
    impronta = models.CharField("impronta SHA-256", max_length=64)
    registrazioni = models.PositiveIntegerField()
    primo_numero = models.CharField(max_length=20, blank=True)
    ultimo_numero = models.CharField(max_length=20, blank=True)
    generato_il = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "registro giornaliero"
        verbose_name_plural = "registri giornalieri"
        ordering = ["-data"]

    def __str__(self):
        return f"Registro del {self.data:%d/%m/%Y}"


class CasellaPosta(models.Model):
    """Casella IMAP (email o PEC) da cui scaricare i messaggi da protocollare."""

    nome = models.CharField(max_length=100)
    pec = models.BooleanField("è una PEC", default=False)
    server = models.CharField("server IMAP", max_length=200)
    porta = models.PositiveIntegerField(default=993)
    ssl = models.BooleanField("connessione cifrata (SSL/TLS)", default=True)
    utente = models.CharField(max_length=200)
    password_cifrata = models.TextField(editable=False, blank=True)
    cartella = models.CharField(max_length=100, default="INBOX")
    giorni = models.PositiveIntegerField(
        "giorni da scaricare",
        default=30,
        help_text="Al primo scaricamento e come finestra di controllo.",
    )
    attiva = models.BooleanField(default=True)
    ultimo_controllo = models.DateTimeField(null=True, blank=True, editable=False)
    ultimo_errore = models.CharField(max_length=500, blank=True, editable=False)

    class Meta:
        verbose_name = "casella di posta"
        verbose_name_plural = "caselle di posta"
        ordering = ["nome"]

    def __str__(self):
        return self.nome

    def imposta_password(self, password):
        from apps.core.cifratura import cifra

        self.password_cifrata = cifra(password)

    def password(self):
        from apps.core.cifratura import decifra

        return decifra(self.password_cifrata)


class MessaggioQuerySet(models.QuerySet):
    def da_esaminare(self):
        return self.filter(stato=MessaggioRicevuto.Stato.NUOVO)


class MessaggioRicevuto(models.Model):
    """Messaggio scaricato da una casella: si protocolla o si scarta (con motivo)."""

    class Stato(models.TextChoices):
        NUOVO = "nuovo", "Da esaminare"
        PROTOCOLLATO = "protocollato", "Protocollato"
        SCARTATO = "scartato", "Scartato"

    casella = models.ForeignKey(CasellaPosta, on_delete=models.PROTECT, related_name="messaggi")
    message_id = models.CharField(max_length=500)
    mittente = models.CharField(max_length=500)
    mittente_email = models.EmailField(max_length=254, blank=True)
    destinatari = models.TextField(blank=True)
    oggetto = models.CharField(max_length=500, blank=True)
    data = models.DateTimeField(null=True, blank=True)
    testo = models.TextField(blank=True, help_text="Solo testo: l'HTML non viene mai mostrato.")
    file_eml = models.FileField(upload_to="protocollo/posta/", max_length=255)
    impronta = models.CharField(max_length=64)
    allegati = models.JSONField(default=list, blank=True)
    scaricato_il = models.DateTimeField(auto_now_add=True)
    stato = models.CharField(
        max_length=12, choices=Stato.choices, default=Stato.NUOVO, db_index=True
    )
    protocollo = models.ForeignKey(
        Protocollo, null=True, blank=True, on_delete=models.SET_NULL, related_name="messaggi"
    )
    motivo_scarto = models.CharField(max_length=255, blank=True)
    gestito_da = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    gestito_il = models.DateTimeField(null=True, blank=True)

    objects = MessaggioQuerySet.as_manager()

    class Meta:
        verbose_name = "messaggio ricevuto"
        verbose_name_plural = "messaggi ricevuti"
        ordering = ["-data", "-id"]
        permissions = [
            ("gestisci_posta", "Può esaminare, protocollare e scartare la posta ricevuta")
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["casella", "message_id"], name="messaggio_unico_per_casella"
            ),
            models.CheckConstraint(
                condition=~Q(stato="scartato") | ~Q(motivo_scarto=""),
                name="scarto_con_motivo",
            ),
        ]

    def __str__(self):
        return self.oggetto or "(senza oggetto)"

    def get_absolute_url(self):
        return reverse("protocollo:messaggio", args=[self.pk])
