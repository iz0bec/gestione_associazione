# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Manuale di gestione documentale (sul modello delle Linee guida AgID sulla
# *              formazione, gestione e conservazione dei documenti informatici): composto dalla
# *              configurazione reale (ruoli, utenti, titolario, caselle, regole del registro,
# *              backup) più i dati organizzativi; l'adozione lo protocolla con il PDF allegato.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from apps.core.audit import Azione, registra
from apps.core.models import Organizzazione, ServizioInvio

from . import segnatura
from .models import (
    CasellaPosta,
    Classificazione,
    Corrispondente,
    ManualeGestione,
    ModelloProtocollo,
    Protocollo,
    RegistroGiornaliero,
    VersioneManuale,
)

TEMPLATE = "protocollo/pdf/manuale_gestione.html"

# capacità riportate nel manuale: (permesso, intestazione della colonna)
CAPACITA = [
    ("protocollo.view_protocollo", "Consulta il registro"),
    ("protocollo.add_protocollo", "Registra e aggiunge documenti"),
    ("protocollo.gestisci_posta", "Protocolla o scarta la posta"),
    ("protocollo.annulla_protocollo", "Annulla"),
    ("protocollo.vedi_riservati", "Vede i riservati"),
    ("protocollo.change_classificazione", "Titolario e caselle"),
    ("protocollo.gestisci_manuale", "Manuale"),
]


def _ruoli():
    from django.contrib.auth.models import Group

    from apps.accounts.ruoli import RUOLI

    politiche = {
        g.name: getattr(getattr(g, "politica", None), "mfa_obbligatoria", False)
        for g in Group.objects.select_related("politica")
    }
    righe = []
    for nome, permessi in RUOLI.items():
        insieme = set(permessi)
        valori = [p in insieme for p, _ in CAPACITA]
        if any(valori):
            righe.append({"nome": nome, "valori": valori, "mfa": politiche.get(nome, False)})
    return righe


def _utenti():
    from django.contrib.auth import get_user_model

    righe = []
    utenti = get_user_model().objects.filter(is_active=True).prefetch_related("groups", "sezioni")
    for u in utenti.order_by("last_name", "first_name", "username"):
        valori = [u.has_perm(p) for p, _ in CAPACITA]
        if not valori[0]:
            continue
        ruoli = ", ".join(g.name for g in u.groups.all())
        righe.append({
            "nome": u.get_full_name() or u.username, "utente": u.username,
            "ruoli": ruoli or ("superutente" if u.is_superuser else ""),
            "sezioni": ", ".join(s.nome for s in u.sezioni.all()), "valori": valori,
        })  # fmt: skip
    return righe


def contesto(manuale=None, *, bozza=True, versione=None, giorno=None, pubblico=False):
    """`pubblico`: versione da pubblicare in rete, senza l'elenco nominativo degli utenti e
    senza gli account delle caselle (informazioni utili a chi tenta un accesso)."""
    from apps.documenti.servizi import testo_html
    from apps.soci.models import Sezione

    manuale = manuale or ManualeGestione.corrente()
    org = Organizzazione.corrente()
    registri = RegistroGiornaliero.objects.order_by("-data")
    return {
        "organizzazione": org,
        "manuale": manuale,
        "bozza": bozza,
        "pubblico": pubblico,
        "versione": versione if versione is not None else manuale.versione,
        "giorno": giorno or timezone.localdate(),
        "app_versione": settings.APP_VERSIONE,
        "sezioni": Sezione.objects.filter(attiva=True),
        "capacita": [titolo for _, titolo in CAPACITA],
        "ruoli": _ruoli(),
        "utenti": [] if pubblico else _utenti(),
        "titolario": Classificazione.objects.order_by("codice"),
        "caselle": CasellaPosta.objects.order_by("nome"),
        "servizi_invio": ServizioInvio.objects.filter(attivo=True).order_by("tipo", "nome"),
        "mezzi": Protocollo.Mezzo.choices,
        "modelli": ModelloProtocollo.objects.filter(attivo=True),
        "estensioni": ", ".join(sorted(settings.PROTOCOLLO_ESTENSIONI)),
        "max_mb": settings.PROTOCOLLO_ALLEGATO_MAX_MB,
        "registri": registri.count(),
        "ultimo_registro": registri.first(),
        "primo_protocollo": Protocollo.objects.order_by("registrato_il").first(),
        "backup": {
            "automatico": settings.BACKUP_AUTOMATICO,
            "ora": settings.BACKUP_ORA,
            "giornalieri": settings.BACKUP_GIORNALIERI,
            "settimanali": settings.BACKUP_SETTIMANALI,
            "mensili": settings.BACKUP_MENSILI,
        },
        "integrazioni": testo_html(manuale.integrazioni, {}) if manuale.integrazioni else "",
        "segnatura": {
            "codice_amministrazione": org.codice_amministrazione_segnatura,
            "ipa": bool(org.codice_amministrazione),
            "codice_aoo": org.codice_aoo_segnatura,
            "aoo_ipa": bool(org.codice_aoo),
            "registro": segnatura.CODICE_REGISTRO,
            "sigillo": segnatura.sigillo_attivo(crea=False),
        },
    }


def pdf(manuale=None, **opzioni):
    from apps.core.pdf import genera_pdf

    return genera_pdf(TEMPLATE, contesto(manuale, **opzioni))


def versioni():
    return VersioneManuale.objects.select_related("protocollo", "allegato")


def ultima_versione():
    return versioni().first()


def _documento_pubblico(manuale, versione, dati, utente):
    """Documento pubblico «Manuale di gestione documentale» con la variante per la rete."""
    from apps.core.models import DocumentoPubblico

    doc = manuale.documento_pubblico or DocumentoPubblico(
        titolo="Manuale di gestione documentale", creato_da=utente, ordine=50
    )
    vecchio = doc.file.name if doc.pk and doc.file else ""
    doc.descrizione = f"versione {versione.versione} adottata il {versione.adottata_il:%d/%m/%Y}"
    doc.nome_file = f"manuale_gestione_v{versione.versione}.pdf"
    doc.dimensione = len(dati)
    doc.pubblicato = True
    doc.modificato_da = utente
    doc.file.save("documento.pdf", ContentFile(dati), save=False)
    doc.save()
    if vecchio:
        transaction.on_commit(lambda: doc.file.storage.delete(vecchio))
    return doc


def _manuale_bloccato():
    return ManualeGestione.objects.select_for_update().get(pk=ManualeGestione.corrente().pk)


@transaction.atomic
def pubblica_in_vigore(utente):
    """Pubblica (o ripubblica) fra i documenti pubblici la versione in vigore, così com'era
    all'adozione (variante senza utenti né account conservata nel protocollo)."""
    from .servizi import OperazioneNonValida

    manuale = _manuale_bloccato()
    versione = ultima_versione()
    if versione is None:
        raise OperazioneNonValida("Nessuna versione adottata da pubblicare.")
    if versione.allegato_pubblico is None:
        raise OperazioneNonValida(
            f"La versione {versione.versione} non ha la variante per la pubblicazione: "
            "adottare una nuova versione."
        )
    with versione.allegato_pubblico.file.open("rb") as f:
        dati = f.read()
    manuale.documento_pubblico = _documento_pubblico(manuale, versione, dati, utente)
    manuale.save(update_fields=["documento_pubblico"])
    VersioneManuale.objects.exclude(pk=versione.pk).update(pubblicata=False)
    versione.pubblicata = True
    versione.save(update_fields=["pubblicata"])
    registra(
        Azione.MODIFICA, manuale, utente=utente,
        descrizione=f"Manuale di gestione pubblicato (versione {versione.versione})",
    )  # fmt: skip
    return versione


@transaction.atomic
def ritira(utente):
    """Toglie il manuale dalla pagina dei documenti pubblici (le versioni restano agli atti)."""
    manuale = _manuale_bloccato()
    doc = manuale.documento_pubblico
    if doc is not None and doc.pubblicato:
        doc.pubblicato = False
        doc.modificato_da = utente
        doc.save(update_fields=["pubblicato", "modificato_da"])
    VersioneManuale.objects.update(pubblicata=False)
    registra(Azione.MODIFICA, manuale, utente=utente, descrizione="Manuale di gestione ritirato")


def pubblicato():
    doc = ManualeGestione.corrente().documento_pubblico
    return bool(doc and doc.pubblicato)


@transaction.atomic
def adotta(utente, *, pubblica=False):
    """Nuova versione: PDF definitivo e variante pubblica allegati a una registrazione di
    protocollo interna, voce nello storico; con `pubblica`, anche fra i documenti pubblici."""
    from . import servizi

    manuale = _manuale_bloccato()
    if manuale.responsabile is None:
        raise servizi.OperazioneNonValida(
            "Indicare il responsabile della gestione documentale prima di adottare il manuale."
        )
    numero = manuale.versione + 1
    oggi = timezone.localdate()
    opzioni = {"bozza": False, "versione": numero, "giorno": oggi}
    documento = pdf(manuale, **opzioni)
    variante = pdf(manuale, pubblico=True, **opzioni)
    org = Organizzazione.corrente()
    protocollo = servizi.registra_protocollo(
        {
            "direzione": Protocollo.Direzione.INTERNO,
            "mezzo": Protocollo.Mezzo.ALTRO,
            "oggetto": f"Adozione del manuale di gestione documentale (versione {numero})",
            "testo": manuale.atto_adozione,
            "data_documento": oggi,
        },
        [{"ruolo": Corrispondente.Ruolo.MITTENTE, "descrizione": org.denominazione}],
        utente,
    )
    allegato = servizi.aggiungi_allegato(
        protocollo, ContentFile(documento, name=f"manuale_gestione_v{numero}.pdf"), utente,
        principale=True,
    )  # fmt: skip
    allegato_pubblico = servizi.aggiungi_allegato(
        protocollo, ContentFile(variante, name=f"manuale_gestione_v{numero}_pubblico.pdf"), utente
    )
    VersioneManuale.objects.create(
        versione=numero, adottata_il=oggi, atto_adozione=manuale.atto_adozione,
        protocollo=protocollo, allegato=allegato, allegato_pubblico=allegato_pubblico,
        adottata_da=utente,
    )  # fmt: skip
    manuale.versione, manuale.adottato_il, manuale.protocollo = numero, oggi, protocollo
    manuale.save()
    registra(
        Azione.MODIFICA, manuale, utente=utente,
        descrizione=f"Manuale di gestione adottato (versione {numero})",
        protocollo=protocollo.segnatura,
    )  # fmt: skip
    if pubblica or pubblicato():  # una versione nuova sostituisce quella pubblicata
        pubblica_in_vigore(utente)
    return manuale
