# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Promemoria per l'archivio centrale: ogni nuovo socio e ogni rettifica
# *              dell'anagrafica di un socio, quando l'archivio centrale (federazione o registro
# *              nazionale) non è collegato via API, diventa un promemoria da riportare a mano;
# *              elenco da spuntare e riepilogo giornaliero per email. I dati che arrivano proprio
# *              dall'archivio centrale (importazione, verifica con la federazione) non ne creano.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import logging
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMessage
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.core.audit import Azione, registra

log = logging.getLogger(__name__)

CAMPI = {
    "cognome": "cognome", "nome": "nome", "codice_fiscale": "codice fiscale", "sesso": "sesso",
    "data_nascita": "data di nascita", "luogo_nascita": "luogo di nascita",
    "indirizzo": "indirizzo", "cap": "CAP", "comune": "comune", "provincia": "provincia",
    "email": "email", "telefono": "telefono", "cellulare": "cellulare",
}  # fmt: skip
PERMESSO = "soci.change_socio"
MAX_ELENCATI = 30

_sospesi = ContextVar("promemoria_archivio_sospesi", default=False)


@contextmanager
def sospesi():
    """Le modifiche fatte qui dentro arrivano dall'archivio centrale: nessun promemoria."""
    token = _sospesi.set(True)
    try:
        yield
    finally:
        _sospesi.reset(token)


def archivio_collegato():
    """La federazione è collegata via API e può leggere i nostri soci (Verifica soci)."""
    from apps.api.models import ClienteApi

    return ClienteApi.objects.filter(
        stato=ClienteApi.Stato.ATTIVA, ruolo=ClienteApi.Ruolo.FEDERAZIONE,
        ambiti__contains=["soci:lettura"],
    ).exists()  # fmt: skip


def nome_archivio():
    from apps.core.models import Organizzazione

    from . import sezioni

    org = Organizzazione.corrente()
    if org.archivio_centrale:
        return org.archivio_centrale
    if sezioni.multisezione():
        return "Registro soci nazionale"
    return f"Federazione {org.federazione}".strip() if org.federazione else "Federazione"


def _mostra(valore):
    if valore in (None, ""):
        return "(vuoto)"
    return valore.strftime("%d/%m/%Y") if isinstance(valore, date) else str(valore)


def _attivi():
    return not _sospesi.get() and not archivio_collegato()


def _aggiungi(socio, tipo, modifiche, utente=None):
    from .models import PromemoriaArchivio

    aperto = (
        PromemoriaArchivio.objects.select_for_update()
        .filter(socio=socio, fatto_il__isnull=True)
        .first()
    )
    if aperto:
        precedenti = {m[0]: m for m in aperto.modifiche}
        for campo, prima, dopo in modifiche:
            if campo in precedenti:  # resta il valore di partenza, cambia quello finale
                precedenti[campo][2] = dopo
            else:  # per un socio nuovo conta solo il dato da riportare
                aperto.modifiche.append([campo, "" if aperto.tipo == "nuovo" else prima, dopo])
        aperto.modifiche = [m for m in aperto.modifiche if m[1] != m[2]]
        aperto.segnalato_il = None  # da segnalare di nuovo con le novità
        aperto.save()
        return aperto
    return PromemoriaArchivio.objects.create(
        socio=socio, tipo=tipo, archivio=nome_archivio()[:150], modifiche=modifiche,
        creato_da=utente,
    )  # fmt: skip


# --- segnali -------------------------------------------------------------------------------------


def soggetto_prima(sender, instance, **kwargs):
    if instance.pk and not getattr(instance, "_promemoria_prima", None):
        instance._promemoria_prima = (
            sender.objects.filter(pk=instance.pk).values(*CAMPI).first() or {}
        )


def soggetto_dopo(sender, instance, created, **kwargs):
    from .models import Socio

    prima = getattr(instance, "_promemoria_prima", None)
    instance._promemoria_prima = None
    if instance.anonimizzato_il:  # anonimizzato: niente da riportare, e nessuna copia dei dati
        from .models import PromemoriaArchivio

        PromemoriaArchivio.objects.filter(socio__soggetto_id=instance.pk).delete()
        return
    if created or not prima or _sospesi.get():
        return
    modifiche = [
        [etichetta, _mostra(prima.get(campo)), _mostra(getattr(instance, campo))]
        for campo, etichetta in CAMPI.items()
        if (prima.get(campo) or "") != (getattr(instance, campo) or "")
    ]
    if not modifiche:
        return
    socio = Socio.objects.filter(soggetto_id=instance.pk).first()
    if socio is None or archivio_collegato():
        return
    with transaction.atomic():
        _aggiungi(socio, "rettifica", modifiche, getattr(instance, "modificato_da", None))


def socio_creato(sender, instance, created, **kwargs):
    if not created or not _attivi():
        return
    p = instance.soggetto
    dati = [[etichetta, "", _mostra(getattr(p, campo))] for campo, etichetta in CAMPI.items()
            if getattr(p, campo)]  # fmt: skip
    with transaction.atomic():
        _aggiungi(instance, "nuovo", dati, instance.creato_da)


def collega():
    from django.db.models.signals import post_save, pre_save

    from apps.anagrafica.models import Soggetto

    from .models import Socio

    pre_save.connect(soggetto_prima, sender=Soggetto, dispatch_uid="promemoria_soggetto_prima")
    post_save.connect(soggetto_dopo, sender=Soggetto, dispatch_uid="promemoria_soggetto_dopo")
    post_save.connect(socio_creato, sender=Socio, dispatch_uid="promemoria_socio_creato")


# --- gestione ------------------------------------------------------------------------------------


def da_fare(utente=None):
    from . import sezioni
    from .models import PromemoriaArchivio

    qs = PromemoriaArchivio.objects.filter(fatto_il__isnull=True).select_related(
        "socio__soggetto", "socio__sezione"
    )
    return sezioni.filtra(qs, utente, "socio__sezione") if utente else qs


def segna_fatti(promemoria, utente):
    """Segna come riportati nell'archivio centrale. Restituisce quanti."""
    from .models import PromemoriaArchivio

    adesso = timezone.now()
    ids = [p.pk for p in promemoria if p.fatto_il is None]
    n = PromemoriaArchivio.objects.filter(pk__in=ids).update(fatto_il=adesso, fatto_da=utente)
    if n:
        descrizione = f"Promemoria per l'archivio centrale segnati come fatti: {n}"
        registra(Azione.MODIFICA, utente=utente, numero=n, descrizione=descrizione)
    return n


def _testo(elenco, totale):
    from apps.core.models import Organizzazione

    org = Organizzazione.corrente()
    righe = [f"{org.denominazione}: modifiche ai soci da riportare nell'archivio centrale "
             f"({totale} da fare in tutto).", ""]  # fmt: skip
    for p in elenco[:MAX_ELENCATI]:
        dettagli = "; ".join(f"{c}: {a} → {b}" if a else f"{c}: {b}" for c, a, b in p.modifiche)
        righe.append(f"- {p.get_tipo_display()} · {p.socio.soggetto.nome_completo} "
                     f"(n. {p.socio.numero}, {p.socio.sezione}) → {p.archivio}")  # fmt: skip
        if dettagli:
            righe.append(f"  {dettagli}")
    if len(elenco) > MAX_ELENCATI:
        righe.append(f"- e altri {len(elenco) - MAX_ELENCATI}")
    if settings.URL_PUBBLICO:
        righe += ["", f"{settings.URL_PUBBLICO}{reverse('soci:promemoria_archivio')}"]
    righe += ["", "Una volta riportate, segnarle come fatte nella pagina indicata."]
    return "\n".join(righe)


def invia_riepilogo():
    """Lavoro giornaliero (rieseguibile): a chi gestisce i soci, i promemoria nuovi o
    aggiornati dall'ultimo riepilogo, ognuno per le proprie sezioni. Restituisce gli invii."""
    from apps.core.models import Organizzazione

    nuovi = list(da_fare().filter(segnalato_il__isnull=True).order_by("creato_il"))
    if not nuovi:
        return 0
    org = Organizzazione.corrente()
    inviati = 0
    for utente in get_user_model().objects.filter(is_active=True).exclude(email=""):
        if not utente.has_perm(PERMESSO):
            continue
        propri = {p.pk for p in da_fare(utente)}
        elenco = [p for p in nuovi if p.pk in propri]
        if not elenco:
            continue
        try:
            EmailMessage(subject=f"Soci da riportare nell'archivio centrale - {org.denominazione}",
                         body=_testo(elenco, len(propri)), to=[utente.email]).send()  # fmt: skip
            inviati += 1
        except OSError as e:  # posta non raggiungibile: si riprova al giro dopo
            log.warning("Riepilogo dei promemoria non inviato a %s: %s", utente, e)
            return inviati
    da_fare().filter(pk__in=[p.pk for p in nuovi]).update(segnalato_il=timezone.now())
    return inviati
