# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Backup e ripristino completi: un file .tar con il database (pg_dump), i file
# *              caricati e un manifesto con versione, migrazioni e impronte SHA-256.
# *              Il ripristino verifica il file, salva prima lo stato attuale, poi sostituisce
# *              database e file e applica le migrazioni mancanti.
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
from django.core.exceptions import ValidationError
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
    _registra("Backup eliminato", utente, file=nome)


def pulisci_automatici(conserva):
    """Tiene solo gli ultimi `conserva` backup automatici (quelli manuali restano)."""
    automatici = [b for b in elenco() if b.automatico]
    for b in automatici[conserva:]:
        b.percorso.unlink(missing_ok=True)
    return max(0, len(automatici) - conserva)


# --- ripristino --------------------------------------------------------------------------


def ripristina(p, *, utente_descrizione="", backup_sicurezza=True, avanzamento=None):
    """Sostituisce database e file con quelli del backup. Prima salva lo stato attuale."""
    from django.core.management import call_command

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
    _registra(
        "Ripristino da backup",
        None,
        file=p.name,
        backup_del=manifesto.get("creato_il"),
        eseguito_da=utente_descrizione,
        backup_sicurezza=sicurezza.name if sicurezza else "",
    )
    return manifesto, sicurezza


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
