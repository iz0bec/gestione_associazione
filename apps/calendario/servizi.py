# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Impegni raccolti dai moduli (riunioni, ricorrenze, restituzioni dei prestiti,
# *              compleanni dei soci) secondo i permessi dell'utente, ed esportazione iCal
# *              (RFC 5545) per i calendari di telefoni e computer.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import hashlib
import secrets
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, time, timedelta

from django.urls import reverse
from django.utils import timezone

from apps.core.audit import Azione, registra

from .models import Appuntamento, FeedCalendario

DOMINIO_UID = "gestione-associazione"
DURATA_RIUNIONE = timedelta(hours=2)


@dataclass
class Evento:
    uid: str
    titolo: str
    inizio: date | datetime  # date = tutto il giorno
    fine: date | datetime | None = None
    luogo: str = ""
    descrizione: str = ""
    percorso: str = ""  # indirizzo nell'applicazione (relativo)
    annuale: bool = False
    categoria: str = ""
    icona: str = "calendar"
    appuntamento: Appuntamento | None = None  # se inserito a mano
    stato: str = ""  # per le scadenze: «fatto» o «scaduto» (calcolato per ogni occorrenza)

    @property
    def tutto_il_giorno(self):
        return not isinstance(self.inizio, datetime)

    def nel(self, anno):
        """Data dell'evento annuale nell'anno indicato (il 29 febbraio diventa 28 se serve)."""
        giorno = self.inizio if self.tutto_il_giorno else self.inizio.date()
        try:
            return giorno.replace(year=anno)
        except ValueError:
            return date(anno, 2, 28)


# --- raccolta degli impegni -----------------------------------------------------------------


def _riunioni(dal, al):
    from django.db.models import Q

    from apps.organi.models import Riunione

    stati = (Riunione.Stato.CONVOCATA, Riunione.Stato.VERBALIZZATA)
    riunioni = (
        Riunione.objects.filter(stato__in=stati)
        .filter(
            Q(prima_convocazione__date__range=(dal, al))
            | Q(seconda_convocazione__date__range=(dal, al))
        )
        .select_related("organo")
        .prefetch_related("punti")
    )
    for r in riunioni:
        righe = [f"{p.ordine}. {p.titolo}" for p in r.punti.all()]
        descrizione = ("Ordine del giorno:\n" + "\n".join(righe)) if righe else ""
        if r.modalita != r.Modalita.PRESENZA:
            descrizione += f"\n\n{r.get_modalita_display()}"
            if r.collegamento:
                descrizione += f": {r.collegamento}"
        percorso = reverse("organi:riunione", args=[r.pk])
        convocazioni = [(1, r.prima_convocazione, r.luogo)]
        if r.seconda_convocazione:
            convocazioni.append((2, r.seconda_convocazione, r.luogo_seconda or r.luogo))
        for n, quando, luogo in convocazioni:
            if not dal <= timezone.localtime(quando).date() <= al:
                continue
            titolo = r.titolo
            if r.seconda_convocazione:
                titolo += f" ({n}ª convocazione)"
            yield Evento(
                uid=f"riunione-{r.pk}-{n}", titolo=titolo, inizio=quando,
                fine=quando + DURATA_RIUNIONE, luogo=luogo, descrizione=descrizione.strip(),
                percorso=percorso, categoria="Riunioni", icona="gavel",
            )  # fmt: skip


def _ricorrenze():
    from apps.comunicazioni.models import Ricorrenza

    for r in Ricorrenza.objects.filter(attiva=True):
        anno = r.anno_inizio or 2000
        try:
            inizio = date(anno, r.mese, r.giorno)
        except ValueError:
            inizio = date(anno, r.mese, 28)
        titolo = r.nome
        yield Evento(
            uid=f"ricorrenza-{r.pk}", titolo=titolo, inizio=inizio, descrizione=r.descrizione,
            annuale=True, categoria="Ricorrenze", icona="flag",
        )  # fmt: skip


def _compleanni(utente):
    from apps.soci import sezioni
    from apps.soci.models import Socio

    soci = sezioni.filtra(Socio.objects.attivi(), utente).filter(
        soggetto__data_nascita__isnull=False, soggetto__data_decesso__isnull=True
    )
    for socio in soci.select_related("soggetto"):
        s = socio.soggetto
        yield Evento(
            uid=f"compleanno-{s.pk}", titolo=f"Compleanno di {s.intestazione}",
            inizio=s.data_nascita, annuale=True, percorso=reverse("soci:dettaglio",
                                                                  args=[socio.pk]),
            categoria="Compleanni", icona="cake",
        )  # fmt: skip


def _prestiti(dal, al):
    from apps.patrimonio.models import Uscita

    prestiti = Uscita.objects.filter(
        tipo=Uscita.Tipo.PRESTITO,
        restituito_il__isnull=True,
        restituzione_prevista__range=(dal, al),
    ).select_related("bene", "controparte")
    for u in prestiti:
        chi = u.controparte.nome_completo if u.controparte else u.controparte_testo
        yield Evento(
            uid=f"prestito-{u.pk}", titolo=f"Restituzione prevista: {u.bene.codice} {u.bene.nome}",
            inizio=u.restituzione_prevista, descrizione=f"Prestito a {chi}: {u.motivo}",
            percorso=reverse("patrimonio:bene", args=[u.bene_id]), categoria="Patrimonio",
            icona="building-warehouse",
        )  # fmt: skip


def _momento(giorno, ora):
    return timezone.make_aware(datetime.combine(giorno, ora))


def _appuntamenti(dal, al):
    from django.db.models import Q

    qs = Appuntamento.objects.filter(annullato=False).filter(
        Q(annuale=True) | Q(giorno__range=(dal, al)) | Q(giorno__lte=al, fine_giorno__gte=dal)
    )
    for a in qs:
        titolo = f"Scadenza: {a.titolo}" if a.scadenza else a.titolo
        if a.ora:
            inizio = _momento(a.giorno, a.ora)
            if a.fine_giorno or a.ora_fine:
                fine = _momento(a.fine_giorno or a.giorno, a.ora_fine or a.ora)
            else:
                fine = inizio + timedelta(hours=1)
            fine = max(fine, inizio)
        else:
            inizio = a.giorno
            fine = (a.fine_giorno + timedelta(days=1)) if a.fine_giorno else None
        yield Evento(
            uid=f"appuntamento-{a.pk}", titolo=titolo, inizio=inizio, fine=fine, luogo=a.luogo,
            descrizione=a.descrizione, percorso=a.get_absolute_url(), annuale=a.annuale,
            categoria=a.get_tipo_display(), icona=a.icona, appuntamento=a,
        )  # fmt: skip


def eventi(utente, *, dal, al, compleanni=False):
    """Impegni visibili all'utente: quelli singoli nel periodo, quelli annuali tutti."""
    elenco = []
    if utente.has_perm("organi.view_riunione"):
        elenco += _riunioni(dal, al)
    if utente.has_perm("comunicazioni.view_ricorrenza"):
        elenco += _ricorrenze()
    if compleanni and utente.has_perm("soci.view_socio"):
        elenco += _compleanni(utente)
    if utente.has_perm("patrimonio.view_bene"):
        elenco += _prestiti(dal, al)
    if utente.has_perm("calendario.view_appuntamento"):
        elenco += _appuntamenti(dal, al)
    return elenco


def _giorno(e):
    return e.inizio if e.tutto_il_giorno else timezone.localtime(e.inizio).date()


def _con_stato(e, giorno):
    a = e.appuntamento
    if a is None or not a.scadenza:
        return e
    if a.fatto_per(giorno):
        stato = "fatto"
    elif giorno < timezone.localdate():
        stato = "scaduto"
    else:
        stato = ""
    return replace(e, stato=stato)


def occorrenze(utente, dal, al, *, compleanni=False):
    """(giorno, evento) fra `dal` e `al` compresi, in ordine: gli annuali in ogni anno del
    periodo, gli impegni di più giorni (tutto il giorno) in ciascun giorno."""
    righe = []
    for e in eventi(utente, dal=dal, al=al, compleanni=compleanni):
        if e.annuale:
            giorni = [e.nel(anno) for anno in range(dal.year, al.year + 1)]
        elif e.tutto_il_giorno and e.fine and (e.fine - e.inizio).days > 1:
            giorni = [e.inizio + timedelta(days=i) for i in range((e.fine - e.inizio).days)]
        else:
            giorni = [_giorno(e)]
        righe += [(g, _con_stato(e, g)) for g in giorni if dal <= g <= al]
    return sorted(righe, key=_ordine)


def _ordine(riga):
    """Per giorno; prima gli impegni di tutto il giorno, poi gli altri per ora."""
    g, e = riga
    ora = time.min if e.tutto_il_giorno else timezone.localtime(e.inizio).time()
    return (g, not e.tutto_il_giorno, ora, e.titolo)


def prossimi(utente, giorni=60, *, compleanni=False):
    """(giorno, evento) da oggi ai prossimi giorni, in ordine."""
    oggi = timezone.localdate()
    return occorrenze(utente, oggi, oggi + timedelta(days=giorni), compleanni=compleanni)


def mese(utente, anno, numero, *, compleanni=False):
    """Settimane (lunedì-domenica) del mese: liste di 7 giorni {giorno, eventi, nel_mese}."""
    import calendar

    settimane = calendar.Calendar(firstweekday=0).monthdatescalendar(anno, numero)
    dal, al = settimane[0][0], settimane[-1][-1]
    per_giorno = {}
    for g, e in occorrenze(utente, dal, al, compleanni=compleanni):
        per_giorno.setdefault(g, []).append(e)
    return [
        [{"giorno": g, "eventi": per_giorno.get(g, []), "nel_mese": g.month == numero}
         for g in settimana]
        for settimana in settimane
    ]  # fmt: skip


def scadenze_aperte(utente, giorni=30):
    """Scadenze non fatte: quelle superate e quelle dei prossimi giorni, per data."""
    if not utente.has_perm("calendario.view_appuntamento"):
        return []
    limite = timezone.localdate() + timedelta(days=giorni)
    aperte = [
        a for a in Appuntamento.objects.filter(tipo=Appuntamento.Tipo.SCADENZA, annullato=False)
        if not a.fatto and a.prossima <= limite
    ]  # fmt: skip
    return sorted(aperte, key=lambda a: a.prossima)


# --- appuntamenti inseriti a mano ------------------------------------------------------------


def salva_appuntamento(form, utente):
    nuovo = form.instance.pk is None
    from apps.core.audit import campi_modificati

    dettagli = {} if nuovo else campi_modificati(form)
    a = form.save(commit=False)
    if nuovo:
        a.creato_da = utente
    a.modificato_da = utente
    a.save()
    if nuovo:
        registra(Azione.CREAZIONE, a, utente=utente)
    elif dettagli.get("campi"):
        registra(Azione.MODIFICA, a, utente=utente, **dettagli)
    return a


def segna_fatto(a, utente, *, fatto=True):
    a.completato_il = timezone.localdate() if fatto else None
    a.modificato_da = utente
    a.save(update_fields=["completato_il", "modificato_da", "modificato_il"])
    registra(Azione.MODIFICA, a, utente=utente, fatto=fatto)
    return a


def annulla_appuntamento(a, utente):
    a.annullato = True
    a.modificato_da = utente
    a.save(update_fields=["annullato", "modificato_da", "modificato_il"])
    registra(Azione.ANNULLAMENTO, a, utente=utente)
    return a


# --- iCal -----------------------------------------------------------------------------------


def _esc(valore):
    return (
        str(valore or "")
        .replace("\\", "\\\\")
        .replace("\r\n", "\n")
        .replace("\n", "\\n")
        .replace(",", "\\,")
        .replace(";", "\\;")
    )


def _piega(riga):
    parti, corrente, lung = [], "", 0
    for car in riga:
        n = len(car.encode("utf-8"))
        if lung + n > (75 if not parti else 74):
            parti.append(corrente)
            corrente, lung = "", 0
        corrente += car
        lung += n
    parti.append(corrente)
    return "\r\n ".join(parti)


def _utc(momento):
    return momento.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def ics(elenco, *, nome, base_url=""):
    """Testo del calendario (text/calendar). Orari in UTC: ogni app li mostra nell'ora locale."""
    adesso = _utc(timezone.now())
    righe = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Gestione Associazione//IT",
        "CALSCALE:GREGORIAN", "METHOD:PUBLISH", f"X-WR-CALNAME:{_esc(nome)}",
        "X-WR-TIMEZONE:Europe/Rome", "REFRESH-INTERVAL;VALUE=DURATION:PT6H",
        "X-PUBLISHED-TTL:PT6H",
    ]  # fmt: skip
    for e in elenco:
        righe += ["BEGIN:VEVENT", f"UID:{e.uid}@{DOMINIO_UID}", f"DTSTAMP:{adesso}"]
        if e.tutto_il_giorno:
            fine = e.fine or e.inizio + timedelta(days=1)
            righe += [f"DTSTART;VALUE=DATE:{e.inizio:%Y%m%d}", f"DTEND;VALUE=DATE:{fine:%Y%m%d}",
                      "TRANSP:TRANSPARENT"]  # fmt: skip
        else:
            righe += [f"DTSTART:{_utc(e.inizio)}", f"DTEND:{_utc(e.fine or e.inizio)}"]
        if e.annuale:
            righe.append("RRULE:FREQ=YEARLY")
        righe.append(f"SUMMARY:{_esc(e.titolo)}")
        if e.luogo:
            righe.append(f"LOCATION:{_esc(e.luogo)}")
        if e.descrizione:
            righe.append(f"DESCRIPTION:{_esc(e.descrizione)}")
        if e.percorso and base_url:
            righe.append(f"URL:{base_url.rstrip('/')}{e.percorso}")
        if e.categoria:
            righe.append(f"CATEGORIES:{_esc(e.categoria)}")
        righe.append("END:VEVENT")
    righe.append("END:VCALENDAR")
    return "".join(_piega(r) + "\r\n" for r in righe)


def periodo():
    """Periodo esportato: tre mesi indietro e un anno avanti."""
    oggi = timezone.localdate()
    return oggi - timedelta(days=90), oggi + timedelta(days=400)


def calendario_di(utente, *, compleanni=False, base_url=""):
    from apps.core.models import Organizzazione

    dal, al = periodo()
    org = Organizzazione.corrente()
    nome = org.nome_breve or org.denominazione or "Associazione"
    return ics(eventi(utente, dal=dal, al=al, compleanni=compleanni), nome=nome,
               base_url=base_url)  # fmt: skip


# --- collegamento personale -----------------------------------------------------------------


def impronta(codice):
    return hashlib.sha256(codice.encode()).hexdigest()


def crea_collegamento(utente, *, compleanni=False):
    """Nuovo codice segreto (il precedente smette di funzionare). Restituisce il codice."""
    codice = secrets.token_urlsafe(32)
    FeedCalendario.objects.update_or_create(
        utente=utente,
        defaults={"impronta": impronta(codice), "compleanni": compleanni, "ultimo_accesso": None},
    )
    registra(Azione.CREAZIONE, utente=utente, descrizione="Collegamento al calendario (iCal)",
             compleanni=compleanni)  # fmt: skip
    return codice


def revoca_collegamento(utente):
    if FeedCalendario.objects.filter(utente=utente).delete()[0]:
        registra(Azione.ELIMINAZIONE, utente=utente,
                 descrizione="Collegamento al calendario revocato")  # fmt: skip


def feed_da_codice(codice):
    """Collegamento attivo corrispondente al codice, o None."""
    feed = (
        FeedCalendario.objects.select_related("utente")
        .filter(impronta=impronta(codice or ""), utente__is_active=True)
        .first()
    )
    if feed:
        FeedCalendario.objects.filter(pk=feed.pk).update(ultimo_accesso=timezone.now())
    return feed
