# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Numerazioni progressive atomiche (protocollo, tessere, inventario, ...).
# *              Il numero va chiesto nella STESSA transazione che salva il documento:
# *              la riga della sequenza resta bloccata fino al commit, quindi richieste
# *              concorrenti non ottengono mai lo stesso numero e un errore non lascia buchi.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.db import connection, transaction

from .models import Sequenza


class TransazioneRichiesta(RuntimeError):
    """prossimo_numero chiamato fuori da transaction.atomic()."""


def prossimo_numero(chiave: str, anno: int | None = None) -> int:
    """Restituisce il prossimo numero della sequenza `chiave` (per `anno`, se indicato)."""
    if not connection.in_atomic_block:
        raise TransazioneRichiesta(
            "prossimo_numero() va chiamato dentro transaction.atomic(), insieme al salvataggio."
        )
    anno = anno or 0
    # crea la riga se manca, senza errori se un'altra transazione la sta creando
    Sequenza.objects.bulk_create([Sequenza(chiave=chiave, anno=anno)], ignore_conflicts=True)
    sequenza = Sequenza.objects.select_for_update().get(chiave=chiave, anno=anno)
    sequenza.ultimo_numero += 1
    sequenza.save(update_fields=["ultimo_numero"])
    return sequenza.ultimo_numero


def numero_formattato(chiave: str, anno: int, cifre: int = 5) -> str:
    """Numero nel formato AAAA-NNNNN (es. 2026-00042)."""
    return f"{anno}-{prossimo_numero(chiave, anno):0{cifre}d}"


__all__ = ["TransazioneRichiesta", "numero_formattato", "prossimo_numero", "transaction"]
