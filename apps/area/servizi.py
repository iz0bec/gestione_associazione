# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Area personale: collegamento di accesso monouso per email (30 minuti),
# *              sessione del socio (2 ore), dati visibili e richieste di correzione
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import hashlib
import logging
import secrets
import time
from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.urls import reverse
from django.utils import timezone

from apps.anagrafica.models import Soggetto
from apps.core import veste_email
from apps.core.audit import Azione, registra
from apps.core.models import Organizzazione

from .models import AccessoArea, RichiestaArea

log = logging.getLogger(__name__)
SALE = "area.accesso"
VALIDITA = 30 * 60  # secondi del collegamento
DURATA_SESSIONE = 2 * 3600
LIMITE_IP = 5  # richieste di collegamento per ora dallo stesso indirizzo
LIMITE_PERSONA = 3  # collegamenti per ora alla stessa persona
CHIAVE = "area_soggetto"
SCADENZA = "area_scade"


class OperazioneNonValida(ValidationError):
    pass


def attiva():
    return Organizzazione.corrente().area_soci


def socio_con_email(email):
    """La persona (socio non cessato) con questa email, se è una sola."""
    from apps.soci.models import Socio

    email = (email or "").strip()
    if not email:
        return None
    soci = (
        Socio.objects.attivi()
        .filter(soggetto__email__iexact=email, soggetto__attivo=True)
        .select_related("soggetto")[:2]
    )
    soci = list(soci)
    return soci[0].soggetto if len(soci) == 1 else None


def _impronta(codice):
    return hashlib.sha256(codice.encode()).hexdigest()


def chiedi_accesso(email, *, base_url, ip=None):
    """Manda il collegamento se l'email è di un socio (a chi chiede si risponde sempre allo stesso
    modo). Restituisce True se è partito, False altrimenti (per i test e il registro)."""
    un_ora_fa = timezone.now() - timedelta(hours=1)
    if ip and AccessoArea.objects.filter(indirizzo_ip=ip, creato_il__gte=un_ora_fa).count() >= (
        LIMITE_IP
    ):
        raise OperazioneNonValida("Troppe richieste da questo collegamento: riprovare più tardi.")
    soggetto = socio_con_email(email)
    if soggetto is None:
        log.info("Area personale: nessun socio con l'email indicata")
        return False
    if soggetto.accessi_area.filter(creato_il__gte=un_ora_fa).count() >= LIMITE_PERSONA:
        return False
    org = Organizzazione.corrente()
    if not org.invio_email:
        log.warning("Area personale: invio dei messaggi spento, collegamento non inviato")
        return False
    codice = secrets.token_urlsafe(32)
    AccessoArea.objects.create(soggetto=soggetto, impronta=_impronta(codice), indirizzo_ip=ip)
    firmato = signing.dumps({"s": soggetto.pk, "c": codice}, salt=SALE)
    link = f"{base_url}{reverse('area:entra', args=[firmato])}"
    corpo = (
        f"Gentile {soggetto.nome or soggetto.nome_completo},\n\n"
        f"per entrare nella tua area personale di {org.denominazione} apri questo collegamento "
        f"entro 30 minuti (vale una sola volta):\n\n{link}\n\n"
        "Se non l'hai chiesto tu, ignora questo messaggio: nessuno può entrare senza il "
        f"collegamento.\n\n-- \n{org.denominazione}"
    )
    # come il recupero della password: messaggio di servizio, fuori dalla coda delle comunicazioni
    # (il collegamento non deve restare leggibile nel registro degli invii)
    email = EmailMessage(subject=f"Accesso all'area personale - {org.denominazione}", body=corpo,
                         to=[soggetto.email])  # fmt: skip
    testo = corpo.rsplit("\n\n-- \n", 1)[0]  # nell'HTML la firma è quella della veste
    veste_email.veste(email, org, testo=testo, titolo="Accesso all'area personale").send()
    registra(Azione.CONSULTAZIONE, soggetto, utente=None, ip=ip,
             descrizione=f"Area personale: collegamento inviato a {soggetto}")  # fmt: skip
    return True


def entra(firmato, ip=None):
    """Soggetto del collegamento valido e non ancora usato (che diventa usato), altrimenti None."""
    try:
        dati = signing.loads(firmato, salt=SALE, max_age=VALIDITA)
        accesso = AccessoArea.objects.select_related("soggetto").get(
            soggetto_id=dati["s"], impronta=_impronta(dati["c"]), usato_il__isnull=True
        )
    except (signing.BadSignature, KeyError, TypeError, AccessoArea.DoesNotExist):
        return None
    accesso.usato_il = timezone.now()
    accesso.save(update_fields=["usato_il"])
    registra(Azione.ACCESSO, accesso.soggetto, utente=None, ip=ip,
             descrizione=f"Area personale: accesso di {accesso.soggetto}")  # fmt: skip
    return accesso.soggetto


def apri_sessione(request, soggetto):
    request.session.cycle_key()  # niente fissazione della sessione
    request.session[CHIAVE] = soggetto.pk
    request.session[SCADENZA] = time.time() + DURATA_SESSIONE


def soggetto_in_sessione(request):
    pk, scade = request.session.get(CHIAVE), request.session.get(SCADENZA, 0)
    if not pk or time.time() > scade or not attiva():
        return None
    return Soggetto.objects.filter(pk=pk, attivo=True).first()


def chiudi_sessione(request):
    request.session.pop(CHIAVE, None)
    request.session.pop(SCADENZA, None)


def chiedi_correzione(soggetto, testo):
    testo = (testo or "").strip()
    if len(testo) < 5:
        raise OperazioneNonValida("Scrivere che cosa va corretto.")
    r = RichiestaArea.objects.create(soggetto=soggetto, testo=testo[:2000])
    registra(Azione.CREAZIONE, r, utente=None,
             descrizione=f"Area personale: richiesta di {soggetto}")  # fmt: skip
    return r


def segna_gestita(richiesta, utente):
    richiesta.gestita_il, richiesta.gestita_da = timezone.now(), utente
    richiesta.save(update_fields=["gestita_il", "gestita_da"])
    registra(Azione.MODIFICA, richiesta, utente=utente, gestita=True)


def base_url(request):
    return settings.URL_PUBBLICO or request.build_absolute_uri("/").rstrip("/")
