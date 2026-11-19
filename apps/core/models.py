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
    # firme e timbri nelle stampe quando manca l'immagine caricata (Organi sociali → Firme e timbri)
    firma_generica = models.BooleanField(
        "firma generica",
        default=True,
        help_text="Se manca l'immagine della firma, il nome di chi firma in corsivo sopra la riga.",
    )
    timbro_generico = models.BooleanField(
        "timbro generico",
        default=True,
        help_text="Se manca l'immagine del timbro, un timbro tondo con la denominazione dell'ente.",
    )
    informativa_privacy = models.TextField(
        "informativa privacy",
        blank=True,
        help_text="Testo riportato nei moduli e nelle comunicazioni.",
    )
    # segnatura di protocollo (AgID, Linee guida, Allegato 6): Identificatore
    codice_amministrazione = models.CharField(
        "codice amministrazione (IPA)", max_length=40, blank=True,
        validators=[RegexValidator(r"^[A-Za-z0-9_.\-]+$", "Solo lettere, cifre, _ . -")],
        help_text="Codice IPA, se l'ente è iscritto all'Indice PA; vuoto: il codice fiscale.",
    )  # fmt: skip
    codice_aoo = models.CharField(
        "codice AOO (IPA)", max_length=40, blank=True,
        validators=[RegexValidator(r"^[A-Za-z0-9_.\-]+$", "Solo lettere, cifre, _ . -")],
        help_text="Codice univoco dell'Area Organizzativa Omogenea nell'IPA; vuoto: «AOO».",
    )  # fmt: skip
    # modulo di richiesta di adesione (Allegato A) e consenso al trattamento dei dati
    federazione = models.CharField(
        max_length=100,
        blank=True,
        help_text="Federazione provinciale di appartenenza, es. «Potenza Matera».",
    )
    federazione_email = models.EmailField(
        "email della federazione",
        blank=True,
        help_text="Indirizzo istituzionale della federazione: riceve le richieste di tessere.",
    )
    consensi_impliciti_soci = models.BooleanField(
        "consensi impliciti per i soci",
        default=True,
        help_text="Chi è ammesso socio accetta le regole sulla privacy: per i soci attivi e "
        "sospesi ogni consenso vale come prestato, salvo un diniego o una revoca registrati.",
    )
    nazionale_email = models.EmailField(
        "email della sede nazionale",
        blank=True,
        help_text="Per gli ordini di tessere della federazione (bozza email con il PDF).",
    )
    archivio_centrale = models.CharField(
        "archivio centrale dei soci",
        max_length=150,
        blank=True,
        help_text="Dove riportare a mano nuovi soci e rettifiche delle anagrafiche quando non è "
        "collegato via API, es. «Registro soci nazionale» o «Federazione Potenza Matera». "
        "Vuoto: la federazione se c'è una sola sezione, altrimenti il registro nazionale.",
    )
    modulo_intestazione = models.TextField(
        "intestazione del modulo di adesione",
        blank=True,
        help_text="Una riga per voce; la prima in grande (es. il nome dell'associazione "
        "nazionale). Vuoto = denominazione dell'ente.",
    )
    modulo_logo = models.ImageField(
        "logo del modulo di adesione",
        upload_to=percorso_logo,
        blank=True,
        max_length=255,
        editable=False,
        help_text="Es. il logo della presidenza nazionale; vuoto = logo dell'ente.",
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
    area_soci = models.BooleanField(
        "area personale dei soci",
        default=False,
        help_text="I soci entrano all'indirizzo /area/ con un collegamento inviato alla propria "
        "email e vedono dati, tessere, quote, ricevute ed eventi.",
    )
    # pagina pubblica di presentazione (indirizzo principale per chi non ha fatto l'accesso)
    pagina_pubblica = models.BooleanField(
        "pagina pubblica di presentazione",
        default=False,
        help_text="Chi apre l'indirizzo principale senza accesso vede finalità, documenti "
        "pubblici, contatti e il pulsante per accedere; spenta, va alla pagina di accesso.",
    )
    presentazione = models.TextField(
        "finalità dell'associazione",
        blank=True,
        help_text="Testo della pagina pubblica; una riga vuota separa i paragrafi.",
    )
    # termini di conservazione dei dati personali (Sistema -> Conservazione dei dati)
    conservazione_anni = models.PositiveSmallIntegerField(
        "anni di conservazione",
        default=10,
        help_text="Dopo la cessazione da socio o l'archiviazione, i dati della persona si possono "
        "anonimizzare. 0 = nessun termine.",
    )
    anonimizzazione_automatica = models.BooleanField(
        "anonimizzazione automatica",
        default=False,
        help_text="Ogni notte il programma anonimizza chi ha superato il termine (irreversibile).",
    )
    # interruttori dei servizi di posta (Sistema -> Servizi di posta)
    invio_email = models.BooleanField(
        "invio dei messaggi",
        default=True,
        help_text="Spento: non parte nulla, né email e PEC né Telegram, SMS e WhatsApp "
        "(comunicazioni, protocolli, auguri, promemoria, recupero password); i messaggi già "
        "confermati restano in coda.",
    )
    ricezione_posta = models.BooleanField(
        "lettura delle caselle di posta (IMAP)",
        default=True,
        help_text="Spento: la posta da protocollare non viene scaricata dalle caselle.",
    )
    modificato_il = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "organizzazione"
        verbose_name_plural = "organizzazione"
        permissions = [
            ("gestisci_organizzazione", "Può modificare i dati dell'organizzazione"),
            ("gestisci_backup", "Può creare, scaricare ed eliminare i backup"),
            ("ripristina_backup", "Può ripristinare un backup (sostituisce tutti i dati)"),
            (
                "gestisci_servizi_posta",
                "Può attivare e disattivare l'invio e la lettura della posta",
            ),
        ]

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
    def codice_amministrazione_segnatura(self):
        """Codice dell'amministrazione nella segnatura: IPA, altrimenti codice fiscale."""
        return self.codice_amministrazione or self.codice_fiscale or ""

    @property
    def codice_aoo_segnatura(self):
        return self.codice_aoo or "AOO"

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


def percorso_documento_pubblico(istanza, nome):
    from .immagini import nome_casuale

    return nome_casuale("pubblici", "pdf")


class DocumentoPubblico(ModelloBase):
    """Documento consultabile da chiunque (es. statuto e regolamento), caricato dal gestore."""

    titolo = models.CharField(max_length=150, help_text="Es. «Statuto sociale».")
    descrizione = models.CharField(
        max_length=255,
        blank=True,
        help_text="Es. «approvato il 17/12/2020, in vigore dal 21/06/2021».",
    )
    file = models.FileField(upload_to=percorso_documento_pubblico, max_length=255, editable=False)
    nome_file = models.CharField(max_length=200, editable=False)
    dimensione = models.PositiveIntegerField(default=0, editable=False)
    pubblicato = models.BooleanField(
        default=True, help_text="Tolta la spunta, il documento non è più consultabile."
    )
    ordine = models.PositiveSmallIntegerField(default=0, help_text="Ordine nell'elenco pubblico.")

    class Meta:
        verbose_name = "documento pubblico"
        verbose_name_plural = "documenti pubblici"
        ordering = ["ordine", "titolo"]

    def __str__(self):
        return self.titolo

    def get_absolute_url(self):
        from django.urls import reverse
        from django.utils.text import slugify

        return reverse("documento_pubblico", args=[self.pk, slugify(self.titolo) or "documento"])


class ServizioInvio(models.Model):
    """Server di invio (SMTP) per email o PEC, gestito in Sistema → Servizi di posta.

    Il servizio «generale» spedisce le comunicazioni, le email dell'accesso e le spedizioni dei
    protocolli per email; gli altri (es. la PEC) si scelgono quando si spedisce un protocollo.
    Senza un servizio generale vale il server del file .env.
    """

    class Tipo(models.TextChoices):
        EMAIL = "email", "Email"
        PEC = "pec", "PEC"

    nome = models.CharField(max_length=100, help_text="Es. «PEC della federazione».")
    tipo = models.CharField(max_length=5, choices=Tipo.choices, default=Tipo.EMAIL)
    indirizzo = models.EmailField("indirizzo del mittente")
    nome_mittente = models.CharField(
        "nome del mittente",
        max_length=200,
        blank=True,
        help_text="Mostrato a chi riceve. Vuoto: la denominazione dell'organizzazione.",
    )
    server = models.CharField("server SMTP", max_length=200, help_text="Es. smtps.pec.aruba.it")
    porta = models.PositiveIntegerField(default=465)
    ssl = models.BooleanField(
        "SSL implicito",
        default=True,
        help_text="Porta 465: SSL; porta 587: togliere la spunta (si usa STARTTLS).",
    )
    utente = models.CharField(
        "nome utente", max_length=200, blank=True, help_text="Vuoto: l'indirizzo del mittente."
    )
    password_cifrata = models.TextField(editable=False, blank=True)
    generale = models.BooleanField(
        "server generale",
        default=False,
        help_text="Spedisce le comunicazioni, le email dell'accesso (es. recupero password) e i "
        "protocolli per email. Uno solo.",
    )
    attivo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "servizio di invio"
        verbose_name_plural = "servizi di invio"
        ordering = ["-generale", "tipo", "nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["generale"],
                condition=models.Q(generale=True),
                name="un_solo_servizio_generale",
            )
        ]

    def __str__(self):
        return self.nome

    @property
    def pec(self):
        return self.tipo == self.Tipo.PEC

    @property
    def nome_utente(self):
        return self.utente or self.indirizzo

    def imposta_password(self, password):
        from .cifratura import cifra

        self.password_cifrata = cifra(password)

    def password(self):
        from .cifratura import decifra

        return decifra(self.password_cifrata)


class CanaleTelegram(models.Model):
    """Bot Telegram dell'organizzazione (uno solo): le persone si collegano con /start e il codice
    del proprio invito, e ricevono lì le comunicazioni scelte «anche su Telegram»."""

    token_cifrato = models.TextField(editable=False, blank=True)
    nome_bot = models.CharField(
        "nome del bot", max_length=64, blank=True, editable=False, help_text="Letto da Telegram."
    )
    attivo = models.BooleanField(default=False)
    ultimo_update = models.BigIntegerField(default=0, editable=False)
    ultimo_controllo = models.DateTimeField(null=True, blank=True, editable=False)
    ultimo_errore = models.CharField(max_length=300, blank=True, editable=False)

    class Meta:
        verbose_name = "canale Telegram"
        verbose_name_plural = "canale Telegram"

    def __str__(self):
        return f"@{self.nome_bot}" if self.nome_bot else "Telegram"

    @classmethod
    def corrente(cls):
        return cls.objects.get_or_create(pk=1)[0]

    def imposta_token(self, token):
        from .cifratura import cifra

        self.token_cifrato = cifra(token)

    def token(self):
        from .cifratura import decifra

        return decifra(self.token_cifrato) if self.token_cifrato else ""

    @property
    def pronto(self):
        return self.attivo and bool(self.token_cifrato and self.nome_bot)


class ServizioMessaggi(models.Model):
    """Fornitore di SMS o WhatsApp Business (Sistema → Servizi di posta). Si usa il primo attivo
    per ciascun canale; le credenziali sono cifrate come le password delle caselle."""

    class Tipo(models.TextChoices):
        SKEBBY = "skebby", "SMS - Skebby"
        ARUBA = "aruba", "SMS - Aruba"
        TWILIO = "twilio", "SMS - Twilio"
        WHATSAPP = "whatsapp", "WhatsApp Business (API Cloud di Meta)"

    URL_PREDEFINITI = {
        "skebby": "https://api.skebby.it/API/v1.0/REST",
        "aruba": "https://smspanel.aruba.it/API/v1.0/REST",
        "twilio": "https://api.twilio.com/2010-04-01",
        "whatsapp": "https://graph.facebook.com/v21.0",
    }

    nome = models.CharField(max_length=100)
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    account = models.CharField(
        max_length=200,
        help_text="Skebby e Aruba: nome utente; Twilio: Account SID; WhatsApp: ID del numero di "
        "telefono (Phone number ID).",
    )
    segreto_cifrato = models.TextField(editable=False, blank=True)
    mittente = models.CharField(
        max_length=40,
        blank=True,
        help_text="SMS: mittente alfanumerico (max 11 caratteri, es. ANCR) o numero; Twilio: "
        "numero (+39...) o Messaging Service SID (MG...). Non serve per WhatsApp.",
    )
    modello = models.CharField(
        "modello WhatsApp",
        max_length=100,
        blank=True,
        help_text="Nome del modello di messaggio approvato da Meta, con un solo parametro {{1}} "
        "nel corpo: lì va il testo breve della comunicazione.",
    )
    lingua = models.CharField("lingua del modello", max_length=10, default="it", blank=True)
    tipo_messaggio = models.CharField(
        "qualità SMS",
        max_length=10,
        blank=True,
        help_text="Skebby e Aruba: tipo di messaggio del listino (es. GP alta qualità, "
        "N notifica). Vuoto: GP.",
    )
    url_base = models.URLField(
        "indirizzo dell'API",
        blank=True,
        help_text="Vuoto: quello predefinito del fornitore. Da cambiare solo se lo indica il "
        "fornitore.",
    )
    attivo = models.BooleanField(default=False)
    ultimo_errore = models.CharField(max_length=300, blank=True, editable=False)

    class Meta:
        verbose_name = "servizio di messaggistica"
        verbose_name_plural = "servizi di messaggistica"
        ordering = ["tipo", "nome"]

    def __str__(self):
        return self.nome

    @property
    def canale(self):
        return "whatsapp" if self.tipo == self.Tipo.WHATSAPP else "sms"

    @property
    def url(self):
        return (self.url_base or self.URL_PREDEFINITI[self.tipo]).rstrip("/")

    def imposta_segreto(self, segreto):
        from .cifratura import cifra

        self.segreto_cifrato = cifra(segreto)

    def segreto(self):
        from .cifratura import decifra

        return decifra(self.segreto_cifrato) if self.segreto_cifrato else ""

    @classmethod
    def attivo_per(cls, canale):
        tipi = ["whatsapp"] if canale == "whatsapp" else ["skebby", "aruba", "twilio"]
        return cls.objects.filter(attivo=True, tipo__in=tipi).exclude(segreto_cifrato="").first()
