# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Spedizione per email o PEC dei protocolli in uscita: preparazione, coda,
# *              invio (un messaggio per destinatario, dal servizio di invio scelto in
# *              Sistema → Servizi di posta) e aggancio delle ricevute PEC.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import contextlib
import logging
from email.utils import formataddr, make_msgid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.mail import EmailMessage
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone

from apps.core import invio
from apps.core.audit import Azione, registra
from apps.core.models import Organizzazione

from .models import DestinatarioSpedizione, Protocollo, Spedizione
from .servizi import OperazioneNonValida, aggiungi_allegato

log = logging.getLogger(__name__)

PERMESSO = "protocollo.spedisci_protocollo"
MAX_TENTATIVI = 3
Stato = DestinatarioSpedizione.Stato

# intestazione X-Ricevuta delle ricevute PEC (regole tecniche, DPR 68/2005)
RICEVUTE = {
    "accettazione": Stato.ACCETTATO,
    "non-accettazione": Stato.NON_ACCETTATO,
    "presa-in-carico": None,
    "avvenuta-consegna": Stato.CONSEGNATO,
    "errore-consegna": Stato.NON_CONSEGNATO,
    "preavviso-errore-consegna": Stato.NON_CONSEGNATO,
    "rilevazione-virus": Stato.NON_CONSEGNATO,
}
# un esito non torna indietro: una consegna vale sempre, gli altri esiti finali non si scavalcano
_PESO = {
    Stato.IN_ATTESA: 0, Stato.ERRORE: 0, Stato.INVIATO: 1, Stato.ACCETTATO: 2,
    Stato.NON_ACCETTATO: 3, Stato.NON_CONSEGNATO: 3, Stato.CONSEGNATO: 4,
}  # fmt: skip


def servizio_proposto(protocollo, servizi):
    """Servizio proposto in «Spedisci da», fra quelli attivi:

    1. per la risposta a un messaggio scaricato, il «Rispondi con» della casella di arrivo;
    2. con mezzo PEC, il primo servizio PEC;
    3. il server generale (None: quello del .env).
    """
    from .models import MessaggioRicevuto

    if protocollo.risposta_a_id:
        arrivo = (
            MessaggioRicevuto.objects.filter(protocollo_id=protocollo.risposta_a_id)
            .select_related("casella__servizio_risposta")
            .first()
        )
        risposta = arrivo.casella.servizio_per_risposte() if arrivo else None
        if risposta is not None and risposta in servizi:
            return risposta
    if protocollo.mezzo == Protocollo.Mezzo.PEC:
        pec = next((s for s in servizi if s.pec), None)
        if pec is not None:
            return pec
    return next((s for s in servizi if s.generale), None)


def puo_spedire(protocollo):
    return protocollo.direzione == Protocollo.Direzione.USCITA and not protocollo.annullato


def _email_valida(indirizzo):
    try:
        validate_email(indirizzo)
    except ValidationError:
        return False
    return True


# parti del dominio tipiche dei gestori PEC (pec.aruba.it, legalmail.it, cert.legalmail.it...)
_DOMINI_PEC = {"legalmail", "postacert", "cert", "arubapec", "sicurezzapostale", "gigapec"}


def sembra_pec(indirizzo, corrispondente=None):
    """L'indirizzo è (probabilmente) una PEC: lo dice l'anagrafica o il dominio."""
    indirizzo = (indirizzo or "").strip().lower()
    soggetto = getattr(corrispondente, "soggetto", None)
    if soggetto is not None and soggetto.pec and soggetto.pec.strip().lower() == indirizzo:
        return True
    dominio = indirizzo.rsplit("@", 1)[-1] if "@" in indirizzo else ""
    return any(p.startswith("pec") or p in _DOMINI_PEC for p in dominio.split(".")[:-1])


def controllo_canale(protocollo, servizio, destinatari):
    """Motivo per cui un'email ordinaria non va spedita (protocollo per PEC o destinatari PEC),
    altrimenti stringa vuota. Una PEC che riceve un'email ordinaria la consegna come «anomalia»,
    senza valore legale."""
    if servizio is not None and servizio.pec:
        return ""
    pec = [i for c, _, i in destinatari if sembra_pec(i, c)]
    if pec:
        elenco = ", ".join(pec[:3]) + ("…" if len(pec) > 3 else "")
        return (f"{elenco}: {'è un indirizzo' if len(pec) == 1 else 'sono indirizzi'} PEC, ma il "
                "servizio scelto spedisce un'email ordinaria: arriverebbe come «anomalia», senza "
                "valore legale.")  # fmt: skip
    if protocollo.mezzo == Protocollo.Mezzo.PEC:
        return ("Il protocollo è registrato con mezzo PEC, ma il servizio scelto spedisce "
                "un'email ordinaria.")  # fmt: skip
    return ""


def indirizzi_proposti(protocollo, pec=False):
    """Un indirizzo per destinatario: prima quello del canale (PEC o email) in anagrafica,
    poi quello registrato nel protocollo, poi l'altro. Vuoto se non ce n'è uno valido."""
    proposti = []
    for c in protocollo.destinatari:
        s = c.soggetto
        candidati = [
            (s.pec if pec else s.email) if s else "",
            c.indirizzo,
            (s.email if pec else s.pec) if s else "",
        ]
        indirizzo = next((i.strip() for i in candidati if i and _email_valida(i.strip())), "")
        proposti.append({"corrispondente": c, "nome": c.descrizione, "indirizzo": indirizzo})
    return proposti


def oggetto_messaggio(protocollo):
    data = timezone.localtime(protocollo.registrato_il)
    return f"Prot. n. {protocollo.segnatura} del {data:%d/%m/%Y} - {protocollo.oggetto}"[:600]


def testo_proposto(protocollo, org=None):
    if protocollo.testo.strip():
        return protocollo.testo
    org = org or Organizzazione.corrente()
    data = timezone.localtime(protocollo.registrato_il)
    return (
        f"Si trasmette in allegato il documento protocollato al n. {protocollo.segnatura} "
        f"del {data:%d/%m/%Y}, avente per oggetto: {protocollo.oggetto}.\n\n"
        f"Distinti saluti.\n\n{org.denominazione}"
    )


def mittente_generale():
    """Indirizzo del server generale: il servizio generale o, senza, DEFAULT_FROM_EMAIL."""
    servizio = invio.servizio_generale()
    return servizio.indirizzo if servizio else invio.mittente_env()[1]


@transaction.atomic
def prepara_spedizione(
    protocollo, utente, *, servizio, destinatari, testo, allegati, email_ordinaria=False
):
    """Mette in coda la spedizione. `destinatari`: lista di (corrispondente o None, nome,
    indirizzo); `servizio`: ServizioInvio, None per il server generale; `email_ordinaria`:
    conferma di spedire un'email ordinaria anche a indirizzi PEC o per un protocollo PEC."""
    if utente is not None and not utente.has_perm(PERMESSO):
        raise OperazioneNonValida("Non hai il permesso di spedire i protocolli.")
    protocollo = Protocollo.objects.select_for_update().get(pk=protocollo.pk)
    if protocollo.annullato:
        raise OperazioneNonValida("Il protocollo è annullato.")
    if protocollo.direzione != Protocollo.Direzione.USCITA:
        raise OperazioneNonValida("Si spediscono solo i protocolli in uscita.")
    if servizio is None:
        servizio = invio.servizio_generale()
    elif not servizio.attivo:
        raise OperazioneNonValida(f"Il servizio di invio «{servizio}» è disattivato.")
    if servizio is not None and not servizio.password_cifrata:
        raise OperazioneNonValida(f"Il servizio di invio «{servizio}»: manca la password.")
    if not (testo or "").strip():
        raise OperazioneNonValida("Il testo del messaggio è obbligatorio.")
    righe, visti = [], set()
    for corrispondente, nome, indirizzo in destinatari:
        indirizzo = (indirizzo or "").strip()
        if not _email_valida(indirizzo):
            raise OperazioneNonValida(f"«{nome}»: indirizzo non valido ({indirizzo or 'vuoto'}).")
        if indirizzo.lower() in visti:
            continue
        visti.add(indirizzo.lower())
        righe.append((corrispondente, nome, indirizzo))
    if not righe:
        raise OperazioneNonValida("Scegliere almeno un destinatario.")
    if not email_ordinaria and (motivo := controllo_canale(protocollo, servizio, righe)):
        raise OperazioneNonValida(
            f"{motivo} Scegliere il servizio PEC, oppure spuntare «Spedisci comunque come email "
            "ordinaria»."
        )
    allegati = list(allegati)
    if any(a.protocollo_id != protocollo.pk for a in allegati):
        raise OperazioneNonValida("Documento non appartenente al protocollo.")
    massimo = settings.PROTOCOLLO_SPEDIZIONE_MAX_MB * 1024 * 1024
    if sum(a.dimensione for a in allegati) > massimo:
        raise OperazioneNonValida(
            f"I documenti scelti superano {settings.PROTOCOLLO_SPEDIZIONE_MAX_MB} MB: "
            "il messaggio verrebbe rifiutato dal server."
        )
    spedizione = Spedizione.objects.create(
        protocollo=protocollo,
        canale=Spedizione.Canale.PEC if servizio and servizio.pec else Spedizione.Canale.EMAIL,
        servizio=servizio,
        mittente=servizio.indirizzo if servizio else mittente_generale(),
        oggetto=oggetto_messaggio(protocollo),
        testo=testo.strip(),
        creato_da=utente,
        modificato_da=utente,
    )
    spedizione.allegati.set(allegati)
    DestinatarioSpedizione.objects.bulk_create(
        DestinatarioSpedizione(
            spedizione=spedizione, corrispondente=c, nome=nome[:300], indirizzo=indirizzo
        )
        for c, nome, indirizzo in righe
    )
    registra(
        Azione.MODIFICA,
        protocollo,
        utente=utente,
        descrizione=f"Protocollo {protocollo.segnatura}",
        spedizione=spedizione.get_canale_display(),
        da=spedizione.mittente,
        destinatari=[i for _, _, i in righe],
        documenti=[a.nome for a in allegati],
    )
    return spedizione


# --- invio -------------------------------------------------------------------------------------


def _connessione(servizio):
    return invio.connessione(servizio)


def messaggio(spedizione, destinatario, org=None):
    org = org or Organizzazione.corrente()
    dominio = spedizione.mittente.rsplit("@", 1)[-1] if "@" in spedizione.mittente else None
    message_id = make_msgid(domain=dominio)
    servizio = spedizione.servizio
    nome = (servizio.nome_mittente if servizio else "") or org.denominazione
    risposte = (
        [org.email]
        if spedizione.canale == Spedizione.Canale.EMAIL
        and org.email
        and org.email.lower() != spedizione.mittente.lower()
        else None
    )
    email = EmailMessage(
        subject=spedizione.oggetto,
        body=spedizione.testo,
        from_email=formataddr((nome, spedizione.mittente)),
        to=[formataddr((destinatario.nome, destinatario.indirizzo))],
        reply_to=risposte,
        headers={
            "Message-ID": message_id,
            "X-Gestione-Protocollo": spedizione.protocollo.segnatura,
        },
    )
    for a in spedizione.allegati.all():
        with a.file.open("rb") as f:
            email.attach(a.nome, f.read(), a.tipo)
    return email, message_id


def invio_attivo():
    """Stesso interruttore delle comunicazioni (Sistema -> Servizi di posta)."""
    return Organizzazione.corrente().invio_email


def spedisci(spedizione=None):
    """Invia i messaggi in coda (di una spedizione o di tutte). Restituisce (inviati, errori)."""
    if not invio_attivo():
        return 0, 0  # restano in coda fino alla riattivazione
    in_coda = (
        DestinatarioSpedizione.objects.filter(
            stato=Stato.IN_ATTESA, spedizione__protocollo__annullato=False
        )
        .select_related("spedizione__protocollo", "spedizione__servizio")
        .order_by("spedizione_id", "id")
    )
    if spedizione is not None:
        in_coda = in_coda.filter(spedizione=spedizione)
    org = Organizzazione.corrente()
    inviati = errori = 0
    connessioni = {}
    try:
        for d in in_coda:
            sped = d.spedizione
            try:
                if sped.servizio_id not in connessioni:
                    connessioni[sped.servizio_id] = _connessione(sped.servizio)
                email, message_id = messaggio(sped, d, org)
                if connessioni[sped.servizio_id].send_messages([email]) != 1:
                    raise OperazioneNonValida("Il server non ha accettato il messaggio.")
            except Exception as e:  # noqa: BLE001 - l'errore resta sul destinatario
                d.tentativi += 1
                d.dettaglio = f"{type(e).__name__}: {e}"[:500]
                if d.tentativi >= MAX_TENTATIVI:
                    d.stato = Stato.ERRORE
                d.aggiornato_il = timezone.now()
                d.save(update_fields=["tentativi", "dettaglio", "stato", "aggiornato_il"])
                errori += 1
                log.warning("Spedizione %s a %s non riuscita: %s", sped.pk, d.indirizzo, e)
                connessioni.pop(sped.servizio_id, None)
                continue
            d.stato = Stato.INVIATO
            d.message_id = message_id
            d.inviato_il = d.aggiornato_il = timezone.now()
            d.dettaglio = ""
            d.save(
                update_fields=["stato", "message_id", "inviato_il", "aggiornato_il", "dettaglio"]
            )
            inviati += 1
    finally:
        for c in connessioni.values():
            with contextlib.suppress(Exception):  # chiusura dopo un errore di rete
                c.close()
    return inviati, errori


@transaction.atomic
def riprova(spedizione, utente):
    """Rimette in coda i destinatari finiti in errore di invio (non quelli non consegnati)."""
    if utente is not None and not utente.has_perm(PERMESSO):
        raise OperazioneNonValida("Non hai il permesso di spedire i protocolli.")
    if spedizione.protocollo.annullato:
        raise OperazioneNonValida("Il protocollo è annullato.")
    n = spedizione.destinatari.filter(stato=Stato.ERRORE).update(
        stato=Stato.IN_ATTESA, tentativi=0, dettaglio=""
    )
    if not n:
        raise OperazioneNonValida("Nessun destinatario in errore da rimettere in coda.")
    registra(Azione.MODIFICA, spedizione.protocollo, utente=utente,
             descrizione=f"Protocollo {spedizione.protocollo.segnatura}",
             spedizione_riprovata=n)  # fmt: skip
    return n


# --- ricevute PEC ------------------------------------------------------------------------------


def ricevuta_pec(msg):
    """(tipo, message-id di riferimento) se il messaggio è una ricevuta PEC, altrimenti None."""
    tipo = str(msg.get("X-Ricevuta") or "").strip().lower()
    riferimento = str(msg.get("X-Riferimento-Message-ID") or "").strip()
    if tipo in RICEVUTE and riferimento:
        return tipo, riferimento
    return None


def destinatario_della_ricevuta(riferimento):
    return (
        DestinatarioSpedizione.objects.select_related("spedizione__protocollo")
        .filter(message_id=riferimento)
        .first()
    )


def applica_ricevuta(destinatario, tipo, grezzo, quando=None):
    """Aggiorna l'esito e conserva la ricevuta fra i documenti del protocollo."""
    protocollo = destinatario.spedizione.protocollo
    nuovo = RICEVUTE[tipo]
    if nuovo is not None and _PESO[nuovo] > _PESO[Stato(destinatario.stato)]:
        destinatario.stato = nuovo
        destinatario.dettaglio = tipo.replace("-", " ")
        destinatario.aggiornato_il = quando or timezone.now()
        destinatario.save(update_fields=["stato", "dettaglio", "aggiornato_il"])
    allegato = aggiungi_allegato(
        protocollo,
        ContentFile(grezzo, name="ricevuta.eml"),
        None,
        nome=f"ricevuta {tipo} - {destinatario.indirizzo}.eml",
        controlla=False,
    )
    registra(Azione.MODIFICA, protocollo, utente=None,
             descrizione=f"Protocollo {protocollo.segnatura}",
             ricevuta_pec=tipo, destinatario=destinatario.indirizzo,
             allegati_aggiunti=[allegato.nome])  # fmt: skip
    return allegato
