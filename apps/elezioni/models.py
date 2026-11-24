# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Rinnovo degli organi a scadenza del mandato: profili elettorali (termini, regole
# *              delle liste, modalità di voto), procedure di rinnovo con le fasi, liste e
# *              candidati, esiti della votazione e ricorsi. Operazioni solo da elezioni.servizi.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.db import models
from django.urls import reverse

from apps.anagrafica.models import Soggetto
from apps.core.models import ModelloBase


class ProfiloElettorale(models.Model):
    """Regole di un rinnovo tradotte in configurazione: termini in giorni, composizione delle liste
    per soglia di soci, supplenti, deleghe e voto. I profili ANCR (sezione, federazione) e quello
    generico ETS sono preimpostati; ogni associazione può modificarli o crearne altri."""

    class Livello(models.TextChoices):
        SEZIONE = "sezione", "Sezione (congresso dei soci)"
        FEDERAZIONE = "federazione", "Federazione (congresso dei presidenti di sezione)"
        ASSOCIAZIONE = "associazione", "Associazione (assemblea dei soci)"

    nome = models.CharField(max_length=120, unique=True)
    livello = models.CharField(max_length=12, choices=Livello.choices)
    riferimento = models.CharField(
        "riferimento normativo", max_length=300, blank=True,
        help_text="Es. Statuto artt. 46-47, Regolamento applicativo art. 22.",
    )  # fmt: skip
    nome_assemblea = models.CharField(
        "nome dell'assemblea elettiva", max_length=100, default="Congresso sezionale"
    )
    durata_mandato = models.PositiveSmallIntegerField("durata del mandato (anni)", default=4)
    # termini (giorni)
    giorni_indizione = models.PositiveSmallIntegerField(
        "indizione: giorni prima della scadenza", default=60,
        help_text="Il consiglio uscente indice l'assemblea almeno tanti giorni prima.",
    )  # fmt: skip
    giorni_avviso = models.PositiveSmallIntegerField(
        "avviso: giorni prima dell'assemblea", default=8
    )
    giorni_liste = models.PositiveSmallIntegerField(
        "liste: giorni prima dell'assemblea", default=15,
        help_text="Termine per presentare le liste dei candidati.",
    )  # fmt: skip
    giorni_ricorsi = models.PositiveSmallIntegerField("ricorsi: giorni dopo il voto", default=15)
    organo_ricorsi = models.CharField(
        "a chi si ricorre", max_length=150, blank=True, default="Consiglio direttivo provinciale"
    )
    giorni_trasmissione = models.PositiveSmallIntegerField(
        "trasmissione dei verbali: giorni dopo il voto", default=10
    )
    destinatario_verbali = models.CharField(
        "a chi si trasmettono i verbali", max_length=150, blank=True,
        default="Federazione provinciale",
    )  # fmt: skip
    giorni_consegne = models.PositiveSmallIntegerField(
        "passaggio di consegne: giorni dopo il voto", default=10
    )
    ore_seconda_convocazione = models.PositiveSmallIntegerField(
        "seconda convocazione: ore dopo la prima (almeno)", default=1
    )
    ore_votazione = models.PositiveSmallIntegerField(
        "durata massima delle operazioni di voto (ore)", default=3
    )
    # liste
    soglia_soci = models.PositiveIntegerField(
        "soglia di soci", default=100,
        help_text="La composizione delle liste cambia oltre questo numero di soci.",
    )  # fmt: skip
    consiglieri_sotto_min = models.PositiveSmallIntegerField(
        "consiglieri fino alla soglia (minimo)", default=0
    )
    consiglieri_sotto_max = models.PositiveSmallIntegerField(
        "consiglieri fino alla soglia (massimo)", default=0
    )
    sindaci_sotto_min = models.PositiveSmallIntegerField(
        "sindaci fino alla soglia (minimo)", default=1
    )
    sindaci_sotto_max = models.PositiveSmallIntegerField(
        "sindaci fino alla soglia (massimo)", default=1
    )
    garanti_sotto = models.PositiveSmallIntegerField("garanti fino alla soglia", default=0)
    consiglieri_sopra = models.PositiveSmallIntegerField("consiglieri oltre la soglia", default=4)
    sindaci_sopra_min = models.PositiveSmallIntegerField(
        "sindaci oltre la soglia (minimo)", default=1,
        help_text="Il Regolamento ammette meno di tre sindaci se è difficile trovarli.",
    )  # fmt: skip
    sindaci_sopra_max = models.PositiveSmallIntegerField(
        "sindaci oltre la soglia (massimo)", default=3
    )
    garanti_sopra = models.PositiveSmallIntegerField("garanti oltre la soglia", default=3)
    seconda_soglia = models.PositiveIntegerField(
        "seconda soglia di soci", null=True, blank=True,
        help_text="Oltre questa, un consigliere in più ogni «soci per consigliere» (federazione).",
    )  # fmt: skip
    soci_per_consigliere = models.PositiveIntegerField("soci per consigliere in più", default=100)
    consiglieri_massimo = models.PositiveSmallIntegerField("consiglieri al massimo", default=10)
    supplenti_max = models.PositiveSmallIntegerField("supplenti (al massimo)", default=4)
    dichiarazione_requisiti = models.BooleanField(
        "dichiarazione dei requisiti dei candidati", default=False,
        help_text="Allegata alla lista (artt. 5 e 7 dello Statuto, per la federazione).",
    )  # fmt: skip
    # voto
    max_deleghe = models.PositiveSmallIntegerField("deleghe per votante", default=2)
    voto_ponderato = models.BooleanField(
        "voto ponderato per sezione", default=False,
        help_text="Ogni sezione vota con tanti voti quanti i suoi soci (congresso provinciale).",
    )  # fmt: skip
    alzata_di_mano_lista_unica = models.BooleanField(
        "con una sola lista si vota per alzata di mano", default=True
    )
    sospende_tesseramento = models.BooleanField(
        "tesseramento sospeso dalla convocazione al voto", default=True,
        help_text="Il programma non blocca: segnala chi si iscrive dopo l'avviso (non vota).",
    )  # fmt: skip
    modelli = models.CharField(
        "modelli dei verbali", max_length=20, default="ancr_sezione",
        help_text="ancr_sezione (B2, C2, C3, D2, D4, G1), ancr_federazione (B1, C1, D1, D3, G) "
        "o generico.",
    )  # fmt: skip
    attivo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "profilo elettorale"
        verbose_name_plural = "profili elettorali"
        ordering = ["livello", "nome"]

    def __str__(self):
        return self.nome


class Rinnovo(ModelloBase):
    """Procedura di rinnovo degli organi di una sezione o dell'ente (federazione)."""

    class Fase(models.TextChoices):
        PREPARAZIONE = "preparazione", "In preparazione"
        INDETTO = "indetto", "Indetto"
        CONVOCATO = "convocato", "Convocato"
        LISTE = "liste", "Liste esaminate"
        VOTATO = "votato", "Votato"
        PROCLAMATO = "proclamato", "Eletti proclamati"
        INSEDIATO = "insediato", "Nuovi organi insediati"
        CONCLUSO = "concluso", "Concluso"
        ANNULLATO = "annullato", "Annullato"

    profilo = models.ForeignKey(ProfiloElettorale, on_delete=models.PROTECT, related_name="+")
    sezione = models.ForeignKey(
        "soci.Sezione", null=True, blank=True, on_delete=models.PROTECT, related_name="rinnovi",
        help_text="Vuota: gli organi dell'ente (federazione o associazione).",
    )  # fmt: skip
    fase = models.CharField(max_length=12, choices=Fase.choices, default=Fase.PREPARAZIONE)
    quadriennio = models.CharField("mandato", max_length=20, help_text="Es. 2027-2031.")
    scadenza = models.DateField("scadenza del mandato uscente", null=True, blank=True)
    # indizione e convocazione
    indetto_il = models.DateField("indetto il", null=True, blank=True)
    delibera_indizione = models.CharField(
        "atto di indizione", max_length=200, blank=True,
        help_text="Es. delibera del consiglio direttivo del 10/01/2027.",
    )  # fmt: skip
    data_assemblea = models.DateTimeField("prima convocazione", null=True, blank=True)
    seconda_convocazione = models.DateTimeField(null=True, blank=True)
    luogo = models.CharField(max_length=200, blank=True)
    seggio = models.CharField("sede del seggio", max_length=200, blank=True)
    apertura_seggio = models.TimeField("apertura delle operazioni di voto", null=True, blank=True)
    chiusura_seggio = models.TimeField("chiusura delle operazioni di voto", null=True, blank=True)
    ordine_del_giorno = models.TextField(blank=True)
    avviso_il = models.DateField("avviso di convocazione inviato il", null=True, blank=True)
    termine_liste = models.DateField("termine per le liste", null=True, blank=True)
    riunione = models.ForeignKey(
        "organi.Riunione", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    invio_avviso = models.ForeignKey(
        "comunicazioni.Invio", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    # aventi diritto fissati all'avviso: soci (sezione) o sezioni con i voti (federazione)
    soci_alla_soglia = models.PositiveIntegerField(
        "soci per la composizione delle liste", null=True, blank=True
    )
    aventi_diritto = models.JSONField(default=list, blank=True, editable=False)
    # assemblea e commissione elettorale
    presidente_assemblea = models.CharField(max_length=150, blank=True)
    segretario_assemblea = models.CharField(max_length=150, blank=True)
    commissione_presidente = models.CharField(
        "presidente della commissione elettorale", max_length=150, blank=True
    )
    commissione_segretario = models.CharField(
        "segretario della commissione", max_length=150, blank=True
    )
    commissione_componenti = models.TextField(
        "componenti e scrutatori", blank=True, help_text="Uno per riga."
    )
    # esiti
    votato_il = models.DateField("giorno del voto", null=True, blank=True)
    voto_aperto = models.TimeField("votazione aperta alle", null=True, blank=True)
    voto_chiuso = models.TimeField("votazione chiusa alle", null=True, blank=True)
    scrutinio_ore = models.TimeField("scrutinio iniziato alle", null=True, blank=True)
    alzata_di_mano = models.BooleanField(default=False)
    presenti = models.PositiveIntegerField("votanti presenti", default=0)
    deleghe = models.PositiveIntegerField("voti per delega", default=0)
    schede_votate = models.PositiveIntegerField(default=0)
    schede_bianche = models.PositiveIntegerField(default=0)
    schede_nulle = models.PositiveIntegerField(default=0)
    non_partecipanti = models.TextField(
        "sezioni che non hanno votato", blank=True, help_text="Congresso provinciale."
    )
    note_votazione = models.TextField(blank=True)
    lista_eletta = models.ForeignKey(
        "Lista", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    proclamato_il = models.DateTimeField("proclamazione", null=True, blank=True)
    # dopo il voto
    insediato_il = models.DateField("insediamento dei nuovi organi", null=True, blank=True)
    trasmesso_il = models.DateField("verbali trasmessi il", null=True, blank=True)
    protocollo_trasmissione = models.ForeignKey(
        "protocollo.Protocollo", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    ratificato_il = models.DateField(
        "esiti ratificati il", null=True, blank=True,
        help_text="Comunicazione di validazione della Commissione nazionale verifica soci.",
    )  # fmt: skip
    consegne = models.JSONField(
        "passaggio di consegne", default=dict, blank=True,
        help_text="Dati del verbale di consegna (G/G1).",
    )  # fmt: skip
    consegne_il = models.DateField("passaggio di consegne il", null=True, blank=True)
    motivo_annullamento = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "rinnovo degli organi"
        verbose_name_plural = "rinnovi degli organi"
        ordering = ["-creato_il"]
        permissions = [
            ("gestisci_rinnovi", "Può condurre il rinnovo degli organi (liste, esiti, nomine)")
        ]

    def __str__(self):
        return f"Rinnovo {self.quadriennio} · {self.ente}"

    def get_absolute_url(self):
        return reverse("elezioni:rinnovo", args=[self.pk])

    @property
    def ente(self):
        if self.sezione_id:
            return f"Sezione di {self.sezione.nome}"
        from apps.core.models import Organizzazione

        return Organizzazione.corrente().denominazione

    @property
    def federazione(self):
        return self.profilo.livello == ProfiloElettorale.Livello.FEDERAZIONE

    @property
    def aperto(self):
        return self.fase not in (self.Fase.CONCLUSO, self.Fase.ANNULLATO)


class Lista(ModelloBase):
    """Lista dei candidati: si compila, si presenta, si ammette o si esclude, prende voti."""

    class Stato(models.TextChoices):
        BOZZA = "bozza", "In compilazione"
        PRESENTATA = "presentata", "Presentata"
        AMMESSA = "ammessa", "Ammessa"
        ESCLUSA = "esclusa", "Esclusa"
        RITIRATA = "ritirata", "Ritirata"

    rinnovo = models.ForeignKey(Rinnovo, on_delete=models.CASCADE, related_name="liste")
    numero = models.PositiveSmallIntegerField(
        null=True, blank=True, editable=False, help_text="Ordine di presentazione."
    )
    motto = models.CharField(
        "denominazione o motto", max_length=150, blank=True,
        help_text="Facoltativo; sulla scheda la lista si riconosce dal candidato presidente.",
    )  # fmt: skip
    presentatore = models.CharField(
        "presentata da", max_length=150, blank=True, help_text="Di norma il candidato presidente."
    )
    stato = models.CharField(max_length=10, choices=Stato.choices, default=Stato.BOZZA)
    presentata_il = models.DateTimeField(null=True, blank=True)
    protocollo = models.ForeignKey(
        "protocollo.Protocollo", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    motivo_esclusione = models.TextField(blank=True)
    esaminata_il = models.DateField(null=True, blank=True)
    programma = models.TextField(blank=True, help_text="Facoltativo: il programma della lista.")
    voti = models.PositiveIntegerField(default=0)
    modulo_firmato = models.FileField(
        upload_to="elezioni/liste/", max_length=255, blank=True, editable=False
    )

    class Meta:
        verbose_name = "lista"
        verbose_name_plural = "liste"
        ordering = ["rinnovo", models.F("numero").asc(nulls_last=True), "creato_il"]

    def __str__(self):
        capolista = self.capolista
        nome = capolista.soggetto.nome_completo if capolista else "(senza candidato presidente)"
        numero = f"Lista n. {self.numero}" if self.numero else "Lista"
        return f"{numero} - {nome}"

    def get_absolute_url(self):
        return reverse("elezioni:lista", args=[self.pk])

    @property
    def capolista(self):
        return next((c for c in self.candidati.all() if c.incarico == "presidente"), None)

    @property
    def in_gara(self):
        return self.stato == self.Stato.AMMESSA


class Candidato(models.Model):
    class Incarico(models.TextChoices):
        PRESIDENTE = "presidente", "Presidente"
        VICEPRESIDENTE = "vicepresidente", "Vicepresidente"
        SEGRETARIO = "segretario", "Segretario"
        CONSIGLIERE = "consigliere", "Consigliere"
        SINDACO = "sindaco", "Sindaco (organo di controllo)"
        GARANTE = "garante", "Garante"
        SUPPLENTE = "supplente", "Supplente"

    lista = models.ForeignKey(Lista, on_delete=models.CASCADE, related_name="candidati")
    soggetto = models.ForeignKey(
        Soggetto, on_delete=models.PROTECT, related_name="+", verbose_name="candidato",
        limit_choices_to={"tipo": "persona"},
    )  # fmt: skip
    incarico = models.CharField(max_length=15, choices=Incarico.choices)
    ordine = models.PositiveSmallIntegerField(default=0)
    accettazione = models.BooleanField(
        "accettazione firmata", default=False,
        help_text="Il candidato ha firmato l'accettazione della carica (e la dichiarazione).",
    )  # fmt: skip
    rinuncia = models.BooleanField(
        "non accetta la carica", default=False,
        help_text="Dichiarazione scritta entro la prima riunione del nuovo consiglio.",
    )  # fmt: skip

    class Meta:
        verbose_name = "candidato"
        verbose_name_plural = "candidati"
        ordering = ["lista", "ordine", "id"]
        constraints = [
            models.UniqueConstraint(fields=["lista", "soggetto"], name="candidato_unico_in_lista")
        ]

    def __str__(self):
        return f"{self.get_incarico_display()}: {self.soggetto.nome_completo}"


class Ricorso(ModelloBase):
    """Ricorso sulle operazioni elettorali (entro i giorni del profilo dal voto)."""

    class Esito(models.TextChoices):
        PENDENTE = "pendente", "In attesa di decisione"
        RESPINTO = "respinto", "Respinto"
        ACCOLTO = "accolto", "Accolto"

    rinnovo = models.ForeignKey(Rinnovo, on_delete=models.CASCADE, related_name="ricorsi")
    presentato_il = models.DateField()
    presentato_da = models.CharField(max_length=200)
    motivi = models.TextField()
    esito = models.CharField(max_length=10, choices=Esito.choices, default=Esito.PENDENTE)
    decisione = models.TextField(blank=True)
    deciso_il = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = "ricorso"
        verbose_name_plural = "ricorsi"
        ordering = ["presentato_il"]

    def __str__(self):
        return f"Ricorso di {self.presentato_da} del {self.presentato_il:%d/%m/%Y}"
