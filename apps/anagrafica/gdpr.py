# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Diritti dell'interessato (GDPR): esportazione di tutti i dati di una persona
# *              (JSON elaborabile + riepilogo PDF + foto, in un archivio ZIP) e anonimizzazione
# *              irreversibile. I documenti ufficiali (protocolli, verbali, prima nota, ricevute)
# *              e il registro attività restano come sono: vanno conservati per legge.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import io
import json
import zipfile
from datetime import date, datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.core.audit import Azione, registra

from .models import Soggetto

ANONIMO = "Persona anonimizzata"
PAROLA_CONFERMA = "ANONIMIZZA"
CAMPI_SCHEDA = [
    "tipo",
    "titolo",
    "nome",
    "cognome",
    "sesso",
    "data_nascita",
    "luogo_nascita",
    "codice_fiscale",
    "data_decesso",
    "denominazione",
    "partita_iva",
    "qualifica",
    "email",
    "pec",
    "telefono",
    "cellulare",
    "indirizzo",
    "cap",
    "comune",
    "provincia",
    "nazione",
    "note",
    "attivo",
    "creato_il",
    "modificato_il",
]


class OperazioneNonValida(ValidationError):
    """Operazione non consentita (messaggio per l'utente)."""


def _valore(v):
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return str(v)
    return v


def _riga(oggetto, campi):
    return {c: _valore(getattr(oggetto, c)) for c in campi}


# --- raccolta ----------------------------------------------------------------------------------


def dati(soggetto):
    """Tutti i dati riferiti alla persona, sezione per sezione (anche quelli negli altri moduli)."""
    from apps.comunicazioni.models import Destinatario
    from apps.organi.models import Presenza

    d = {"scheda": _riga(soggetto, CAMPI_SCHEDA)}
    d["scheda"]["categorie"] = [c.nome for c in soggetto.categorie.all()]
    d["scheda"]["foto"] = bool(soggetto.foto)
    d["consensi"] = [
        {
            "finalita": c.get_finalita_display(),
            "prestato": c.prestato,
            "data": _valore(c.data),
            "modalita": c.modalita,
        }
        for c in soggetto.consensi.order_by("data")
    ]
    utente = getattr(soggetto, "utente", None)
    if utente is not None:
        d["utente"] = {
            "nome_utente": utente.username,
            "email": utente.email,
            "ruoli": [g.name for g in utente.groups.all()],
            "ultimo_accesso": _valore(utente.last_login),
            "attivo": utente.is_active,
        }
    socio = getattr(soggetto, "socio", None)
    if socio is not None:
        d["socio"] = {
            "numero": socio.numero,
            "matricola": socio.matricola,
            "sezione": str(socio.sezione) if socio.sezione_id else "",
            "tipologia": str(socio.tipologia),
            "stato": socio.get_stato_display(),
            "ammissione": _valore(socio.data_ammissione),
            "delibera": socio.delibera_ammissione,
            "cessazione": _valore(socio.data_cessazione),
            "note": socio.note,
        }
        d["tessere"] = [
            {
                "anno": t.anno,
                "tessera": t.codice,
                "importo": _valore(t.importo),
                "pagata_il": _valore(t.pagata_il),
                "ricevuta": t.codice_ricevuta,
                "annullata": t.annullata,
            }
            for t in socio.tessere.order_by("anno")
        ]
        d["domande_di_iscrizione"] = [
            _riga(
                dm,
                [
                    "ricevuta_il",
                    "nome",
                    "cognome",
                    "codice_fiscale",
                    "data_nascita",
                    "luogo_nascita",
                    "email",
                    "telefono",
                    "cellulare",
                    "indirizzo",
                    "cap",
                    "comune",
                    "provincia",
                    "motivazione",
                    "stato",
                    "esito_il",
                ],
            )
            for dm in socio.domande.all()
        ]
    d["cariche"] = [
        {
            "organo": str(c.organo),
            "ruolo": c.get_ruolo_display(),
            "dal": _valore(c.dal),
            "al": _valore(c.al),
            "atto_di_nomina": c.nomina,
        }
        for c in soggetto.cariche.select_related("organo__sezione")
    ]
    d["presenze_alle_riunioni"] = [
        {"riunione": str(p.riunione), "stato": p.get_stato_display(), "qualifica": p.qualifica}
        for p in Presenza.objects.filter(soggetto=soggetto).select_related("riunione__organo")
    ]
    d["protocolli"] = [
        {
            "protocollo": c.protocollo.segnatura,
            "data": _valore(c.protocollo.registrato_il),
            "oggetto": c.protocollo.oggetto,
            "ruolo": c.get_ruolo_display(),
        }
        for c in soggetto.protocolli.select_related("protocollo")
    ]
    d["comunicazioni_ricevute"] = [
        {
            "oggetto": x.invio.oggetto,
            "email": x.email,
            "stato": x.get_stato_display(),
            "inviata_il": _valore(x.inviato_il),
        }
        for x in Destinatario.objects.filter(soggetto=soggetto).select_related("invio")
    ]
    d["liste_di_distribuzione"] = [str(lista) for lista in soggetto.liste.all()]
    d["movimenti_di_tesoreria"] = [
        {
            "data": _valore(m.data),
            "descrizione": str(m),
            "importo": _valore(getattr(m, "importo", "")),
        }
        for m in soggetto.movimenti.all()
    ]
    d["beni_donati"] = [str(b) for b in soggetto.beni_donati.all()]
    d["beni_ricevuti"] = [str(u) for u in soggetto.beni_ricevuti.select_related("bene")]
    return d


def esporta(soggetto, utente):
    """Archivio ZIP: dati-personali.json, riepilogo.pdf e l'eventuale foto."""
    from apps.core.models import Organizzazione
    from apps.core.pdf import genera_pdf

    contenuto = dati(soggetto)
    adesso = timezone.localtime()
    pdf = genera_pdf(
        "anagrafica/pdf/dati_personali.html",
        {
            "soggetto": soggetto,
            "dati": contenuto,
            "adesso": adesso,
            "organizzazione": Organizzazione.corrente(),
        },
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(
            "dati-personali.json",
            json.dumps(
                {"estratto_il": adesso.isoformat(), "dati": contenuto}, ensure_ascii=False, indent=2
            ),
        )
        z.writestr("riepilogo.pdf", pdf)
        if soggetto.foto:
            with soggetto.foto.open("rb") as f:
                z.writestr("foto" + soggetto.foto.name[soggetto.foto.name.rfind(".") :], f.read())
    registra(Azione.ESPORTAZIONE, soggetto, utente=utente, documento="dati personali (GDPR)")
    return buffer.getvalue()


# --- anonimizzazione ---------------------------------------------------------------------------


def impedimenti(soggetto):
    """Motivi per cui la persona non si può anonimizzare (lista vuota = si può)."""
    from apps.soci.models import Socio

    motivi = []
    if not soggetto.is_persona:
        motivi.append("si anonimizzano solo le persone (gli enti non sono dati personali)")
    if soggetto.anonimizzato_il:
        motivi.append("la scheda è già anonimizzata")
    socio = getattr(soggetto, "socio", None)
    if socio is not None and socio.stato != Socio.Stato.CESSATO:
        motivi.append(
            f"è socio {socio.get_stato_display().lower()}: prima va registrata la cessazione"
        )
    if getattr(soggetto, "utente", None) is not None:
        motivi.append("è collegata a un utente del programma")
    return motivi


@transaction.atomic
def anonimizza(soggetto, utente, *, motivo, conferma):
    from apps.comunicazioni.models import Destinatario

    soggetto = Soggetto.objects.select_for_update().get(pk=soggetto.pk)
    if conferma.strip().upper() != PAROLA_CONFERMA:
        raise OperazioneNonValida(f"Per confermare scrivere {PAROLA_CONFERMA}.")
    if not (motivo or "").strip():
        raise OperazioneNonValida("Indicare il motivo (es. richiesta dell'interessato).")
    motivi = impedimenti(soggetto)
    if motivi:
        raise OperazioneNonValida("Non si può anonimizzare: " + "; ".join(motivi) + ".")
    if soggetto.foto:
        soggetto.foto.delete(save=False)
    for campo in (
        "titolo",
        "nome",
        "sesso",
        "luogo_nascita",
        "qualifica",
        "email",
        "pec",
        "telefono",
        "cellulare",
        "indirizzo",
        "cap",
        "comune",
        "provincia",
        "note",
    ):
        setattr(soggetto, campo, "")
    soggetto.cognome = ANONIMO
    soggetto.codice_fiscale = None
    soggetto.data_nascita = soggetto.data_decesso = None
    soggetto.attivo = False
    soggetto.anonimizzato_il = timezone.now()
    soggetto.modificato_da = utente
    soggetto.save()
    soggetto.categorie.clear()
    soggetto.liste.clear()
    Destinatario.objects.filter(soggetto=soggetto).update(nome=ANONIMO, email="")
    socio = getattr(soggetto, "socio", None)
    if socio is not None:
        if socio.modulo_adesione:
            socio.modulo_adesione.delete(save=False)
        socio.matricola, socio.note = "", ""
        socio.save(update_fields=["matricola", "note", "modulo_adesione"])
        # domande di iscrizione collegate al socio
        socio.domande.update(
            nome="",
            cognome=ANONIMO,
            codice_fiscale="",
            luogo_nascita="",
            email="",
            telefono="",
            cellulare="",
            indirizzo="",
            cap="00000",
            comune="",
            provincia="XX",
            motivazione="",
            indirizzo_ip=None,
            esito_note="",
        )
    # nel registro attività niente dati personali: solo il fatto e il motivo
    registra(
        Azione.ANNULLAMENTO,
        soggetto,
        utente=utente,
        operazione="anonimizzazione (GDPR)",
        motivo=motivo.strip()[:255],
    )
    return soggetto
