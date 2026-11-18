# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Base dei modelli esposti dall'API (ADR-030 §7): `uuid`, `versione` crescente e
# *              scrittura del cambiamento nel feed nella stessa transazione del salvataggio
# *              (outbox). Il gancio è nel save() del modello, così nessun punto di scrittura
# *              (viste, servizi, importazioni) può dimenticarlo.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import uuid

from django.db import models, transaction
from django.db.models import F


class RisorsaApi(models.Model):
    """Modello esposto dall'API. Le sottoclassi indicano FLUSSO e RISORSA."""

    FLUSSO = ""
    RISORSA = ""

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    versione = models.PositiveIntegerField(default=0, editable=False)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        nuovo = self._state.adding
        azione = self.azione_api(nuovo)
        campi = kwargs.get("update_fields")
        if not nuovo:
            # la versione la scrive solo l'UPDATE atomico qui sotto: una copia in memoria non
            # aggiornata non deve poterla riportare indietro
            if campi is None:
                campi = [f.name for f in self._meta.concrete_fields
                         if not f.primary_key and f.name != "versione"]  # fmt: skip
            kwargs["update_fields"] = [c for c in campi if c != "versione"]
        with transaction.atomic():
            super().save(*args, **kwargs)
            self.registra_cambiamento(azione)

    def delete(self, *args, **kwargs):
        with transaction.atomic():
            self.registra_cambiamento("eliminato")
            return super().delete(*args, **kwargs)

    def azione_api(self, nuovo):
        """Azione del cambiamento (creato, modificato, annullato, …), calcolata prima del save."""
        return "creato" if nuovo else "modificato"

    def tocca(self):
        """Nuova versione senza modifiche dirette (es. sono cambiate le adesioni di un evento)."""
        with transaction.atomic():
            self.registra_cambiamento("modificato")

    def registra_cambiamento(self, azione):
        from . import feed

        modello = type(self)
        modello.objects.filter(pk=self.pk).update(versione=F("versione") + 1)
        self.versione = modello.objects.filter(pk=self.pk).values_list("versione", flat=True).get()
        tipo = f"{self.RISORSA}.{azione}"
        feed.registra(self.FLUSSO, tipo, self.uuid, self.RISORSA, self.versione)
