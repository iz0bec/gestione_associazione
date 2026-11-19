# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Modelli dell'API di interoperabilità (ADR-030): identità dell'istanza e sue
# *              chiavi, controparti (installazioni e integrazioni), inviti di abbinamento,
# *              nonce già visti e registro delle chiamate.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

AMBITI = {
    "eventi:lettura": "Eventi: lettura",
    "adesioni:lettura": "Adesioni agli eventi: lettura",
    "adesioni:scrittura": "Adesioni agli eventi: scrittura",
    "sezioni:lettura": "Sezioni: lettura",
    "soci:lettura": "Soci e tessere: lettura (dati personali)",
    "lotti:lettura": "Lotti di tessere: lettura",
    "domande:scrittura": "Domande di iscrizione: invio",
    "consegne:scrittura": "Consegna dei cambiamenti (modalità a spinta)",
    "contatti:scrittura": "Messaggi del modulo contatti: invio",
    "documenti:lettura": "Documenti pubblici: lettura",
    "organigramma:lettura": "Organigramma pubblico: lettura",
    "tessere:verifica": "Verifica di una tessera",
    "tessere:scambio": "Ciclo delle tessere: richieste, consegne, ricevute (federazione e sezioni)",
}
AMBITI_DATI_PERSONALI = {"soci:lettura"}


class Istanza(models.Model):
    """Identità di questa installazione (una sola riga). Non dipende da host o indirizzo IP."""

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    creata_il = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "identità dell'istanza"
        verbose_name_plural = "identità dell'istanza"

    def __str__(self):
        return str(self.uuid)


class ChiaveIstanza(models.Model):
    """Coppia di chiavi dell'istanza: Ed25519 per firmare, X25519 per ricevere dati cifrati.
    La privata è cifrata con CHIAVE_CIFRATURA. Una chiave ritirata resta pubblicata fino a
    `valida_fino` (sovrapposizione durante la rotazione)."""

    class Uso(models.TextChoices):
        FIRMA = "sig", "Firma (Ed25519)"
        CIFRATURA = "enc", "Cifratura (X25519)"

    kid = models.CharField(max_length=64, unique=True)
    uso = models.CharField(max_length=3, choices=Uso.choices)
    pubblica = models.CharField(max_length=64)
    privata = models.TextField(blank=True)  # cifrata; vuota dopo la fine della sovrapposizione
    creata_il = models.DateTimeField(auto_now_add=True)
    ritirata_il = models.DateTimeField(null=True, blank=True)
    valida_fino = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "chiave dell'istanza"
        verbose_name_plural = "chiavi dell'istanza"
        ordering = ["-creata_il"]

    def __str__(self):
        return f"{self.get_uso_display()} {self.kid}"


class ClienteApi(models.Model):
    """Controparte dell'API: un'altra installazione o un'integrazione esterna."""

    class Tipo(models.TextChoices):
        INSTALLAZIONE = "installazione", "Installazione di Gestione Associazione"
        INTEGRAZIONE = "integrazione", "Integrazione esterna (sito, app, gestionale)"

    class Stato(models.TextChoices):
        IN_PROVA = "in_prova", "In prova"
        ATTIVA = "attiva", "Attiva"
        SOSPESA = "sospesa", "Sospesa"
        REVOCATA = "revocata", "Revocata"

    class VerificaTls(models.TextChoices):
        PUBBLICA = "pubblica", "Autorità di certificazione del sistema"
        CA_INTERNA = "ca_interna", "Autorità di certificazione interna (PEM)"
        IMPRONTA = "impronta", "Impronta della chiave del certificato (SPKI)"

    class Origine(models.TextChoices):
        INVITO_NOSTRO = "invito_nostro", "Ha usato un nostro invito"
        INVITO_LORO = "invito_loro", "Abbiamo usato un suo invito"

    class Ruolo(models.TextChoices):
        PARI = "pari", "Installazione pari o integrazione"
        FEDERAZIONE = "federazione", "È la nostra federazione"
        SEZIONE = "sezione", "È una nostra sezione"

    nome = models.CharField(max_length=150)
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    ruolo = models.CharField(
        max_length=12, choices=Ruolo.choices, default=Ruolo.PARI,
        help_text="Per il ciclo delle tessere e lo scambio dei soci fra federazione e sezioni.",
    )  # fmt: skip
    sezione = models.ForeignKey(
        "soci.Sezione", null=True, blank=True, on_delete=models.PROTECT, related_name="+",
        help_text="Se è una nostra sezione: quale, nel nostro elenco delle sezioni.",
    )  # fmt: skip
    stato = models.CharField(max_length=10, choices=Stato.choices, default=Stato.IN_PROVA)
    origine = models.CharField(max_length=15, choices=Origine.choices)
    istanza = models.UUIDField("UUID della controparte", null=True, blank=True)
    nome_dichiarato = models.CharField(max_length=255, blank=True)
    jwks = models.JSONField(default=dict, blank=True)
    impronta = models.CharField(max_length=64, blank=True)
    ambiti = models.JSONField(default=list, blank=True)
    ip_ammessi = models.TextField(
        "indirizzi IP ammessi",
        blank=True,
        help_text="Uno per riga, anche reti (192.168.0.0/24). Vuoto: nessun limite. "
        "È un controllo in più: l'identità è data dalla firma.",
    )
    scade_il = models.DateField(
        "scadenza", null=True, blank=True, help_text="Dopo questa data la controparte è sospesa."
    )
    indirizzo_pubblico = models.URLField(
        blank=True, help_text="Indirizzo pubblico (solo https), es. https://gestionale.example.org"
    )
    indirizzo_interno = models.URLField(
        blank=True,
        help_text="Indirizzo in rete interna, usato per primo. Es. https://192.168.0.34:8003",
    )
    rete_interna = models.BooleanField(
        "rete interna",
        default=False,
        help_text="La controparte sta nella nostra rete: ammette indirizzi privati.",
    )
    verifica_tls = models.CharField(
        "verifica del certificato (indirizzo interno)",
        max_length=12,
        choices=VerificaTls.choices,
        default=VerificaTls.PUBBLICA,
    )
    ca_pem = models.TextField("certificato della CA interna (PEM)", blank=True)
    tls_spki = models.JSONField("impronte SPKI ammesse", default=list, blank=True)
    http_in_chiaro = models.BooleanField(
        "consenti http in chiaro",
        default=False,
        help_text="Solo indirizzo interno privato e rete interna. Sconsigliato: preferire HTTPS.",
    )
    indirizzo_notifiche = models.URLField(
        blank=True, help_text="Dove inviare l'avviso dei cambiamenti (CloudEvent firmato)."
    )
    notifiche_flussi = models.JSONField(
        "flussi notificati", default=list, blank=True,
        help_text="Flussi di cui avvisare la controparte a ogni cambiamento.",
    )  # fmt: skip
    note = models.TextField(blank=True)
    creata_il = models.DateTimeField(auto_now_add=True)
    abbinata_il = models.DateTimeField(null=True, blank=True)
    attivata_il = models.DateTimeField(null=True, blank=True)
    attivata_da = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    ultima_chiamata_il = models.DateTimeField(null=True, blank=True)
    ultima_prova_il = models.DateTimeField(null=True, blank=True)
    ultimo_esito_prova = models.TextField(blank=True)

    class Meta:
        verbose_name = "controparte dell'API"
        verbose_name_plural = "controparti dell'API"
        ordering = ["nome"]
        permissions = [("gestisci_controparti", "Gestire le controparti dell'API")]
        constraints = [
            models.UniqueConstraint(
                fields=["istanza"],
                condition=Q(istanza__isnull=False) & ~Q(stato="revocata"),
                name="api_controparte_istanza_unica",
            )
        ]

    def __str__(self):
        return self.nome

    @property
    def abbinata(self):
        return bool(self.istanza and self.jwks)

    def chiavi(self, uso):
        return [k for k in (self.jwks or {}).get("keys", []) if k.get("use") == uso]


class InvitoAbbinamento(models.Model):
    """Invito monouso: si conserva solo l'impronta del codice."""

    cliente = models.ForeignKey(ClienteApi, on_delete=models.CASCADE, related_name="inviti")
    impronta_codice = models.CharField(max_length=64, unique=True)
    creato_il = models.DateTimeField(auto_now_add=True)
    creato_da = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    scade_il = models.DateTimeField()
    usato_il = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "invito di abbinamento"
        verbose_name_plural = "inviti di abbinamento"
        ordering = ["-creato_il"]

    def __str__(self):
        return f"Invito per {self.cliente}"


class NonceVisto(models.Model):
    """Nonce delle firme già ricevute (conservati 10 minuti: contro la ripetizione)."""

    kid = models.CharField(max_length=64)
    nonce = models.CharField(max_length=64)
    visto_il = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["kid", "nonce"], name="api_nonce_unico")]

    def __str__(self):
        return self.nonce


class ChiamataApi(models.Model):
    """Registro delle chiamate ricevute (conservato 90 giorni)."""

    momento = models.DateTimeField(auto_now_add=True, db_index=True)
    cliente = models.ForeignKey(
        ClienteApi, null=True, blank=True, on_delete=models.SET_NULL, related_name="chiamate"
    )
    metodo = models.CharField(max_length=10)
    percorso = models.CharField(max_length=255)
    stato = models.PositiveSmallIntegerField()
    codice = models.CharField(max_length=40, blank=True)
    indirizzo_ip = models.GenericIPAddressField(null=True, blank=True)
    durata_ms = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "chiamata all'API"
        verbose_name_plural = "chiamate all'API"
        ordering = ["-momento"]

    def __str__(self):
        return f"{self.metodo} {self.percorso} {self.stato}"


class Cambiamento(models.Model):
    """Voce del feed (ADR-030 §7): CloudEvent senza dati personali, progressivo senza buchi per
    flusso e catena di impronte. `contenuto` è il JSON canonico dell'evento senza ga_impronta."""

    flusso = models.CharField(max_length=80)
    progressivo = models.PositiveBigIntegerField()
    tipo = models.CharField(max_length=80)
    soggetto = models.UUIDField()
    risorsa = models.CharField(max_length=20)
    versione = models.PositiveIntegerField()
    momento = models.DateTimeField()
    precedente = models.CharField(max_length=64)
    impronta = models.CharField(max_length=64)
    contenuto = models.TextField()

    class Meta:
        verbose_name = "cambiamento"
        verbose_name_plural = "cambiamenti"
        ordering = ["flusso", "progressivo"]
        constraints = [
            models.UniqueConstraint(fields=["flusso", "progressivo"], name="api_feed_progressivo")
        ]
        indexes = [models.Index(fields=["momento"], name="api_feed_momento")]

    def __str__(self):
        return f"{self.flusso}:{self.progressivo} {self.tipo}"


class NotificaApi(models.Model):
    """Avviso di un cambiamento da consegnare a una controparte (ripetuto con attesa crescente;
    dopo l'ultimo tentativo resta visibile come fallito, mai scartato in silenzio)."""

    class Stato(models.TextChoices):
        IN_CODA = "in_coda", "In coda"
        CONSEGNATA = "consegnata", "Consegnata"
        FALLITA = "fallita", "Fallita"

    cliente = models.ForeignKey(ClienteApi, on_delete=models.CASCADE, related_name="notifiche")
    cambiamento = models.ForeignKey(Cambiamento, on_delete=models.CASCADE, related_name="+")
    stato = models.CharField(max_length=10, choices=Stato.choices, default=Stato.IN_CODA)
    tentativi = models.PositiveSmallIntegerField(default=0)
    prossimo_tentativo = models.DateTimeField(db_index=True)
    ultimo_errore = models.TextField(blank=True)
    consegnata_il = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "notifica"
        verbose_name_plural = "notifiche"
        ordering = ["prossimo_tentativo"]

    def __str__(self):
        return f"{self.cambiamento} → {self.cliente}"


class ChiaveIdempotenza(models.Model):
    """Scrittura già eseguita per (controparte, Idempotency-Key): stessa chiave e stesso
    contenuto restituiscono la stessa risposta, contenuto diverso è un errore (conservata 30
    giorni)."""

    cliente = models.ForeignKey(ClienteApi, on_delete=models.CASCADE, related_name="+")
    chiave = models.CharField(max_length=64)
    impronta = models.CharField(max_length=64)
    stato = models.PositiveSmallIntegerField()
    tipo = models.CharField(max_length=100)
    corpo = models.TextField()
    intestazioni = models.JSONField(default=dict)
    creata_il = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "chiave di idempotenza"
        verbose_name_plural = "chiavi di idempotenza"
        constraints = [
            models.UniqueConstraint(fields=["cliente", "chiave"], name="api_idempotenza_unica")
        ]

    def __str__(self):
        return self.chiave


class CursoreFlusso(models.Model):
    """Fin dove abbiamo letto un flusso di una controparte (progressivo e impronta, per la
    verifica della catena alla lettura successiva)."""

    cliente = models.ForeignKey(ClienteApi, on_delete=models.CASCADE, related_name="cursori")
    flusso = models.CharField(max_length=80)
    progressivo = models.PositiveBigIntegerField(default=0)
    impronta = models.CharField(max_length=64, blank=True)
    letto_il = models.DateTimeField(null=True, blank=True)
    ultimo_errore = models.TextField(blank=True)

    class Meta:
        verbose_name = "cursore di un flusso"
        verbose_name_plural = "cursori dei flussi"
        constraints = [
            models.UniqueConstraint(fields=["cliente", "flusso"], name="api_cursore_unico")
        ]

    def __str__(self):
        return f"{self.cliente} {self.flusso}:{self.progressivo}"


class DocumentoRicevuto(models.Model):
    """Documento ricevuto da una controparte (ADR-030, F4): resta in coda finché chi riceve non
    lo conferma (o lo scarta). Le conferme tecniche si applicano da sole."""

    class Tipo(models.TextChoices):
        RICHIESTA = "richiesta", "Richiesta di tessere"
        CONSEGNA = "consegna", "Consegna di tessere"
        RICEVUTA = "ricevuta", "Ricevuta di un versamento"
        PRESA = "presa", "Presa in carico di una consegna"

    class Stato(models.TextChoices):
        DA_ESAMINARE = "da_esaminare", "Da esaminare"
        APPLICATO = "applicato", "Confermato"
        SCARTATO = "scartato", "Scartato"

    cliente = models.ForeignKey(ClienteApi, on_delete=models.PROTECT, related_name="documenti")
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    uuid_origine = models.UUIDField("identificativo presso la controparte")
    versione = models.PositiveIntegerField(default=1)
    dati = models.JSONField(default=dict)
    pdf = models.FileField(upload_to="api/arrivi/", blank=True, max_length=255)
    stato = models.CharField(max_length=12, choices=Stato.choices, default=Stato.DA_ESAMINARE,
                             db_index=True)  # fmt: skip
    ricevuto_il = models.DateTimeField(auto_now_add=True)
    aggiornato_il = models.DateTimeField(auto_now=True)
    gestito_il = models.DateTimeField(null=True, blank=True)
    gestito_da = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    motivo = models.CharField(max_length=255, blank=True)
    protocollo = models.ForeignKey(
        "protocollo.Protocollo", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        verbose_name = "documento ricevuto"
        verbose_name_plural = "documenti ricevuti"
        ordering = ["-ricevuto_il"]
        constraints = [
            models.UniqueConstraint(
                fields=["cliente", "tipo", "uuid_origine"], name="api_documento_unico"
            )
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} da {self.cliente}"


class VerificaSoci(models.Model):
    """Verifica dei soci con una controparte (ADR-030, F4): l'elenco ricevuto e la proposta
    (soci da creare, modifiche campo per campo) restano qui finché chi verifica non sceglie cosa
    applicare. Dopo l'applicazione l'elenco ricevuto si cancella (restano gli esiti)."""

    cliente = models.ForeignKey(ClienteApi, on_delete=models.CASCADE, related_name="verifiche_soci")
    sezione = models.ForeignKey("soci.Sezione", on_delete=models.PROTECT, related_name="+")
    da_sezione = models.BooleanField(
        default=False, help_text="La controparte è la sezione: manda anche stato e rinnovi."
    )
    creata_il = models.DateTimeField(auto_now_add=True)
    creata_da = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    righe = models.JSONField(default=list, blank=True)
    proposta = models.JSONField(default=dict, blank=True)
    applicata_il = models.DateTimeField(null=True, blank=True)
    applicata_da = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    esiti = models.JSONField(default=list, blank=True)

    class Meta:
        verbose_name = "verifica dei soci"
        verbose_name_plural = "verifiche dei soci"
        ordering = ["-creata_il"]

    def __str__(self):
        return f"Verifica soci con {self.cliente} del {self.creata_il:%d/%m/%Y %H:%M}"
