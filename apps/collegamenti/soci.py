# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Verifica dei soci con la controparte (ADR-030, F4): legge via API i soci della
# *              sezione presso la federazione (o presso la sezione), prepara la proposta (chi
# *              manca si popola, chi c'è mostra le modifiche) e applica le voci scelte.
# *              Allineamento automatico (dopo la prima verifica): in ordine di tempo rispetto
# *              all'ultimo allineamento, con l'avviso email di ciò che è cambiato e delle
# *              incongruenze; modalità a spinta per chi non si raggiunge (POST /consegne).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import hashlib
import json
import logging
import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMessage
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.api import tessere
from apps.api.models import ClienteApi, VerificaSoci
from apps.core.audit import Azione, registra
from apps.soci import allineamento

from . import client
from .trasporto import ErroreTrasporto

log = logging.getLogger(__name__)
MAX_SOCI = 20_000
A_MANO = "da correggere a mano"
PERMESSO_AVVISI = "soci.change_socio"
MAX_ELENCATI = 50


class OperazioneNonValida(Exception):
    pass


def scarica(cliente):
    """Elenco dei soci della sezione presso la controparte (risposta cifrata)."""
    try:
        risposta, _, _ = client.chiama(cliente, "GET", "/soci")
        if risposta.stato != 200:
            raise OperazioneNonValida(f"La controparte ha risposto: {client._problema(risposta)}")
        dati = client.json_risposta(risposta)
    except (client.ErroreCollegamento, ErroreTrasporto) as e:
        raise OperazioneNonValida(f"Controparte non raggiungibile: {e}") from e
    atteso = "sezione" if cliente.ruolo == ClienteApi.Ruolo.FEDERAZIONE else "federazione"
    visto = ((dati.get("tu") or {}).get("ruolo") if isinstance(dati, dict) else None) or "?"
    if visto != atteso:
        noi = "una sua sezione" if atteso == "sezione" else "la sua federazione"
        raise OperazioneNonValida(
            f"Ruoli incoerenti: qui «{cliente}» è indicata come "
            f"«{cliente.get_ruolo_display()}», quindi l'altra installazione dovrebbe vederci come "
            f"{noi}, ma ci ha indicati con il ruolo «{visto}». Correggere il ruolo nella scheda "
            "sbagliata (su una delle due installazioni) e ripetere."
        )
    return controlla_righe(dati.get("soci") if isinstance(dati, dict) else None)


def controlla_righe(righe):
    if not isinstance(righe, list) or not all(isinstance(r, dict) for r in righe):
        raise OperazioneNonValida("Elenco dei soci della controparte non valido.")
    if len(righe) > MAX_SOCI:
        raise OperazioneNonValida(f"Troppi soci nell'elenco (più di {MAX_SOCI}).")
    return righe


def controparti(utente):
    """Controparti con cui l'utente può avviare la Verifica soci: (controparte, sezione)."""
    from apps.soci import sezioni

    consentite = sezioni.id_sezioni(utente)
    risultato = []
    qs = ClienteApi.objects.filter(
        stato=ClienteApi.Stato.ATTIVA, tipo=ClienteApi.Tipo.INSTALLAZIONE
    )
    for c in qs.select_related("sezione").order_by("nome"):
        if not c.abbinata or (sezione := tessere.sezione_per(c)) is None:
            continue
        if consentite is None or sezione.pk in consentite:
            risultato.append((c, sezione))
    return risultato


def verifica(cliente: ClienteApi, utente):
    """Nuova verifica: legge i soci dalla controparte e prepara la proposta (nulla si modifica)."""
    if cliente.stato != ClienteApi.Stato.ATTIVA or not cliente.abbinata:
        raise OperazioneNonValida("La controparte non è attiva.")
    sezione = tessere.sezione_per(cliente)
    if sezione is None:
        raise OperazioneNonValida(
            "Indicare nella controparte il ruolo (federazione o sezione) e, sulla federazione, "
            "la sezione dell'elenco."
        )
    righe = scarica(cliente)
    da_sezione = cliente.ruolo == ClienteApi.Ruolo.SEZIONE
    proposta = allineamento.confronta(righe, sezione, da_sezione=da_sezione)
    v = VerificaSoci.objects.create(cliente=cliente, sezione=sezione, da_sezione=da_sezione,
                                    creata_da=utente, righe=righe, proposta=proposta)  # fmt: skip
    registra(Azione.CONSULTAZIONE, v, utente=utente, descrizione=f"Verifica soci con {cliente}",
             **proposta["conteggi"])  # fmt: skip
    return v


def applica(v: VerificaSoci, scelti, utente):
    with transaction.atomic():
        v = VerificaSoci.objects.select_for_update().get(pk=v.pk)
        if v.applicata_il:
            raise OperazioneNonValida("Questa verifica è già stata applicata.")
        esiti = allineamento.applica(
            v.righe, v.proposta, scelti, v.sezione, utente,
            da_sezione=v.da_sezione, controparte=v.cliente.nome,
        )  # fmt: skip
        v.esiti, v.righe = esiti, []  # i dati ricevuti non servono più
        v.applicata_il, v.applicata_da = timezone.now(), utente
        v.save()
    return v


# --- allineamento automatico ---------------------------------------------------------------------


def _riferimento_iniziale(cliente):
    ultima = cliente.verifiche_soci.filter(applicata_il__isnull=False).order_by("-applicata_il")
    return ultima.values_list("applicata_il", flat=True).first()


def attiva_automatico(cliente: ClienteApi, utente):
    """Accende l'allineamento automatico: serve almeno una verifica già applicata (si parte da
    lì: conta ciò che cambia dopo)."""
    if cliente.stato != ClienteApi.Stato.ATTIVA or not cliente.abbinata:
        raise OperazioneNonValida("La controparte non è attiva.")
    if tessere.sezione_per(cliente) is None:
        raise OperazioneNonValida(
            "Indicare prima il ruolo della controparte (federazione o sezione)."
        )
    riferimento = _riferimento_iniziale(cliente)
    if riferimento is None:
        raise OperazioneNonValida(
            "Fare prima una Verifica soci e applicarla: l'allineamento automatico parte da lì."
        )
    cliente.allineamento_automatico = True
    cliente.allineato_il = max(filter(None, [riferimento, cliente.allineato_il]))
    cliente.allineamento_errore = ""
    cliente.save(update_fields=["allineamento_automatico", "allineato_il", "allineamento_errore"])
    registra(Azione.MODIFICA, cliente, utente=utente,
             descrizione=f"Allineamento automatico dei soci con {cliente} attivato")  # fmt: skip
    return cliente


def disattiva_automatico(cliente: ClienteApi, utente):
    cliente.allineamento_automatico = False
    cliente.save(update_fields=["allineamento_automatico"])
    registra(Azione.MODIFICA, cliente, utente=utente,
             descrizione=f"Allineamento automatico dei soci con {cliente} disattivato")  # fmt: skip
    return cliente


def _decidi(voce, riferimento):
    """Ordine di tempo per una voce della proposta: (si applica?, nota). Note: «conflitto»
    (cambiato da entrambe le parti dopo l'ultimo allineamento: vale la modifica più recente),
    «a_mano» (differenza che non si sistema da sola), «escluso»; "" = niente da segnalare."""
    remoto = allineamento._momento(voce.get("remoto_il"))
    novita = riferimento is None or remoto is None or remoto > riferimento
    if voce["stato"] == "nuovo":
        return True, ""
    if voce["stato"] == "escluso":
        return False, "escluso" if novita else ""
    if voce["stato"] != "differenze" or not novita:
        return False, ""  # nulla, o cambiato solo qui: lo prenderà la controparte
    if remoto is None or any(A_MANO in str(m[2]) for m in voce["modifiche"]):
        return False, "a_mano"
    locale = allineamento._momento(voce.get("locale_il"))
    if riferimento is not None and locale is not None and locale > riferimento:
        return remoto > locale, "conflitto"
    return True, ""


def allinea(cliente: ClienteApi, righe=None, *, origine="lettura"):
    """Un giro di allineamento automatico. Applica in ordine di tempo, registra (solo se c'è
    qualcosa da dire) una verifica «automatica» con gli esiti e avvisa per email chi gestisce i
    soci della sezione. Restituisce la verifica registrata o None."""
    sezione = tessere.sezione_per(cliente)
    if sezione is None:
        raise OperazioneNonValida("Indicare il ruolo della controparte (federazione o sezione).")
    if righe is None:
        righe = scarica(cliente)
    controlla_righe(righe)
    da_sezione = cliente.ruolo == ClienteApi.Ruolo.SEZIONE
    riferimento = cliente.allineato_il
    proposta = allineamento.confronta(righe, sezione, da_sezione=da_sezione)
    scelti, note = [], {}
    for voce in proposta["voci"]:
        applica_voce, nota = _decidi(voce, riferimento)
        if applica_voce:
            scelti.append(voce["indice"])
        if nota:
            note[voce["indice"]] = nota
            if nota == "conflitto":
                voce["vince"] = "controparte" if applica_voce else "qui"
        voce["allineamento"] = nota
    esiti = []
    if scelti:
        esiti = allineamento.applica(righe, proposta, scelti, sezione, None,
                                     da_sezione=da_sezione, controparte=cliente.nome)  # fmt: skip
    # un socio nuovo che non si riesce a creare si riprova a ogni giro: si segnala una volta
    nuovi_vecchi = {
        v["indice"] for v in proposta["voci"]
        if v["stato"] == "nuovo" and riferimento is not None
        and (m := allineamento._momento(v.get("remoto_il"))) is not None and m <= riferimento
    }  # fmt: skip
    esiti = [e for e in esiti if not (e["esito"] == "errore" and e["indice"] in nuovi_vecchi)]
    applicati = {e["indice"] for e in esiti}
    voci = [v for v in proposta["voci"] if v["indice"] in applicati or v["indice"] in note]
    adesso = timezone.now()
    verifica = None
    if voci:
        conteggi = {k: sum(1 for e in esiti if e["esito"] == k)
                    for k in ("creato", "aggiornato", "errore")}  # fmt: skip
        conteggi["incongruenze"] = sum(1 for n in note.values() if n == "conflitto")
        conteggi["da_verificare"] = sum(1 for n in note.values() if n in ("a_mano", "escluso"))
        verifica = VerificaSoci.objects.create(
            cliente=cliente, sezione=sezione, da_sezione=da_sezione, righe=[],
            proposta={"voci": voci, "solo_qui": [], "conteggi": conteggi}, esiti=esiti,
            applicata_il=adesso, automatica=True, origine=origine,
        )  # fmt: skip
        avvisa(verifica)
    cliente.allineato_il = adesso
    cliente.allineamento_errore = ""
    cliente.save(update_fields=["allineato_il", "allineamento_errore"])
    return verifica


def _da_leggere(cliente):
    # una sezione «a spinta» manda lei l'elenco: non la si legge
    return not (cliente.ruolo == ClienteApi.Ruolo.SEZIONE and cliente.allineamento_spinta)


def allinea_tutti():
    """Lavoro periodico (rieseguibile): legge e allinea le controparti con l'automatico acceso,
    poi invia a spinta l'elenco dei soci a chi lo chiede. Restituisce {nome: esito}."""
    risultati = {}
    qs = ClienteApi.objects.filter(
        stato=ClienteApi.Stato.ATTIVA,
        ruolo__in=[ClienteApi.Ruolo.FEDERAZIONE, ClienteApi.Ruolo.SEZIONE],
    )
    for cliente in qs:
        if not cliente.abbinata:
            continue
        if cliente.allineamento_automatico and _da_leggere(cliente):
            try:
                v = allinea(cliente)
                risultati[cliente.nome] = "allineato" + (" (con novità)" if v else "")
            except OperazioneNonValida as e:
                cliente.allineamento_errore = str(e)[:1000]
                cliente.save(update_fields=["allineamento_errore"])
                log.warning("Allineamento soci con %s non riuscito: %s", cliente, e)
                risultati[cliente.nome] = f"errore: {e}"
        if cliente.allineamento_spinta and cliente.ruolo == ClienteApi.Ruolo.FEDERAZIONE:
            try:
                if spingi(cliente):
                    risultati[cliente.nome + " (spinta)"] = "inviato"
            except OperazioneNonValida as e:
                risultati[cliente.nome + " (spinta)"] = f"errore: {e}"
    return risultati


# --- modalità a spinta ---------------------------------------------------------------------------


def _impronta(elenco):
    testo = json.dumps(elenco, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(testo.encode()).hexdigest()


def spingi(cliente: ClienteApi, *, sempre=False):
    """Siamo la sezione e la federazione non ci raggiunge: le inviamo l'elenco dei nostri soci
    quando cambia (POST /consegne, cifrato). Restituisce l'esito della controparte o None se non
    c'era nulla di nuovo da inviare."""
    sezione = tessere.sezione_per(cliente)
    if cliente.ruolo != ClienteApi.Ruolo.FEDERAZIONE or sezione is None:
        raise OperazioneNonValida("La spinta dei soci si fa verso la federazione.")
    elenco = allineamento.elenco(sezione)
    impronta = _impronta(elenco)
    if impronta == cliente.spinta_impronta and not sempre:
        return None
    corpo = {"flusso": "soci", "sezione": {"codice": sezione.codice, "nome": sezione.nome},
             "soci": elenco}  # fmt: skip
    try:
        risposta, _, _ = client.chiama(cliente, "POST", "/consegne", corpo, cifra=True,
                                       extra={"Idempotency-Key": uuid.uuid4().hex})  # fmt: skip
        if risposta.stato != 200:
            raise OperazioneNonValida(f"La controparte ha risposto: {client._problema(risposta)}")
        esito = client.json_risposta(risposta)
    except (client.ErroreCollegamento, ErroreTrasporto) as e:
        cliente.allineamento_errore = f"Spinta non riuscita: {e}"[:1000]
        cliente.save(update_fields=["allineamento_errore"])
        raise OperazioneNonValida(f"Controparte non raggiungibile: {e}") from e
    except OperazioneNonValida as e:
        cliente.allineamento_errore = f"Spinta non riuscita: {e}"[:1000]
        cliente.save(update_fields=["allineamento_errore"])
        raise
    cliente.spinta_impronta, cliente.spinta_inviata_il = impronta, timezone.now()
    cliente.allineamento_errore = ""
    cliente.save(update_fields=["spinta_impronta", "spinta_inviata_il", "allineamento_errore"])
    return esito


def ricevi_consegna(cliente: ClienteApi, dati):
    """Siamo la federazione: la sezione ci ha inviato i suoi soci. Con l'automatico acceso si
    allinea subito; altrimenti resta una verifica da decidere (sostituisce quella di prima)."""
    if not isinstance(dati, dict) or dati.get("flusso") != "soci":
        raise OperazioneNonValida("Si accettano consegne del flusso «soci».")
    if cliente.ruolo != ClienteApi.Ruolo.SEZIONE or tessere.sezione_per(cliente) is None:
        raise OperazioneNonValida("Solo una sezione collegata può consegnare i propri soci.")
    righe = controlla_righe(dati.get("soci"))
    if cliente.allineamento_automatico:
        v = allinea(cliente, righe, origine="spinta")
        conteggi = v.proposta["conteggi"] if v else {}
        return {"flusso": "soci", "applicazione": "automatica", "conteggi": conteggi}
    sezione = tessere.sezione_per(cliente)
    with transaction.atomic():
        precedenti = VerificaSoci.objects.filter(cliente=cliente, origine="spinta",
                                                 applicata_il__isnull=True)  # fmt: skip
        gia_segnalata = precedenti.exists()
        precedenti.delete()
        proposta = allineamento.confronta(righe, sezione, da_sezione=True)
        v = VerificaSoci.objects.create(
            cliente=cliente, sezione=sezione, da_sezione=True, righe=righe, proposta=proposta,
            origine="spinta",
        )  # fmt: skip
    registra(Azione.CREAZIONE, v, descrizione=f"Soci ricevuti a spinta da {cliente}",
             **proposta["conteggi"])  # fmt: skip
    if not gia_segnalata:
        avvisa(v)
    return {"flusso": "soci", "applicazione": "in_anteprima", "conteggi": proposta["conteggi"]}


# --- avvisi --------------------------------------------------------------------------------------


def _riga_voce(voce, esiti):
    modifiche = "; ".join(f"{c}: {a} → {b}" for c, a, b in voce.get("modifiche") or [])
    esito = esiti.get(voce["indice"])
    if voce.get("allineamento") == "conflitto":
        chi = "la controparte" if voce.get("vince") == "controparte" else "questa installazione"
        testo = f"- {voce['nome']}: modificato da entrambe le parti, vale la modifica più " \
                f"recente ({chi})"  # fmt: skip
    elif voce.get("allineamento") in ("a_mano", "escluso"):
        testo = f"- {voce['nome']}: da verificare a mano"
        if voce.get("motivo"):
            testo += f" ({voce['motivo']})"
    elif voce["stato"] == "nuovo":
        testo = f"- {voce['nome']}: nuovo socio"
    else:
        testo = f"- {voce['nome']}"
    if esito and esito["esito"] == "errore":
        testo += f" - NON applicato: {'; '.join(esito['note'])}"
    return testo + (f"\n  {modifiche}" if modifiche else "")


def _testo(v):
    from apps.core.models import Organizzazione

    org = Organizzazione.corrente()
    esiti = {e["indice"]: e for e in v.esiti}
    c = v.proposta.get("conteggi", {})
    voci = v.proposta.get("voci", [])
    if v.automatica:
        righe = [f"{org.denominazione}: allineamento automatico dei soci di «{v.sezione}» con "
                 f"«{v.cliente}» del {timezone.localtime(v.creata_il):%d/%m/%Y %H:%M}.",
                 f"Creati {c.get('creato', 0)}, aggiornati {c.get('aggiornato', 0)}, "
                 f"errori {c.get('errore', 0)}, incongruenze {c.get('incongruenze', 0)}, "
                 f"da verificare {c.get('da_verificare', 0)}.", ""]  # fmt: skip
        if c.get("incongruenze"):
            righe += ["Incongruenze: lo stesso socio è stato modificato qui e presso la "
                      "controparte dopo l'ultimo allineamento. Vale la modifica più recente; "
                      "controllare che il risultato sia giusto.", ""]  # fmt: skip
    else:
        righe = [f"{org.denominazione}: «{v.cliente}» ha inviato i soci di «{v.sezione}».",
                 "L'allineamento automatico non è attivo: aprire la verifica e scegliere cosa "
                 "applicare.", ""]  # fmt: skip
        voci = [x for x in voci if x["stato"] in ("nuovo", "differenze")]
    for voce in voci[:MAX_ELENCATI]:
        righe.append(_riga_voce(voce, esiti))
    if len(voci) > MAX_ELENCATI:
        righe.append(f"- e altri {len(voci) - MAX_ELENCATI}")
    if settings.URL_PUBBLICO:
        righe += ["", f"{settings.URL_PUBBLICO}{reverse('api:verifica_soci', args=[v.pk])}"]
    return "\n".join(righe)


def destinatari(sezione):
    for utente in get_user_model().objects.filter(is_active=True).exclude(email=""):
        if not utente.has_perm(PERMESSO_AVVISI):
            continue
        from apps.soci import sezioni

        consentite = sezioni.id_sezioni(utente)
        if consentite is None or sezione.pk in consentite:
            yield utente


def avvisa(v: VerificaSoci):
    """Email a chi gestisce i soci della sezione (la federazione supervisiona così ogni novità
    arrivata dalle sezioni; la sezione vede ciò che arriva dalla federazione)."""
    from apps.core import veste_email
    from apps.core.models import Organizzazione

    org = Organizzazione.corrente()
    c = v.proposta.get("conteggi", {})
    if not v.automatica:
        oggetto = f"Soci da verificare inviati da {v.cliente}"
    elif c.get("incongruenze"):
        oggetto = f"Incongruenze nell'allineamento dei soci con {v.cliente}"
    else:
        oggetto = f"Allineamento dei soci con {v.cliente}"
    corpo = _testo(v)
    inviati = 0
    for utente in destinatari(v.sezione):
        try:
            email = EmailMessage(subject=f"{oggetto} - {org.denominazione}", body=corpo,
                                 to=[utente.email])  # fmt: skip
            veste_email.veste(email, org, titolo=oggetto, markdown=False).send()
            inviati += 1
        except OSError as e:  # la verifica resta comunque consultabile nella controparte
            log.warning("Avviso dell'allineamento soci non inviato a %s: %s", utente, e)
    return inviati
