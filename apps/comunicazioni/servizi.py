# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Operazioni delle comunicazioni: segnaposto, consensi, preparazione degli
# *              invii, coda di invio (un messaggio per destinatario), auguri automatici,
# *              invii collegati a riunioni, quote e domande di iscrizione.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import hashlib
import logging
import mimetypes
import re
from datetime import date
from email.utils import parseaddr

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.mail import EmailMultiAlternatives
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils import timezone

from apps.anagrafica.models import Consenso, Soggetto
from apps.core.audit import Azione, registra
from apps.core.models import Organizzazione

from . import anniversari
from .models import (
    AllegatoInvio,
    Automazione,
    ConsegnaMessaggio,
    Destinatario,
    DestinatarioRegistrato,
    Finalita,
    Invio,
    Modello,
    PromemoriaRinnovo,
    Ricorrenza,
)

log = logging.getLogger(__name__)

MAX_TENTATIVI = 3
SOLO_ALTRI_CANALI = "niente email: solo SMS, WhatsApp o Telegram"

SEGNAPOSTO = {
    "nome": "nome della persona",
    "cognome": "cognome",
    "nome_completo": "cognome e nome, o denominazione dell'ente",
    "titolo": "titolo (es. Cav., Dott.)",
    "intestazione": "titolo, nome e cognome (es. Cav. Mario Rossi)",
    "saluto": "«Caro», «Cara» o «Gentile» secondo il sesso",
    "anni": "anni compiuti, di iscrizione o della ricorrenza",
    "numero_socio": "numero nel libro soci",
    "anni_socio": "anni di iscrizione",
    "organizzazione": "denominazione dell'associazione",
    "data": "data di oggi",
    "ricorrenza": "nome della ricorrenza",
    "riunione": "organo e numero della riunione",
    "data_riunione": "data e ora della prima convocazione",
    "luogo_riunione": "luogo della riunione",
    "ordine_del_giorno": "elenco dei punti",
    "anno_quota": "anno della quota",
    "importo": "importo della quota",
    "ricevuta": "numero della ricevuta",
    "tessera": "numero della tessera",
    "esito": "esito della domanda di iscrizione",
    "richiedente": "nome e cognome di chi chiede l'iscrizione",
    "protocollo": "numero di protocollo",
    "data_protocollo": "data della registrazione di protocollo",
    # ciclo delle tessere (avvisi alle sezioni)
    "anno": "anno di tesseramento",
    "sezione": "nome della sezione",
    "quota_tessera": "importo per tessera (costo nazionale + quota federale)",
    "costo_nazionale": "costo di una tessera alla sede nazionale",
    "quota_federale": "quota federale per tessera",
    "delibera": "delibera del consiglio direttivo che ha fissato la quota",
    "scadenza_richiesta": "termine per chiedere le tessere",
    "modalita_pagamento": "modalità di pagamento (dal listino)",
    "riferimento_avviso": "riferimento dell'avviso di tesseramento",
    "nuova_scadenza": "nuovo termine indicato nel sollecito",
    "numero_consegna": "numero del documento di consegna",
    "tessere": "numeri delle tessere attribuite (serie, dal, al)",
    "quantita": "quantità di tessere",
    "importo_dovuto": "importo dovuto dalla sezione per l'anno",
    "importo_versato": "importo già versato dalla sezione",
    "saldo": "importo ancora da versare",
    "modalita_distribuzione": "ritiro in sede, consegna a mano o spedizione",
    "note_distribuzione": "luogo, date e orari della distribuzione",
}
_RE_SEGNAPOSTO = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")


class OperazioneNonValida(ValidationError):
    """Operazione rifiutata (messaggio per l'utente)."""


def componi(testo, contesto):
    """Sostituisce {{ chiave }} con i valori del contesto; i segnaposto ignoti restano visibili."""

    def sostituisci(m):
        valore = contesto.get(m[1])
        return m[0] if valore is None else str(valore)

    return _RE_SEGNAPOSTO.sub(sostituisci, testo)


def segnaposto_sconosciuti(testo):
    return sorted({m for m in _RE_SEGNAPOSTO.findall(testo) if m not in SEGNAPOSTO})


def contesto_soggetto(soggetto, oggi=None):
    oggi = oggi or timezone.localdate()
    c = {
        "nome": soggetto.nome or soggetto.nome_completo,
        "cognome": soggetto.cognome,
        "nome_completo": soggetto.nome_completo,
        "titolo": soggetto.titolo,
        "intestazione": soggetto.intestazione,
        "saluto": {"M": "Caro", "F": "Cara"}.get(soggetto.sesso, "Gentile"),
    }
    if soggetto.data_nascita:
        c["anni"] = soggetto.eta
    socio = getattr(soggetto, "socio", None)
    if socio is not None:
        c["numero_socio"] = socio.numero
        c["anni_socio"] = oggi.year - socio.data_ammissione.year
    return c


def contesto_generale():
    return {
        "organizzazione": Organizzazione.corrente().denominazione,
        "data": timezone.localdate().strftime("%d/%m/%Y"),
    }


# --- consensi e destinatari ------------------------------------------------------------------


def consensi_prestati(soggetti, finalita):
    """Id dei soggetti il cui ultimo consenso registrato per la finalità è «prestato»."""
    ultimo = {}
    for c in Consenso.objects.filter(soggetto__in=soggetti, finalita=finalita).order_by(
        "data", "registrato_il"
    ):
        ultimo[c.soggetto_id] = c.prestato
    return {pk for pk, prestato in ultimo.items() if prestato}


def motivo_esclusione(soggetto, finalita, con_consenso, indirizzo=None):
    if not soggetto.attivo:
        return "scheda archiviata"
    if soggetto.deceduto:
        return "deceduto"
    if not (soggetto.email if indirizzo is None else indirizzo):
        return "senza email"
    if finalita != Finalita.ISTITUZIONALE and soggetto.pk not in con_consenso:
        return "consenso non prestato"
    return ""


def motivi_lista(lista, anno=None):
    """{id del soggetto: [perché è nella lista]}: scelto, categoria, soci, organo."""
    from apps.soci.models import Socio

    anno = anno or timezone.localdate().year
    motivi = {}

    def aggiungi(ids, motivo):
        for pk in ids:
            motivi.setdefault(pk, []).append(motivo)

    aggiungi(lista.soggetti.values_list("pk", flat=True), "scelto")
    for c in lista.categorie.all():
        aggiungi(c.soggetti.values_list("pk", flat=True), f"categoria {c.nome}")
    if lista.soci_attivi or lista.soci_in_regola:
        soci = Socio.objects.attivi()
        if lista.soci_in_regola:
            soci = soci.in_regola(anno)
        motivo = "socio in regola" if lista.soci_in_regola else "socio"
        sezioni = list(lista.sezioni.all())
        if sezioni:
            soci = soci.filter(sezione__in=sezioni)
        nomi = {s.pk: s.nome for s in sezioni}
        for soggetto_id, sezione_id in soci.values_list("soggetto_id", "sezione_id"):
            testo = f"{motivo} ({nomi[sezione_id]})" if sezione_id in nomi else motivo
            aggiungi([soggetto_id], testo)
    if lista.organo_id:
        aggiungi(lista.organo.cariche_al().values_list("soggetto_id", flat=True),
                 str(lista.organo))  # fmt: skip
    return motivi


def soggetti_lista(lista, anno=None):
    return Soggetto.objects.filter(pk__in=motivi_lista(lista, anno))


def leggi_indirizzi(testo):
    """Indirizzi liberi, uno per riga: «Nome <email>» o solo l'email."""
    risultato, errati = [], []
    for riga in (testo or "").splitlines():
        riga = riga.strip()
        if not riga:
            continue
        nome, email = parseaddr(riga)
        try:
            validate_email(email)
        except ValidationError:
            errati.append(riga)
            continue
        risultato.append((nome or email, email.lower()))
    return risultato, errati


@transaction.atomic
def crea_invio(
    utente,
    *,
    oggetto,
    corpo,
    finalita,
    soggetti=(),
    indirizzi=(),
    modello=None,
    allegati=(),
    protocolla=False,
    programmato_il=None,
    origine="",
    origine_id=None,
    contesto=None,
    contesti_soggetto=None,
    servizio=None,
    telegram=False,
    sms=False,
    whatsapp=False,
    testo_breve="",
    email=True,
):
    """Prepara un invio in bozza con i destinatari (i non raggiungibili esclusi, con il motivo).

    `allegati`: lista di (nome, bytes); `contesti_soggetto`: {soggetto_id: {segnaposto: valore}}.
    `servizio`: ServizioInvio (None: server generale); se è una PEC, chi ha la PEC la riceve per
    PEC e gli altri per email dal server generale. `telegram`: anche a chi ha collegato Telegram;
    `sms`, `whatsapp`: anche per SMS (a chi ha il cellulare) e WhatsApp (a chi ha dato il consenso),
    con `testo_breve` (vuoto: l'oggetto). `email=False`: niente email, solo gli altri canali.
    """
    if not oggetto.strip() or not corpo.strip():
        raise OperazioneNonValida("Oggetto e testo sono obbligatori.")
    if protocolla:
        from apps.protocollo.servizi import puo_protocollare

        if not puo_protocollare(utente):
            raise OperazioneNonValida("Non hai il permesso di protocollare.")
    soggetti = list({s.pk: s for s in soggetti}.values())
    if not soggetti and not indirizzi:
        raise OperazioneNonValida("Indicare almeno un destinatario.")
    if servizio is not None and not servizio.attivo:
        raise OperazioneNonValida(f"Il servizio di invio «{servizio}» è disattivato.")
    from apps.core.models import CanaleTelegram, ServizioMessaggi

    telegram = telegram and CanaleTelegram.corrente().pronto
    sms = sms and ServizioMessaggi.attivo_per("sms") is not None
    whatsapp = whatsapp and ServizioMessaggi.attivo_per("whatsapp") is not None
    if testo_breve and (sconosciuti := segnaposto_sconosciuti(testo_breve)):
        raise OperazioneNonValida(f"Segnaposto sconosciuti: {', '.join(sconosciuti)}.")
    if not email and not (telegram or sms or whatsapp):
        raise OperazioneNonValida(
            "Senza email serve almeno un altro canale attivo (SMS, WhatsApp o Telegram)."
        )
    pec = servizio is not None and servizio.pec
    invio = Invio.objects.create(
        oggetto=oggetto.strip(), corpo=corpo, finalita=finalita, modello=modello,
        protocolla=protocolla, programmato_il=programmato_il, origine=origine,
        origine_id=origine_id, contesto=contesto or {}, creato_da=utente, modificato_da=utente,
        servizio=servizio, telegram=telegram, sms=sms, whatsapp=whatsapp, email=email,
        testo_breve=(testo_breve or "").strip()[:320],
    )  # fmt: skip
    con_consenso = (
        consensi_prestati(soggetti, finalita) if finalita != Finalita.ISTITUZIONALE else set()
    )
    contesti_soggetto = contesti_soggetto or {}
    righe = []
    for s in sorted(soggetti, key=lambda x: x.nome_completo):
        canale = Destinatario.Canale.PEC if pec and s.pec else Destinatario.Canale.EMAIL
        indirizzo = s.pec if canale == Destinatario.Canale.PEC else s.email
        motivo = motivo_esclusione(s, finalita, con_consenso, indirizzo)
        su_telegram = telegram and s.telegram_chat_id and motivo in ("", "senza email")
        if not email and not motivo:
            motivo = SOLO_ALTRI_CANALI
        righe.append(
            Destinatario(
                invio=invio,
                soggetto=s,
                nome=s.nome_completo[:200],
                email=indirizzo,
                canale=canale,
                stato=Destinatario.Stato.ESCLUSO if motivo else Destinatario.Stato.IN_ATTESA,
                motivo=motivo,
                telegram_stato="in_attesa" if su_telegram else "",
                contesto=dict(contesti_soggetto.get(s.pk, {})),
            )  # fmt: skip
        )
    gia = {r.email.lower() for r in righe if r.email}
    for nome, indirizzo in indirizzi if email else ():  # indirizzi liberi: solo per email
        if indirizzo not in gia:
            from apps.protocollo.spedizioni import sembra_pec

            canale = Destinatario.Canale.PEC if pec and sembra_pec(indirizzo) else "email"
            righe.append(Destinatario(invio=invio, nome=nome[:200], email=indirizzo, canale=canale))
            gia.add(indirizzo)
    Destinatario.objects.bulk_create(righe)
    if sms or whatsapp:
        _consegne_messaggi(invio, sms, whatsapp)
    for nome, dati in allegati:
        _allega(invio, nome, dati)
    registra(
        Azione.CREAZIONE,
        invio,
        utente=utente,
        destinatari=len(righe),
        esclusi=sum(1 for r in righe if r.stato == Destinatario.Stato.ESCLUSO),
    )
    return invio


def _consegne_messaggi(invio, sms, whatsapp):
    """SMS a chi ha il cellulare, WhatsApp a chi ha anche dato il consenso: per i destinatari non
    esclusi (o esclusi solo perché senza email), con le stesse regole di finalità e consenso."""
    from .messaggi import numero_e164

    consegne = []
    for d in invio.destinatari.filter(soggetto__isnull=False).select_related("soggetto"):
        if d.stato == Destinatario.Stato.ESCLUSO and d.motivo not in (
            "senza email",
            SOLO_ALTRI_CANALI,
        ):
            continue
        numero = numero_e164(d.soggetto.cellulare)
        if not numero:
            continue
        if sms:
            consegne.append(ConsegnaMessaggio(destinatario=d, canale="sms", numero=numero))
        if whatsapp and d.soggetto.whatsapp_consenso_il:
            consegne.append(ConsegnaMessaggio(destinatario=d, canale="whatsapp", numero=numero))
    ConsegnaMessaggio.objects.bulk_create(consegne)


def _allega(invio, nome, dati):
    from apps.protocollo.servizi import nome_file_sicuro

    nome = nome_file_sicuro(nome)
    impronta = hashlib.sha256(dati).hexdigest()
    a = AllegatoInvio(
        invio=invio, nome=nome, tipo=mimetypes.guess_type(nome)[0] or "application/octet-stream",
        dimensione=len(dati), impronta=impronta,
    )  # fmt: skip
    a.file.save(nome, ContentFile(dati), save=False)
    a.save()
    return a


@transaction.atomic
def conferma(invio, utente):
    invio = Invio.objects.select_for_update().get(pk=invio.pk)
    if invio.stato != Invio.Stato.BOZZA:
        raise OperazioneNonValida("L'invio è già stato confermato.")
    if not invio.destinatari.filter(
        Q(stato=Destinatario.Stato.IN_ATTESA)
        | Q(telegram_stato="in_attesa")
        | Q(consegne__stato=ConsegnaMessaggio.Stato.IN_ATTESA)
    ).exists():
        raise OperazioneNonValida("Nessun destinatario raggiungibile.")
    if sconosciuti := segnaposto_sconosciuti(invio.oggetto + invio.corpo):
        raise OperazioneNonValida(f"Segnaposto sconosciuti: {', '.join(sconosciuti)}.")
    invio.stato = Invio.Stato.IN_CODA
    invio.confermato_il = timezone.now()
    invio.modificato_da = utente
    invio.save()
    registra(Azione.MODIFICA, invio, utente=utente, confermato=True)
    return invio


@transaction.atomic
def annulla(invio, utente):
    invio = Invio.objects.select_for_update().get(pk=invio.pk)
    if invio.stato not in (Invio.Stato.BOZZA, Invio.Stato.IN_CODA):
        raise OperazioneNonValida("L'invio è già concluso.")
    invio.stato = Invio.Stato.ANNULLATO
    invio.modificato_da = utente
    invio.save()
    invio.destinatari.filter(stato=Destinatario.Stato.IN_ATTESA).update(
        stato=Destinatario.Stato.ESCLUSO, motivo="invio annullato"
    )
    invio.destinatari.filter(telegram_stato="in_attesa").update(telegram_stato="")
    ConsegnaMessaggio.objects.filter(
        destinatario__invio=invio, stato=ConsegnaMessaggio.Stato.IN_ATTESA
    ).delete()
    registra(Azione.ANNULLAMENTO, invio, utente=utente)
    return invio


# --- invio dei messaggi ------------------------------------------------------------------------


def contesto_destinatario(invio, destinatario):
    """Segnaposto risolti per un destinatario: dati generali, dell'invio e della persona."""
    contesto = {**contesto_generale(), **invio.contesto}
    if destinatario.soggetto_id:
        contesto.update(contesto_soggetto(destinatario.soggetto))
    else:
        contesto.update(
            {"nome": destinatario.nome, "nome_completo": destinatario.nome, "saluto": "Gentile"}
        )
    contesto.update(destinatario.contesto)
    return contesto


def servizio_per(invio, destinatario):
    """Servizio da cui parte il messaggio (None: server generale): la PEC scelta per chi ha la
    PEC; per l'email il servizio scelto se è un'email, altrimenti il generale."""
    servizio = invio.servizio
    if servizio is None:
        return None
    if servizio.pec:
        return servizio if destinatario.canale == Destinatario.Canale.PEC else None
    return servizio


def messaggio(invio, destinatario, org=None):
    org = org or Organizzazione.corrente()
    contesto = contesto_destinatario(invio, destinatario)
    oggetto = " ".join(componi(invio.oggetto, contesto).split())
    testo = componi(invio.corpo, contesto)
    piede = render_to_string(
        "comunicazioni/email/piede.txt", {"organizzazione": org, "finalita": invio.finalita}
    )
    html = render_to_string(
        "comunicazioni/email/messaggio.html",
        {"testo": testo, "organizzazione": org, "piede": piede},
    )
    servizio = servizio_per(invio, destinatario)
    pec = servizio is not None and servizio.pec
    intestazioni = {"X-Gestione-Invio": str(invio.pk)}
    mittente = None  # quello del server generale
    if servizio is not None:
        from email.utils import make_msgid

        from apps.core import invio as servizi_invio

        mittente = servizi_invio.mittente(servizio, org)
        intestazioni["Message-ID"] = make_msgid(domain=servizio.indirizzo.rsplit("@")[-1])
    email = EmailMultiAlternatives(
        subject=oggetto,
        body=f"{testo}\n\n-- \n{piede}",
        from_email=mittente,
        to=[
            f"{destinatario.nome} <{destinatario.email}>"
            if destinatario.nome
            else destinatario.email
        ],
        reply_to=[org.email] if org.email and not pec else None,
        headers=intestazioni,
    )
    email.attach_alternative(html, "text/html")
    for a in invio.allegati.all():
        with a.file.open("rb") as f:
            email.attach(a.nome, f.read(), a.tipo)
    return email


def invio_attivo():
    """Interruttore generale dell'invio delle email (Sistema -> Servizi di posta)."""
    return Organizzazione.corrente().invio_email


def elabora_coda(limite=None, invio=None):
    """Invia i messaggi in attesa degli invii in coda. Restituisce (inviati, errori)."""
    if not invio_attivo():
        return 0, 0  # i messaggi restano in coda fino alla riattivazione
    limite = limite or settings.COMUNICAZIONI_LOTTO
    adesso = timezone.now()
    invii = Invio.objects.filter(stato=Invio.Stato.IN_CODA).exclude(programmato_il__gt=adesso)
    if invio is not None:
        invii = invii.filter(pk=invio.pk)
    inviati = errori = 0
    org = Organizzazione.corrente()
    for inv in invii.order_by("confermato_il"):
        connessioni = {}
        for d in inv.destinatari.filter(stato=Destinatario.Stato.IN_ATTESA).select_related(
            "soggetto__socio"
        ):
            if inviati + errori >= limite:
                return inviati, errori
            try:
                email = messaggio(inv, d, org)
                servizio = servizio_per(inv, d)
                if servizio not in connessioni:
                    from apps.core import invio as servizi_invio

                    connessioni[servizio] = servizi_invio.connessione(servizio)
                if connessioni[servizio].send_messages([email]) != 1:
                    raise OperazioneNonValida("Il server non ha accettato il messaggio.")
                d.message_id = email.extra_headers.get("Message-ID", "")[:255]
            except Exception as e:  # noqa: BLE001 - l'errore resta sul destinatario
                d.tentativi += 1
                d.motivo = str(e)[:255]
                if d.tentativi >= MAX_TENTATIVI:
                    d.stato = Destinatario.Stato.ERRORE
                d.save(update_fields=["tentativi", "motivo", "stato"])
                errori += 1
                log.warning("Invio %s a %s non riuscito: %s", inv.pk, d.email, e)
                continue
            d.stato = Destinatario.Stato.INVIATO
            d.inviato_il = timezone.now()
            d.motivo = ""
            d.save(update_fields=["stato", "inviato_il", "motivo", "message_id"])
            inviati += 1
        if inv.telegram:
            from . import telegram

            fatti, falliti = telegram.invia_coda(inv, limite - inviati - errori)
            inviati, errori = inviati + fatti, errori + falliti
            if inviati + errori >= limite:
                return inviati, errori
        if inv.sms or inv.whatsapp:
            from . import messaggi

            fatti, falliti = messaggi.invia_coda(inv, limite - inviati - errori)
            inviati, errori = inviati + fatti, errori + falliti
            if inviati + errori >= limite:
                return inviati, errori
        _concludi_se_finito(inv)
    return inviati, errori


# ricevute PEC: un esito non torna indietro (la consegna vale sempre)
_PESO_RICEVUTE = {
    "accettazione": 1, "presa-in-carico": 1, "non-accettazione": 2, "preavviso-errore-consegna": 2,
    "errore-consegna": 2, "rilevazione-virus": 2, "avvenuta-consegna": 3,
}  # fmt: skip


def applica_ricevuta_pec(riferimento, tipo):
    """Aggancia una ricevuta PEC (X-Riferimento-Message-ID) a una comunicazione: il destinatario,
    oppure None se non è di una comunicazione."""
    d = (
        Destinatario.objects.select_related("invio")
        .filter(canale=Destinatario.Canale.PEC, message_id=riferimento)
        .exclude(message_id="")
        .first()
    )
    if d is None:
        return None
    if _PESO_RICEVUTE.get(tipo, 0) >= _PESO_RICEVUTE.get(d.esito_pec, 0):
        d.esito_pec = tipo
        d.save(update_fields=["esito_pec"])
    return d


def _concludi_se_finito(invio):
    if invio.destinatari.filter(
        Q(stato=Destinatario.Stato.IN_ATTESA)
        | Q(telegram_stato="in_attesa")
        | Q(consegne__stato=ConsegnaMessaggio.Stato.IN_ATTESA)
    ).exists():
        return
    errori = invio.destinatari.filter(
        Q(stato=Destinatario.Stato.ERRORE)
        | Q(telegram_stato="errore")
        | Q(consegne__stato=ConsegnaMessaggio.Stato.ERRORE)
    ).exists()
    invio.stato = Invio.Stato.CON_ERRORI if errori else Invio.Stato.INVIATO
    invio.completato_il = timezone.now()
    invio.save(update_fields=["stato", "completato_il"])
    if invio.protocolla and invio.protocollo_id is None:
        try:
            invio.protocollo = _protocolla(invio)
            invio.save(update_fields=["protocollo"])
        except Exception:  # noqa: BLE001 - l'invio è fatto, la protocollazione si può rifare
            log.exception("Protocollazione dell'invio %s non riuscita", invio.pk)
    registra(
        Azione.MODIFICA,
        invio,
        utente=None,
        concluso=invio.get_stato_display(),
        inviati=invio.destinatari.filter(stato=Destinatario.Stato.INVIATO).count(),
    )


def _protocolla(invio):
    from apps.protocollo import servizi as protocollo
    from apps.protocollo.models import Protocollo

    destinatari = [
        protocollo.corrispondente_da_soggetto(d.soggetto, "destinatario")
        if d.soggetto
        else {"ruolo": "destinatario", "descrizione": d.nome, "indirizzo": d.email}
        for d in invio.destinatari.filter(stato=Destinatario.Stato.INVIATO).select_related(
            "soggetto"
        )
    ]
    p = protocollo.registra_protocollo(
        {
            "direzione": Protocollo.Direzione.USCITA,
            "mezzo": Protocollo.Mezzo.PEC
            if invio.servizio_id and invio.servizio.pec
            else Protocollo.Mezzo.EMAIL,
            "oggetto": invio.oggetto[:500],
        },
        destinatari,
        invio.creato_da,
    )
    testo = f"Oggetto: {invio.oggetto}\n\n{invio.corpo}".encode()
    protocollo.aggiungi_allegato(
        p,
        ContentFile(testo, name="comunicazione.txt"),
        invio.creato_da,
        principale=True,
        controlla=False,
    )
    for a in invio.allegati.all():
        with a.file.open("rb") as f:
            protocollo.aggiungi_allegato(
                p, ContentFile(f.read(), name=a.nome), invio.creato_da, controlla=False
            )
    return p


# --- auguri automatici -------------------------------------------------------------------------


def _modello(uso):
    return Modello.objects.filter(uso=uso, attivo=True).order_by("pk").first()


def auguri_del_giorno(oggi=None, adesso=None):
    """Prepara e mette in coda gli auguri automatici di oggi (rieseguibile senza doppioni)."""
    from apps.soci.models import Socio

    if not invio_attivo():
        return []  # niente auguri preparati: partirebbero in ritardo alla riattivazione
    oggi = oggi or timezone.localdate()
    ora = (adesso or timezone.localtime()).hour
    creati = []
    for auto in Automazione.objects.filter(attiva=True):
        if auto.ultimo_giorno == oggi or ora < auto.ora:
            continue
        modello = auto.modello or _modello(auto.tipo)
        if modello is None:
            log.warning("Auguri %s: nessun modello", auto.tipo)
            continue
        if auto.tipo == Automazione.Tipo.ANZIANITA:
            eventi = anniversari.anzianita(oggi, oggi, auto.anni_scelti())
        else:
            calcolo = {"compleanno": anniversari.compleanni, "onomastico": anniversari.onomastici}
            eventi = calcolo[auto.tipo](oggi, oggi)
        eventi = [e for e in eventi if e.soggetto is not None]
        if auto.destinatari == Automazione.Destinatari.SOCI:
            soci = set(Socio.objects.attivi().values_list("soggetto_id", flat=True))
            eventi = [e for e in eventi if e.soggetto.pk in soci]
        nuovi = []
        for e in eventi:
            try:
                with transaction.atomic():
                    DestinatarioRegistrato.objects.create(
                        automazione=auto.tipo, soggetto=e.soggetto, giorno=oggi
                    )
                nuovi.append(e)
            except IntegrityError:
                continue
        if nuovi:
            invio = crea_invio(
                None,
                oggetto=modello.oggetto,
                corpo=modello.corpo,
                finalita=Finalita.AUGURI,
                soggetti=[e.soggetto for e in nuovi],
                modello=modello,
                origine=f"auguri:{auto.tipo}",
                contesti_soggetto={e.soggetto.pk: {"anni": e.anni} for e in nuovi if e.anni},
            )
            DestinatarioRegistrato.objects.filter(
                automazione=auto.tipo, giorno=oggi, soggetto__in=[e.soggetto for e in nuovi]
            ).update(invio=invio)
            if invio.destinatari.filter(stato=Destinatario.Stato.IN_ATTESA).exists():
                invio = conferma(invio, None)
            else:
                invio.stato = Invio.Stato.ANNULLATO
                invio.save(update_fields=["stato"])
            creati.append(invio)
        auto.ultimo_giorno = oggi
        auto.save(update_fields=["ultimo_giorno"])
    creati += _ricorrenze_del_giorno(oggi)
    return creati


def _euro(valore):
    return f"{valore:.2f}".replace(".", ",")


def soci_da_sollecitare(anno):
    """Soci attivi non in regola con la quota dell'anno: (socio, contesto del messaggio)."""
    from apps.soci.models import Socio, Tessera
    from apps.soci.servizi import quota_per

    soci = Socio.objects.morosi(anno).select_related("soggetto", "tipologia")
    tessere = {
        t.socio_id: t
        for t in Tessera.objects.valide().filter(anno=anno, socio__in=soci, pagata_il__isnull=True)
    }
    elenco = []
    for socio in soci:
        tessera = tessere.get(socio.pk)
        importo = tessera.importo if tessera else quota_per(socio.tipologia, anno)
        contesto = {"anno_quota": anno, "importo": _euro(importo)}
        if tessera and tessera.codice:
            contesto["tessera"] = tessera.codice
        elenco.append((socio, contesto))
    return elenco


def promemoria_rinnovo(oggi=None, adesso=None, *, utente=None, subito=False):
    """Promemoria ai soci non in regola. Dal pianificatore (subito=False) parte solo nelle date
    impostate, dopo l'ora indicata, una volta al giorno, ed è confermato; con `subito` prepara
    un invio in bozza da controllare. Nessuno lo riceve due volte nello stesso giorno."""
    if not subito and not invio_attivo():
        return None
    conf = PromemoriaRinnovo.corrente()
    oggi = oggi or timezone.localdate()
    ora = (adesso or timezone.localtime()).hour
    if not subito and (
        not conf.attivo
        or conf.ultimo_giorno == oggi
        or ora < conf.ora
        or (oggi.day, oggi.month) not in conf.date_scelte()
    ):
        return None
    modello = conf.modello or _modello(Modello.Uso.RINNOVO)
    if modello is None:
        if subito:
            raise OperazioneNonValida("Manca un modello di promemoria di rinnovo attivo.")
        log.warning("Promemoria di rinnovo: nessun modello")
        return None
    chiave = f"rinnovo-{oggi.year}"
    nuovi = []
    for socio, contesto in soci_da_sollecitare(oggi.year):
        try:
            with transaction.atomic():
                DestinatarioRegistrato.objects.create(
                    automazione=chiave, soggetto=socio.soggetto, giorno=oggi
                )
            nuovi.append((socio.soggetto, contesto))
        except IntegrityError:
            continue
    if not subito:
        conf.ultimo_giorno = oggi
        conf.save(update_fields=["ultimo_giorno"])
    if not nuovi:
        if subito:
            raise OperazioneNonValida(
                "Nessun socio da sollecitare oggi: sono tutti in regola o hanno già ricevuto "
                "il promemoria in giornata."
            )
        return None
    invio = crea_invio(
        utente,
        oggetto=modello.oggetto,
        corpo=modello.corpo,
        finalita=Finalita.ISTITUZIONALE,
        soggetti=[s for s, _c in nuovi],
        modello=modello,
        origine="rinnovo",
        contesti_soggetto={s.pk: c for s, c in nuovi},
    )
    DestinatarioRegistrato.objects.filter(
        automazione=chiave, giorno=oggi, soggetto__in=[s for s, _c in nuovi]
    ).update(invio=invio)
    if subito:
        return invio
    if invio.destinatari.filter(stato=Destinatario.Stato.IN_ATTESA).exists():
        return conferma(invio, None)
    invio.stato = Invio.Stato.ANNULLATO
    invio.save(update_fields=["stato"])
    return invio


def _ricorrenze_del_giorno(oggi):
    creati = []
    for r in Ricorrenza.objects.filter(
        attiva=True, invio_automatico=True, giorno=oggi.day, mese=oggi.month
    ):
        if (
            r.lista is None
            or Invio.objects.filter(
                origine="ricorrenza", origine_id=r.pk, creato_il__date=oggi
            ).exists()
        ):
            continue
        modello = r.modello or _modello(Modello.Uso.RICORRENZA)
        if modello is None:
            continue
        anni = oggi.year - r.anno_inizio if r.anno_inizio else ""
        invio = crea_invio(
            None, oggetto=modello.oggetto, corpo=modello.corpo, finalita=Finalita.COMUNICAZIONI,
            soggetti=list(soggetti_lista(r.lista)), modello=modello, origine="ricorrenza",
            origine_id=r.pk, contesto={"ricorrenza": r.nome, "anni": anni},
        )  # fmt: skip
        if invio.destinatari.filter(stato=Destinatario.Stato.IN_ATTESA).exists():
            invio = conferma(invio, None)
        creati.append(invio)
    return creati


# --- invii collegati ad altri moduli -----------------------------------------------------------


def da_riunione(riunione, utente):
    from apps.organi import servizi as organi

    modello = _modello(Modello.Uso.CONVOCAZIONE)
    if modello is None:
        raise OperazioneNonValida("Manca un modello di convocazione attivo.")
    quando = timezone.localtime(riunione.prima_convocazione)
    return crea_invio(
        utente,
        oggetto=modello.oggetto,
        corpo=modello.corpo,
        finalita=Finalita.ISTITUZIONALE,
        soggetti=[s for s, _, _ in organi.aventi_diritto(riunione)],
        modello=modello,
        allegati=[("convocazione.pdf", organi.pdf_convocazione(riunione))],
        origine="riunione",
        origine_id=riunione.pk,
        contesto={
            "riunione": riunione.titolo,
            "data_riunione": quando.strftime("%d/%m/%Y alle ore %H:%M"),
            "luogo_riunione": riunione.luogo,
            "ordine_del_giorno": "\n".join(f"{p.ordine}. {p.titolo}" for p in riunione.punti.all()),
        },
    )


def da_tessera(tessera, utente):
    from apps.core.pdf import genera_pdf

    if not tessera.pagata:
        raise OperazioneNonValida("La quota non risulta pagata.")
    modello = _modello(Modello.Uso.RICEVUTA)
    if modello is None:
        raise OperazioneNonValida("Manca un modello di ricevuta attivo.")
    pdf = genera_pdf(
        "soci/pdf/ricevuta.html",
        {"tessera": tessera, "organizzazione": Organizzazione.corrente(), "oggi": date.today()},
    )
    return crea_invio(
        utente,
        oggetto=modello.oggetto,
        corpo=modello.corpo,
        finalita=Finalita.ISTITUZIONALE,
        soggetti=[tessera.socio.soggetto],
        modello=modello,
        allegati=[(f"ricevuta_{tessera.codice_ricevuta.replace('/', '_')}.pdf", pdf)],
        origine="tessera",
        origine_id=tessera.pk,
        contesto={
            "anno_quota": tessera.anno,
            "importo": f"{tessera.importo:.2f}".replace(".", ","),
            "ricevuta": tessera.codice_ricevuta,
            "tessera": tessera.codice,
        },
    )


def da_tessera_digitale(tessera, utente, base_url):
    """Invio (in bozza) della tessera digitale in PDF, con il QR di verifica."""
    from apps.soci import tessera_digitale

    if tessera.annullata:
        raise OperazioneNonValida("La tessera è annullata.")
    if not tessera.attribuita:
        raise OperazioneNonValida("Alla tessera non è ancora attribuito un numero.")
    modello = _modello(Modello.Uso.TESSERA)
    if modello is None:
        raise OperazioneNonValida("Manca un modello attivo per la tessera digitale.")
    pdf = tessera_digitale.pdf(tessera, utente, base_url)
    return crea_invio(
        utente,
        oggetto=modello.oggetto,
        corpo=modello.corpo,
        finalita=Finalita.ISTITUZIONALE,
        soggetti=[tessera.socio.soggetto],
        modello=modello,
        allegati=[(tessera_digitale.nome_file(tessera), pdf)],
        origine="tessera_digitale",
        origine_id=tessera.pk,
        contesto={"anno_quota": tessera.anno, "tessera": tessera.codice},
    )


def da_domanda(domanda, utente):
    if domanda.stato == "in_attesa":
        raise OperazioneNonValida("La domanda non è ancora stata valutata.")
    modello = _modello(Modello.Uso.DOMANDA)
    if modello is None:
        raise OperazioneNonValida("Manca un modello per l'esito delle domande.")
    esito = "accolta" if domanda.stato == "accolta" else f"respinta ({domanda.esito_note})"
    contesto = {"esito": esito}
    if domanda.socio:
        contesto["numero_socio"] = domanda.socio.numero
        return crea_invio(
            utente, oggetto=modello.oggetto, corpo=modello.corpo, finalita=Finalita.ISTITUZIONALE,
            soggetti=[domanda.socio.soggetto], modello=modello, origine="domanda",
            origine_id=domanda.pk, contesto=contesto,
        )  # fmt: skip
    return crea_invio(
        utente, oggetto=modello.oggetto, corpo=modello.corpo, finalita=Finalita.ISTITUZIONALE,
        indirizzi=[(f"{domanda.nome} {domanda.cognome}", domanda.email)], modello=modello,
        origine="domanda", origine_id=domanda.pk, contesto={**contesto, "nome": domanda.nome},
    )  # fmt: skip


ORIGINE_RICEZIONE = "ricezione_domanda"


def conferma_ricezione_domanda(domanda, utente, *, nome, email):
    """Mette in coda la conferma di ricezione di una domanda di iscrizione (finalità
    istituzionale, nessun consenso). Rieseguibile: se è già stata preparata non la ripete.
    Parte con la coda delle email (se l'invio è spento resta in attesa)."""
    if not email:
        raise OperazioneNonValida("Manca l'indirizzo email a cui confermare la ricezione.")
    gia = Invio.objects.filter(origine=ORIGINE_RICEZIONE, origine_id=domanda.pk).exclude(
        stato=Invio.Stato.ANNULLATO
    )
    if invio := gia.first():
        return invio
    modello = _modello(Modello.Uso.RICEZIONE)
    if modello is None:
        raise OperazioneNonValida(
            "Manca un modello attivo per la conferma di ricezione (Comunicazioni → Modelli)."
        )
    contesto = {"richiedente": f"{domanda.nome} {domanda.cognome}".strip()}
    if domanda.protocollo_id:
        contesto["protocollo"] = domanda.protocollo.segnatura
        contesto["data_protocollo"] = timezone.localtime(domanda.protocollo.registrato_il).strftime(
            "%d/%m/%Y"
        )
    invio = crea_invio(
        utente, oggetto=modello.oggetto, corpo=modello.corpo, finalita=Finalita.ISTITUZIONALE,
        indirizzi=[(nome or email, email)], modello=modello, origine=ORIGINE_RICEZIONE,
        origine_id=domanda.pk, contesto=contesto,
    )  # fmt: skip
    return conferma(invio, utente)


def prossimi_anniversari(giorni=7):
    return anniversari.eventi(giorni=giorni)


def invii_di(origine, origine_id):
    return Invio.objects.filter(origine=origine, origine_id=origine_id).order_by("-creato_il")
