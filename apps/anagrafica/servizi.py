# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Operazioni sull'anagrafica (con registro attività)
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import csv

from django.db import transaction

from apps.core.audit import Azione, campi_modificati, registra

CAMPI_ESPORTAZIONE = [
    "tipo", "titolo", "cognome", "nome", "denominazione", "qualifica", "codice_fiscale",
    "partita_iva", "sesso", "data_nascita", "luogo_nascita", "email", "pec", "telefono",
    "cellulare", "indirizzo", "cap", "comune", "provincia", "nazione",
]  # fmt: skip


@transaction.atomic
def salva_soggetto(form, utente):
    """Crea o aggiorna un soggetto dal form validato."""
    nuovo = form.instance.pk is None
    dettagli = {} if nuovo else campi_modificati(form)
    soggetto = form.save(commit=False)
    if nuovo:
        soggetto.creato_da = utente
    soggetto.modificato_da = utente
    soggetto.save()
    form.save_m2m()
    if nuovo:
        registra(Azione.CREAZIONE, soggetto, utente=utente)
    elif dettagli.get("campi"):
        registra(Azione.MODIFICA, soggetto, utente=utente, **dettagli)
    return soggetto


@transaction.atomic
def imposta_archiviato(soggetto, archiviato, utente):
    soggetto.attivo = not archiviato
    soggetto.modificato_da = utente
    soggetto.save(update_fields=["attivo", "modificato_da", "modificato_il"])
    registra(
        Azione.ARCHIVIAZIONE if archiviato else Azione.MODIFICA,
        soggetto,
        utente=utente,
        attivo=soggetto.attivo,
    )


def cella_sicura(valore):
    """Evita che un foglio di calcolo interpreti il valore come formula (CSV injection)."""
    testo = "" if valore is None else str(valore)
    if testo[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + testo
    return testo


def esporta_csv(queryset, destinazione, utente):
    """Scrive l'elenco in CSV (separatore ;, compatibile con Excel italiano)."""
    writer = csv.writer(destinazione, delimiter=";")
    writer.writerow([*CAMPI_ESPORTAZIONE, "categorie"])
    n = 0
    for s in queryset.prefetch_related("categorie"):
        riga = [cella_sicura(getattr(s, c)) for c in CAMPI_ESPORTAZIONE]
        riga.append(cella_sicura(", ".join(c.nome for c in s.categorie.all())))
        writer.writerow(riga)
        n += 1
    registra(Azione.ESPORTAZIONE, utente=utente, descrizione=f"Anagrafica CSV ({n} righe)", righe=n)
    return n
