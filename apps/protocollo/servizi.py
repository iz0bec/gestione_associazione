# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Operazioni del protocollo: registrazione numerata, allegati con impronta,
# *              annullamento, registro giornaliero, protocollazione della posta ricevuta.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import csv
import hashlib
import mimetypes
import re
import unicodedata
from datetime import date, datetime, time, timedelta
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile, File
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.anagrafica.models import Soggetto
from apps.anagrafica.servizi import cella_sicura
from apps.core.audit import Azione, campi_modificati, registra
from apps.core.models import Organizzazione, Sequenza
from apps.core.numerazione import prossimo_numero

from .models import (
    SEQ_PROTOCOLLO,
    Allegato,
    Corrispondente,
    MessaggioRicevuto,
    Protocollo,
    RegistroGiornaliero,
)


class OperazioneNonValida(ValidationError):
    """Operazione rifiutata per una regola del protocollo (messaggio per l'utente)."""


# --- file ----------------------------------------------------------------------------------


def nome_file_sicuro(nome: str) -> str:
    """Nome da mostrare e da proporre al download: senza percorsi né caratteri di controllo."""
    nome = Path(str(nome).replace("\\", "/")).name
    nome = unicodedata.normalize("NFC", nome)
    nome = "".join(c for c in nome if unicodedata.category(c)[0] != "C")
    nome = re.sub(r'[<>:"/|?*]', "_", nome).strip(" .")
    if len(nome) > 150:
        radice, est = Path(nome).stem, Path(nome).suffix[:12]
        nome = radice[: 150 - len(est)] + est
    return nome or "documento"


def estensione(nome: str) -> str:
    return Path(nome).suffix.lower().lstrip(".")


def controlla_file(nome: str, dimensione: int):
    est = estensione(nome)
    if est not in settings.PROTOCOLLO_ESTENSIONI:
        raise OperazioneNonValida(
            f"«{nome}»: tipo di file non ammesso (.{est or '?'}). Ammessi: "
            + ", ".join(settings.PROTOCOLLO_ESTENSIONI)
        )
    massimo = settings.PROTOCOLLO_ALLEGATO_MAX_MB * 1024 * 1024
    if dimensione > massimo:
        raise OperazioneNonValida(
            f"«{nome}»: file troppo grande (massimo {settings.PROTOCOLLO_ALLEGATO_MAX_MB} MB)."
        )


def impronta_file(file) -> str:
    h = hashlib.sha256()
    file.seek(0)
    for blocco in iter(lambda: file.read(1024 * 1024), b""):
        h.update(blocco)
    file.seek(0)
    return h.hexdigest()


def tipo_file(nome):
    # dedotto dall'estensione, mai dal tipo dichiarato dal browser
    return mimetypes.guess_type(nome)[0] or "application/octet-stream"


def aggiungi_allegato(protocollo, file, utente, *, nome=None, principale=False, controlla=True):
    """Salva un file come allegato del protocollo (nome su disco = impronta)."""
    nome = nome_file_sicuro(nome or getattr(file, "name", "documento"))
    if controlla:
        controlla_file(nome, file.size)
    allegato = Allegato(
        protocollo=protocollo,
        nome=nome,
        tipo=tipo_file(nome),
        dimensione=file.size,
        impronta=impronta_file(file),
        principale=principale,
        caricato_da=utente,
    )
    allegato.file.save(nome, file if isinstance(file, File) else File(file), save=False)
    allegato.save()
    return allegato


# --- registrazione -------------------------------------------------------------------------


def corrispondente_da_soggetto(soggetto, ruolo, pec_preferita=False):
    indirizzo = (soggetto.pec if pec_preferita else "") or soggetto.email or soggetto.pec
    if not indirizzo and soggetto.indirizzo_completo:
        indirizzo = soggetto.indirizzo_completo
    return {
        "ruolo": ruolo,
        "soggetto": soggetto,
        "descrizione": soggetto.nome_completo,
        "indirizzo": indirizzo or "",
    }


PERMESSO_PROTOCOLLARE = "protocollo.add_protocollo"


def puo_protocollare(utente):
    """Chi può registrare protocolli. `None` = operazione di sistema (lavori pianificati)."""
    return utente is None or utente.has_perm(PERMESSO_PROTOCOLLARE)


def controlla_permesso(utente):
    """Ogni registrazione, anche fatta da altri moduli, richiede il permesso di protocollare."""
    if not puo_protocollare(utente):
        raise OperazioneNonValida(f"{utente} non ha il permesso di protocollare.")


@transaction.atomic
def registra_protocollo(dati, corrispondenti, utente, *, allegati=(), principale=None):
    """Assegna il numero e registra.

    `dati`: campi del protocollo; `corrispondenti`: lista di dict (ruolo, soggetto, descrizione,
    indirizzo); `allegati`: file caricati; `principale`: indice del documento principale.
    """
    controlla_permesso(utente)
    if not dati.get("oggetto", "").strip():
        raise OperazioneNonValida("L'oggetto è obbligatorio.")
    ruoli = {c["ruolo"] for c in corrispondenti}
    direzione = dati["direzione"]
    if direzione == Protocollo.Direzione.ENTRATA and Corrispondente.Ruolo.MITTENTE not in ruoli:
        raise OperazioneNonValida("Indicare almeno un mittente.")
    if direzione == Protocollo.Direzione.USCITA and Corrispondente.Ruolo.DESTINATARIO not in ruoli:
        raise OperazioneNonValida("Indicare almeno un destinatario.")
    anno = timezone.localdate().year
    numero = prossimo_numero(SEQ_PROTOCOLLO, anno)
    protocollo = Protocollo(
        **dati,
        anno=anno,
        numero=numero,
        # l'ora si prende dopo il numero (riga di sequenza bloccata): ordine numeri = ordine orari
        registrato_il=timezone.now(),
        creato_da=utente,
        modificato_da=utente,
    )
    protocollo.save()
    for c in corrispondenti:
        Corrispondente.objects.create(
            protocollo=protocollo,
            ruolo=c["ruolo"],
            soggetto=c.get("soggetto"),
            descrizione=c["descrizione"][:300],
            indirizzo=(c.get("indirizzo") or "")[:300],
        )
    for i, f in enumerate(allegati):
        aggiungi_allegato(protocollo, f, utente, principale=(i == (principale or 0)))
    registra(
        Azione.CREAZIONE,
        protocollo,
        utente=utente,
        descrizione=f"Protocollo {protocollo.segnatura}",
        direzione=direzione,
        allegati=len(allegati),
    )
    return protocollo


@transaction.atomic
def registra_storico(dati, *, anno, numero, registrato_il, corrispondenti, utente,
                     annullato=False, motivo_annullamento=""):  # fmt: skip
    """Registrazione importata da un protocollo precedente, con il suo numero originale.

    Unica eccezione a `prossimo_numero`: la sequenza dell'anno viene portata almeno al numero
    importato, così le registrazioni successive continuano la numerazione senza buchi né doppi.
    """
    if Protocollo.objects.filter(anno=anno, numero=numero).exists():
        raise OperazioneNonValida(f"Il numero {anno}-{numero:05d} esiste già.")
    Sequenza.objects.bulk_create(
        [Sequenza(chiave=SEQ_PROTOCOLLO, anno=anno)], ignore_conflicts=True
    )
    sequenza = Sequenza.objects.select_for_update().get(chiave=SEQ_PROTOCOLLO, anno=anno)
    if sequenza.ultimo_numero < numero:
        sequenza.ultimo_numero = numero
        sequenza.save(update_fields=["ultimo_numero"])
    protocollo = Protocollo.objects.create(
        **dati, anno=anno, numero=numero, registrato_il=registrato_il, creato_da=utente,
        modificato_da=utente, annullato=annullato,
        motivo_annullamento=motivo_annullamento[:500] if annullato else "",
        annullato_il=registrato_il if annullato else None,
    )  # fmt: skip
    for c in corrispondenti:
        Corrispondente.objects.create(
            protocollo=protocollo, ruolo=c["ruolo"], soggetto=c.get("soggetto"),
            descrizione=c["descrizione"][:300], indirizzo=(c.get("indirizzo") or "")[:300],
        )  # fmt: skip
    return protocollo


@transaction.atomic
def carica_allegati(protocollo, files, utente):
    protocollo = Protocollo.objects.select_for_update().get(pk=protocollo.pk)
    if protocollo.annullato:
        raise OperazioneNonValida("Il protocollo è annullato.")
    for f in files:
        controlla_file(nome_file_sicuro(f.name), f.size)
    nuovi = [aggiungi_allegato(protocollo, f, utente) for f in files]
    registra(
        Azione.MODIFICA,
        protocollo,
        utente=utente,
        descrizione=f"Protocollo {protocollo.segnatura}",
        allegati_aggiunti=[a.nome for a in nuovi],
    )
    return nuovi


@transaction.atomic
def modifica_protocollo(form, utente):
    """Solo i dati accessori (classificazione, collegamento, riservatezza, note)."""
    if form.instance.annullato:
        raise OperazioneNonValida("Il protocollo è annullato.")
    dettagli = campi_modificati(form)
    protocollo = form.save(commit=False)
    protocollo.modificato_da = utente
    protocollo.save()
    if dettagli.get("campi"):
        registra(
            Azione.MODIFICA,
            protocollo,
            utente=utente,
            descrizione=f"Protocollo {protocollo.segnatura}",
            **dettagli,
        )
    return protocollo


@transaction.atomic
def annulla_protocollo(protocollo, utente, motivo):
    motivo = (motivo or "").strip()
    if len(motivo) < 5:
        raise OperazioneNonValida("Indicare il motivo dell'annullamento.")
    protocollo = Protocollo.objects.select_for_update().get(pk=protocollo.pk)
    if protocollo.annullato:
        raise OperazioneNonValida("Il protocollo è già annullato.")
    protocollo.annullato = True
    protocollo.motivo_annullamento = motivo[:500]
    protocollo.annullato_il = timezone.now()
    protocollo.annullato_da = utente
    protocollo.modificato_da = utente
    protocollo.save()
    registra(
        Azione.ANNULLAMENTO,
        protocollo,
        utente=utente,
        descrizione=f"Protocollo {protocollo.segnatura}",
        motivo=motivo,
    )
    return protocollo


# --- registro giornaliero ------------------------------------------------------------------


def protocolli_del_giorno(giorno):
    tz = timezone.get_current_timezone()
    inizio = timezone.make_aware(datetime.combine(giorno, time.min), tz)
    fine = timezone.make_aware(datetime.combine(giorno, time.max), tz)
    return (
        Protocollo.objects.filter(registrato_il__range=(inizio, fine))
        .select_related("classificazione", "annullato_da")
        .prefetch_related("corrispondenti")
        .order_by("anno", "numero")
    )


def genera_registro_giornaliero(giorno):
    """Crea (una sola volta) il PDF del registro del giorno, con impronta. Solo giorni conclusi."""
    from apps.core.pdf import genera_pdf

    if giorno >= timezone.localdate():
        raise OperazioneNonValida("Il registro giornaliero si genera solo per i giorni conclusi.")
    esistente = RegistroGiornaliero.objects.filter(data=giorno).first()
    if esistente:
        return esistente, False
    protocolli = list(protocolli_del_giorno(giorno))
    pdf = genera_pdf(
        "protocollo/pdf/registro_giornaliero.html",
        {
            "giorno": giorno,
            "protocolli": protocolli,
            "organizzazione": Organizzazione.corrente(),
            "generato_il": timezone.localtime(),
        },
    )
    registro = RegistroGiornaliero(
        data=giorno,
        impronta=hashlib.sha256(pdf).hexdigest(),
        registrazioni=len(protocolli),
        primo_numero=protocolli[0].segnatura if protocolli else "",
        ultimo_numero=protocolli[-1].segnatura if protocolli else "",
    )
    with transaction.atomic():
        registro.file.save(f"registro_{giorno:%Y%m%d}.pdf", ContentFile(pdf), save=False)
        registro.save()
        registra(
            Azione.CREAZIONE,
            registro,
            utente=None,
            descrizione=f"Registro giornaliero {giorno:%d/%m/%Y}",
            impronta=registro.impronta,
            registrazioni=registro.registrazioni,
        )
    return registro, True


def genera_registri_mancanti(dal=None):
    """Genera i registri mancanti dei giorni conclusi (dal primo protocollo, o da `dal`)."""
    primo = Protocollo.objects.order_by("registrato_il").first()
    if primo is None:
        return []
    giorno = max(dal or date.min, timezone.localtime(primo.registrato_il).date())
    ieri = timezone.localdate() - timedelta(days=1)
    esistenti = set(
        RegistroGiornaliero.objects.filter(data__gte=giorno).values_list("data", flat=True)
    )
    creati = []
    while giorno <= ieri:
        if giorno not in esistenti:
            creati.append(genera_registro_giornaliero(giorno)[0])
        giorno += timedelta(days=1)
    return creati


# --- posta ricevuta ------------------------------------------------------------------------


def soggetto_per_indirizzo(indirizzo):
    if not indirizzo:
        return None
    return (
        Soggetto.objects.filter(Q(email__iexact=indirizzo) | Q(pec__iexact=indirizzo))
        .order_by("-attivo", "pk")
        .first()
    )


@transaction.atomic
def protocolla_messaggio(
    messaggio, utente, *, oggetto, classificazione=None, riservato=False, note=""
):
    """Registra in entrata un messaggio ricevuto: mittente, testo originale (.eml) e allegati."""
    from django.core.files.storage import default_storage

    messaggio = (
        MessaggioRicevuto.objects.select_for_update().select_related("casella").get(pk=messaggio.pk)
    )
    if messaggio.stato != MessaggioRicevuto.Stato.NUOVO:
        raise OperazioneNonValida("Il messaggio è già stato gestito.")
    soggetto = soggetto_per_indirizzo(messaggio.mittente_email)
    mittente = {
        "ruolo": Corrispondente.Ruolo.MITTENTE,
        "soggetto": soggetto,
        "descrizione": soggetto.nome_completo if soggetto else messaggio.mittente,
        "indirizzo": messaggio.mittente_email,
    }
    protocollo = registra_protocollo(
        {
            "direzione": Protocollo.Direzione.ENTRATA,
            "mezzo": Protocollo.Mezzo.PEC if messaggio.casella.pec else Protocollo.Mezzo.EMAIL,
            "oggetto": oggetto,
            "data_documento": timezone.localtime(messaggio.data).date() if messaggio.data else None,
            "classificazione": classificazione,
            "riservato": riservato,
            "note": note,
        },
        [mittente],
        utente,
    )
    with messaggio.file_eml.open("rb") as f:
        aggiungi_allegato(
            protocollo, File(f), utente, nome="messaggio.eml", principale=True, controlla=False
        )
    for a in messaggio.allegati:
        with default_storage.open(a["percorso"], "rb") as f:
            aggiungi_allegato(protocollo, File(f), utente, nome=a["nome"], controlla=False)
    messaggio.stato = MessaggioRicevuto.Stato.PROTOCOLLATO
    messaggio.protocollo = protocollo
    messaggio.gestito_da = utente
    messaggio.gestito_il = timezone.now()
    messaggio.save()
    return protocollo


@transaction.atomic
def scarta_messaggio(messaggio, utente, motivo):
    motivo = (motivo or "").strip()
    if not motivo:
        raise OperazioneNonValida("Indicare il motivo (es. pubblicità, già protocollato).")
    messaggio = MessaggioRicevuto.objects.select_for_update().get(pk=messaggio.pk)
    if messaggio.stato != MessaggioRicevuto.Stato.NUOVO:
        raise OperazioneNonValida("Il messaggio è già stato gestito.")
    messaggio.stato = MessaggioRicevuto.Stato.SCARTATO
    messaggio.motivo_scarto = motivo[:255]
    messaggio.gestito_da = utente
    messaggio.gestito_il = timezone.now()
    messaggio.save()
    registra(Azione.ARCHIVIAZIONE, messaggio, utente=utente, motivo=motivo)
    return messaggio


# --- esportazione --------------------------------------------------------------------------


def esporta_csv(queryset, destinazione, utente):
    writer = csv.writer(destinazione, delimiter=";")
    writer.writerow([
        "numero", "data registrazione", "direzione", "mezzo", "oggetto", "mittenti",
        "destinatari", "data documento", "protocollo mittente", "classificazione", "riservato",
        "annullato", "motivo annullamento",
    ])  # fmt: skip
    n = 0
    for p in queryset.select_related("classificazione").prefetch_related("corrispondenti"):
        riga = [
            p.segnatura, timezone.localtime(p.registrato_il).strftime("%d/%m/%Y %H:%M"),
            p.get_direzione_display(), p.get_mezzo_display(), p.oggetto,
            ", ".join(c.descrizione for c in p.mittenti),
            ", ".join(c.descrizione for c in p.destinatari),
            p.data_documento or "", p.riferimento_mittente, p.classificazione or "",
            "sì" if p.riservato else "", "sì" if p.annullato else "", p.motivo_annullamento,
        ]  # fmt: skip
        writer.writerow([cella_sicura(v) for v in riga])
        n += 1
    registra(Azione.ESPORTAZIONE, utente=utente, descrizione=f"Protocollo CSV ({n} righe)", righe=n)
    return n
