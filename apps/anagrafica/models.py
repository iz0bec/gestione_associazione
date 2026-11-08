# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Anagrafica unica: persone fisiche ed enti, categorie e consensi privacy.
# *              Soci, mittenti, destinatari, partecipanti sono ruoli dello stesso soggetto.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from datetime import date

from django.db import models
from django.db.models import Q
from django.urls import reverse

from apps.core.models import ModelloBase, validatore_cap, validatore_provincia

from .validatori import valida_codice_fiscale, valida_partita_iva


def percorso_foto(istanza, nome):
    from apps.core.immagini import nome_casuale

    return nome_casuale("anagrafica/foto")


class Categoria(models.Model):
    """Categoria di soggetti (Socio, Autorità, Amico della sezione, ...)."""

    nome = models.CharField(max_length=80, unique=True)
    descrizione = models.CharField(max_length=255, blank=True)
    colore = models.CharField(
        max_length=20,
        default="secondary",
        choices=[
            ("primary", "Blu"),
            ("green", "Verde"),
            ("red", "Rosso"),
            ("yellow", "Giallo"),
            ("purple", "Viola"),
            ("orange", "Arancio"),
            ("cyan", "Azzurro"),
            ("secondary", "Grigio"),
        ],
    )

    class Meta:
        verbose_name = "categoria"
        verbose_name_plural = "categorie"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class SoggettoQuerySet(models.QuerySet):
    def attivi(self):
        return self.filter(attivo=True)

    def ricerca(self, testo):
        q = Q()
        for parola in testo.split():
            q &= (
                Q(cognome__icontains=parola)
                | Q(nome__icontains=parola)
                | Q(denominazione__icontains=parola)
                | Q(email__icontains=parola)
                | Q(codice_fiscale__iexact=parola)
                | Q(comune__icontains=parola)
                | Q(qualifica__icontains=parola)
            )
        return self.filter(q)


class Soggetto(ModelloBase):
    """Una persona fisica o un ente (associazione, ente pubblico, azienda, ...)."""

    class Tipo(models.TextChoices):
        PERSONA = "persona", "Persona fisica"
        ENTE = "ente", "Ente / organizzazione"

    class Sesso(models.TextChoices):
        M = "M", "Maschio"
        F = "F", "Femmina"

    tipo = models.CharField(max_length=10, choices=Tipo.choices, default=Tipo.PERSONA)

    # persona fisica
    titolo = models.CharField(
        max_length=40, blank=True, help_text="Es. Gen., Cav., Dott., On., Prof."
    )
    nome = models.CharField(max_length=100, blank=True)
    cognome = models.CharField(max_length=100, blank=True, db_index=True)
    sesso = models.CharField(max_length=1, choices=Sesso.choices, blank=True)
    data_nascita = models.DateField("data di nascita", null=True, blank=True)
    luogo_nascita = models.CharField("luogo di nascita", max_length=100, blank=True)
    codice_fiscale = models.CharField(
        "codice fiscale",
        max_length=16,
        blank=True,
        null=True,
        unique=True,
        validators=[valida_codice_fiscale],
    )
    data_decesso = models.DateField(
        "data di decesso",
        null=True,
        blank=True,
        help_text="Se indicata, la persona non riceve più comunicazioni né auguri.",
    )

    # ente
    denominazione = models.CharField(max_length=255, blank=True, db_index=True)
    partita_iva = models.CharField(
        "partita IVA", max_length=11, blank=True, validators=[valida_partita_iva]
    )

    # comuni
    qualifica = models.CharField(
        max_length=150,
        blank=True,
        help_text="Ruolo o carica, es. «Sindaco di Avigliano», «Presidente provinciale».",
    )
    email = models.EmailField(blank=True)
    pec = models.EmailField("PEC", blank=True)
    telefono = models.CharField(max_length=30, blank=True)
    cellulare = models.CharField(max_length=30, blank=True)
    indirizzo = models.CharField(max_length=255, blank=True)
    cap = models.CharField("CAP", max_length=5, blank=True, validators=[validatore_cap])
    comune = models.CharField(max_length=100, blank=True)
    provincia = models.CharField(max_length=2, blank=True, validators=[validatore_provincia])
    nazione = models.CharField(max_length=2, default="IT", help_text="Codice ISO a 2 lettere")
    categorie = models.ManyToManyField(Categoria, blank=True, related_name="soggetti")
    foto = models.ImageField(
        upload_to=percorso_foto,
        blank=True,
        max_length=255,
        editable=False,
        help_text="Foto della persona o logo dell'ente; visibile solo a chi accede all'anagrafica.",
    )
    note = models.TextField(blank=True)
    attivo = models.BooleanField(
        default=True, help_text="I soggetti archiviati restano nei documenti ma non nelle liste."
    )
    anonimizzato_il = models.DateTimeField(
        "anonimizzato il", null=True, blank=True, editable=False,
        help_text="Dati personali cancellati (GDPR): la scheda non si modifica più.",
    )  # fmt: skip

    objects = SoggettoQuerySet.as_manager()

    class Meta:
        verbose_name = "soggetto"
        verbose_name_plural = "soggetti"
        ordering = ["cognome", "nome", "denominazione"]
        permissions = [
            ("archivia_soggetto", "Può archiviare e ripristinare soggetti"),
            ("esporta_soggetti", "Può esportare l'anagrafica"),
            ("esporta_dati_personali", "Può esportare tutti i dati di una persona (GDPR)"),
            ("anonimizza_soggetto", "Può anonimizzare una persona (irreversibile)"),
            ("importa_soggetti", "Può importare schede da una rubrica (vCard)"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(Q(tipo="persona") & ~Q(cognome=""))
                | (Q(tipo="ente") & ~Q(denominazione="")),
                name="soggetto_nome_obbligatorio",
                violation_error_message="Indicare il cognome (persona) o la denominazione (ente).",
            ),
        ]

    def __str__(self):
        return self.nome_completo

    def get_absolute_url(self):
        return reverse("anagrafica:dettaglio", args=[self.pk])

    @property
    def is_persona(self):
        return self.tipo == self.Tipo.PERSONA

    @property
    def nome_completo(self):
        if self.is_persona:
            return " ".join(p for p in [self.cognome, self.nome] if p)
        return self.denominazione

    @property
    def intestazione(self):
        """Forma per lettere e indirizzi: «Gen. Mario Rossi»."""
        if self.is_persona:
            return " ".join(p for p in [self.titolo, self.nome, self.cognome] if p)
        return self.denominazione

    @property
    def iniziali(self):
        if self.is_persona:
            return ((self.nome[:1] if self.nome else "") + (self.cognome[:1])).upper()
        return self.denominazione[:2].upper()

    @property
    def deceduto(self):
        return self.data_decesso is not None

    @property
    def eta(self):
        if not self.data_nascita:
            return None
        fine = self.data_decesso or date.today()
        nascita = self.data_nascita
        return fine.year - nascita.year - ((fine.month, fine.day) < (nascita.month, nascita.day))

    @property
    def indirizzo_completo(self):
        localita = " ".join(p for p in [self.cap, self.comune] if p)
        if self.provincia:
            localita = f"{localita} ({self.provincia})"
        return ", ".join(p for p in [self.indirizzo, localita] if p)

    def save(self, *args, **kwargs):
        self.codice_fiscale = (self.codice_fiscale or "").strip().upper() or None
        self.provincia = (self.provincia or "").strip().upper()
        self.nazione = (self.nazione or "IT").strip().upper()
        if self.email:
            self.email = self.email.strip().lower()
        if self.pec:
            self.pec = self.pec.strip().lower()
        super().save(*args, **kwargs)

    @classmethod
    def compleanni_prossimi(cls, giorni=14, oggi=None):
        """Persone attive e in vita con compleanno nei prossimi `giorni` giorni, in ordine."""
        oggi = oggi or date.today()
        risultato = []
        persone = cls.objects.attivi().filter(
            tipo=cls.Tipo.PERSONA, data_nascita__isnull=False, data_decesso__isnull=True
        )
        for p in persone.only("id", "nome", "cognome", "titolo", "data_nascita", "tipo"):
            prossimo = _prossimo_anniversario(p.data_nascita, oggi)
            mancano = (prossimo - oggi).days
            if mancano <= giorni:
                p.prossimo_compleanno = prossimo
                p.giorni_mancanti = mancano
                p.anni_compiuti = prossimo.year - p.data_nascita.year
                risultato.append(p)
        return sorted(risultato, key=lambda p: p.giorni_mancanti)


def _prossimo_anniversario(nascita, oggi):
    def nell_anno(anno):
        try:
            return nascita.replace(year=anno)
        except ValueError:  # 29 febbraio in anno non bisestile
            return date(anno, 3, 1)

    data = nell_anno(oggi.year)
    return data if data >= oggi else nell_anno(oggi.year + 1)


class Consenso(models.Model):
    """Consenso al trattamento dei dati per una finalità (GDPR art. 6-7)."""

    class Finalita(models.TextChoices):
        TRATTAMENTO = "trattamento", "Trattamento dei dati personali (adesione)"
        PARTICOLARI = "particolari", "Trattamento dei dati particolari (art. 9 GDPR)"
        COMUNICAZIONI = "comunicazioni", "Comunicazioni associative (email, posta)"
        AUGURI = "auguri", "Auguri e ricorrenze"
        IMMAGINI = "immagini", "Pubblicazione di foto e video"
        TERZI = "terzi", "Comunicazione dei dati a enti collegati"

    soggetto = models.ForeignKey(Soggetto, on_delete=models.CASCADE, related_name="consensi")
    finalita = models.CharField("finalità", max_length=20, choices=Finalita.choices)
    prestato = models.BooleanField(default=True, help_text="Falso = consenso negato o revocato.")
    data = models.DateField(default=date.today)
    modalita = models.CharField(
        "modalità", max_length=100, blank=True, help_text="Es. modulo cartaceo, email, verbale."
    )
    registrato_il = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "consenso"
        verbose_name_plural = "consensi"
        ordering = ["-data", "-registrato_il"]

    def __str__(self):
        stato = "prestato" if self.prestato else "negato/revocato"
        return f"{self.get_finalita_display()}: {stato} il {self.data:%d/%m/%Y}"
