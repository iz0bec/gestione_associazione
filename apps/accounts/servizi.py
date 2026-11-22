# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Gestione degli utenti: creazione, ruoli, password temporanee, secondo fattore
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import secrets

from allauth.mfa.models import Authenticator
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.core import sicurezza
from apps.core.audit import Azione, registra

from .models import PoliticaRuolo, Utente

# Caratteri senza ambiguità (niente 0/O, 1/l/I)
_ALFABETO = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
PERMESSO_GESTIONE = "accounts.change_utente"
FATTORI_FORTI = (Authenticator.Type.TOTP, Authenticator.Type.WEBAUTHN)


class OperazioneNonValida(ValidationError):
    """Operazione rifiutata per una regola sugli utenti (messaggio per l'utente)."""


def password_temporanea() -> str:
    """Password casuale leggibile, es. «Kp7x-Qm3a-Zt9w-Hn4c» (circa 110 bit)."""
    gruppi = ["".join(secrets.choice(_ALFABETO) for _ in range(4)) for _ in range(4)]
    return "-".join(gruppi)


# --- verifiche --------------------------------------------------------------------------


def puo_gestire(attore, utente) -> None:
    """Solo un superutente può intervenire su un superutente."""
    if utente.is_superuser and not attore.is_superuser:
        raise OperazioneNonValida("Solo un superutente può modificare un superutente.")


def _gruppi_danno_gestione(gruppi) -> bool:
    app_label, codename = PERMESSO_GESTIONE.split(".")
    return Permission.objects.filter(
        group__in=list(gruppi), content_type__app_label=app_label, codename=codename
    ).exists()


def controlla_ruoli_propri(attore, utente, gruppi) -> None:
    """Chi gestisce gli utenti non può togliersi da solo questa possibilità."""
    if utente.pk == attore.pk and not attore.is_superuser and not _gruppi_danno_gestione(gruppi):
        raise OperazioneNonValida(
            "Non puoi toglierti i ruoli che ti permettono di gestire gli utenti."
        )


def ha_secondo_fattore(utente) -> bool:
    return Authenticator.objects.filter(user=utente, type__in=FATTORI_FORTI).exists()


def mfa_richiesta(utente) -> bool:
    return PoliticaRuolo.objects.filter(
        ruolo__in=utente.groups.all(), mfa_obbligatoria=True
    ).exists()


def ruoli_con_mfa() -> set[int]:
    return set(
        PoliticaRuolo.objects.filter(mfa_obbligatoria=True).values_list("ruolo_id", flat=True)
    )


# --- operazioni -------------------------------------------------------------------------


def _collega_scheda(utente, form, attore):
    """Crea la scheda in anagrafica se richiesto; completa nome e cognome dalla scheda."""
    from apps.anagrafica.models import Soggetto

    if form.cleaned_data.get("crea_scheda"):
        soggetto = Soggetto.objects.create(
            tipo=Soggetto.Tipo.PERSONA, cognome=utente.last_name.strip(),
            nome=utente.first_name.strip(), email=utente.email, cellulare=utente.telefono,
            creato_da=attore, modificato_da=attore,
        )  # fmt: skip
        registra(Azione.CREAZIONE, soggetto, utente=attore, origine="utente " + utente.username)
        utente.soggetto = soggetto
    elif utente.soggetto_id:
        utente.first_name = utente.first_name or utente.soggetto.nome
        utente.last_name = utente.last_name or utente.soggetto.cognome


@transaction.atomic
def crea_utente(form, attore) -> tuple[Utente, str]:
    """Salva un nuovo utente dal modulo; restituisce l'utente e la password temporanea."""
    utente = form.save(commit=False)
    _collega_scheda(utente, form, attore)
    password = password_temporanea()
    utente.set_password(password)
    utente.deve_cambiare_password = utente.puo_cambiare_password
    utente.is_staff = False
    utente.is_superuser = False
    utente.save()
    form.save_m2m()
    ruoli = [g.name for g in utente.groups.all()]
    registra(Azione.CREAZIONE, utente, ruoli=ruoli, sezioni=[str(s) for s in utente.sezioni.all()])
    sicurezza.operazione_utenti(
        f"Nuovo utente {utente.username} ({', '.join(ruoli) or 'senza ruoli'})", attore
    )
    return utente, password


@transaction.atomic
def aggiorna_utente(form, attore, dettagli: dict) -> Utente:
    puo_gestire(attore, form.instance)
    controlla_ruoli_propri(attore, form.instance, form.cleaned_data["groups"])
    utente = form.save(commit=False)
    _collega_scheda(utente, form, attore)
    utente.save()
    form.save_m2m()
    if dettagli.get("campi"):
        registra(Azione.MODIFICA, utente, **dettagli)
    if ruoli := dettagli.get("campi", {}).get("groups"):
        prima = ", ".join(ruoli["prima"] or []) or "nessuno"
        dopo = ", ".join(ruoli["dopo"] or []) or "nessuno"
        sicurezza.operazione_utenti(f"Ruoli di {utente.username}: {prima} → {dopo}", attore)
    return utente


@transaction.atomic
def reimposta_password(utente, attore) -> str:
    puo_gestire(attore, utente)
    if utente.pk == attore.pk:
        raise OperazioneNonValida("Per la tua password usa la pagina del tuo profilo.")
    password = password_temporanea()
    utente.set_password(password)
    utente.deve_cambiare_password = utente.puo_cambiare_password
    utente.save(update_fields=["password", "deve_cambiare_password"])
    registra(Azione.MODIFICA, utente, operazione="password temporanea")
    sicurezza.operazione_utenti(f"Password temporanea per {utente.username}", attore)
    return password


def imposta_password(utente, attore, password, *, obbligo_cambio=False):
    """Password scelta dall'amministratore (validata come le altre); mai nel registro."""
    from django.contrib.auth.password_validation import validate_password

    puo_gestire(attore, utente)
    if utente.pk == attore.pk:
        raise OperazioneNonValida("Per la tua password usa la pagina del tuo profilo.")
    validate_password(password, utente)
    utente.set_password(password)
    utente.deve_cambiare_password = obbligo_cambio and utente.puo_cambiare_password
    utente.save(update_fields=["password", "deve_cambiare_password"])
    registra(Azione.MODIFICA, utente, operazione="password impostata dall'amministratore",
             obbligo_cambio=utente.deve_cambiare_password)  # fmt: skip
    sicurezza.operazione_utenti(f"Password di {utente.username} impostata", attore)
    return utente


@transaction.atomic
def azzera_secondo_fattore(utente, attore) -> int:
    """Elimina app di autenticazione, passkey e codici di recupero (es. telefono perso)."""
    puo_gestire(attore, utente)
    if utente.pk == attore.pk:
        raise OperazioneNonValida("Il tuo secondo fattore si gestisce dal tuo profilo.")
    eliminati, _ = Authenticator.objects.filter(user=utente).delete()
    registra(Azione.MODIFICA, utente, operazione="secondo fattore azzerato", eliminati=eliminati)
    sicurezza.operazione_utenti(f"Secondo fattore di {utente.username} azzerato", attore)
    return eliminati


@transaction.atomic
def imposta_attivo(utente, attore, attivo: bool) -> None:
    puo_gestire(attore, utente)
    if utente.pk == attore.pk and not attivo:
        raise OperazioneNonValida("Non puoi disattivare il tuo account.")
    if utente.is_active == attivo:
        return
    utente.is_active = attivo
    utente.save(update_fields=["is_active"])
    registra(
        Azione.ARCHIVIAZIONE if not attivo else Azione.MODIFICA,
        utente,
        operazione="disattivato" if not attivo else "riattivato",
    )
    stato = "disattivato" if not attivo else "riattivato"
    sicurezza.operazione_utenti(f"Utente {utente.username} {stato}", attore)


@transaction.atomic
def imposta_mfa_ruoli(ruoli_obbligati: set[int], tutti) -> list[str]:
    """Allinea le regole dei ruoli; restituisce i nomi dei ruoli cambiati."""
    cambiati = []
    for ruolo in tutti:
        politica, _ = PoliticaRuolo.objects.get_or_create(ruolo=ruolo)
        valore = ruolo.pk in ruoli_obbligati
        if politica.mfa_obbligatoria != valore:
            politica.mfa_obbligatoria = valore
            politica.save(update_fields=["mfa_obbligatoria"])
            cambiati.append(ruolo.name)
    if cambiati:
        registra(
            Azione.MODIFICA,
            descrizione="Secondo fattore obbligatorio per ruolo",
            ruoli=cambiati,
            obbligatori=sorted(r.name for r in tutti if r.pk in ruoli_obbligati),
        )
    return cambiati


# --- utenti «standard» dalle cariche degli organi sociali -------------------------------------
# (chiave, etichetta, ruoli del gestionale, utente attivo per impostazione predefinita)
CATEGORIE_CARICA = [
    ("presidente", "Presidente", ["Presidente"], True),
    ("vicepresidente", "Vicepresidente", ["Presidente"], True),
    ("segretario", "Segretario", ["Segretario", "Tesoriere"], True),
    ("tesoriere", "Tesoriere", ["Tesoriere"], False),
    ("consigliere", "Consigliere", ["Consigliere"], False),
    ("supplente", "Supplente", ["Consigliere"], False),
    ("controllo", "Organo di controllo", ["Revisore"], False),
    ("altro", "Altri organi (es. garanti)", ["Consigliere"], False),
]
_ORDINE = [c[0] for c in CATEGORIE_CARICA]
_GRUPPI = {c[0]: c[2] for c in CATEGORIE_CARICA}
EMAIL_SEGNAPOSTO = "senza-email.invalid"


def categoria_carica(carica) -> str:
    tipo = carica.organo.tipo
    if tipo == "controllo" or carica.ruolo == "presidente_controllo":
        return "controllo"
    if tipo == "altro":
        return "altro"
    return carica.ruolo if carica.ruolo in _GRUPPI else "consigliere"


def _normalizza(testo) -> str:
    import unicodedata

    testo = unicodedata.normalize("NFKD", testo or "").encode("ascii", "ignore").decode().lower()
    return "".join(c for c in testo if c.isalnum())


def nome_utente_proposto(soggetto) -> str:
    nome = (soggetto.nome or "").replace(".", " ").split()
    base = ".".join(
        p for p in (_normalizza(nome[0] if nome else ""), _normalizza(soggetto.cognome)) if p
    )
    base = base or f"utente{soggetto.pk}"
    proposto, i = base, 2
    while Utente.objects.filter(username__iexact=proposto).exists():
        proposto, i = f"{base}{i}", i + 1
    return proposto


def proposte_da_cariche():
    """Persone con una carica in corso negli organi attivi (non assemblee) e senza utente:
    [{soggetto, categoria, categorie, ruoli, cariche, sezioni, username}], per categoria."""
    from django.db.models import Q
    from django.utils import timezone

    from apps.organi.models import Carica
    from apps.soci.sezioni import multisezione

    oggi = timezone.localdate()
    cariche = (
        Carica.objects.filter(Q(al__isnull=True) | Q(al__gte=oggi), dal__lte=oggi,
                              organo__attivo=True, soggetto__utente__isnull=True)
        .exclude(organo__tipo="assemblea")
        .select_related("organo", "organo__sezione", "soggetto")
    )  # fmt: skip
    per_persona = {}
    for c in cariche:
        p = per_persona.setdefault(c.soggetto_id, {"soggetto": c.soggetto, "categorie": set(),
                                                   "cariche": [], "sezioni": set()})  # fmt: skip
        p["categorie"].add(categoria_carica(c))
        p["cariche"].append(c)
        if c.organo.sezione_id:
            p["sezioni"].add(c.organo.sezione)
    limita = multisezione()
    proposte = []
    for p in per_persona.values():
        p["categoria"] = min(p["categorie"], key=_ORDINE.index)
        p["ruoli"] = sorted({g for k in p["categorie"] for g in _GRUPPI[k]})
        # in un'installazione con più sezioni chi ha cariche solo in una sezione vede solo quella
        p["sezioni"] = sorted(p["sezioni"], key=str) if limita and all(
            c.organo.sezione_id for c in p["cariche"]) else []  # fmt: skip
        p["username"] = nome_utente_proposto(p["soggetto"])
        proposte.append(p)
    return sorted(proposte, key=lambda p: (_ORDINE.index(p["categoria"]), str(p["soggetto"])))


@transaction.atomic
def crea_utenti_da_cariche(attore, soggetti, password, attive, *, obbligo_cambio=False):
    """Crea un utente per ognuna delle persone indicate (id dei soggetti) tra le proposte.
    `password`: {categoria: password} (vuota = generata, una per categoria); `attive`: categorie il
    cui utente nasce attivo. Restituisce (utenti creati [(utente, categoria)], password usate)."""
    from django.contrib.auth.models import Group
    from django.contrib.auth.password_validation import validate_password

    proposte = {p["soggetto"].pk: p for p in proposte_da_cariche() if p["soggetto"].pk in soggetti}
    if not proposte:
        raise OperazioneNonValida("Nessuna persona scelta (o hanno già un utente).")
    usate = {}
    for p in proposte.values():
        k = p["categoria"]
        if k not in usate:
            scelta = (password.get(k) or "").strip()
            if scelta:
                try:
                    validate_password(scelta)
                except ValidationError as e:
                    etichetta = {c[0]: c[1] for c in CATEGORIE_CARICA}[k]
                    raise OperazioneNonValida(
                        f"Password per «{etichetta}»: {' '.join(e.messages)}"
                    ) from e
            usate[k] = scelta or password_temporanea()
    creati = []
    for p in proposte.values():
        s, k = p["soggetto"], p["categoria"]
        username = nome_utente_proposto(s)
        email = (
            s.email if s.email and not Utente.objects.filter(email__iexact=s.email).exists() else ""
        )
        utente = Utente(username=username, email=email or f"{username}@{EMAIL_SEGNAPOSTO}",
                        first_name=s.nome[:150], last_name=s.cognome[:150], soggetto=s,
                        is_active=bool(p["categorie"] & set(attive)),
                        deve_cambiare_password=obbligo_cambio)  # fmt: skip
        utente.set_password(usate[k])
        utente.save()
        utente.groups.set(Group.objects.filter(name__in=p["ruoli"]))
        if p["sezioni"]:
            utente.sezioni.set(p["sezioni"])
        registra(Azione.CREAZIONE, utente, utente=attore, origine="cariche degli organi",
                 ruoli=p["ruoli"], attivo=utente.is_active)  # fmt: skip
        creati.append((utente, k))
    sicurezza.operazione_utenti(f"{len(creati)} utenti creati dalle cariche degli organi", attore)
    return creati, usate


CAMBIO_OBBLIGATO = "Al primo accesso il programma ti chiederà di sceglierne una nuova."
CAMBIO_CONSIGLIATO = "**Cambia la password al primo accesso.**"
MFA_OBBLIGATORIA = (
    "Al primo accesso ti verrà chiesto anche di attivare la **verifica in due passaggi** (app di "
    "autenticazione sul telefono o chiave di sicurezza): segui le indicazioni a schermo."
)
MFA_CONSIGLIATA = (
    "Per più sicurezza puoi attivare la **verifica in due passaggi** dal menu con il tuo nome, "
    "voce *Verifica in due passaggi*."
)
# testo della bozza: {{ saluto }} e {{ nome }} sono segnaposto delle comunicazioni (raddoppiati)
TESTO_CREDENZIALI = """{{{{ saluto }}}} {{{{ nome }}}},

per il tuo incarico è stato creato il tuo accesso al gestionale di {ente}.

- Indirizzo: {indirizzo}
- Nome utente: **{utente}**
- Password iniziale: **{password}**
- Ruolo nel gestionale: {ruoli}

{cambio}

Come cambiare la password:

1. apri {indirizzo} ed entra con nome utente e password iniziale;
2. in alto a destra apri il menu con il tuo nome e scegli **Cambia password**;
3. scrivi la password attuale e due volte quella nuova (almeno 12 caratteri, non troppo comune) e
   premi **Cambia password**.

{mfa}

Il **manuale** è nel programma: il pulsante **?** in alto, in ogni pagina, apre la parte che
riguarda la pagina che stai usando; dal menu con il tuo nome, voce **Manuale**, trovi l'indice
completo e il pulsante **Manuale in PDF** per scaricarlo. Il manuale in PDF è anche qui:
https://github.com/iz0bec/gestione_associazione/blob/main/docs/manuale/manuale-operativo.pdf

Per qualsiasi difficoltà rispondi a questo messaggio.

Non inoltrare questo messaggio: contiene le tue credenziali personali.
"""


TESTO_PER_CONTO = """{{{{ saluto }}}} {{{{ nome }}}},

ti scriviamo{qualita} perché **{persona}**, {carica}, non ha un indirizzo email registrato nel
gestionale di {ente}. Ti chiediamo di consegnare personalmente a questa persona le credenziali di
accesso qui sotto.

- Indirizzo: {indirizzo}
- Nome utente: **{utente}**
- Password iniziale: **{password}**
- Ruolo nel gestionale: {ruoli}

Invitala a **cambiare la password al primo accesso** e a **dotarsi di un indirizzo email**, da
comunicare alla segreteria perché venga inserito nella sua scheda: per il corretto svolgimento
delle attività di gestione (recupero della password, avvisi, comunicazioni) è opportuno che ogni
incaricato ne abbia uno.

Come cambiare la password: aprire {indirizzo} ed entrare con nome utente e password iniziale; in
alto a destra aprire il menu con il proprio nome, scegliere **Cambia password**, scrivere la
password attuale e due volte quella nuova (almeno 12 caratteri, non troppo comune).

Il **manuale** è nel programma: il pulsante **?** in alto, in ogni pagina, apre la parte che
riguarda la pagina in uso; dal menu con il proprio nome, voce **Manuale**, si trovano l'indice
completo e il pulsante **Manuale in PDF** per scaricarlo. Il manuale in PDF è anche qui:
https://github.com/iz0bec/gestione_associazione/blob/main/docs/manuale/manuale-operativo.pdf

**Uso di queste informazioni**: le credenziali riguardano un'altra persona e ti sono affidate solo
perché tu possa consegnarle. Usale esclusivamente per questo scopo, non conservarle e non inoltrarle
ad altri.

Per qualsiasi difficoltà rispondi a questo messaggio.
"""
ORIGINE_BOZZE = "utenti-cariche"
ORDINE_RICEVENTE = [
    "presidente", "vicepresidente", "segretario", "tesoriere", "consigliere", "supplente",
    "presidente_controllo", "componente",
]  # fmt: skip


def ricevente_per_conto(soggetto):
    """Chi riceve le credenziali di chi non ha l'email: la carica più alta, con un'email, dello
    stesso organo (il consiglio prima degli altri). Restituisce (carica del ricevente o None se
    nessuno: si usa la casella dell'ente, carica della persona)."""
    from django.db.models import Q
    from django.utils import timezone

    from apps.organi.models import Carica

    oggi = timezone.localdate()
    in_corso = Carica.objects.filter(
        Q(al__isnull=True) | Q(al__gte=oggi), dal__lte=oggi, organo__attivo=True
    ).exclude(organo__tipo="assemblea")
    proprie = list(in_corso.filter(soggetto=soggetto).select_related("organo"))
    for carica in sorted(proprie, key=lambda c: c.organo.tipo != "consiglio"):
        altri = (
            in_corso.filter(organo=carica.organo, ruolo__in=ORDINE_RICEVENTE)
            .exclude(soggetto=soggetto)
            .exclude(soggetto__email="")
            .select_related("soggetto")
        )
        if altri:
            return min(altri, key=lambda c: ORDINE_RICEVENTE.index(c.ruolo)), carica
    return None, (proprie[0] if proprie else None)


def _bozza_diretta(attore, utente, password, indirizzo, org):
    from apps.comunicazioni import servizi as comunicazioni
    from apps.comunicazioni.models import Finalita

    corpo = TESTO_CREDENZIALI.format(
        ente=org.denominazione,
        indirizzo=indirizzo,
        utente=utente.username,
        password=password,
        ruoli=", ".join(g.name for g in utente.groups.all()),
        cambio=CAMBIO_OBBLIGATO if utente.deve_cambiare_password else CAMBIO_CONSIGLIATO,
        mfa=MFA_OBBLIGATORIA if mfa_richiesta(utente) else MFA_CONSIGLIATA,
    )
    return comunicazioni.crea_invio(
        attore,
        oggetto=f"Accesso al gestionale - {org.denominazione}",
        corpo=corpo,
        finalita=Finalita.ISTITUZIONALE,
        soggetti=[utente.soggetto],
        origine=ORIGINE_BOZZE,
    )


def _bozza_per_conto(attore, utente, password, indirizzo, org):
    """Bozza per chi non ha l'email, a chi la consegna; None se non c'è nessun destinatario."""
    from apps.comunicazioni import servizi as comunicazioni
    from apps.comunicazioni.models import Finalita

    ricevente, carica = (None, None)
    if utente.soggetto:
        ricevente, carica = ricevente_per_conto(utente.soggetto)
    if ricevente is None and not org.email:
        return None
    persona = utente.get_full_name() or utente.username
    corpo = TESTO_PER_CONTO.format(
        ente=org.denominazione,
        indirizzo=indirizzo,
        utente=utente.username,
        password=password,
        ruoli=", ".join(g.name for g in utente.groups.all()),
        persona=persona,
        carica=f"{carica.get_ruolo_display().lower()} ({carica.organo})"
        if carica
        else "incaricato",
        qualita=f" in qualità di {ricevente.get_ruolo_display().lower()}" if ricevente else "",
    )
    comuni = {
        "oggetto": f"Accesso al gestionale per conto di {persona} - {org.denominazione}",
        "finalita": Finalita.ISTITUZIONALE,
        "origine": ORIGINE_BOZZE,
    }
    if ricevente is not None:
        invio = comunicazioni.crea_invio(
            attore, corpo=corpo, soggetti=[ricevente.soggetto], **comuni
        )
    else:  # nessuno con l'email nell'organo: la casella dell'ente
        corpo = corpo.replace("{{ saluto }} {{ nome }},", "Alla cortese attenzione del Presidente,")
        invio = comunicazioni.crea_invio(
            attore, corpo=corpo, indirizzi=[(org.denominazione, org.email)], **comuni
        )
    invio.per_conto = persona
    return invio


def bozze_credenziali(attore, creati, usate, indirizzo):
    """Una comunicazione in bozza per ogni utente attivo: a chi ha un'email le sue credenziali e i
    passaggi per cambiare la password; per chi non ce l'ha, una bozza «per conto» alla carica più
    alta dello stesso organo con un'email (o alla casella dell'ente), che gliele consegni e lo
    inviti a dotarsi di un'email. Restituisce (bozze create, utenti senza alcun destinatario)."""
    from apps.core.models import Organizzazione

    org = Organizzazione.corrente()
    bozze, senza = [], []
    for utente, k in creati:
        if not utente.is_active:
            continue
        if utente.soggetto and utente.soggetto.email:
            bozze.append(_bozza_diretta(attore, utente, usate[k], indirizzo, org))
        elif invio := _bozza_per_conto(attore, utente, usate[k], indirizzo, org):
            bozze.append(invio)
        else:
            senza.append(utente)
    return bozze, senza
