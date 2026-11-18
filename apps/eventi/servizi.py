# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Adesioni agli eventi: controlli di posti, scadenza e doppioni, collegamento
# *              all'anagrafica, annullamento; elenco degli aderenti in Excel
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import io

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.anagrafica.models import Soggetto
from apps.anagrafica.servizi import cella_sicura
from apps.core.audit import Azione, registra

from .models import Adesione, Evento


class OperazioneNonValida(ValidationError):
    pass


def _trova_soggetto(email, cognome, nome):
    """Persona dell'anagrafica riconosciuta con certezza (email unica o nome e cognome unici)."""
    attivi = Soggetto.objects.filter(attivo=True)
    if email:
        trovati = list(attivi.filter(email__iexact=email)[:2])
        if len(trovati) == 1:
            return trovati[0]
    if cognome and nome:
        trovati = list(attivi.filter(cognome__iexact=cognome, nome__iexact=nome)[:2])
        if len(trovati) == 1:
            return trovati[0]
    return None


@transaction.atomic
def aderisci(evento, dati, *, origine, utente=None, ip=None, soggetto=None, cliente_api=None,
             riferimento_esterno=""):  # fmt: skip
    """Registra un'adesione. `dati`: cognome, nome, email, telefono, accompagnatori, note.
    La segreteria può aderire anche a adesioni chiuse o oltre la scadenza, mai oltre i posti."""
    evento = Evento.objects.select_for_update().get(pk=evento.pk)
    if evento.annullato:
        raise OperazioneNonValida("L'evento è annullato.")
    chiuse = not evento.adesioni_aperte or timezone.now() >= evento.scadenza_adesioni
    if origine != Adesione.Origine.SEGRETERIA and chiuse:
        raise OperazioneNonValida("Le adesioni sono chiuse.")
    try:
        accompagnatori = int(dati.get("accompagnatori") or 0)
    except (TypeError, ValueError):
        raise OperazioneNonValida("Numero di accompagnatori non valido.") from None
    if accompagnatori < 0:
        raise OperazioneNonValida("Numero di accompagnatori non valido.")
    if accompagnatori > evento.accompagnatori:
        raise OperazioneNonValida(
            f"Al massimo {evento.accompagnatori} accompagnator"
            f"{'e' if evento.accompagnatori == 1 else 'i'} per adesione."
        )
    if evento.posti is not None and evento.partecipanti + 1 + accompagnatori > evento.posti:
        raise OperazioneNonValida(
            f"Posti esauriti (disponibili {evento.posti_liberi} su {evento.posti})."
        )
    email = (dati.get("email") or "").strip().lower()
    cognome = (dati.get("cognome") or "").strip()
    nome = (dati.get("nome") or "").strip()
    if not cognome:
        raise OperazioneNonValida("Indicare il cognome (o la denominazione).")
    soggetto = soggetto or _trova_soggetto(email, cognome, nome)
    valide = evento.adesioni_valide()
    if (soggetto and valide.filter(soggetto=soggetto).exists()) or (
        email and valide.filter(email__iexact=email).exists()
    ):
        raise OperazioneNonValida("Questa persona ha già aderito all'evento.")
    adesione = Adesione.objects.create(
        evento=evento, soggetto=soggetto, cognome=cognome[:100], nome=nome[:100], email=email,
        telefono=(dati.get("telefono") or "").strip()[:30], accompagnatori=accompagnatori,
        note=(dati.get("note") or "").strip()[:255], origine=origine, indirizzo_ip=ip,
        cliente_api=cliente_api, riferimento_esterno=(riferimento_esterno or "")[:100],
    )  # fmt: skip
    registra(Azione.CREAZIONE, adesione, utente=utente, ip=ip,
             descrizione=f"Adesione a «{evento}»: {adesione}", origine=origine)  # fmt: skip
    evento.tocca()  # cambiano i posti liberi: nuova versione dell'evento nel feed
    return adesione


@transaction.atomic
def annulla_adesione(adesione, utente=None):
    if adesione.annullata:
        raise OperazioneNonValida("L'adesione è già annullata.")
    adesione.annullata = True
    adesione.versione += 1
    adesione.save(update_fields=["annullata", "versione", "modificata_il"])
    adesione.evento.tocca()
    registra(Azione.ANNULLAMENTO, adesione, utente=utente,
             descrizione=f"Adesione a «{adesione.evento}» annullata: {adesione}")  # fmt: skip
    return adesione


def aderenti_xlsx(evento):
    from openpyxl import Workbook
    from openpyxl.styles import Font

    wb = Workbook()
    ws = wb.active
    ws.title = "Aderenti"
    intestazioni = ["Cognome", "Nome", "Email", "Telefono", "Accompagnatori", "Note", "Origine",
                    "Aderito il"]  # fmt: skip
    ws.append(intestazioni)
    for cella in ws[1]:
        cella.font = Font(bold=True)
    for a in evento.adesioni_valide():
        ws.append([cella_sicura(a.cognome), cella_sicura(a.nome), a.email,
                   cella_sicura(a.telefono), a.accompagnatori, cella_sicura(a.note),
                   a.get_origine_display(),
                   timezone.localtime(a.creata_il).replace(tzinfo=None)])  # fmt: skip
    for col, larghezza in zip("ABCDEFGH", (22, 18, 28, 16, 14, 30, 16, 18), strict=True):
        ws.column_dimensions[col].width = larghezza
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
