# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Modelli trasversali: base comune, dati dell'organizzazione,
# *              sequenze di numerazione e registro delle attività (audit).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.core.validators import RegexValidator
from django.db import models


class ModelloBase(models.Model):
    """Campi comuni: date e autori di creazione e ultima modifica."""

    creato_il = models.DateTimeField("creato il", auto_now_add=True)
    modificato_il = models.DateTimeField("modificato il", auto_now=True)
    creato_da = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="creato da",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="+",
    )
    modificato_da = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="modificato da",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="+",
    )

    class Meta:
        abstract = True


validatore_provincia = RegexValidator(r"^[A-Z]{2}$", "Sigla di due lettere maiuscole (es. PZ).")
validatore_colore = RegexValidator(r"^#[0-9a-fA-F]{6}$", "Colore nel formato #RRGGBB.")


def percorso_logo(istanza, nome):
    from .immagini import nome_casuale

    return nome_casuale("organizzazione", "png")


validatore_cap = RegexValidator(r"^\d{5}$", "Il CAP è di 5 cifre.")


class Organizzazione(models.Model):
    """Dati dell'ente: una sola riga (pk=1), usata per intestazioni e documenti."""

    denominazione = models.CharField(max_length=255, default="Associazione")
    denominazione_breve = models.CharField("denominazione breve", max_length=80, blank=True)
    codice_fiscale = models.CharField("codice fiscale", max_length=16, blank=True)
    partita_iva = models.CharField("partita IVA", max_length=11, blank=True)
    iscrizione_runts = models.CharField(
        "iscrizione RUNTS",
        max_length=50,
        blank=True,
        help_text="Numero di repertorio, se iscritta.",
    )
    indirizzo = models.CharField(max_length=255, blank=True)
    cap = models.CharField("CAP", max_length=5, blank=True, validators=[validatore_cap])
    comune = models.CharField(max_length=100, blank=True)
    provincia = models.CharField(max_length=2, blank=True, validators=[validatore_provincia])
    telefono = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    pec = models.EmailField("PEC", blank=True)
    sito_web = models.URLField("sito web", blank=True)
    logo = models.ImageField(upload_to=percorso_logo, blank=True, max_length=255, editable=False)
    # aspetto dell'interfaccia
    colore_primario = models.CharField(
        "colore principale",
        max_length=7,
        default="#1d4e89",
        validators=[validatore_colore],
        help_text="Pulsanti, collegamenti, intestazioni dei documenti.",
    )

    class StileMenu(models.TextChoices):
        SCURO = "scuro", "Scuro"
        CHIARO = "chiaro", "Chiaro"
        COLORATO = "colorato", "Nel colore principale"

    stile_menu = models.CharField(
        "menu laterale", max_length=10, choices=StileMenu.choices, default=StileMenu.SCURO
    )
    configurata = models.BooleanField(
        "configurazione iniziale completata", default=False, editable=False
    )
    informativa_privacy = models.TextField(
        "informativa privacy",
        blank=True,
        help_text="Testo riportato nei moduli e nelle comunicazioni.",
    )
    # modulo di richiesta di adesione (Allegato A) e consenso al trattamento dei dati
    federazione = models.CharField(
        max_length=100,
        blank=True,
        help_text="Federazione provinciale di appartenenza, es. «Potenza Matera».",
    )
    modulo_intestazione = models.TextField(
        "intestazione del modulo di adesione",
        blank=True,
        help_text="Una riga per voce; la prima in grande (es. il nome dell'associazione "
        "nazionale). Vuoto = denominazione dell'ente.",
    )
    modulo_articoli_statuto = models.CharField(
        "articoli dello statuto richiamati",
        max_length=200,
        blank=True,
        help_text="Es. «all'art. 2 ed agli articoli 5, 6, 7, 8, 9 e 58».",
    )
    modulo_dichiarazione = models.CharField(
        "dichiarazione con risposta SI/NO",
        max_length=255,
        blank=True,
        help_text="Es. «iscritto all'Associazione Decorati di Medaglia d'Oro al valor Militare e/o "
        "Valor Civile». Vuoto = non richiesta.",
    )
    modulo_piede = models.TextField(
        "piè di pagina del modulo",
        blank=True,
        help_text="Es. sede legale nazionale, partita IVA, recapiti.",
    )
    iscrizioni_online = models.BooleanField(
        "domande di iscrizione online",
        default=False,
        help_text="Pubblica il modulo di domanda di iscrizione all'indirizzo /iscrizione/.",
    )
    modificato_il = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "organizzazione"
        verbose_name_plural = "organizzazione"
        permissions = [("gestisci_organizzazione", "Può modificare i dati dell'organizzazione")]

    def __str__(self):
        return self.denominazione

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied("I dati dell'organizzazione non si eliminano.")

    @classmethod
    def corrente(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def nome_breve(self):
        return self.denominazione_breve or self.denominazione

    @property
    def righe_intestazione_modulo(self):
        righe = [r.strip() for r in self.modulo_intestazione.splitlines() if r.strip()]
        return righe or [self.denominazione]

    @property
    def nome_modulo(self):
        """Nome dell'associazione a cui si chiede l'adesione (prima riga dell'intestazione),
        scritto come nel testo: «Associazione Nazionale Combattenti e Reduci»."""
        nome = self.righe_intestazione_modulo[0]
        if not nome.isupper():
            return nome
        minuscole = {"e", "di", "del", "della", "dei", "degli", "delle", "per", "a", "in", "ed"}
        return " ".join(
            p.lower() if i and p.lower() in minuscole else p.capitalize()
            for i, p in enumerate(nome.split())
        )

    @property
    def colore_testo_primario(self):
        """Bianco o scuro, quello leggibile sul colore principale (luminanza WCAG)."""
        r, g, b = (int(self.colore_primario[i : i + 2], 16) / 255 for i in (1, 3, 5))

        def lineare(c):
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

        luminanza = 0.2126 * lineare(r) + 0.7152 * lineare(g) + 0.0722 * lineare(b)
        return "#ffffff" if luminanza < 0.4 else "#182433"

    @property
    def colore_rgb(self):
        return ",".join(str(int(self.colore_primario[i : i + 2], 16)) for i in (1, 3, 5))

    @property
    def versione_aspetto(self):
        return int(self.modificato_il.timestamp()) if self.modificato_il else 0


class Sequenza(models.Model):
    """Contatore di una numerazione (es. protocollo 2026). Usare apps.core.numerazione."""

    chiave = models.CharField(max_length=50)
    anno = models.PositiveIntegerField(default=0, help_text="0 = numerazione non annuale")
    ultimo_numero = models.PositiveIntegerField("ultimo numero", default=0)

    class Meta:
        verbose_name = "sequenza di numerazione"
        verbose_name_plural = "sequenze di numerazione"
        constraints = [
            models.UniqueConstraint(fields=["chiave", "anno"], name="sequenza_unica_per_anno")
        ]

    def __str__(self):
        return f"{self.chiave}/{self.anno or '-'}: {self.ultimo_numero}"


class EventoAudit(models.Model):
    """Registro delle attività: scritto dai servizi, mai modificato né cancellato dall'app."""

    class Azione(models.TextChoices):
        ACCESSO = "accesso", "Accesso"
        ACCESSO_FALLITO = "accesso_fallito", "Accesso fallito"
        USCITA = "uscita", "Uscita"
        CREAZIONE = "creazione", "Creazione"
        MODIFICA = "modifica", "Modifica"
        ARCHIVIAZIONE = "archiviazione", "Archiviazione"
        ELIMINAZIONE = "eliminazione", "Eliminazione"
        ANNULLAMENTO = "annullamento", "Annullamento"
        ESPORTAZIONE = "esportazione", "Esportazione"
        CONSULTAZIONE = "consultazione", "Consultazione"

    momento = models.DateTimeField(auto_now_add=True, db_index=True)
    utente = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    utente_descrizione = models.CharField(max_length=150, blank=True)
    azione = models.CharField(max_length=20, choices=Azione.choices, db_index=True)
    oggetto_tipo = models.ForeignKey(
        ContentType, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    oggetto_id = models.CharField(max_length=64, blank=True)
    oggetto_descrizione = models.CharField(max_length=255, blank=True)
    dettagli = models.JSONField(default=dict, blank=True)
    indirizzo_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name = "evento del registro attività"
        verbose_name_plural = "registro attività"
        ordering = ["-momento", "-id"]
        indexes = [models.Index(fields=["oggetto_tipo", "oggetto_id"])]

    def __str__(self):
        return (
            f"{self.momento:%d/%m/%Y %H:%M} {self.utente_descrizione} {self.get_azione_display()}"
        )

    def save(self, *args, **kwargs):
        if self.pk:
            raise PermissionDenied("Gli eventi del registro attività non si modificano.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied("Gli eventi del registro attività non si eliminano.")
