# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Modelli del modulo Progetti (P1): finalità statutarie, criteri di valutazione,
# *              idee e necessità (anche da sollecitazioni esterne), valutazioni, progetti con
# *              stati e storico, gruppo di lavoro, scadenze, commenti e allegati.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import secrets
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse

from apps.core.models import ModelloBase


class Categoria(models.TextChoices):
    """Categorie delle voci di costo del piano economico."""

    PERSONALE = "personale", "Personale"
    BENI = "beni", "Beni e attrezzature"
    SERVIZI = "servizi", "Servizi"
    VIAGGI = "viaggi", "Viaggi e trasferte"
    COMUNICAZIONE = "comunicazione", "Comunicazione e promozione"
    VOLONTARIATO = "volontariato", "Volontariato valorizzato"
    ALTRO = "altro", "Altre spese"


SEQ_IDEA = "idea"
SEQ_PROGETTO = "progetto"


def _percorso_allegato(istanza, nome):
    estensione = Path(nome).suffix.lower()[:10]
    return f"progetti/allegati/{secrets.token_urlsafe(12)}{estensione}"


class FinalitaStatutaria(models.Model):
    """Una finalità dello statuto, a cui idee e progetti rispondono."""

    codice = models.CharField(max_length=10, help_text="Es. «a» per l'art. 2 lettera a).")
    titolo = models.CharField(max_length=150, help_text="Breve, per gli elenchi.")
    testo = models.TextField("testo dello statuto", blank=True)
    ordine = models.PositiveSmallIntegerField(default=0)
    attiva = models.BooleanField(default=True)

    class Meta:
        verbose_name = "finalità statutaria"
        verbose_name_plural = "finalità statutarie"
        ordering = ["ordine", "codice"]

    def __str__(self):
        return f"{self.codice}) {self.titolo}" if self.codice else self.titolo


class CriterioValutazione(models.Model):
    """Criterio con cui si valutano le idee (punteggio da 1 a 5), con il suo peso."""

    nome = models.CharField(max_length=100, unique=True)
    descrizione = models.CharField(max_length=255, blank=True)
    peso = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Conta nella media pesata (1 = normale).",
    )
    ordine = models.PositiveSmallIntegerField(default=0)
    attivo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "criterio di valutazione"
        verbose_name_plural = "criteri di valutazione"
        ordering = ["ordine", "nome"]

    def __str__(self):
        return self.nome


class Idea(ModelloBase):
    """Idea o necessità da cui può nascere un progetto."""

    class Stato(models.TextChoices):
        NUOVA = "nuova", "Nuova"
        IN_VALUTAZIONE = "valutazione", "In valutazione"
        APPROVATA = "approvata", "Approvata (progetto)"
        ACCANTONATA = "accantonata", "Accantonata"

    class Fonte(models.TextChoices):
        INTERNA = "interna", "Interna (soci, organi)"
        ESTERNA = "esterna", "Esterna (ente, cittadino, altri)"

    class Priorita(models.TextChoices):
        ALTA = "alta", "Alta"
        MEDIA = "media", "Media"
        BASSA = "bassa", "Bassa"

    anno = models.PositiveIntegerField(editable=False)
    numero = models.PositiveIntegerField(editable=False)
    titolo = models.CharField(max_length=200)
    descrizione = models.TextField(help_text="In cosa consiste l'idea.")
    bisogno = models.TextField(
        "bisogno", blank=True, help_text="Quale necessità affronta, per chi, perché ora."
    )
    destinatari = models.CharField(
        max_length=255, blank=True, help_text="Es. studenti delle scuole medie, soci anziani."
    )
    finalita = models.ManyToManyField(
        FinalitaStatutaria, blank=True, related_name="idee", verbose_name="finalità statutarie"
    )
    costo_stimato = models.DecimalField(
        "costo stimato", max_digits=12, decimal_places=2, null=True, blank=True
    )
    fonte = models.CharField(max_length=10, choices=Fonte.choices, default=Fonte.INTERNA)
    fonte_soggetto = models.ForeignKey(
        "anagrafica.Soggetto",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="idee_proposte",
        verbose_name="proposta da (anagrafica)",
    )
    fonte_testo = models.CharField(
        "proposta da",
        max_length=255,
        blank=True,
        help_text="Chi l'ha sollecitata, se non è in anagrafica (es. «Dirigente dell'istituto X»).",
    )
    protocollo = models.ForeignKey(
        "protocollo.Protocollo",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="idee",
        editable=False,
    )
    messaggio = models.ForeignKey(
        "protocollo.MessaggioRicevuto",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="idee",
        editable=False,
    )
    proponente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="idee",
        editable=False,
    )
    stato = models.CharField(max_length=12, choices=Stato.choices, default=Stato.NUOVA)
    motivo_stato = models.CharField(max_length=255, blank=True, editable=False)
    priorita = models.CharField("priorità", max_length=6, choices=Priorita.choices, blank=True)
    delibera_priorita = models.ForeignKey(
        "organi.Delibera",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="delibera della priorità",
    )

    class Meta:
        verbose_name = "idea"
        verbose_name_plural = "idee"
        ordering = ["-anno", "-numero"]
        constraints = [models.UniqueConstraint(fields=["anno", "numero"], name="idea_numero_unico")]
        permissions = [
            ("valuta_idea", "Valutare e commentare le idee"),
            ("gestisci_idee", "Gestire le idee: stato, priorità, trasformazione in progetto"),
        ]

    def __str__(self):
        return f"{self.codice} {self.titolo}"

    @property
    def codice(self):
        return f"I-{self.anno}-{self.numero:03d}"

    def get_absolute_url(self):
        return reverse("progetti:idea", args=[self.pk])

    @property
    def proposta_da(self):
        if self.fonte_soggetto_id:
            return self.fonte_soggetto.nome_completo
        return self.fonte_testo


class Valutazione(models.Model):
    """Valutazione di un'idea da parte di un utente: punteggi per criterio e commento."""

    idea = models.ForeignKey(Idea, on_delete=models.CASCADE, related_name="valutazioni")
    utente = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    punteggi = models.JSONField(default=dict, help_text="{id del criterio: punteggio 1-5}")
    media = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    commento = models.TextField(blank=True)
    creata_il = models.DateTimeField(auto_now_add=True)
    modificata_il = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "valutazione"
        verbose_name_plural = "valutazioni"
        ordering = ["-modificata_il"]
        constraints = [
            models.UniqueConstraint(fields=["idea", "utente"], name="una_valutazione_per_utente")
        ]

    def __str__(self):
        return f"Valutazione di {self.utente} su {self.idea.codice}"


class Bando(ModelloBase):
    """Bando o avviso di finanziamento: registrato a mano (in P3 anche raccolto da fonti)."""

    class Stato(models.TextChoices):
        SEGNALATO = "segnalato", "Da valutare"
        INTERESSANTE = "interessante", "Interessante"
        PARTECIPATO = "partecipato", "Partecipato"
        SCARTATO = "scartato", "Scartato"

    titolo = models.CharField(max_length=255)
    finanziatore = models.ForeignKey(
        "anagrafica.Soggetto",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bandi_finanziati",
        help_text="L'ente che finanzia, se è in anagrafica.",
    )
    finanziatore_testo = models.CharField(
        "finanziatore (testo)", max_length=200, blank=True, help_text="Se non è in anagrafica."
    )
    link = models.URLField("indirizzo del bando", max_length=500, blank=True)
    descrizione = models.TextField(blank=True, help_text="Cosa finanzia, a chi si rivolge.")
    finalita = models.ManyToManyField(
        FinalitaStatutaria, blank=True, related_name="bandi", verbose_name="finalità statutarie"
    )
    importo_massimo = models.DecimalField(
        "contributo massimo (€)", max_digits=12, decimal_places=2, null=True, blank=True
    )
    cofinanziamento = models.DecimalField(
        "cofinanziamento richiesto (%)",
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Quota del costo a carico dell'associazione.",
    )
    apertura = models.DateField(null=True, blank=True)
    scadenza = models.DateField("scadenza della domanda", null=True, blank=True)
    esito_previsto = models.DateField("esito previsto", null=True, blank=True)
    stato = models.CharField(
        max_length=12, choices=Stato.choices, default=Stato.SEGNALATO, editable=False
    )
    motivo = models.CharField("motivo", max_length=255, blank=True, editable=False)
    promemoria = models.JSONField(default=list, editable=False)  # giorni già avvisati
    spese_generali_massime = models.DecimalField(
        "spese generali massime (%)",
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Sul totale dei costi diretti.",
    )
    tariffa_volontariato = models.DecimalField(
        "tariffa oraria del volontariato (€)",
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Se il bando la fissa: valorizza le ore come cofinanziamento in natura.",
    )
    natura_massima = models.DecimalField(
        "cofinanziamento in natura massimo (%)",
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Quota del cofinanziamento che può essere in natura (volontariato valorizzato).",
    )

    class Meta:
        verbose_name = "bando"
        verbose_name_plural = "bandi"
        ordering = ["scadenza", "titolo"]
        permissions = [("gestisci_bandi", "Gestire i bandi: stato, requisiti, candidature")]

    def __str__(self):
        return self.titolo

    def get_absolute_url(self):
        return reverse("progetti:bando", args=[self.pk])

    @property
    def ente(self):
        return str(self.finanziatore) if self.finanziatore_id else self.finanziatore_testo

    def giorni_alla_scadenza(self, oggi=None):
        from django.utils import timezone

        if not self.scadenza:
            return None
        return (self.scadenza - (oggi or timezone.localdate())).days

    @property
    def scaduto(self):
        giorni = self.giorni_alla_scadenza()
        return giorni is not None and giorni < 0

    @property
    def candidabile(self):
        return self.stato != self.Stato.SCARTATO and not self.scaduto


class LimiteCategoria(models.Model):
    """Percentuale massima di una categoria di costo sul totale del progetto, fissata dal bando."""

    bando = models.ForeignKey(Bando, on_delete=models.CASCADE, related_name="limiti")
    categoria = models.CharField(max_length=15, choices=Categoria.choices)
    percentuale_massima = models.DecimalField(
        "percentuale massima",
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    class Meta:
        verbose_name = "limite di categoria"
        verbose_name_plural = "limiti di categoria"
        constraints = [
            models.UniqueConstraint(fields=["bando", "categoria"], name="un_limite_per_categoria")
        ]

    def __str__(self):
        return f"{self.get_categoria_display()} ≤ {self.percentuale_massima}%"


class SezioneBando(models.Model):
    """Sezione del formulario richiesta da un bando (sostituisce lo schema predefinito)."""

    bando = models.ForeignKey(Bando, on_delete=models.CASCADE, related_name="sezioni")
    titolo = models.CharField(max_length=200)
    domande = models.TextField("domande guida", blank=True, help_text="Una per riga.")
    massimo_caratteri = models.PositiveIntegerField("massimo di caratteri", null=True, blank=True)
    ordine = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "sezione del formulario"
        verbose_name_plural = "sezioni del formulario"
        ordering = ["ordine", "pk"]

    def __str__(self):
        return self.titolo


class Requisito(models.Model):
    """Requisito di partecipazione: verificato sui dati del gestionale o a mano."""

    class Esito(models.TextChoices):
        SI = "si", "Soddisfatto"
        NO = "no", "Mancante"
        VERIFICARE = "verificare", "Da verificare"

    bando = models.ForeignKey(Bando, on_delete=models.CASCADE, related_name="requisiti")
    descrizione = models.CharField(max_length=255)
    verifica = models.CharField(
        "verifica automatica", max_length=30, blank=True, help_text="Vuoto: si controlla a mano."
    )
    parametro = models.CharField(max_length=100, blank=True)
    esito_manuale = models.CharField(
        "esito indicato", max_length=10, choices=Esito.choices, blank=True
    )
    nota = models.CharField(max_length=255, blank=True)
    ordine = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "requisito"
        verbose_name_plural = "requisiti"
        ordering = ["ordine", "pk"]

    def __str__(self):
        return self.descrizione


class FonteBandi(models.Model):
    """Fonte sorvegliata per la raccolta automatica dei bandi (P3)."""

    class Tipo(models.TextChoices):
        FEED = "feed", "Feed RSS o Atom"
        PAGINA = "pagina", "Pagina web (collegamenti nuovi)"

    nome = models.CharField(max_length=150)
    tipo = models.CharField(max_length=6, choices=Tipo.choices, default=Tipo.FEED)
    indirizzo = models.URLField(max_length=500, unique=True)
    parole_chiave = models.CharField(
        "parole chiave proprie",
        max_length=500,
        blank=True,
        help_text="Oltre a quelle generali, separate da virgole. Vuoto: solo quelle generali.",
    )
    tutte = models.BooleanField(
        "proponi tutto",
        default=False,
        help_text="Per le fonti di soli bandi: propone ogni novità, senza parole chiave.",
    )
    attiva = models.BooleanField(default=True)
    ultimo_controllo = models.DateTimeField(null=True, blank=True, editable=False)
    ultimo_esito = models.CharField(max_length=255, blank=True, editable=False)
    errori = models.PositiveSmallIntegerField(default=0, editable=False)

    class Meta:
        verbose_name = "fonte dei bandi"
        verbose_name_plural = "fonti dei bandi"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class ParolaChiave(models.Model):
    """Parola o espressione che rende interessante (o esclude) una novità delle fonti."""

    parola = models.CharField(max_length=100, unique=True)
    esclusa = models.BooleanField(
        default=False, help_text="Se presente, la novità si scarta (es. «imprese», «concorso»)."
    )

    class Meta:
        verbose_name = "parola chiave"
        verbose_name_plural = "parole chiave"
        ordering = ["esclusa", "parola"]

    def __str__(self):
        return f"−{self.parola}" if self.esclusa else self.parola


class BandoProposto(models.Model):
    """Novità raccolta da una fonte, da vagliare: diventa un bando o si scarta."""

    class Stato(models.TextChoices):
        NUOVO = "nuovo", "Da vagliare"
        ACCOLTO = "accolto", "Accolto"
        SCARTATO = "scartato", "Scartato"

    fonte = models.ForeignKey(
        FonteBandi, null=True, on_delete=models.SET_NULL, related_name="proposte"
    )
    titolo = models.CharField(max_length=500)
    link = models.URLField(max_length=1000, unique=True)
    sommario = models.TextField(blank=True)
    pubblicato_il = models.DateTimeField(null=True, blank=True)
    trovato_il = models.DateTimeField(auto_now_add=True)
    parole = models.CharField("parole trovate", max_length=255, blank=True)
    stato = models.CharField(max_length=8, choices=Stato.choices, default=Stato.NUOVO)
    bando = models.ForeignKey(
        Bando, null=True, blank=True, on_delete=models.SET_NULL, related_name="proposte"
    )
    esaminato_da = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    esaminato_il = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "bando proposto"
        verbose_name_plural = "bandi proposti"
        ordering = ["-trovato_il"]

    def __str__(self):
        return self.titolo


class Progetto(ModelloBase):
    """Progetto finalizzato agli scopi statutari, dall'idea alla chiusura."""

    class Stato(models.TextChoices):
        PROGETTAZIONE = "progettazione", "In progettazione"
        CANDIDATO = "candidato", "Candidato"
        FINANZIATO = "finanziato", "Finanziato"
        NON_FINANZIATO = "non_finanz", "Non finanziato"
        IN_CORSO = "in_corso", "In corso"
        RENDICONTAZIONE = "rendiconto", "In rendicontazione"
        CHIUSO = "chiuso", "Chiuso"
        ACCANTONATO = "accantonato", "Accantonato"

    # passaggi ammessi (gli altri richiedono di passare dagli stati intermedi)
    PASSAGGI = {
        Stato.PROGETTAZIONE: [Stato.CANDIDATO, Stato.IN_CORSO, Stato.ACCANTONATO],
        Stato.CANDIDATO: [Stato.FINANZIATO, Stato.NON_FINANZIATO, Stato.PROGETTAZIONE],
        Stato.FINANZIATO: [Stato.IN_CORSO, Stato.ACCANTONATO],
        Stato.NON_FINANZIATO: [Stato.PROGETTAZIONE, Stato.ACCANTONATO],
        Stato.IN_CORSO: [Stato.RENDICONTAZIONE, Stato.CHIUSO],
        Stato.RENDICONTAZIONE: [Stato.CHIUSO, Stato.IN_CORSO],
        Stato.CHIUSO: [],
        Stato.ACCANTONATO: [Stato.PROGETTAZIONE],
    }

    anno = models.PositiveIntegerField(editable=False)
    numero = models.PositiveIntegerField(editable=False)
    titolo = models.CharField(max_length=200)
    sintesi = models.TextField(help_text="Cosa si vuole fare, per chi e perché, in poche righe.")
    idea = models.OneToOneField(
        Idea,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="progetto",
        editable=False,
    )
    finalita = models.ManyToManyField(
        FinalitaStatutaria, blank=True, related_name="progetti", verbose_name="finalità statutarie"
    )
    responsabile = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="progetti_responsabile",
    )
    inizio_previsto = models.DateField("inizio previsto", null=True, blank=True)
    fine_prevista = models.DateField("fine prevista", null=True, blank=True)
    stato = models.CharField(
        max_length=13, choices=Stato.choices, default=Stato.PROGETTAZIONE, editable=False
    )
    bando = models.ForeignKey(
        Bando,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="progetti",
        editable=False,
    )
    # quadro del progetto (P4)
    obiettivo_generale = models.TextField("obiettivo generale", blank=True)
    destinatari = models.TextField(blank=True, help_text="Chi ne beneficia e quanti.")
    territorio = models.CharField(max_length=255, blank=True)
    tariffa_volontariato = models.DecimalField(
        "tariffa oraria del volontariato (€)",
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Dal bando o fissata dal consiglio.",
    )
    eventi = models.ManyToManyField("eventi.Evento", blank=True, related_name="progetti")
    protocollo_candidatura = models.ForeignKey(
        "protocollo.Protocollo",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        editable=False,
    )
    spese_generali = models.DecimalField(
        "spese generali (%)",
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Forfettarie, in percentuale sui costi diretti (se il bando le ammette).",
    )

    class Meta:
        verbose_name = "progetto"
        verbose_name_plural = "progetti"
        ordering = ["-anno", "-numero"]
        constraints = [
            models.UniqueConstraint(fields=["anno", "numero"], name="progetto_numero_unico")
        ]
        permissions = [("gestisci_progetti", "Gestire i progetti: stato, gruppo, scadenze")]

    def __str__(self):
        return f"{self.codice} {self.titolo}"

    @property
    def codice(self):
        return f"P-{self.anno}-{self.numero:03d}"

    def get_absolute_url(self):
        return reverse("progetti:progetto", args=[self.pk])

    @property
    def stati_successivi(self):
        return [(s, self.Stato(s).label) for s in self.PASSAGGI.get(self.stato, [])]

    @property
    def aperto(self):
        return self.stato not in (self.Stato.CHIUSO, self.Stato.ACCANTONATO)

    @property
    def sezioni_proposta(self):
        return self.sezioni.filter(documento="proposta")

    @property
    def sezioni_relazione(self):
        return self.sezioni.filter(documento="relazione")

    @property
    def sezioni_consiglio(self):
        return self.sezioni.filter(documento="consiglio")


class PassaggioStato(models.Model):
    """Storico degli stati di un progetto, con l'eventuale delibera."""

    progetto = models.ForeignKey(Progetto, on_delete=models.CASCADE, related_name="passaggi")
    da = models.CharField(max_length=13, choices=Progetto.Stato.choices, blank=True)
    a = models.CharField(max_length=13, choices=Progetto.Stato.choices)
    data = models.DateTimeField(auto_now_add=True)
    utente = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    motivo = models.CharField(max_length=255, blank=True)
    delibera = models.ForeignKey(
        "organi.Delibera", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        verbose_name = "passaggio di stato"
        verbose_name_plural = "passaggi di stato"
        ordering = ["-data", "-pk"]

    def __str__(self):
        return f"{self.progetto.codice}: {self.get_a_display()}"


class Membro(models.Model):
    """Persona del gruppo di lavoro: un utente del gestionale o una persona dell'anagrafica."""

    progetto = models.ForeignKey(Progetto, on_delete=models.CASCADE, related_name="membri")
    utente = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="+"
    )
    soggetto = models.ForeignKey(
        "anagrafica.Soggetto",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="progetti",
    )
    ruolo = models.CharField(max_length=100, help_text="Es. referente scuole, volontario, partner.")
    volontario = models.BooleanField(default=False)

    class Meta:
        verbose_name = "membro del gruppo"
        verbose_name_plural = "gruppo di lavoro"
        ordering = ["ruolo", "pk"]

    def __str__(self):
        chi = self.soggetto.nome_completo if self.soggetto_id else str(self.utente)
        return f"{chi} ({self.ruolo})"


class Scadenza(models.Model):
    progetto = models.ForeignKey(Progetto, on_delete=models.CASCADE, related_name="scadenze")
    titolo = models.CharField(max_length=200)
    data = models.DateField()
    fatta = models.BooleanField(default=False)

    class Meta:
        verbose_name = "scadenza"
        verbose_name_plural = "scadenze"
        ordering = ["fatta", "data"]

    def __str__(self):
        return f"{self.titolo} ({self.data:%d/%m/%Y})"


class Obiettivo(models.Model):
    """Obiettivo specifico del progetto, con i risultati attesi."""

    progetto = models.ForeignKey(Progetto, on_delete=models.CASCADE, related_name="obiettivi")
    testo = models.CharField("obiettivo specifico", max_length=500)
    risultati = models.TextField("risultati attesi", blank=True)
    ordine = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "obiettivo specifico"
        verbose_name_plural = "obiettivi specifici"
        ordering = ["ordine", "pk"]

    def __str__(self):
        return self.testo


class Indicatore(models.Model):
    """Indicatore misurabile di un risultato (valore raggiunto aggiornato nell'esecuzione)."""

    progetto = models.ForeignKey(Progetto, on_delete=models.CASCADE, related_name="indicatori")
    obiettivo = models.ForeignKey(
        Obiettivo, null=True, blank=True, on_delete=models.SET_NULL, related_name="indicatori"
    )
    descrizione = models.CharField(max_length=255)
    unita = models.CharField("unità di misura", max_length=50, blank=True)
    valore_iniziale = models.DecimalField(
        "valore iniziale", max_digits=12, decimal_places=2, null=True, blank=True
    )
    valore_atteso = models.DecimalField("valore atteso", max_digits=12, decimal_places=2)
    valore_raggiunto = models.DecimalField(
        "valore raggiunto", max_digits=12, decimal_places=2, null=True, blank=True, editable=False
    )
    fonte_verifica = models.CharField("fonte di verifica", max_length=255, blank=True)

    class Meta:
        verbose_name = "indicatore"
        verbose_name_plural = "indicatori"
        ordering = ["obiettivo__ordine", "pk"]

    def __str__(self):
        return self.descrizione


class Attivita(models.Model):
    """Attività del cronoprogramma."""

    progetto = models.ForeignKey(Progetto, on_delete=models.CASCADE, related_name="attivita")
    titolo = models.CharField(max_length=200)
    descrizione = models.TextField(blank=True)
    obiettivo = models.ForeignKey(
        Obiettivo, null=True, blank=True, on_delete=models.SET_NULL, related_name="attivita"
    )
    responsabile = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="attivita_progetti",
    )
    inizio = models.DateField()
    fine = models.DateField()
    dopo = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="successive",
        verbose_name="dopo l'attività",
        help_text="Inizia quando questa è finita.",
    )
    completata = models.BooleanField(default=False, editable=False)

    class Meta:
        verbose_name = "attività"
        verbose_name_plural = "attività"
        ordering = ["inizio", "fine", "pk"]

    def __str__(self):
        return self.titolo


class Partner(models.Model):
    """Ente o persona che partecipa al progetto (dall'anagrafica)."""

    class Ruolo(models.TextChoices):
        CAPOFILA = "capofila", "Capofila"
        PARTNER = "partner", "Partner"
        SOSTENITORE = "sostenitore", "Sostenitore"
        RETE = "rete", "Rete / adesione"

    progetto = models.ForeignKey(Progetto, on_delete=models.CASCADE, related_name="partner")
    soggetto = models.ForeignKey(
        "anagrafica.Soggetto", on_delete=models.PROTECT, related_name="partenariati"
    )
    ruolo = models.CharField(max_length=12, choices=Ruolo.choices, default=Ruolo.PARTNER)
    contributo = models.TextField("contributo al progetto", blank=True)
    cofinanziamento = models.DecimalField(
        "cofinanziamento (€)", max_digits=12, decimal_places=2, null=True, blank=True
    )
    lettera_ricevuta = models.BooleanField("lettera di partenariato ricevuta", default=False)

    class Meta:
        verbose_name = "partner"
        verbose_name_plural = "partner"
        constraints = [
            models.UniqueConstraint(fields=["progetto", "soggetto"], name="partner_unico")
        ]

    def __str__(self):
        return f"{self.soggetto} ({self.get_ruolo_display()})"


class VoceCosto(models.Model):
    """Voce del piano economico: quantità per costo unitario."""

    progetto = models.ForeignKey(Progetto, on_delete=models.CASCADE, related_name="voci")
    categoria = models.CharField(max_length=15, choices=Categoria.choices)
    descrizione = models.CharField(max_length=255)
    quantita = models.DecimalField("quantità", max_digits=10, decimal_places=2, default=1)
    unita = models.CharField(
        "unità", max_length=30, blank=True, help_text="Es. ore, giorni, pezzi."
    )
    costo_unitario = models.DecimalField("costo unitario (€)", max_digits=12, decimal_places=2)
    ordine = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "voce di costo"
        verbose_name_plural = "voci di costo"
        ordering = ["categoria", "ordine", "pk"]

    def __str__(self):
        return self.descrizione

    @property
    def importo(self):
        from decimal import Decimal

        return (self.quantita * self.costo_unitario).quantize(Decimal("0.01"))

    @property
    def in_natura(self):
        return self.categoria == Categoria.VOLONTARIATO


class FonteFinanziamento(models.Model):
    """Copertura del piano economico. Il cofinanziamento in natura (volontariato valorizzato) e
    quello dei partner si calcolano dalle voci e dai partner."""

    class Tipo(models.TextChoices):
        CONTRIBUTO = "contributo", "Contributo richiesto al bando"
        PROPRIO = "proprio", "Cofinanziamento proprio in denaro"
        ALTRO = "altro", "Altri finanziatori"

    progetto = models.ForeignKey(Progetto, on_delete=models.CASCADE, related_name="fonti")
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    descrizione = models.CharField(max_length=255, blank=True)
    importo = models.DecimalField("importo (€)", max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = "fonte di finanziamento"
        verbose_name_plural = "fonti di finanziamento"
        ordering = ["tipo", "pk"]

    def __str__(self):
        return self.descrizione or self.get_tipo_display()


class TestoSezione(models.Model):
    """Testo di una sezione della proposta (scrittura guidata, senza IA)."""

    class Documento(models.TextChoices):
        PROPOSTA = "proposta", "Proposta"
        RELAZIONE = "relazione", "Relazione finale"
        CONSIGLIO = "consiglio", "Relazione al consiglio"

    progetto = models.ForeignKey(Progetto, on_delete=models.CASCADE, related_name="sezioni")
    documento = models.CharField(
        max_length=9, choices=Documento.choices, default=Documento.PROPOSTA
    )
    chiave = models.CharField(max_length=30, blank=True)  # sezione predefinita, se lo è
    titolo = models.CharField(max_length=200)
    domande = models.TextField("domande guida", blank=True)
    massimo_caratteri = models.PositiveIntegerField(null=True, blank=True)
    testo = models.TextField(blank=True)
    ordine = models.PositiveSmallIntegerField(default=0)
    modificato_il = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "sezione della proposta"
        verbose_name_plural = "sezioni della proposta"
        ordering = ["ordine", "pk"]

    def __str__(self):
        return self.titolo

    @property
    def caratteri(self):
        return len(self.testo)

    @property
    def troppo_lungo(self):
        return bool(self.massimo_caratteri) and self.caratteri > self.massimo_caratteri

    @property
    def elenco_domande(self):
        return [d.strip() for d in self.domande.splitlines() if d.strip()]


class Commento(models.Model):
    """Commento di discussione interna su un'idea o un progetto."""

    idea = models.ForeignKey(
        Idea, null=True, blank=True, on_delete=models.CASCADE, related_name="commenti"
    )
    progetto = models.ForeignKey(
        Progetto, null=True, blank=True, on_delete=models.CASCADE, related_name="commenti"
    )
    utente = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    testo = models.TextField()
    creato_il = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "commento"
        verbose_name_plural = "commenti"
        ordering = ["creato_il"]

    def __str__(self):
        return f"Commento di {self.utente}"


class Allegato(models.Model):
    """Documento allegato a un'idea o a un progetto (servito solo da viste con permessi)."""

    idea = models.ForeignKey(
        Idea, null=True, blank=True, on_delete=models.CASCADE, related_name="allegati"
    )
    progetto = models.ForeignKey(
        Progetto, null=True, blank=True, on_delete=models.CASCADE, related_name="allegati"
    )
    file = models.FileField(upload_to=_percorso_allegato, max_length=255)
    nome = models.CharField(max_length=255)
    descrizione = models.CharField(max_length=255, blank=True)
    caricato_il = models.DateTimeField(auto_now_add=True)
    caricato_da = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        verbose_name = "allegato"
        verbose_name_plural = "allegati"
        ordering = ["-caricato_il"]

    def __str__(self):
        return self.nome


class Imputazione(models.Model):
    """Movimento di prima nota attribuito al progetto (centro di costo); il movimento non cambia."""

    class Tipo(models.TextChoices):
        COSTO = "costo", "Costo del progetto"
        CONTRIBUTO = "contributo", "Contributo del finanziatore (anticipo o saldo)"
        ENTRATA = "entrata", "Altra entrata del progetto"

    movimento = models.OneToOneField(
        "tesoreria.Movimento", on_delete=models.PROTECT, related_name="imputazione_progetto"
    )
    progetto = models.ForeignKey(Progetto, on_delete=models.CASCADE, related_name="imputazioni")
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    voce = models.ForeignKey(
        VoceCosto, null=True, blank=True, on_delete=models.SET_NULL, related_name="imputazioni"
    )
    importo = models.DecimalField("importo imputato (€)", max_digits=12, decimal_places=2)
    nota = models.CharField(max_length=255, blank=True)
    creato_il = models.DateTimeField(auto_now_add=True)
    creato_da = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        verbose_name = "imputazione al progetto"
        verbose_name_plural = "imputazioni al progetto"
        ordering = ["movimento__data", "pk"]

    def __str__(self):
        return f"{self.movimento} → {self.progetto.codice}"


class OreVolontariato(models.Model):
    """Ore di volontariato prestate per il progetto (valorizzate con la tariffa del progetto)."""

    progetto = models.ForeignKey(Progetto, on_delete=models.CASCADE, related_name="ore")
    attivita = models.ForeignKey(
        Attivita,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ore",
        verbose_name="attività",
    )
    soggetto = models.ForeignKey(
        "anagrafica.Soggetto",
        on_delete=models.PROTECT,
        related_name="ore_volontariato",
        verbose_name="volontario",
    )
    data = models.DateField()
    ore = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.25")), MaxValueValidator(24)],
    )
    descrizione = models.CharField(max_length=255, blank=True)
    creato_da = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        verbose_name = "ore di volontariato"
        verbose_name_plural = "ore di volontariato"
        ordering = ["-data", "pk"]

    def __str__(self):
        return f"{self.soggetto}: {self.ore} ore il {self.data:%d/%m/%Y}"


class Variante(models.Model):
    """Variante al piano economico in esecuzione, con la delibera e i piani prima e dopo."""

    progetto = models.ForeignKey(Progetto, on_delete=models.CASCADE, related_name="varianti")
    descrizione = models.TextField()
    delibera = models.ForeignKey(
        "organi.Delibera", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    aperta_il = models.DateTimeField(auto_now_add=True)
    chiusa_il = models.DateTimeField(null=True, blank=True)
    utente = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    piano_prima = models.JSONField(default=dict)
    piano_dopo = models.JSONField(default=dict)

    class Meta:
        verbose_name = "variante"
        verbose_name_plural = "varianti"
        ordering = ["-aperta_il"]

    def __str__(self):
        return f"Variante del {self.aperta_il:%d/%m/%Y}"

    @property
    def aperta(self):
        return self.chiusa_il is None


class ConnettoreMCP(models.Model):
    """Impostazioni del connettore MCP (una riga): spento di norma."""

    attivo = models.BooleanField(default=False)
    commenti_ammessi = models.BooleanField(
        "commenti dell'assistente ammessi",
        default=False,
        help_text="I token con il permesso possono aggiungere commenti firmati «Assistente».",
    )
    modificato_il = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "connettore MCP"
        verbose_name_plural = "connettore MCP"
        permissions = [
            ("usa_mcp", "Creare token personali per il connettore MCP"),
            ("gestisci_mcp", "Attivare il connettore MCP"),
        ]

    def __str__(self):
        return "Connettore MCP"

    @classmethod
    def corrente(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class TokenMCP(models.Model):
    """Token personale per un client MCP: vale con i permessi dell'utente; nel database c'è solo
    l'impronta."""

    utente = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="token_mcp"
    )
    nome = models.CharField(max_length=100, help_text="Es. «Claude sul portatile».")
    prefisso = models.CharField(max_length=16, editable=False)
    impronta = models.CharField(max_length=64, unique=True, editable=False)
    commenti = models.BooleanField(
        "può aggiungere commenti", default=False, help_text="Solo se ammessi dall'amministratore."
    )
    creato_il = models.DateTimeField(auto_now_add=True)
    scade_il = models.DateField("scade il", null=True, blank=True)
    ultimo_uso = models.DateTimeField(null=True, blank=True, editable=False)
    revocato_il = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        verbose_name = "token MCP"
        verbose_name_plural = "token MCP"
        ordering = ["-creato_il"]

    def __str__(self):
        return f"{self.nome} ({self.prefisso}…)"

    @property
    def valido(self):
        from django.utils import timezone

        scaduto = self.scade_il is not None and self.scade_il < timezone.localdate()
        return self.revocato_il is None and not scaduto and self.utente.is_active
