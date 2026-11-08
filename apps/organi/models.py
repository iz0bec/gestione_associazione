# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Modelli degli organi sociali: organi, cariche con storico, riunioni con
# *              convocazioni e ordine del giorno, presenze e deleghe, verbali e delibere.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from datetime import date

from django.conf import settings
from django.core.validators import MaxValueValidator
from django.db import models
from django.db.models import Q
from django.urls import reverse

from apps.anagrafica.models import Soggetto
from apps.core.models import ModelloBase


class Organo(models.Model):
    """Organo dell'associazione con le regole di validità delle riunioni."""

    class Tipo(models.TextChoices):
        ASSEMBLEA = "assemblea", "Assemblea dei soci"
        CONSIGLIO = "consiglio", "Organo di amministrazione"
        CONTROLLO = "controllo", "Organo di controllo"
        ALTRO = "altro", "Altro"

    nome = models.CharField(max_length=100, unique=True)
    sigla = models.CharField(max_length=10, help_text="Usata nei numeri, es. CD, ASS.")
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    quorum_prima = models.PositiveSmallIntegerField(
        "quorum in prima convocazione (%)",
        default=50,
        validators=[MaxValueValidator(100)],
        help_text="Presenti (con deleghe) oltre questa percentuale degli aventi diritto. "
        "50 = più della metà.",
    )
    quorum_seconda = models.PositiveSmallIntegerField(
        "quorum in seconda convocazione (%)",
        default=0,
        validators=[MaxValueValidator(100)],
        help_text="0 = valida qualunque sia il numero dei presenti.",
    )
    max_deleghe = models.PositiveSmallIntegerField(
        "deleghe per persona",
        default=0,
        help_text="Deleghe che un presente può ricevere (0 = deleghe non ammesse).",
    )
    solo_soci_in_regola = models.BooleanField(
        "votano solo i soci in regola con la quota",
        default=True,
        help_text="Per l'assemblea dei soci.",
    )
    ordine = models.PositiveSmallIntegerField(default=0)
    attivo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "organo"
        verbose_name_plural = "organi"
        ordering = ["ordine", "nome"]
        permissions = [("gestisci_cariche", "Può registrare nomine e cessazioni dalle cariche")]

    def __str__(self):
        return self.nome

    def get_absolute_url(self):
        return reverse("organi:organo", args=[self.pk])

    @property
    def e_assemblea(self):
        return self.tipo == self.Tipo.ASSEMBLEA

    def cariche_al(self, giorno=None):
        giorno = giorno or date.today()
        return self.cariche.filter(Q(al__isnull=True) | Q(al__gte=giorno), dal__lte=giorno)


def cariche_di(soggetto):
    """Cariche di una persona: prima quelle in corso, poi le concluse (più recenti prima)."""
    cariche = list(soggetto.cariche.select_related("organo").order_by("-dal"))
    return sorted(cariche, key=lambda c: not c.in_carica)


class Carica(ModelloBase):
    """Incarico di una persona in un organo, con data di inizio e (eventuale) fine."""

    class Ruolo(models.TextChoices):
        PRESIDENTE = "presidente", "Presidente"
        VICEPRESIDENTE = "vicepresidente", "Vicepresidente"
        SEGRETARIO = "segretario", "Segretario"
        TESORIERE = "tesoriere", "Tesoriere"
        CONSIGLIERE = "consigliere", "Consigliere"
        PRESIDENTE_CONTROLLO = "presidente_controllo", "Presidente dell'organo di controllo"
        COMPONENTE = "componente", "Componente"
        SUPPLENTE = "supplente", "Supplente"

    organo = models.ForeignKey(Organo, on_delete=models.PROTECT, related_name="cariche")
    soggetto = models.ForeignKey(
        Soggetto,
        on_delete=models.PROTECT,
        related_name="cariche",
        limit_choices_to={"tipo": "persona"},
        verbose_name="persona",
    )
    ruolo = models.CharField(max_length=20, choices=Ruolo.choices)
    dal = models.DateField()
    al = models.DateField(null=True, blank=True, help_text="Vuoto = in carica.")
    nomina = models.CharField(
        "atto di nomina", max_length=200, blank=True, help_text="Es. assemblea del 20/04/2026."
    )
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "carica"
        verbose_name_plural = "cariche"
        ordering = ["organo__ordine", "-al", "ruolo", "soggetto__cognome"]
        constraints = [
            models.CheckConstraint(
                condition=Q(al__isnull=True) | Q(al__gte=models.F("dal")),
                name="carica_date_coerenti",
            )
        ]

    def __str__(self):
        return f"{self.get_ruolo_display()} - {self.soggetto.nome_completo}"

    @property
    def in_carica(self):
        return self.al is None or self.al >= date.today()

    @property
    def vota(self):
        return self.ruolo != self.Ruolo.SUPPLENTE


class Riunione(ModelloBase):
    class Stato(models.TextChoices):
        BOZZA = "bozza", "In preparazione"
        CONVOCATA = "convocata", "Convocata"
        VERBALIZZATA = "verbalizzata", "Verbale chiuso"
        ANNULLATA = "annullata", "Annullata"

    class Modalita(models.TextChoices):
        PRESENZA = "presenza", "In presenza"
        MISTA = "mista", "In presenza e in collegamento"
        REMOTO = "remoto", "In videoconferenza"

    organo = models.ForeignKey(Organo, on_delete=models.PROTECT, related_name="riunioni")
    straordinaria = models.BooleanField(default=False)
    anno = models.PositiveIntegerField(editable=False)
    numero = models.PositiveIntegerField(null=True, blank=True, editable=False)
    prima_convocazione = models.DateTimeField("prima convocazione")
    luogo = models.CharField(max_length=200)
    seconda_convocazione = models.DateTimeField("seconda convocazione", null=True, blank=True)
    luogo_seconda = models.CharField(
        "luogo della seconda convocazione",
        max_length=200,
        blank=True,
        help_text="Vuoto = stesso luogo.",
    )
    modalita = models.CharField(max_length=10, choices=Modalita.choices, default=Modalita.PRESENZA)
    collegamento = models.CharField(
        "istruzioni di collegamento", max_length=500, blank=True, help_text="Link o istruzioni."
    )
    data_convocazione = models.DateField("data della convocazione", null=True, blank=True)
    premessa = models.TextField(
        "testo della convocazione",
        blank=True,
        help_text="Riportato nella lettera prima dell'ordine del giorno.",
    )
    stato = models.CharField(
        max_length=12, choices=Stato.choices, default=Stato.BOZZA, db_index=True
    )
    motivo_annullamento = models.CharField(max_length=255, blank=True)
    protocollo_convocazione = models.ForeignKey(
        "protocollo.Protocollo", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        verbose_name = "riunione"
        verbose_name_plural = "riunioni"
        ordering = ["-prima_convocazione"]
        permissions = [
            ("convoca_riunione", "Può convocare e annullare le riunioni"),
            ("verbalizza", "Può redigere e chiudere i verbali"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["organo", "anno", "numero"], name="riunione_numero_unico"
            )
        ]

    def __str__(self):
        return f"{self.titolo} del {self.prima_convocazione:%d/%m/%Y}"

    def get_absolute_url(self):
        return reverse("organi:riunione", args=[self.pk])

    @property
    def titolo(self):
        tipo = "straordinaria" if self.straordinaria else ""
        n = f" n. {self.numero}/{self.anno}" if self.numero else ""
        return f"{self.organo}{' ' + tipo if tipo else ''}{n}".strip()

    @property
    def modificabile(self):
        return self.stato in (self.Stato.BOZZA, self.Stato.CONVOCATA)


class PuntoOdg(models.Model):
    riunione = models.ForeignKey(Riunione, on_delete=models.CASCADE, related_name="punti")
    ordine = models.PositiveSmallIntegerField()
    titolo = models.CharField(max_length=500)
    discussione = models.TextField(blank=True, help_text="Sintesi della discussione (verbale).")

    class Meta:
        verbose_name = "punto all'ordine del giorno"
        verbose_name_plural = "ordine del giorno"
        ordering = ["riunione", "ordine"]
        constraints = [
            models.UniqueConstraint(fields=["riunione", "ordine"], name="punto_ordine_unico")
        ]

    def __str__(self):
        return f"{self.ordine}. {self.titolo}"


class Presenza(models.Model):
    """Avente diritto alla riunione (elenco fissato all'apertura delle presenze)."""

    class Stato(models.TextChoices):
        PRESENTE = "presente", "Presente"
        COLLEGATO = "collegato", "In collegamento"
        DELEGA = "delega", "Rappresentato per delega"
        GIUSTIFICATO = "giustificato", "Assente giustificato"
        ASSENTE = "assente", "Assente"

    riunione = models.ForeignKey(Riunione, on_delete=models.CASCADE, related_name="presenze")
    soggetto = models.ForeignKey(Soggetto, on_delete=models.PROTECT, related_name="+")
    descrizione = models.CharField(max_length=200)
    qualifica = models.CharField(max_length=100, blank=True)
    vota = models.BooleanField(default=True)
    stato = models.CharField(max_length=12, choices=Stato.choices, default=Stato.ASSENTE)
    delegato = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="deleghe_ricevute",
        verbose_name="delegato",
    )

    class Meta:
        verbose_name = "presenza"
        verbose_name_plural = "presenze"
        ordering = ["riunione", "descrizione"]
        constraints = [
            models.UniqueConstraint(fields=["riunione", "soggetto"], name="presenza_unica")
        ]

    def __str__(self):
        return self.descrizione

    @property
    def intervenuto(self):
        return self.stato in (self.Stato.PRESENTE, self.Stato.COLLEGATO)


class Verbale(ModelloBase):
    """Verbale di una riunione. Chiuso, riceve il numero del libro e non si modifica più."""

    class Convocazione(models.TextChoices):
        PRIMA = "prima", "Prima convocazione"
        SECONDA = "seconda", "Seconda convocazione"

    riunione = models.OneToOneField(Riunione, on_delete=models.PROTECT, related_name="verbale")
    convocazione = models.CharField(
        max_length=8, choices=Convocazione.choices, default=Convocazione.PRIMA
    )
    inizio = models.DateTimeField("apertura della seduta", null=True, blank=True)
    fine = models.DateTimeField("chiusura della seduta", null=True, blank=True)
    luogo = models.CharField(max_length=200, blank=True)
    presidente = models.CharField("presidente della seduta", max_length=150, blank=True)
    segretario = models.CharField("segretario verbalizzante", max_length=150, blank=True)
    altri_presenti = models.TextField(
        "altri intervenuti", blank=True, help_text="Ospiti o invitati senza diritto di voto."
    )
    apertura = models.TextField(
        "constatazioni iniziali",
        blank=True,
        help_text="Es. verifica della validità della seduta, nomina del segretario.",
    )
    varie = models.TextField("varie ed eventuali", blank=True)
    chiuso = models.BooleanField(default=False, editable=False)
    numero = models.PositiveIntegerField("numero nel libro dei verbali", null=True, editable=False)
    chiuso_il = models.DateTimeField(null=True, blank=True, editable=False)
    chiuso_da = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    file = models.FileField(upload_to="organi/verbali/", max_length=255, blank=True, editable=False)
    impronta = models.CharField(max_length=64, blank=True, editable=False)
    presenti = models.PositiveIntegerField(default=0, editable=False)
    rappresentati = models.PositiveIntegerField(default=0, editable=False)
    aventi_diritto = models.PositiveIntegerField(default=0, editable=False)
    protocollo = models.ForeignKey(
        "protocollo.Protocollo", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        verbose_name = "verbale"
        verbose_name_plural = "verbali"
        ordering = ["-riunione__prima_convocazione"]

    def __str__(self):
        n = f"n. {self.numero} " if self.numero else ""
        return f"Verbale {n}- {self.riunione}"

    def get_absolute_url(self):
        return reverse("organi:verbale", args=[self.riunione_id])


class Delibera(models.Model):
    class Esito(models.TextChoices):
        APPROVATA = "approvata", "Approvata"
        RESPINTA = "respinta", "Respinta"
        RINVIATA = "rinviata", "Rinviata"

    class Votazione(models.TextChoices):
        PALESE = "palese", "Palese"
        SEGRETA = "segreta", "Segreta"
        ACCLAMAZIONE = "acclamazione", "Per acclamazione"

    verbale = models.ForeignKey(Verbale, on_delete=models.PROTECT, related_name="delibere")
    punto = models.ForeignKey(
        PuntoOdg, null=True, blank=True, on_delete=models.SET_NULL, related_name="delibere"
    )
    oggetto = models.CharField(max_length=300)
    testo = models.TextField("dispositivo", help_text="Il testo di ciò che si delibera.")
    votazione = models.CharField(max_length=12, choices=Votazione.choices, default=Votazione.PALESE)
    favorevoli = models.PositiveIntegerField(default=0)
    contrari = models.PositiveIntegerField(default=0)
    astenuti = models.PositiveIntegerField(default=0)
    unanimita = models.BooleanField("all'unanimità", default=False)
    esito = models.CharField(max_length=10, choices=Esito.choices, default=Esito.APPROVATA)
    anno = models.PositiveIntegerField(null=True, editable=False)
    numero = models.PositiveIntegerField(null=True, editable=False)

    class Meta:
        verbose_name = "delibera"
        verbose_name_plural = "delibere"
        ordering = ["-anno", "-numero", "id"]

    def __str__(self):
        n = f"n. {self.numero}/{self.anno} " if self.numero else ""
        return f"Delibera {n}{self.oggetto}"

    @property
    def codice(self):
        if not self.numero:
            return ""
        return f"{self.verbale.riunione.organo.sigla} {self.numero}/{self.anno}"
