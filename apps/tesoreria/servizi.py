# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Operazioni della tesoreria: esercizi e saldi, prima nota numerata con
# *              giustificativi, quote sociali in prima nota, chiusura con riporto dei saldi,
# *              preventivo e rendiconto per cassa (Modello D, D.M. 5 marzo 2020).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import csv
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from apps.anagrafica.servizi import cella_sicura
from apps.core.audit import Azione, campi_modificati, registra
from apps.core.numerazione import prossimo_numero

from .models import SEQ_PRIMA_NOTA, Conto, Esercizio, Movimento, Previsione, SaldoConto, Voce

ZERO = Decimal("0.00")
VOCE_QUOTE = "E.A.1"  # Entrate da quote associative e apporti dei fondatori


class OperazioneNonValida(ValidationError):
    """Operazione rifiutata per una regola della tesoreria (messaggio per l'utente)."""


# --- esercizi e saldi ----------------------------------------------------------------------------


def esercizio_di(giorno):
    return Esercizio.objects.filter(anno=giorno.year).first()


def _controlla_aperto(esercizio):
    if not esercizio.aperto:
        raise OperazioneNonValida(f"L'esercizio {esercizio.anno} è chiuso.")


@transaction.atomic
def apri_esercizio(anno, utente):
    """Crea l'esercizio con i saldi iniziali: quelli finali dell'anno prima, se chiuso, o zero."""
    if Esercizio.objects.filter(anno=anno).exists():
        raise OperazioneNonValida(f"L'esercizio {anno} esiste già.")
    esercizio = Esercizio.objects.create(anno=anno)
    precedente = Esercizio.objects.filter(anno=anno - 1, stato=Esercizio.Stato.CHIUSO).first()
    finali = {s.conto_id: s.finale for s in precedente.saldi.all()} if precedente else {}
    for conto in Conto.objects.filter(attivo=True):
        SaldoConto.objects.create(
            esercizio=esercizio, conto=conto, iniziale=finali.get(conto.pk) or ZERO
        )
    registra(Azione.CREAZIONE, esercizio, utente=utente, riporto=bool(precedente))
    # all'apertura dell'anno contabile si fissano anche i costi del tesseramento
    from apps.soci.servizi import prepara_listino

    prepara_listino(anno, utente)
    return esercizio


def saldi_iniziali_modificabili(esercizio):
    """I saldi iniziali si scrivono a mano solo nel primo esercizio (gli altri sono riportati)."""
    return esercizio.aperto and not Esercizio.objects.filter(anno=esercizio.anno - 1).exists()


@transaction.atomic
def imposta_saldi_iniziali(esercizio, valori, utente):
    if not saldi_iniziali_modificabili(esercizio):
        raise OperazioneNonValida("I saldi iniziali sono riportati dall'esercizio precedente.")
    for conto, importo in valori.items():
        saldo, _ = SaldoConto.objects.get_or_create(esercizio=esercizio, conto=conto)
        saldo.iniziale = importo
        saldo.save()
    registra(
        Azione.MODIFICA,
        esercizio,
        utente=utente,
        saldi_iniziali={c.nome: str(v) for c, v in valori.items()},
    )


def saldo(conto, esercizio, fino_al=None):
    iniziale = (
        SaldoConto.objects.filter(esercizio=esercizio, conto=conto)
        .values_list("iniziale", flat=True)
        .first()
        or ZERO
    )
    movimenti = esercizio.movimenti.validi()
    if fino_al:
        movimenti = movimenti.filter(data__lte=fino_al)

    def somma(qs):
        return qs.aggregate(t=Sum("importo"))["t"] or ZERO

    entrate = somma(movimenti.filter(conto=conto, tipo=Movimento.Tipo.ENTRATA))
    uscite = somma(movimenti.filter(conto=conto, tipo=Movimento.Tipo.USCITA))
    girati_via = somma(movimenti.filter(conto=conto, tipo=Movimento.Tipo.GIROCONTO))
    girati_qui = somma(movimenti.filter(conto_destinazione=conto, tipo=Movimento.Tipo.GIROCONTO))
    return iniziale + entrate - uscite - girati_via + girati_qui


def saldi(esercizio):
    conti = Conto.objects.filter(Q(attivo=True) | Q(saldi__esercizio=esercizio)).distinct()
    return [(c, saldo(c, esercizio)) for c in conti]


@transaction.atomic
def chiudi_esercizio(esercizio, utente, approvazione=""):
    """Fissa i saldi finali e li riporta come iniziali dell'esercizio successivo."""
    esercizio = Esercizio.objects.select_for_update().get(pk=esercizio.pk)
    _controlla_aperto(esercizio)
    if esercizio.anno >= timezone.localdate().year:
        raise OperazioneNonValida("Si chiude un esercizio solo dopo la fine dell'anno.")
    finali = {}
    for conto, valore in saldi(esercizio):
        s, _ = SaldoConto.objects.get_or_create(esercizio=esercizio, conto=conto)
        s.finale = valore
        s.save()
        finali[conto] = valore
    esercizio.stato = Esercizio.Stato.CHIUSO
    esercizio.chiuso_il = timezone.now()
    esercizio.chiuso_da = utente
    esercizio.approvazione = approvazione or esercizio.approvazione
    esercizio.save()
    successivo = Esercizio.objects.filter(anno=esercizio.anno + 1).first()
    if successivo is None:
        successivo = apri_esercizio(esercizio.anno + 1, utente)
    elif successivo.aperto:
        for conto, valore in finali.items():
            SaldoConto.objects.update_or_create(
                esercizio=successivo, conto=conto, defaults={"iniziale": valore}
            )
    registra(
        Azione.MODIFICA,
        esercizio,
        utente=utente,
        chiuso=True,
        saldi_finali={c.nome: str(v) for c, v in finali.items()},
    )
    return esercizio


@transaction.atomic
def riapri_esercizio(esercizio, utente, motivo):
    if not (motivo or "").strip():
        raise OperazioneNonValida("Indicare il motivo della riapertura.")
    esercizio = Esercizio.objects.select_for_update().get(pk=esercizio.pk)
    if esercizio.aperto:
        raise OperazioneNonValida("L'esercizio è già aperto.")
    if Esercizio.objects.filter(anno=esercizio.anno + 1, stato=Esercizio.Stato.CHIUSO).exists():
        raise OperazioneNonValida("L'esercizio successivo è chiuso: riaprire prima quello.")
    esercizio.stato = Esercizio.Stato.APERTO
    esercizio.chiuso_il = None
    esercizio.save()
    esercizio.saldi.update(finale=None)
    registra(Azione.MODIFICA, esercizio, utente=utente, riaperto=True, motivo=motivo.strip())
    return esercizio


# --- prima nota ----------------------------------------------------------------------------------


def _controlla_coerenza(dati):
    tipo, voce = dati["tipo"], dati.get("voce")
    if tipo == Movimento.Tipo.GIROCONTO:
        if not dati.get("conto_destinazione") or dati["conto_destinazione"] == dati["conto"]:
            raise OperazioneNonValida(
                "Per un giroconto scegliere un conto di destinazione diverso."
            )
        dati["voce"] = None
    else:
        dati["conto_destinazione"] = None
        if voce is None:
            raise OperazioneNonValida("Scegliere la voce del rendiconto.")
        if voce.tipo != tipo:
            raise OperazioneNonValida(f"La voce «{voce}» non è una voce di {tipo}.")


def _salva_giustificativo(movimento, file):
    from apps.protocollo.servizi import controlla_file, impronta_file, nome_file_sicuro

    nome = nome_file_sicuro(file.name)
    controlla_file(nome, file.size)
    movimento.impronta = impronta_file(file)
    movimento.giustificativo_nome = nome
    movimento.giustificativo.save(nome, file, save=False)


@transaction.atomic
def registra_movimento(dati, utente, *, giustificativo=None, tessera=None):
    dati = dict(dati)
    esercizio = esercizio_di(dati["data"])
    if esercizio is None:
        raise OperazioneNonValida(f"Manca l'esercizio {dati['data'].year}: aprirlo in Tesoreria.")
    esercizio = Esercizio.objects.select_for_update().get(pk=esercizio.pk)
    _controlla_aperto(esercizio)
    _controlla_coerenza(dati)
    for conto in filter(None, (dati["conto"], dati.get("conto_destinazione"))):
        SaldoConto.objects.get_or_create(esercizio=esercizio, conto=conto)
    m = Movimento(
        **dati,
        esercizio=esercizio,
        numero=prossimo_numero(SEQ_PRIMA_NOTA, esercizio.anno),
        tessera=tessera,
        creato_da=utente,
        modificato_da=utente,
    )
    if giustificativo:
        _salva_giustificativo(m, giustificativo)
    m.save()
    registra(Azione.CREAZIONE, m, utente=utente, importo=str(m.importo), tipo=m.tipo)
    return m


@transaction.atomic
def modifica_movimento(form, utente, *, giustificativo=None):
    m = form.instance
    _controlla_aperto(m.esercizio)
    if m.annullato:
        raise OperazioneNonValida("Il movimento è annullato.")
    if form.cleaned_data["data"].year != m.esercizio.anno:
        raise OperazioneNonValida(f"La data deve essere nel {m.esercizio.anno}.")
    dettagli = campi_modificati(form)
    m = form.save(commit=False)
    dati = {
        "tipo": m.tipo,
        "voce": m.voce,
        "conto": m.conto,
        "conto_destinazione": m.conto_destinazione,
    }
    _controlla_coerenza(dati)
    m.voce, m.conto_destinazione = dati["voce"], dati["conto_destinazione"]
    if giustificativo:
        _salva_giustificativo(m, giustificativo)
    m.modificato_da = utente
    m.save()
    if dettagli.get("campi") or giustificativo:
        registra(Azione.MODIFICA, m, utente=utente, **dettagli)
    return m


@transaction.atomic
def annulla_movimento(movimento, utente, motivo):
    if not (motivo or "").strip():
        raise OperazioneNonValida("Indicare il motivo dell'annullamento.")
    m = Movimento.objects.select_for_update().select_related("esercizio").get(pk=movimento.pk)
    _controlla_aperto(m.esercizio)
    if m.annullato:
        raise OperazioneNonValida("Il movimento è già annullato.")
    m.annullato = True
    m.motivo_annullamento = motivo.strip()[:255]
    m.modificato_da = utente
    m.save()
    registra(Azione.ANNULLAMENTO, m, utente=utente, motivo=m.motivo_annullamento)
    return m


# --- quote sociali -------------------------------------------------------------------------------


def conto_per_metodo(metodo):
    if metodo == "contanti":
        return Conto.objects.filter(per_contanti=True, attivo=True).first()
    return Conto.objects.filter(per_pagamenti_elettronici=True, attivo=True).first()


def registra_quota(tessera, utente):
    """Mette in prima nota l'incasso della quota. Restituisce (movimento, motivo se non fatto)."""
    if not tessera.pagata or tessera.importo <= 0 or tessera.annullata:
        return None, "quota non incassata"
    if tessera.incasso_esterno:
        return None, "incassata fuori dall'applicazione"
    if Movimento.objects.filter(tessera=tessera).exists():
        return None, "già in prima nota"
    esercizio = esercizio_di(tessera.pagata_il)
    if esercizio is None or not esercizio.aperto:
        return None, f"esercizio {tessera.pagata_il.year} mancante o chiuso"
    conto = conto_per_metodo(tessera.metodo_pagamento)
    if conto is None:
        return None, "nessun conto impostato per questo metodo di pagamento"
    voce = Voce.objects.filter(codice=VOCE_QUOTE).first()
    socio = tessera.socio
    m = registra_movimento(
        {
            "data": tessera.pagata_il,
            "tipo": Movimento.Tipo.ENTRATA,
            "conto": conto,
            "importo": tessera.importo,
            "voce": voce,
            "descrizione": f"Quota associativa {tessera.anno} - socio n. {socio.numero}",
            "controparte": socio.soggetto,
            "controparte_testo": socio.soggetto.nome_completo,
            "documento": f"ricevuta n. {tessera.codice_ricevuta}",
        },
        utente,
        tessera=tessera,
    )
    return m, ""


def quote_da_registrare(esercizio):
    from apps.soci.models import Tessera

    return (
        Tessera.objects.pagate()
        .filter(pagata_il__year=esercizio.anno, importo__gt=0, movimento__isnull=True)
        .exclude(incasso_esterno=True)
        .select_related("socio__soggetto")
    )


def registra_quote_mancanti(esercizio, utente):
    fatte, saltate = 0, []
    for t in quote_da_registrare(esercizio):
        m, motivo = registra_quota(t, utente)
        if m:
            fatte += 1
        else:
            saltate.append((t, motivo))
    return fatte, saltate


# --- preventivo e rendiconto -------------------------------------------------------------------


def voci_ufficiali():
    return Voce.objects.filter(padre__isnull=True)


def totali_per_voce(esercizio):
    """{voce ufficiale id: totale} dei movimenti validi (le sottovoci confluiscono nella voce)."""
    totali = defaultdict(lambda: ZERO)
    if esercizio is None:
        return totali
    righe = (
        esercizio.movimenti.validi()
        .exclude(tipo=Movimento.Tipo.GIROCONTO)
        .values("voce_id", "voce__padre_id")
        .annotate(t=Sum("importo"))
    )
    for r in righe:
        totali[r["voce__padre_id"] or r["voce_id"]] += r["t"]
    return totali


@transaction.atomic
def salva_preventivo(esercizio, valori, utente):
    _controlla_aperto(esercizio)
    for voce, importo in valori.items():
        Previsione.objects.update_or_create(
            esercizio=esercizio, voce=voce, defaults={"importo": importo or ZERO}
        )
    registra(Azione.MODIFICA, esercizio, utente=utente, preventivo=True)


@dataclass
class Sezione:
    codice: str
    titolo: str
    uscite: list = field(default_factory=list)  # (voce, corrente, precedente)
    entrate: list = field(default_factory=list)

    def _somma(self, righe, i):
        return sum((r[i] for r in righe), ZERO)

    @property
    def tot_uscite(self):
        return self._somma(self.uscite, 1)

    @property
    def tot_entrate(self):
        return self._somma(self.entrate, 1)

    @property
    def tot_uscite_prec(self):
        return self._somma(self.uscite, 2)

    @property
    def tot_entrate_prec(self):
        return self._somma(self.entrate, 2)

    @property
    def avanzo(self):
        return self.tot_entrate - self.tot_uscite

    @property
    def avanzo_prec(self):
        return self.tot_entrate_prec - self.tot_uscite_prec


def rendiconto(esercizio):
    """Dati del rendiconto per cassa (Modello D) con il confronto sull'esercizio precedente."""
    precedente = Esercizio.objects.filter(anno=esercizio.anno - 1).first()
    correnti, prec = totali_per_voce(esercizio), totali_per_voce(precedente)
    sezioni = {s: Sezione(s, etichetta) for s, etichetta in Voce.Sezione.choices}
    for v in voci_ufficiali().order_by("sezione", "numero"):
        riga = (v, correnti[v.pk], prec[v.pk])
        (
            sezioni[v.sezione].entrate if v.tipo == Voce.Tipo.ENTRATA else sezioni[v.sezione].uscite
        ).append(riga)
    gestione = [sezioni[s] for s in "ABCDE"]
    tot_uscite = sum((s.tot_uscite for s in gestione), ZERO)
    tot_entrate = sum((s.tot_entrate for s in gestione), ZERO)
    tot_uscite_prec = sum((s.tot_uscite_prec for s in gestione), ZERO)
    tot_entrate_prec = sum((s.tot_entrate_prec for s in gestione), ZERO)
    imposte, inv = sezioni["IMP"], sezioni["INV"]
    avanzo = tot_entrate - tot_uscite
    avanzo_prec = tot_entrate_prec - tot_uscite_prec
    fine = date(esercizio.anno, 12, 31)
    cassa = banca = ZERO
    for conto in Conto.objects.filter(saldi__esercizio=esercizio).distinct():
        valore = saldo(conto, esercizio, fine)
        if conto.e_cassa:
            cassa += valore
        else:
            banca += valore
    return {
        "esercizio": esercizio,
        "precedente": precedente,
        "gestione": gestione,
        "tot_uscite": tot_uscite,
        "tot_entrate": tot_entrate,
        "tot_uscite_prec": tot_uscite_prec,
        "tot_entrate_prec": tot_entrate_prec,
        "avanzo": avanzo,
        "avanzo_prec": avanzo_prec,
        "imposte": imposte,
        "avanzo_dopo_imposte": avanzo - imposte.tot_uscite,
        "avanzo_dopo_imposte_prec": avanzo_prec - imposte.tot_uscite_prec,
        "investimenti": inv,
        "avanzo_complessivo": avanzo - imposte.tot_uscite + inv.avanzo,
        "avanzo_complessivo_prec": avanzo_prec - imposte.tot_uscite_prec + inv.avanzo_prec,
        "cassa": cassa,
        "banca": banca,
    }


def confronto_preventivo(esercizio):
    previsti = {p.voce_id: p.importo for p in esercizio.previsioni.all()}
    effettivi = totali_per_voce(esercizio)
    righe = []
    for v in voci_ufficiali().order_by("tipo", "sezione", "numero"):
        p, e = previsti.get(v.pk, ZERO), effettivi[v.pk]
        if p or e:
            righe.append({"voce": v, "previsto": p, "effettivo": e, "differenza": e - p})
    return righe


def riepilogo(esercizio):
    mov = esercizio.movimenti.validi()
    entrate = mov.filter(tipo=Movimento.Tipo.ENTRATA).aggregate(t=Sum("importo"))["t"] or ZERO
    uscite = mov.filter(tipo=Movimento.Tipo.USCITA).aggregate(t=Sum("importo"))["t"] or ZERO
    return {"entrate": entrate, "uscite": uscite, "avanzo": entrate - uscite}


# --- esportazioni --------------------------------------------------------------------------------


def esporta_prima_nota(queryset, destinazione, utente):
    w = csv.writer(destinazione, delimiter=";")
    w.writerow(["numero", "data", "tipo", "conto", "verso", "voce", "descrizione", "controparte",
                "documento", "entrata", "uscita", "annullato"])  # fmt: skip
    n = 0
    for m in queryset.select_related("esercizio", "conto", "conto_destinazione", "voce__padre"):
        importo = str(m.importo).replace(".", ",")
        riga = [
            m.codice, m.data.strftime("%d/%m/%Y"), m.get_tipo_display(), m.conto,
            m.conto_destinazione or "", m.voce or "", m.descrizione, m.controparte_testo,
            m.documento, importo if m.tipo == "entrata" else "",
            importo if m.tipo == "uscita" else "",
            "sì" if m.annullato else "",
        ]  # fmt: skip
        w.writerow([cella_sicura(v) for v in riga])
        n += 1
    registra(Azione.ESPORTAZIONE, utente=utente, descrizione=f"Prima nota CSV ({n} righe)", righe=n)
    return n
