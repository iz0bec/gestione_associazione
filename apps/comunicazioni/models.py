# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Modelli delle comunicazioni: modelli di testo con segnaposto, liste di
# *              destinatari, invii con coda e registro, anniversari (compleanni, onomastici,
# *              ricorrenze, anzianità da socio) e auguri automatici.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse

from apps.anagrafica.models import Categoria, Soggetto
from apps.core.models import ModelloBase


class Finalita(models.TextChoices):
    """Base del trattamento: decide quali consensi servono per ricevere la comunicazione."""

    ISTITUZIONALE = (
        "istituzionale",
        "Istituzionale (convocazioni, ricevute, esiti: nessun consenso)",
    )
    COMUNICAZIONI = "comunicazioni", "Comunicazioni associative (serve il consenso)"
    AUGURI = "auguri", "Auguri e ricorrenze (serve il consenso)"


class Modello(models.Model):
    """Testo riutilizzabile con segnaposto {{ nome }}, {{ anni }}, ... (vedi SEGNAPOSTO)."""

    class Uso(models.TextChoices):
        GENERICO = "generico", "Comunicazione generica"
        CONVOCAZIONE = "convocazione", "Convocazione"
        RICEVUTA = "ricevuta", "Ricevuta della quota"
        DOMANDA = "domanda", "Esito della domanda di iscrizione"
        COMPLEANNO = "compleanno", "Auguri di compleanno"
        ONOMASTICO = "onomastico", "Auguri di onomastico"
        ANZIANITA = "anzianita", "Anniversario di iscrizione"
        RICORRENZA = "ricorrenza", "Ricorrenza"
        RINNOVO = "rinnovo", "Promemoria di rinnovo della quota"
        TESSERA = "tessera", "Tessera digitale"

    nome = models.CharField(max_length=100, unique=True)
    uso = models.CharField(max_length=15, choices=Uso.choices, default=Uso.GENERICO)
    oggetto = models.CharField(max_length=200)
    corpo = models.TextField()
    attivo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "modello di comunicazione"
        verbose_name_plural = "modelli di comunicazione"
        ordering = ["uso", "nome"]

    def __str__(self):
        return self.nome


class Lista(models.Model):
    """Lista di destinatari: persone scelte più gruppi dinamici (categorie, soci, organo)."""

    nome = models.CharField(max_length=100, unique=True)
    descrizione = models.CharField(max_length=255, blank=True)
    soggetti = models.ManyToManyField(Soggetto, blank=True, related_name="liste")
    categorie = models.ManyToManyField(Categoria, blank=True, related_name="liste")
    soci_attivi = models.BooleanField("tutti i soci attivi", default=False)
    soci_in_regola = models.BooleanField(
        "solo i soci in regola con la quota dell'anno", default=False
    )
    organo = models.ForeignKey(
        "organi.Organo",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="componenti in carica dell'organo",
    )

    class Meta:
        verbose_name = "lista di destinatari"
        verbose_name_plural = "liste di destinatari"
        ordering = ["nome"]

    def __str__(self):
        return self.nome

    def get_absolute_url(self):
        return reverse("comunicazioni:lista", args=[self.pk])


class Invio(ModelloBase):
    """Una comunicazione inviata a più destinatari (un messaggio separato per ciascuno)."""

    class Stato(models.TextChoices):
        BOZZA = "bozza", "Bozza"
        IN_CODA = "in_coda", "In coda"
        INVIATO = "inviato", "Inviato"
        CON_ERRORI = "con_errori", "Inviato con errori"
        ANNULLATO = "annullato", "Annullato"

    oggetto = models.CharField(max_length=200)
    corpo = models.TextField(help_text="Si possono usare i segnaposto, es. {{ nome }}.")
    finalita = models.CharField(
        max_length=15, choices=Finalita.choices, default=Finalita.COMUNICAZIONI
    )
    modello = models.ForeignKey(Modello, null=True, blank=True, on_delete=models.SET_NULL)
    stato = models.CharField(
        max_length=12, choices=Stato.choices, default=Stato.BOZZA, db_index=True
    )
    programmato_il = models.DateTimeField(
        "invio programmato", null=True, blank=True, help_text="Vuoto = appena confermato."
    )
    confermato_il = models.DateTimeField(null=True, blank=True, editable=False)
    completato_il = models.DateTimeField(null=True, blank=True, editable=False)
    protocolla = models.BooleanField(
        "protocolla in uscita", default=False, help_text="Al termine dell'invio."
    )
    protocollo = models.ForeignKey(
        "protocollo.Protocollo", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    origine = models.CharField(max_length=30, blank=True, editable=False)
    origine_id = models.PositiveBigIntegerField(null=True, blank=True, editable=False)
    contesto = models.JSONField(default=dict, blank=True, editable=False)

    class Meta:
        verbose_name = "invio"
        verbose_name_plural = "invii"
        ordering = ["-creato_il"]
        permissions = [("conferma_invio", "Può confermare l'invio delle comunicazioni")]
        indexes = [models.Index(fields=["origine", "origine_id"])]

    def __str__(self):
        return self.oggetto

    def get_absolute_url(self):
        return reverse("comunicazioni:invio", args=[self.pk])

    @property
    def modificabile(self):
        return self.stato == self.Stato.BOZZA

    @property
    def finalita_breve(self):
        return {
            "istituzionale": "istituzionale",
            "comunicazioni": "associativa",
            "auguri": "auguri",
        }[self.finalita]

    @property
    def titolo(self):
        """Oggetto per elenchi e intestazioni: con un solo destinatario i segnaposto sono risolti
        con i suoi dati (come nell'email inviata); con più destinatari restano quelli personali."""
        from .servizi import componi, contesto_destinatario, contesto_generale

        destinatari = list(self.destinatari.all()) if self.pk else []
        if len(destinatari) == 1:
            contesto = contesto_destinatario(self, destinatari[0])
        else:
            contesto = {**contesto_generale(), **self.contesto}
        return " ".join(componi(self.oggetto, contesto).split())


class Destinatario(models.Model):
    class Stato(models.TextChoices):
        IN_ATTESA = "in_attesa", "In attesa"
        INVIATO = "inviato", "Inviato"
        ERRORE = "errore", "Errore"
        ESCLUSO = "escluso", "Escluso"

    invio = models.ForeignKey(Invio, on_delete=models.CASCADE, related_name="destinatari")
    soggetto = models.ForeignKey(
        Soggetto, null=True, blank=True, on_delete=models.SET_NULL, related_name="comunicazioni"
    )
    nome = models.CharField(max_length=200)
    email = models.EmailField(blank=True)
    stato = models.CharField(
        max_length=10, choices=Stato.choices, default=Stato.IN_ATTESA, db_index=True
    )
    motivo = models.CharField(max_length=255, blank=True)
    tentativi = models.PositiveSmallIntegerField(default=0)
    inviato_il = models.DateTimeField(null=True, blank=True)
    contesto = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "destinatario"
        verbose_name_plural = "destinatari"
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["invio", "soggetto"],
                condition=models.Q(soggetto__isnull=False),
                name="destinatario_unico_per_invio",
            )
        ]

    def __str__(self):
        return f"{self.nome} <{self.email}>"


def percorso_allegato_invio(istanza, nome):
    return f"comunicazioni/{istanza.invio_id}/{istanza.impronta[:20]}"


class AllegatoInvio(models.Model):
    invio = models.ForeignKey(Invio, on_delete=models.CASCADE, related_name="allegati")
    file = models.FileField(upload_to=percorso_allegato_invio, max_length=255)
    nome = models.CharField(max_length=255)
    tipo = models.CharField(max_length=100)
    dimensione = models.PositiveBigIntegerField()
    impronta = models.CharField(max_length=64)

    class Meta:
        verbose_name = "allegato"
        verbose_name_plural = "allegati"

    def __str__(self):
        return self.nome


# --- anniversari -----------------------------------------------------------------------------


class Onomastico(models.Model):
    """Calendario degli onomastici: nome proprio e giorno della festa."""

    nome = models.CharField(max_length=50, unique=True, help_text="In minuscolo, senza accenti.")
    giorno = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(31)]
    )
    mese = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)]
    )
    santo = models.CharField(max_length=150, blank=True)

    class Meta:
        verbose_name = "onomastico"
        verbose_name_plural = "calendario degli onomastici"
        ordering = ["mese", "giorno", "nome"]

    def __str__(self):
        return f"{self.nome.title()} ({self.giorno}/{self.mese})"


class Ricorrenza(models.Model):
    """Data da ricordare ogni anno (festa nazionale, fondazione della sezione, commemorazione)."""

    nome = models.CharField(max_length=150)
    giorno = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(31)]
    )
    mese = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)]
    )
    anno_inizio = models.PositiveIntegerField(
        "anno dell'evento",
        null=True,
        blank=True,
        help_text="Per calcolare l'anniversario (es. 1918).",
    )
    descrizione = models.TextField(blank=True)
    lista = models.ForeignKey(
        Lista,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="destinatari degli auguri",
    )
    modello = models.ForeignKey(
        Modello,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="modello del messaggio",
    )
    invio_automatico = models.BooleanField(
        default=False,
        help_text="Prepara e invia il messaggio alla lista il giorno della ricorrenza.",
    )
    attiva = models.BooleanField(default=True)

    class Meta:
        verbose_name = "ricorrenza"
        verbose_name_plural = "ricorrenze"
        ordering = ["mese", "giorno"]

    def __str__(self):
        return f"{self.nome} ({self.giorno}/{self.mese})"


class Automazione(models.Model):
    """Auguri automatici per un tipo di anniversario."""

    class Tipo(models.TextChoices):
        COMPLEANNO = "compleanno", "Compleanni"
        ONOMASTICO = "onomastico", "Onomastici"
        ANZIANITA = "anzianita", "Anniversari di iscrizione"

    class Destinatari(models.TextChoices):
        SOCI = "soci", "Soci attivi"
        ANAGRAFICA = "anagrafica", "Tutte le persone dell'anagrafica"

    tipo = models.CharField(max_length=12, choices=Tipo.choices, unique=True)
    attiva = models.BooleanField(default=False)
    modello = models.ForeignKey(Modello, null=True, blank=True, on_delete=models.SET_NULL)
    destinatari = models.CharField(
        max_length=12, choices=Destinatari.choices, default=Destinatari.SOCI
    )
    anni = models.CharField(
        "anni da festeggiare",
        max_length=100,
        blank=True,
        default="1,5,10,15,20,25,30,40,50,60",
        help_text="Solo per l'iscrizione: anni di anzianità che ricevono gli auguri.",
    )
    ultimo_giorno = models.DateField(null=True, blank=True, editable=False)
    ora = models.PositiveSmallIntegerField(
        "ora dell'invio", default=9, validators=[MaxValueValidator(23)]
    )

    class Meta:
        verbose_name = "auguri automatici"
        verbose_name_plural = "auguri automatici"
        ordering = ["tipo"]

    def __str__(self):
        return self.get_tipo_display()

    def anni_scelti(self):
        return {int(a) for a in self.anni.replace(" ", "").split(",") if a.isdigit()}


class PromemoriaRinnovo(models.Model):
    """Promemoria automatici ai soci non in regola con la quota dell'anno (una sola riga)."""

    attivo = models.BooleanField(default=False)
    modello = models.ForeignKey(
        Modello, null=True, blank=True, on_delete=models.SET_NULL,
        limit_choices_to={"uso": "rinnovo"}, verbose_name="modello del messaggio",
    )  # fmt: skip
    date_invio = models.CharField(
        "date dell'invio",
        max_length=200,
        default="15/01, 01/03, 15/04, 01/06",
        help_text="Giorno/mese, separati da virgola: in quei giorni parte il promemoria ai soci "
        "non ancora in regola con la quota dell'anno.",
    )
    ora = models.PositiveSmallIntegerField(
        "ora dell'invio", default=9, validators=[MaxValueValidator(23)]
    )
    ultimo_giorno = models.DateField(null=True, blank=True, editable=False)

    class Meta:
        verbose_name = "promemoria di rinnovo"
        verbose_name_plural = "promemoria di rinnovo"

    def __str__(self):
        return "Promemoria di rinnovo della quota"

    @classmethod
    def corrente(cls):
        return cls.objects.get_or_create(pk=1)[0]

    def date_scelte(self):
        """Insiemi di (giorno, mese) validi tra quelli scritti."""
        scelte = set()
        for parte in self.date_invio.replace(";", ",").split(","):
            pezzi = parte.strip().replace("-", "/").replace(".", "/").split("/")
            if len(pezzi) == 2 and all(p.strip().isdigit() for p in pezzi):
                giorno, mese = int(pezzi[0]), int(pezzi[1])
                if 1 <= mese <= 12 and 1 <= giorno <= 31:
                    scelte.add((giorno, mese))
        return scelte


class DestinatarioRegistrato(models.Model):
    """Impedisce di mandare due volte gli stessi auguri automatici alla stessa persona."""

    automazione = models.CharField(max_length=40)
    soggetto = models.ForeignKey(Soggetto, on_delete=models.CASCADE, related_name="+")
    giorno = models.DateField()
    invio = models.ForeignKey(Invio, null=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["automazione", "soggetto", "giorno"], name="auguri_una_volta"
            )
        ]

    def __str__(self):
        return f"{self.automazione} {self.giorno}: {self.soggetto_id}"
