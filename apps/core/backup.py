# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Backup e ripristino completi: un file .tar con il database (pg_dump), i file
# *              caricati e un manifesto con versione, migrazioni e impronte SHA-256.
# *              Il ripristino verifica il file, salva prima lo stato attuale, poi sostituisce
# *              database e file e applica le migrazioni mancanti. Conservazione a rotazione
# *              (giornalieri, settimanali, mensili), tetto di spazio e controllo del disco.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess  # noqa: S404 - pg_dump/pg_restore con argomenti fissi, senza shell
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import connection
from django.utils import timezone

log = logging.getLogger(__name__)
FORMATO = 1
MANIFESTO = "manifest.json"
DATABASE = "database.dump"
FILE = "file.tar.gz"
NOME_VALIDO = re.compile(r"^backup_[A-Za-z0-9_-]{1,80}\.tar$")


class BackupNonValido(ValidationError):
    pass


@dataclass
class Backup:
    nome: str
    percorso: Path
    dimensione: int
    manifesto: dict

    @property
    def creato_il(self):
        from datetime import datetime

        try:
            return datetime.fromisoformat(self.manifesto.get("creato_il", ""))
        except ValueError:
            return None

    @property
    def motivo(self):
        return self.manifesto.get("motivo", "")

    @property
    def automatico(self):
        return self.motivo == "automatico"


def cartella():
    c = Path(settings.BACKUP_ROOT)
    c.mkdir(parents=True, exist_ok=True)
    c.chmod(0o700)
    return c


def percorso(nome):
    """Percorso di un backup dal nome (solo nomi validi, solo nella cartella dei backup)."""
    if not NOME_VALIDO.match(nome or ""):
        raise BackupNonValido("Nome del backup non valido.")
    p = cartella() / nome
    if not p.is_file():
        raise BackupNonValido("Backup non trovato.")
    return p


# --- PostgreSQL --------------------------------------------------------------------------


def _programma(nome):
    trovato = shutil.which(nome)
    if not trovato:
        raise BackupNonValido(f"{nome} non trovato: installare il client di PostgreSQL.")
    return trovato


def _connessione():
    db = settings.DATABASES["default"]
    argomenti = [
        f"--host={db.get('HOST') or 'localhost'}",
        f"--port={db.get('PORT') or 5432}",
        f"--username={db.get('USER') or ''}",
        f"--dbname={db['NAME']}",
    ]
    return argomenti, {**os.environ, "PGPASSWORD": str(db.get("PASSWORD") or "")}


def _esegui(comando, ambiente, errore):
    esito = subprocess.run(comando, env=ambiente, capture_output=True, text=True)  # noqa: S603
    if esito.returncode != 0:
        raise BackupNonValido(f"{errore}: {esito.stderr.strip()[-2000:]}")


def svuota_database():
    tabelle = connection.introspection.table_names()
    with connection.cursor() as cursore:
        for tabella in tabelle:
            cursore.execute(f"DROP TABLE IF EXISTS {connection.ops.quote_name(tabella)} CASCADE")
    return len(tabelle)


def _migrazioni_applicate():
    from django.db.migrations.recorder import MigrationRecorder

    applicate = {}
    for app, nome in MigrationRecorder(connection).applied_migrations():
        applicate.setdefault(app, []).append(nome)
    return {app: sorted(nomi) for app, nomi in sorted(applicate.items())}


def _conteggi():
    from apps.anagrafica.models import Soggetto
    from apps.protocollo.models import Protocollo
    from apps.soci.models import Socio
    from apps.tesoreria.models import Movimento

    try:
        return {
            "soggetti": Soggetto.objects.count(),
            "soci": Socio.objects.count(),
            "protocolli": Protocollo.objects.count(),
            "movimenti": Movimento.objects.count(),
        }
    except Exception:  # noqa: BLE001 - database vuoto o parziale: i conteggi sono indicativi
        return {}


def _impronta(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for blocco in iter(lambda: f.read(1024 * 1024), b""):
            h.update(blocco)
    return h.hexdigest()


# --- creazione ---------------------------------------------------------------------------


def crea(motivo="manuale", utente=None):
    """Crea il backup completo e restituisce il percorso del file."""
    from apps.core.models import Organizzazione

    pg_dump = _programma("pg_dump")
    controlla_spazio()
    destinazione = cartella()
    marca = timezone.localtime().strftime("%Y%m%d_%H%M%S")
    tipo = re.sub(r"[^a-z0-9]+", "-", motivo.lower()).strip("-")[:30] or "manuale"
    nome = f"backup_{marca}_{tipo}.tar"
    with tempfile.TemporaryDirectory(dir=destinazione) as lavoro:
        lavoro = Path(lavoro)
        argomenti, ambiente = _connessione()
        _esegui([pg_dump, "--format=custom", "--no-owner", "--no-privileges",
                 f"--file={lavoro / DATABASE}", *argomenti], ambiente,
                "Backup del database non riuscito")  # fmt: skip
        media = Path(settings.MEDIA_ROOT)
        with tarfile.open(lavoro / FILE, "w:gz") as tar:
            if media.is_dir():
                for voce in sorted(media.iterdir()):
                    if voce.name.startswith("."):
                        continue
                    tar.add(voce, arcname=voce.name)
        try:
            ente = Organizzazione.corrente().denominazione
        except Exception:  # noqa: BLE001
            ente = ""
        manifesto = {
            "formato": FORMATO,
            "applicazione": settings.APP_NOME,
            "versione": settings.APP_VERSIONE,
            "creato_il": timezone.localtime().isoformat(timespec="seconds"),
            "motivo": motivo,
            "creato_da": str(utente) if utente else "",
            "ente": ente,
            "database": settings.DATABASES["default"]["NAME"],
            "migrazioni": _migrazioni_applicate(),
            "conteggi": _conteggi(),
            "impronte": {n: _impronta(lavoro / n) for n in (DATABASE, FILE)},
        }
        (lavoro / MANIFESTO).write_text(json.dumps(manifesto, indent=2, ensure_ascii=False))
        parziale = destinazione / f".{nome}.parziale"
        with tarfile.open(parziale, "w") as tar:
            for n in (MANIFESTO, DATABASE, FILE):
                tar.add(lavoro / n, arcname=n)
        parziale.chmod(0o600)
        parziale.replace(destinazione / nome)
    _registra("Backup creato", utente, file=nome, motivo=motivo)
    return destinazione / nome


def _registra(descrizione, utente=None, **dettagli):
    from apps.core.audit import Azione, registra

    try:
        registra(Azione.CREAZIONE, utente=utente, descrizione=descrizione, **dettagli)
    except Exception:  # il registro non deve impedire backup e ripristino
        log.warning("Evento non registrato: %s", descrizione, exc_info=True)


# --- lettura e verifica ------------------------------------------------------------------


def leggi_manifesto(p):
    try:
        with tarfile.open(p, "r:") as tar:
            membro = tar.getmember(MANIFESTO)
            if not membro.isfile() or membro.size > 1024 * 1024:
                raise BackupNonValido("Manifesto non valido.")
            return json.loads(tar.extractfile(membro).read())
    except (tarfile.TarError, KeyError, json.JSONDecodeError, OSError):
        raise BackupNonValido("Il file non è un backup di questa applicazione.") from None


def elenco():
    backup = []
    for p in sorted(cartella().glob("backup_*.tar"), reverse=True):
        try:
            manifesto = leggi_manifesto(p)
        except BackupNonValido:
            manifesto = {"motivo": "illeggibile"}
        backup.append(Backup(p.name, p, p.stat().st_size, manifesto))
    return backup


def verifica(p):
    """Controlla struttura, impronte e compatibilità con questa versione. Restituisce il
    manifesto, oppure solleva BackupNonValido senza aver modificato nulla."""
    from django.db.migrations.loader import MigrationLoader

    manifesto = leggi_manifesto(p)
    if manifesto.get("formato") != FORMATO or manifesto.get("applicazione") != settings.APP_NOME:
        raise BackupNonValido("Il file non è un backup di questa applicazione.")
    with tarfile.open(p, "r:") as tar:
        nomi = {m.name: m for m in tar.getmembers()}
        if set(nomi) != {MANIFESTO, DATABASE, FILE} or not all(m.isfile() for m in nomi.values()):
            raise BackupNonValido("Contenuto del backup inatteso.")
        for n in (DATABASE, FILE):
            h = hashlib.sha256()
            f = tar.extractfile(nomi[n])
            for blocco in iter(lambda f=f: f.read(1024 * 1024), b""):
                h.update(blocco)
            if h.hexdigest() != manifesto.get("impronte", {}).get(n):
                raise BackupNonValido(f"Backup danneggiato: impronta di {n} non corrispondente.")
    # un backup di una versione più recente non si ripristina su codice più vecchio
    note = MigrationLoader(None, ignore_no_migrations=True).disk_migrations
    sconosciute = [
        f"{app}.{nome}"
        for app, nomi in manifesto.get("migrazioni", {}).items()
        for nome in nomi
        if (app, nome) not in note
    ]
    if sconosciute:
        raise BackupNonValido(
            "Il backup viene da una versione più recente dell'applicazione: aggiornarla prima "
            f"di ripristinarlo ({', '.join(sconosciute[:3])}...)."
        )
    return manifesto


def salva_caricato(file_caricato):
    """Salva un backup caricato dall'interfaccia dopo averlo verificato."""
    marca = timezone.localtime().strftime("%Y%m%d_%H%M%S")
    destinazione = cartella() / f"backup_{marca}_caricato.tar"
    parziale = cartella() / f".{destinazione.name}.parziale"
    with open(parziale, "wb") as f:
        for pezzo in file_caricato.chunks():
            f.write(pezzo)
    parziale.chmod(0o600)
    try:
        verifica(parziale)
    except BackupNonValido:
        parziale.unlink(missing_ok=True)
        raise
    parziale.replace(destinazione)
    return destinazione


def elimina(nome, utente=None):
    p = percorso(nome)
    p.unlink()
    if nome in (dati := conservati()):
        del dati[nome]
        _scrivi_conservati(dati)
    _registra("Backup eliminato", utente, file=nome)


# --- conservazione -----------------------------------------------------------------------
#
# Automatici a rotazione: l'ultimo di ciascuno degli ultimi BACKUP_GIORNALIERI giorni,
# BACKUP_SETTIMANALI settimane e BACKUP_MENSILI mesi. Gli altri (manuali, caricati, «prima
# del ripristino», ...) sono gli ultimi BACKUP_ALTRI. Sopra BACKUP_SPAZIO_MASSIMO si tolgono i
# più vecchi. L'ultimo backup di ciascun gruppo non si elimina mai da solo.


def dimensione_byte(testo):
    """«20G», «500M», «1.5T» o un numero di byte; vuoto o 0 = nessun limite (0)."""
    t = str(testo or "").strip().upper().removesuffix("B")
    if not t:
        return 0
    multipli = {"K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}
    fattore = multipli.get(t[-1], 1)
    try:
        return int(float(t[:-1] if t[-1] in multipli else t) * fattore)
    except ValueError:
        raise ImproperlyConfigured(f"Dimensione non valida: «{testo}» (es. 20G, 500M).") from None


@dataclass
class Politica:
    giornalieri: int
    settimanali: int
    mensili: int
    altri: int
    spazio_massimo: int
    spazio_libero_minimo: int

    @classmethod
    def corrente(cls):
        return cls(
            giornalieri=settings.BACKUP_GIORNALIERI,
            settimanali=settings.BACKUP_SETTIMANALI,
            mensili=settings.BACKUP_MENSILI,
            altri=settings.BACKUP_ALTRI,
            spazio_massimo=dimensione_byte(settings.BACKUP_SPAZIO_MASSIMO),
            spazio_libero_minimo=dimensione_byte(settings.BACKUP_SPAZIO_LIBERO_MINIMO),
        )


CONSERVATI = ".conservati.json"


def conservati():
    """Backup esclusi dalla rotazione: {nome: {"da": utente, "il": data, "nota": testo}}."""
    p = cartella() / CONSERVATI
    try:
        dati = json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return dati if isinstance(dati, dict) else {}


def _scrivi_conservati(dati):
    p = cartella() / CONSERVATI
    parziale = p.with_name(p.name + ".parziale")
    parziale.write_text(json.dumps(dati, indent=2, ensure_ascii=False))
    parziale.chmod(0o600)
    parziale.replace(p)


def imposta_conservato(nome, conserva, utente=None, nota=""):
    """Esclude il backup dalla rotazione (o lo rimette): non sarà eliminato in automatico."""
    percorso(nome)  # solo backup esistenti, solo nomi validi
    dati = conservati()
    if conserva:
        dati[nome] = {"da": str(utente) if utente else "",
                      "il": timezone.localtime().isoformat(timespec="seconds"),
                      "nota": (nota or "").strip()[:200]}  # fmt: skip
    else:
        dati.pop(nome, None)
    _scrivi_conservati(dati)
    _registra("Backup escluso dalla rotazione" if conserva else "Backup rimesso in rotazione",
              utente, file=nome)  # fmt: skip


def _datato(b):
    return b.creato_il is not None and b.motivo != "illeggibile"


def classifica(backup=None, politica=None, fissati=None):
    """{nome: motivo di conservazione}; chi manca verrebbe eliminato. Gli illeggibili, i
    backup senza data e quelli esclusi dalla rotazione non sono mai toccati."""
    politica = politica or Politica.corrente()
    backup = elenco() if backup is None else backup
    fissi = set(conservati()) if fissati is None else set(fissati)
    tenuti = {b.nome: "da controllare" for b in backup if not _datato(b)}
    tenuti |= {b.nome: "escluso dalla rotazione" for b in backup if b.nome in fissi}
    automatici = sorted((b for b in backup if _datato(b) and b.automatico and b.nome not in fissi),
                        key=lambda b: b.creato_il, reverse=True)  # fmt: skip
    regole = [
        ("mensile", politica.mensili, lambda d: (d.year, d.month)),
        ("settimanale", politica.settimanali, lambda d: d.isocalendar()[:2]),
        ("giornaliero", politica.giornalieri, lambda d: d.date()),
    ]
    for motivo, quanti, periodo in regole:  # l'ultimo assegnato prevale: giornaliero
        visti = []
        for b in automatici:
            chiave = periodo(b.creato_il)
            if chiave in visti:
                continue
            visti.append(chiave)
            if len(visti) > quanti:
                break
            tenuti[b.nome] = motivo
    if automatici:
        tenuti.setdefault(automatici[0].nome, "il più recente")
    altri = sorted((b for b in backup if _datato(b) and not b.automatico and b.nome not in fissi),
                   key=lambda b: b.creato_il, reverse=True)  # fmt: skip
    for i, b in enumerate(altri):
        if politica.altri <= 0 or i < politica.altri:
            tenuti[b.nome] = "recente"
    if altri:
        tenuti.setdefault(altri[0].nome, "il più recente")

    if politica.spazio_massimo:
        totale = sum(b.dimensione for b in backup if b.nome in tenuti)
        # prima gli automatici più vecchi, poi gli altri; mai l'ultimo di ciascun gruppo
        candidati = [b for b in reversed(automatici[1:]) if b.nome in tenuti]
        candidati += [b for b in reversed(altri[1:]) if b.nome in tenuti]
        for b in candidati:
            if totale <= politica.spazio_massimo:
                break
            del tenuti[b.nome]
            totale -= b.dimensione
    return tenuti


def pulisci(utente=None, politica=None):
    """Elimina i backup fuori dalla politica di conservazione. Restituisce i nomi tolti.
    Durante un ripristino non tocca nulla (il file in uso potrebbe essere fra i più vecchi)."""
    if (cartella() / ".ripristino.lock").exists():
        return []
    backup = elenco()
    tenuti = classifica(backup, politica)
    tolti = []
    for b in backup:
        if b.nome not in tenuti:
            b.percorso.unlink(missing_ok=True)
            tolti.append(b.nome)
    if tolti:
        _registra("Backup eliminati dalla conservazione", utente, file=tolti)
    return tolti


def occupazione():
    """Spazio dei backup e del disco che li ospita."""
    backup = elenco()
    disco = shutil.disk_usage(cartella())
    return {"backup": sum(b.dimensione for b in backup), "numero": len(backup),
            "libero": disco.free, "totale": disco.total}  # fmt: skip


def controlla_spazio(politica=None):
    """Prima di un backup: servono circa due volte l'ultimo backup (file temporanei e file
    finale) più lo spazio libero minimo. Altrimenti non si comincia nemmeno."""
    politica = politica or Politica.corrente()
    backup = elenco()
    stima = 2 * max((b.dimensione for b in backup[:3]), default=0)
    libero = shutil.disk_usage(cartella()).free
    if libero - stima < politica.spazio_libero_minimo:
        raise BackupNonValido(
            f"Spazio su disco insufficiente per il backup: liberi {formato_dimensione(libero)}, "
            f"servono circa {formato_dimensione(stima)} più "
            f"{formato_dimensione(politica.spazio_libero_minimo)} di margine. Eliminare backup "
            "vecchi (dopo averli copiati altrove) o ridurre la conservazione."
        )


def crea_e_pulisci(motivo="manuale", utente=None):
    """Backup ordinario (pianificato, manuale, prima di un aggiornamento): fa spazio secondo la
    politica, crea il backup, poi applica di nuovo la politica. Restituisce (percorso, tolti)."""
    tolti = pulisci(utente)
    p = crea(motivo=motivo, utente=utente)
    return p, tolti + pulisci(utente)


# --- ripristino --------------------------------------------------------------------------


class RipristinoAnnullato(BackupNonValido):
    """Il ripristino non è riuscito ed è stato rimesso lo stato precedente."""


def ripristina(p, *, utente_descrizione="", backup_sicurezza=True, avanzamento=None):
    """Sostituisce database e file con quelli del backup. Prima salva lo stato attuale; se
    il ripristino fallisce (database, aggiornamento dello schema, file) rimette quello."""

    def passo(testo):
        if avanzamento:
            avanzamento(testo)

    passo("Verifica del backup")
    manifesto = verifica(p)
    pg_restore = _programma("pg_restore")
    sicurezza = None
    if backup_sicurezza:
        passo("Backup dello stato attuale")
        sicurezza = crea(motivo="prima del ripristino")
    try:
        _sostituisci(p, pg_restore, passo)
    except Exception as errore:
        if sicurezza is None:
            raise
        log.exception("Ripristino di %s non riuscito: si torna allo stato precedente", p.name)
        passo("Ripristino non riuscito: ritorno allo stato precedente")
        try:
            connection.close()
            _sostituisci(sicurezza, pg_restore, passo)
        except Exception as secondo:
            raise BackupNonValido(
                f"Ripristino non riuscito ({errore}) e non è stato possibile tornare allo stato "
                f"precedente ({secondo}). Ripristinare a mano il backup {sicurezza.name}."
            ) from secondo
        _registra("Ripristino da backup non riuscito, stato precedente rimesso", None,
                  file=p.name, errore=str(errore)[:500], eseguito_da=utente_descrizione,
                  backup_sicurezza=sicurezza.name)  # fmt: skip
        raise RipristinoAnnullato(
            f"Ripristino non riuscito: {errore}. I dati sono stati riportati allo stato "
            f"precedente (backup {sicurezza.name}): nulla è cambiato."
        ) from errore
    _registra(
        "Ripristino da backup",
        None,
        file=p.name,
        backup_del=manifesto.get("creato_il"),
        eseguito_da=utente_descrizione,
        backup_sicurezza=sicurezza.name if sicurezza else "",
    )
    return manifesto, sicurezza


def _sostituisci(p, pg_restore, passo):
    """Database e file dal backup p, poi le migrazioni mancanti (backup di versioni precedenti)."""
    from django.core.management import call_command

    with tempfile.TemporaryDirectory(dir=cartella()) as lavoro:
        lavoro = Path(lavoro)
        with tarfile.open(p, "r:") as tar:
            for n in (DATABASE, FILE):
                tar.extract(n, lavoro, filter="data")
        passo("Ripristino del database")
        svuota_database()
        argomenti, ambiente = _connessione()
        _esegui([pg_restore, "--no-owner", "--no-privileges", "--exit-on-error",
                 "--single-transaction", *argomenti, str(lavoro / DATABASE)], ambiente,
                "Ripristino del database non riuscito")  # fmt: skip
        connection.close()
        passo("Aggiornamento dello schema")
        call_command("migrate", interactive=False, verbosity=0)
        passo("Ripristino dei file")
        media = Path(settings.MEDIA_ROOT)
        media.mkdir(parents=True, exist_ok=True)
        for voce in media.iterdir():
            if voce.is_dir() and not voce.is_symlink():
                shutil.rmtree(voce)
            else:
                voce.unlink()
        with tarfile.open(lavoro / FILE, "r:gz") as tar:
            tar.extractall(media, filter="data")


def stato_ripristino():
    p = cartella() / ".ripristino.json"
    try:
        return json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def scrivi_stato(**stato):
    p = cartella() / ".ripristino.json"
    p.write_text(json.dumps({**(stato_ripristino() or {}), **stato}, ensure_ascii=False))
    p.chmod(0o600)


def formato_dimensione(byte):
    for unita in ("B", "KB", "MB", "GB"):
        if byte < 1024 or unita == "GB":
            return f"{byte:.0f} {unita}" if unita == "B" else f"{byte:.1f} {unita}"
        byte /= 1024
    return str(byte)
