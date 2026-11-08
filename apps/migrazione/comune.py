# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Parti comuni delle importazioni: rapporto, corrispondenze, lettura SQLite
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError

from .models import Origine


class FonteNonValida(ValidationError):
    """Il database indicato non è quello del gestionale atteso."""


@dataclass
class Voce:
    stato: str  # nuovo, aggiornato, invariato, saltato, errore
    descrizione: str
    note: list = field(default_factory=list)


@dataclass
class Rapporto:
    fonte: str
    eseguito: bool = False
    parti: dict = field(default_factory=lambda: defaultdict(list))
    avvisi: list = field(default_factory=list)

    def aggiungi(self, parte, stato, descrizione, note=()):
        self.parti[parte].append(Voce(stato, descrizione, list(note)))

    def conteggi(self):
        return {parte: dict(Counter(v.stato for v in voci)) for parte, voci in self.parti.items()}

    def testo(self, dettagli=False):
        righe = [f"{self.fonte} - {'IMPORTAZIONE ESEGUITA' if self.eseguito else 'ANTEPRIMA'}"]
        for parte, voci in self.parti.items():
            conti = Counter(v.stato for v in voci)
            righe.append(f"\n{parte}: " + ", ".join(f"{s} {n}" for s, n in sorted(conti.items())))
            for v in voci:
                # senza dettagli: solo errori e record con annotazioni (non i già importati)
                if dettagli or v.stato == "errore" or (v.note and v.stato != "invariato"):
                    nota = f" - {'; '.join(v.note)}" if v.note else ""
                    righe.append(f"  [{v.stato}] {v.descrizione}{nota}")
        if self.avvisi:
            righe.append("\nAvvisi:")
            righe += [f"  - {a}" for a in self.avvisi]
        return "\n".join(righe)


def apri_sqlite(percorso, tabelle_attese):
    """Apre il database in sola lettura e controlla che abbia le tabelle del gestionale."""
    percorso = Path(percorso)
    if not percorso.is_file() or percorso.stat().st_size == 0:
        raise FonteNonValida(f"Database {percorso} inesistente o vuoto.")
    conn = sqlite3.connect(f"file:{percorso}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    presenti = {r[0] for r in conn.execute("select name from sqlite_master where type='table'")}
    mancanti = set(tabelle_attese) - presenti
    if mancanti:
        conn.close()
        raise FonteNonValida(
            f"{percorso.name} non sembra il database atteso: mancano {', '.join(sorted(mancanti))}."
        )
    return conn


def righe(conn, tabella, ordine="id"):
    """Righe di una tabella come dizionari (colonne assenti nelle versioni vecchie = None)."""
    return [dict(r) for r in conn.execute(f"select * from {tabella} order by {ordine}")]  # noqa: S608


def importato(fonte, tabella, chiave, modello):
    """L'oggetto già importato da quel record, se esiste ancora."""
    o = Origine.objects.filter(fonte=fonte, tabella=tabella, chiave=str(chiave)).first()
    if o is None:
        return None
    return modello.objects.filter(pk=o.oggetto_id).first()


def segna(fonte, tabella, chiave, oggetto):
    Origine.objects.update_or_create(
        fonte=fonte,
        tabella=tabella,
        chiave=str(chiave),
        defaults={
            "oggetto_tipo": ContentType.objects.get_for_model(oggetto),
            "oggetto_id": str(oggetto.pk),
        },
    )


def testo(valore):
    return str(valore).strip() if valore is not None else ""
