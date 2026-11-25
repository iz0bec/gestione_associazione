# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Verifica dei soci fra federazione e sezione (ADR-030, F4): elenco dei soci di
# *              una sezione da esporre alla controparte, confronto con i soci ricevuti (chi
# *              manca si popola, chi c'è mostra campo per campo le modifiche proposte) e
# *              applicazione delle sole modifiche scelte, con le regole dell'importazione.
# *              La sezione aggiorna anagrafiche e rinnovi; la federazione solo le anagrafiche.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from contextlib import nullcontext
from dataclasses import replace
from datetime import date, datetime

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.core.audit import Azione, registra

from . import importazione as imp
from . import servizi
from .models import Socio, Tessera, TipologiaSocio

ETICHETTE = {
    "sesso": "sesso", "data_nascita": "data di nascita", "luogo_nascita": "luogo di nascita",
    "indirizzo": "indirizzo", "cap": "CAP", "comune": "comune", "provincia": "provincia",
    "email": "email", "telefono": "telefono", "cellulare": "cellulare", "matricola": "matricola",
}  # fmt: skip
ANNI_TESSERE = 1  # oltre all'anno in corso, il precedente (e i successivi già aperti)


# --- elenco da esporre ---------------------------------------------------------------------------


def _iso(valore):
    return valore.isoformat() if valore else ""


def riga(socio, tessere, trasferito_da=""):
    """Dati di un socio per la controparte (stessi nomi dei campi dell'importazione).
    `trasferito_da`: codice della sezione di provenienza se è arrivato per trasferimento."""
    p = socio.soggetto
    momenti = [socio.modificato_il, p.modificato_il, *(t.modificato_il for t in tessere)]
    return {
        "codice_fiscale": p.codice_fiscale or "", "cognome": p.cognome, "nome": p.nome,
        **{c: _iso(v) if isinstance(v := getattr(p, c), date) else (v or "")
           for c in imp.CAMPI_ANAGRAFICI},
        "matricola": socio.matricola, "tipologia": socio.tipologia.nome,
        "data_iscrizione": _iso(socio.data_ammissione), "stato_socio": socio.stato,
        "data_cessazione": _iso(socio.data_cessazione),
        "causa_cessazione": socio.get_causa_cessazione_display() if socio.causa_cessazione else "",
        "tessere": [
            {"anno": t.anno, "codice": t.carta.codice if t.carta_id else "",
             "data": _iso(t.data_rilascio), "pagata": t.pagata or t.importo == 0,
             "pagata_il": _iso(t.pagata_il)}
            for t in tessere
        ],
        "modificato_il": max(momenti).isoformat(),
        "trasferito_da": trasferito_da,
    }  # fmt: skip


def _soci(sezione):
    return Socio.objects.filter(sezione=sezione).select_related("soggetto", "tipologia")


def _tessere(soci):
    elenco = {}
    for t in (
        Tessera.objects.valide()
        .filter(socio__in=soci, anno__gte=date.today().year - ANNI_TESSERE)
        .select_related("carta")
        .order_by("anno")
    ):
        elenco.setdefault(t.socio_id, []).append(t)
    return elenco


def elenco(sezione):
    """Tutti i soci della sezione, cessati compresi."""
    from apps.collegamenti.trasferimenti import codici_origine

    soci = list(_soci(sezione).order_by("numero"))
    tessere = _tessere(soci)
    origini = codici_origine(soci)
    return [riga(s, tessere.get(s.pk, []), origini.get(s.pk, "")) for s in soci]


def numeri(sezione, anno=None):
    """Numeri del tesseramento della sezione nell'anno: solo conteggi, nessun dato personale."""
    from django.db.models import Q

    anno = anno or date.today().year
    soci = Socio.objects.filter(sezione=sezione)
    tessere = Tessera.objects.valide().filter(socio__sezione=sezione, anno=anno)
    return {
        "anno": anno,
        "soci_attivi": soci.filter(stato=Socio.Stato.ATTIVO).count(),
        "soci_sospesi": soci.filter(stato=Socio.Stato.SOSPESO).count(),
        "tessere": tessere.count(),
        "tessere_pagate": tessere.filter(Q(pagata_il__isnull=False) | Q(importo=0)).count(),
        "tessere_senza_carta": tessere.filter(carta__isnull=True).count(),
        "nuovi_iscritti": soci.filter(data_ammissione__year=anno).count(),
        "cessati": soci.filter(data_cessazione__year=anno).count(),
    }


# --- confronto -----------------------------------------------------------------------------------


def _pulita(remota):
    dati = {k: v for k, v in remota.items()
            if k not in ("tessere", "modificato_il", "trasferito_da")}  # fmt: skip
    return imp._pulisci(dati)


class Omonimi(Exception):
    pass


def trova(d, sezione, tessere_remote=()):
    """Persona già presente: codice fiscale, matricola o nome con data di nascita (come
    l'importazione); senza questi dati, nella sezione, per numero di tessera o per nome e
    cognome se unico. Omonimi non distinguibili: eccezione (meglio fermarsi che duplicare)."""
    if soggetto := imp._trova_soggetto(d):
        return soggetto
    if d["codice_fiscale"]:
        return None  # codice fiscale noto e assente qui: è davvero un altro
    nella_sezione = Socio.objects.filter(sezione=sezione).select_related("soggetto")
    codici = {str(t["codice"]) for t in tessere_remote if t.get("codice")}
    if codici:
        per_tessera = list(
            nella_sezione.filter(
                tessere__carta__codice__in=codici, tessere__annullata=False
            ).distinct()[:2]
        )
        if len(per_tessera) == 1:
            return per_tessera[0].soggetto
    omonimi = list(nella_sezione.filter(soggetto__cognome__iexact=d["cognome"],
                                        soggetto__nome__iexact=d["nome"])[:2])  # fmt: skip
    if len(omonimi) == 1 and not (d["data_nascita"] and omonimi[0].soggetto.data_nascita):
        return omonimi[0].soggetto
    if len(omonimi) > 1:
        raise Omonimi("più soci con lo stesso nome qui, senza codice fiscale né data di nascita "
                      "per distinguerli: verificare a mano")  # fmt: skip
    return None


def _momento(testo):
    try:
        return datetime.fromisoformat(testo) if testo else None
    except ValueError:
        return None


def _mostra(valore):
    return imp._mostra(valore)


def _modifiche_anagrafica(socio, d):
    p = socio.soggetto
    modifiche = []
    noti = {c for _, c in imp.numeri_telefono(p.telefono, p.cellulare)}
    for c in imp.CAMPI_ANAGRAFICI:
        if (
            c in ("telefono", "cellulare")
            and not getattr(p, c)
            and d.get(c)
            and all(n in noti for _, n in imp.numeri_telefono(d[c]))
        ):
            continue  # numero già presente qui nell'altro campo
        if d.get(c) and (not getattr(p, c) or imp._diverso(p, c, d)):
            modifiche.append([ETICHETTE[c], _mostra(getattr(p, c)), _mostra(d[c])])
    if d.get("matricola") and d["matricola"] != socio.matricola:
        modifiche.append([ETICHETTE["matricola"], _mostra(socio.matricola), d["matricola"]])
    return modifiche


CAUSA_TRASFERIMENTO = "Trasferimento ad altra sezione"


def _per_trasferimento(d):
    return (d.get("causa_cessazione") or "").strip().lower() == CAUSA_TRASFERIMENTO.lower()


def _modifiche_sezione(socio, d, tessere_remote, tessere_locali):
    """Stato, cessazione e rinnovi: solo quando la controparte è la sezione."""
    modifiche = []
    voluto = imp._stato_socio(d.get("stato_socio"))
    if d.get("data_cessazione") and _per_trasferimento(d):
        return modifiche  # il socio passa a un'altra sezione: lo sposta la riga della sezione nuova
    if d.get("data_cessazione") and socio.stato != Socio.Stato.CESSATO:
        modifiche.append(["cessazione", "—", f"{d['data_cessazione']:%d/%m/%Y} "
                          f"({d.get('causa_cessazione') or 'causa non indicata'})"])  # fmt: skip
    elif voluto in (Socio.Stato.ATTIVO, Socio.Stato.SOSPESO) and voluto != socio.stato \
            and socio.stato != Socio.Stato.CESSATO:  # fmt: skip
        modifiche.append(["stato", socio.get_stato_display(), Socio.Stato(voluto).label])
    if socio.stato == Socio.Stato.CESSATO or d.get("data_cessazione"):
        return modifiche
    locali = {t.anno: t for t in tessere_locali}
    for t in tessere_remote:
        if not t.get("codice"):
            continue
        locale = locali.get(t["anno"])
        codice_locale = locale.carta.codice if locale and locale.carta_id else ""
        if not codice_locale:
            modifiche.append([f"tessera {t['anno']}", "—", t["codice"]])
        elif codice_locale != t["codice"] and str(locale.carta.numero) != t["codice"].lstrip("0"):
            modifiche.append([f"tessera {t['anno']}", codice_locale,
                              f"{t['codice']} (diversa: da correggere a mano)"])  # fmt: skip
            continue
        if t.get("pagata") and not (locale and (locale.pagata or locale.importo == 0)):
            modifiche.append([f"quota {t['anno']}", "da versare", "versata"])
    return modifiche


def confronta(righe_remote, sezione, *, da_sezione):
    """Proposta: per ogni socio ricevuto «nuovo» (si crea), «differenze» (modifiche campo per
    campo), «invariato» o «escluso» (con il motivo). `da_sezione`: la controparte è la sezione
    (manda anche stato, cessazioni e rinnovi). Nulla viene modificato."""
    soci = list(_soci(sezione))
    tessere = _tessere(soci)
    trovati, voci = set(), []
    for i, remota in enumerate(righe_remote):
        d = _pulita(remota)
        nome = f"{d['cognome']} {d['nome']}".strip() or "(senza nome)"
        voce = {"indice": i, "nome": nome, "codice_fiscale": d["codice_fiscale"],
                "modifiche": [], "motivo": "", "piu_recente": "",
                "remoto_il": remota.get("modificato_il") or "", "locale_il": ""}  # fmt: skip
        try:
            soggetto = trova(d, sezione, remota.get("tessere") or []) if d["cognome"] else None
        except Omonimi as e:
            voce.update(stato="escluso", motivo=str(e))
            voci.append(voce)
            continue
        socio = getattr(soggetto, "socio", None) if soggetto else None
        if socio is not None and socio.pk in trovati:
            motivo = f"stesso socio di un'altra riga (n. {socio.numero}): verificare a mano"
            voce.update(stato="escluso", motivo=motivo)
            voci.append(voce)
            continue
        if not d["cognome"]:
            voce.update(stato="escluso", motivo="cognome mancante")
        elif socio is None:
            voce["stato"] = "nuovo"
            if soggetto is not None:
                voce["motivo"] = "già in anagrafica: si iscrive al libro soci"
        elif socio.sezione_id != sezione.pk:
            trovati.add(socio.pk)
            origine = remota.get("trasferito_da") or ""
            if da_sezione and origine and origine == socio.sezione.codice \
                    and socio.stato != Socio.Stato.CESSATO:  # fmt: skip
                # arrivato per trasferimento dalla sezione in cui è qui: si sposta
                modifiche = [["sezione", str(socio.sezione), str(sezione)]]
                modifiche += _modifiche_anagrafica(socio, d)
                voce.update(stato="differenze", modifiche=modifiche, trasferimento=origine,
                            locale_il=socio.modificato_il.isoformat())  # fmt: skip
            elif _per_trasferimento(d):
                voce["stato"] = "invariato"  # ceduto da quella sezione: già spostato qui
            else:
                voce.update(stato="escluso", motivo=f"qui è socio della sezione «{socio.sezione}»")
        else:
            trovati.add(socio.pk)
            modifiche = _modifiche_anagrafica(socio, d)
            if da_sezione:
                modifiche += _modifiche_sezione(socio, d, remota.get("tessere") or [],
                                                tessere.get(socio.pk, []))  # fmt: skip
            locale = max([socio.modificato_il, socio.soggetto.modificato_il,
                          *(t.modificato_il for t in tessere.get(socio.pk, []))])  # fmt: skip
            remoto = _momento(remota.get("modificato_il"))
            voce["locale_il"] = locale.isoformat()
            if modifiche and remoto:
                voce["piu_recente"] = "controparte" if remoto > locale else "qui"
            voce.update(stato="differenze" if modifiche else "invariato", modifiche=modifiche)
        voci.append(voce)
    solo_qui = [
        {"numero": s.numero, "nome": s.soggetto.nome_completo, "stato": s.get_stato_display()}
        for s in sorted(soci, key=lambda s: s.numero)
        if s.pk not in trovati and s.stato != Socio.Stato.CESSATO
    ]
    conteggi = {k: sum(1 for v in voci if v["stato"] == k)
                for k in ("nuovo", "differenze", "invariato", "escluso")}  # fmt: skip
    return {"voci": voci, "solo_qui": solo_qui, "conteggi": conteggi}


# --- applicazione --------------------------------------------------------------------------------


def _opzioni(sezione, controparte):
    tipologia = TipologiaSocio.objects.filter(attiva=True).order_by("ordine", "pk").first()
    return imp.Opzioni(sezione=sezione, tipologia=tipologia, tessere=False, cessazioni=True,
                       valido=True, crea_tessere=True,
                       fonte=f"gestionale di {controparte}"[:100])  # fmt: skip


def _applica_tessere(socio, tessere_remote, opzioni, utente):
    note = []
    socio.refresh_from_db()
    for t in tessere_remote:
        if not t.get("codice") or not str(t.get("anno", "")).isdigit():
            continue
        note += imp._tessera(
            socio, str(t["codice"]), int(t["anno"]), imp._data(t.get("data")), opzioni, utente,
            pagata=bool(t.get("pagata")), pagata_il=imp._data(t.get("pagata_il")),
        )  # fmt: skip
    return note


def _sospendi_se_serve(socio, d, utente):
    socio.refresh_from_db()
    if imp._stato_socio(d.get("stato_socio")) == Socio.Stato.SOSPESO and \
            socio.stato == Socio.Stato.ATTIVO:  # fmt: skip
        servizi.cambia_stato(socio, Socio.Stato.SOSPESO, utente, motivo="Verifica soci")
        return ["sospeso"]
    return []


def _applica_voce(remota, voce, sezione, opzioni, utente, *, da_sezione):
    d = _pulita(remota)
    tessere_remote = remota.get("tessere") or []
    try:
        soggetto = trova(d, sezione, tessere_remote)
    except Omonimi as e:
        raise imp._Errore(str(e)) from None
    if voce["stato"] == "nuovo":
        if soggetto is not None and getattr(soggetto, "socio", None) is not None:
            raise imp._Errore("è già socio qui (forse da una verifica precedente): rifare la "
                              "verifica")  # fmt: skip
        # popolamento: tutto quello che la controparte sa del socio, storia delle tessere compresa
        _, note, socio = imp._riga(d, sezione, opzioni, utente, soggetto=soggetto)
        note += _applica_tessere(socio, tessere_remote, opzioni, utente)
        return note + _sospendi_se_serve(socio, d, utente)
    socio = getattr(soggetto, "socio", None) if soggetto else None
    if socio is not None and voce.get("trasferimento") and socio.sezione_id != sezione.pk:
        if socio.sezione.codice != voce["trasferimento"]:
            raise imp._Errore("il socio non è più nella sezione di provenienza")
        servizi.trasferisci(socio, sezione, utente, data=max(date.today(), socio.data_ammissione),
                            motivo="Trasferimento fra sezioni collegate")  # fmt: skip
        socio.refresh_from_db()
    if socio is None or socio.sezione_id != sezione.pk:
        raise imp._Errore("socio non più presente in questa sezione")
    if not da_sezione:  # dalla federazione solo le anagrafiche: niente stato, cessazioni, rinnovi
        for chiave in ("stato_socio", "data_cessazione", "causa_cessazione"):
            d[chiave] = ""
    _, note, socio = imp._riga(d, sezione, replace(opzioni, aggiorna_dati=True,
                                                    cessazioni=da_sezione), utente,
                               soggetto=soggetto)  # fmt: skip
    if da_sezione:
        note += _applica_tessere(socio, tessere_remote, opzioni, utente)
    return note


def applica(righe_remote, proposta, scelti, sezione, utente, *, da_sezione, controparte=""):
    """Applica le voci scelte (indici) della proposta; ogni voce riesce o fallisce da sola.
    Restituisce gli esiti [{indice, nome, esito, note}]."""
    from . import promemoria

    scelti = set(scelti)
    opzioni = _opzioni(sezione, controparte or "un'altra installazione")
    esiti = []
    # dalla federazione (l'archivio centrale della sezione) nessun promemoria; dalla sezione sì:
    # la federazione deve riportare i dati nel registro nazionale
    with nullcontext() if da_sezione else promemoria.sospesi(), transaction.atomic():
        for voce in proposta["voci"]:
            if voce["indice"] not in scelti or voce["stato"] not in ("nuovo", "differenze"):
                continue
            try:
                with transaction.atomic():
                    note = _applica_voce(righe_remote[voce["indice"]], voce, sezione, opzioni,
                                         utente, da_sezione=da_sezione)  # fmt: skip
                esito = "creato" if voce["stato"] == "nuovo" else "aggiornato"
            except imp._Errore as e:
                esito, note = "errore", [str(e)]
            except ValidationError as e:
                esito, note = "errore", e.messages
            esiti.append({"indice": voce["indice"], "nome": voce["nome"], "esito": esito,
                          "note": note})  # fmt: skip
        registra(
            Azione.MODIFICA, utente=utente, descrizione=f"Verifica soci con {controparte}",
            sezione=sezione.nome,
            creati=sum(1 for e in esiti if e["esito"] == "creato"),
            aggiornati=sum(1 for e in esiti if e["esito"] == "aggiornato"),
            errori=sum(1 for e in esiti if e["esito"] == "errore"),
            momento=timezone.now().isoformat(timespec="seconds"),
        )  # fmt: skip
    return esiti
