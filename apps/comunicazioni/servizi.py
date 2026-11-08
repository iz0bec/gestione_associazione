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
from django.template.loader import render_to_string
from django.utils import timezone

from apps.anagrafica.models import Consenso, Soggetto
from apps.core.audit import Azione, registra
from apps.core.models import Organizzazione

from . import anniversari
from .models import (
    AllegatoInvio,
    Automazione,
    Destinatario,
    DestinatarioRegistrato,
    Finalita,
    Invio,
    Modello,
    Ricorrenza,
)

log = logging.getLogger(__name__)

MAX_TENTATIVI = 3

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


def motivo_esclusione(soggetto, finalita, con_consenso):
    if not soggetto.attivo:
        return "scheda archiviata"
    if soggetto.deceduto:
        return "deceduto"
    if not soggetto.email:
        return "senza email"
    if finalita != Finalita.ISTITUZIONALE and soggetto.pk not in con_consenso:
        return "consenso non prestato"
    return ""


def soggetti_lista(lista, anno=None):
    from apps.soci.models import Socio

    anno = anno or timezone.localdate().year
    ids = set(lista.soggetti.values_list("pk", flat=True))
    ids |= set(
        Soggetto.objects.filter(categorie__in=lista.categorie.all()).values_list("pk", flat=True)
    )
    if lista.soci_attivi or lista.soci_in_regola:
        soci = Socio.objects.attivi()
        if lista.soci_in_regola:
            soci = soci.in_regola(anno)
        ids |= set(soci.values_list("soggetto_id", flat=True))
    if lista.organo_id:
        ids |= set(lista.organo.cariche_al().values_list("soggetto_id", flat=True))
    return Soggetto.objects.filter(pk__in=ids)


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
):
    """Prepara un invio in bozza con i destinatari (i non raggiungibili esclusi, con il motivo).

    `allegati`: lista di (nome, bytes); `contesti_soggetto`: {soggetto_id: {segnaposto: valore}}.
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
    invio = Invio.objects.create(
        oggetto=oggetto.strip(), corpo=corpo, finalita=finalita, modello=modello,
        protocolla=protocolla, programmato_il=programmato_il, origine=origine,
        origine_id=origine_id, contesto=contesto or {}, creato_da=utente, modificato_da=utente,
    )  # fmt: skip
    con_consenso = (
        consensi_prestati(soggetti, finalita) if finalita != Finalita.ISTITUZIONALE else set()
    )
    contesti_soggetto = contesti_soggetto or {}
    righe = []
    for s in sorted(soggetti, key=lambda x: x.nome_completo):
        motivo = motivo_esclusione(s, finalita, con_consenso)
        righe.append(
            Destinatario(
                invio=invio,
                soggetto=s,
                nome=s.nome_completo[:200],
                email=s.email,
                stato=Destinatario.Stato.ESCLUSO if motivo else Destinatario.Stato.IN_ATTESA,
                motivo=motivo,
                contesto=dict(contesti_soggetto.get(s.pk, {})),
            )  # fmt: skip
        )
    gia = {s.email.lower() for s in soggetti if s.email}
    for nome, email in indirizzi:
        if email not in gia:
            righe.append(Destinatario(invio=invio, nome=nome[:200], email=email))
            gia.add(email)
    Destinatario.objects.bulk_create(righe)
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
    if not invio.destinatari.filter(stato=Destinatario.Stato.IN_ATTESA).exists():
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
    registra(Azione.ANNULLAMENTO, invio, utente=utente)
    return invio


# --- invio dei messaggi ------------------------------------------------------------------------


def messaggio(invio, destinatario, org=None):
    org = org or Organizzazione.corrente()
    contesto = {**contesto_generale(), **invio.contesto}
    if destinatario.soggetto_id:
        contesto.update(contesto_soggetto(destinatario.soggetto))
    else:
        contesto.update(
            {"nome": destinatario.nome, "nome_completo": destinatario.nome, "saluto": "Gentile"}
        )
    contesto.update(destinatario.contesto)
    oggetto = " ".join(componi(invio.oggetto, contesto).split())
    testo = componi(invio.corpo, contesto)
    piede = render_to_string(
        "comunicazioni/email/piede.txt", {"organizzazione": org, "finalita": invio.finalita}
    )
    html = render_to_string(
        "comunicazioni/email/messaggio.html",
        {"testo": testo, "organizzazione": org, "piede": piede},
    )
    email = EmailMultiAlternatives(
        subject=oggetto,
        body=f"{testo}\n\n-- \n{piede}",
        to=[
            f"{destinatario.nome} <{destinatario.email}>"
            if destinatario.nome
            else destinatario.email
        ],
        reply_to=[org.email] if org.email else None,
        headers={"X-Gestione-Invio": str(invio.pk)},
    )
    email.attach_alternative(html, "text/html")
    for a in invio.allegati.all():
        with a.file.open("rb") as f:
            email.attach(a.nome, f.read(), a.tipo)
    return email


def elabora_coda(limite=None, invio=None):
    """Invia i messaggi in attesa degli invii in coda. Restituisce (inviati, errori)."""
    limite = limite or settings.COMUNICAZIONI_LOTTO
    adesso = timezone.now()
    invii = Invio.objects.filter(stato=Invio.Stato.IN_CODA).exclude(programmato_il__gt=adesso)
    if invio is not None:
        invii = invii.filter(pk=invio.pk)
    inviati = errori = 0
    org = Organizzazione.corrente()
    for inv in invii.order_by("confermato_il"):
        for d in inv.destinatari.filter(stato=Destinatario.Stato.IN_ATTESA).select_related(
            "soggetto__socio"
        ):
            if inviati + errori >= limite:
                return inviati, errori
            try:
                messaggio(inv, d, org).send()
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
            d.save(update_fields=["stato", "inviato_il", "motivo"])
            inviati += 1
        _concludi_se_finito(inv)
    return inviati, errori


def _concludi_se_finito(invio):
    if invio.destinatari.filter(stato=Destinatario.Stato.IN_ATTESA).exists():
        return
    errori = invio.destinatari.filter(stato=Destinatario.Stato.ERRORE).exists()
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
            "mezzo": Protocollo.Mezzo.EMAIL,
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


def prossimi_anniversari(giorni=7):
    return anniversari.eventi(giorni=giorni)


def invii_di(origine, origine_id):
    return Invio.objects.filter(origine=origine, origine_id=origine_id).order_by("-creato_il")
