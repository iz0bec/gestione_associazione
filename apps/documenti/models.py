# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Modelli di stampa: testi con segnaposto stampati su carta intestata
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.db import models


def percorso_stemma(istanza, nome):
    from apps.core.immagini import nome_casuale

    return nome_casuale("stemmi", "png")


class ModelloStampa(models.Model):
    class Tipo(models.TextChoices):
        LETTERA = "lettera", "Lettera (destinatario, luogo e data, oggetto, firma)"
        ATTESTATO = "attestato", "Attestato (titolo centrato, luogo e data, firma)"
        DOCUMENTO = "documento", "Documento libero (titolo e testo)"
        BENEMERENZA = (
            "benemerenza",
            ("Attestato solenne / benemerenza (pagina orizzontale con cornice, stemmi e coccarda)"),
        )

    class SecondaFirma(models.TextChoices):
        VICEPRESIDENTE = "vicepresidente", "Il Vicepresidente"
        SEGRETARIO = "segretario", "Il Segretario"
        TESORIERE = "tesoriere", "Il Tesoriere"

    nome = models.CharField(max_length=100, unique=True)
    tipo = models.CharField(max_length=12, choices=Tipo.choices, default=Tipo.LETTERA)
    titolo = models.CharField(
        "titolo o oggetto",
        max_length=200,
        blank=True,
        help_text="Oggetto della lettera o titolo dell'attestato; ammette i segnaposto.",
    )
    corpo = models.TextField(
        "testo",
        help_text="Una riga vuota separa i paragrafi; **testo** = grassetto, *testo* = corsivo, "
        "righe che iniziano con «- » = elenco. Segnaposto come {{ nome_completo }}.",
    )
    firma_ruolo = models.CharField(
        "qualifica del firmatario", max_length=100, blank=True, default="Il Presidente"
    )
    firma_nome = models.CharField(
        "nome del firmatario",
        max_length=150,
        blank=True,
        help_text="Vuoto = il presidente in carica negli Organi sociali.",
    )
    seconda_firma = models.CharField(
        "seconda firma",
        max_length=16,
        choices=SecondaFirma.choices,
        blank=True,
        help_text="Solo per l'attestato solenne: firma a sinistra, con il nome di chi è in carica.",
    )
    stemma = models.ImageField(
        "stemma o logo aggiuntivo",
        upload_to=percorso_stemma,
        blank=True,
        max_length=255,
        editable=False,
        help_text="Attestato solenne: a destra del logo dell'ente (vuoto = logo del modulo di "
        "adesione, se presente).",
    )
    attivo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "modello di stampa"
        verbose_name_plural = "modelli di stampa"
        ordering = ["nome"]
        permissions = [("stampa_documento", "Può stampare documenti dai modelli")]

    def __str__(self):
        return self.nome
