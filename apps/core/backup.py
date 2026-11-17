# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Backup e ripristino completi: un file .tar con il database (pg_dump), l'elenco
# *              dei file caricati e un manifesto con versione, migrazioni e impronte SHA-256.
# *              I file stanno una volta sola nell'archivio per contenuto (backup incrementali);
# *              con CHIAVE_BACKUP database e file sono cifrati (AES-256-GCM).
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
FORMATO = 2  # 1: file in un unico file.tar.gz (backup fino alla 1.0.29), ancora ripristinabili
MANIFESTO = "manifest.json"
DATABASE = "database.dump"
DATABASE_CIFRATO = "database.dump.cif"
FILE = "file.tar.gz"  # solo formato 1
ELENCO_FILE = "file.json"  # formato 2: [{"percorso", "sha256", "dimensione"}]
OGGETTI = "oggetti"  # archivio dei file per contenuto (e cartella nel .tar completo)
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


# --- archivio dei file per contenuto -----------------------------------------------------
#
# Ogni file caricato si salva una volta sola in BACKUP_ROOT/oggetti/<aa>/<sha256>, cifrato se
# c'è CHIAVE_BACKUP (<sha256>.<impronta della chiave>.cif): i backup contengono solo l'elenco.
# I file del protocollo non cambiano mai, quindi ogni backup aggiunge solo le novità.

INDICE = ".indice_file.json"  # cache {percorso: [dimensione, mtime_ns, sha256]}


def archivio():
    c = cartella() / OGGETTI
    c.mkdir(parents=True, exist_ok=True)
    c.chmod(0o700)
    return c


def nome_oggetto(sha, impronta_chiave=""):
    return f"{sha}.{impronta_chiave}.cif" if impronta_chiave else sha


def percorso_oggetto(sha, impronta_chiave=""):
    return archivio() / sha[:2] / nome_oggetto(sha, impronta_chiave)


def _censisci_media():
    """Elenco dei file caricati con impronta (ricalcolata solo se dimensione o data cambiano)."""
    media = Path(settings.MEDIA_ROOT)
    p_indice = cartella() / INDICE
    try:
        indice = json.loads(p_indice.read_text())
    except (OSError, json.JSONDecodeError):
        indice = {}
    nuovo, voci = {}, []
    if media.is_dir():
        for f in sorted(media.rglob("*")):
            relativo = f.relative_to(media).as_posix()
            if not f.is_file() or f.is_symlink() or relativo.startswith("."):
                continue
            stato = f.stat()
            vecchio = indice.get(relativo)
            if vecchio and vecchio[:2] == [stato.st_size, stato.st_mtime_ns]:
                sha = vecchio[2]
            else:
                sha = _impronta(f)
            nuovo[relativo] = [stato.st_size, stato.st_mtime_ns, sha]
            voci.append({"percorso": relativo, "sha256": sha, "dimensione": stato.st_size})
    parziale = p_indice.with_name(INDICE + ".parziale")
    parziale.write_text(json.dumps(nuovo))
    parziale.chmod(0o600)
    parziale.replace(p_indice)
    return voci


def _archivia(sorgente, sha, chiave):
    from . import cifratura_backup as cb

    impronta_chiave = cb.impronta(chiave) if chiave else ""
    dest = percorso_oggetto(sha, impronta_chiave)
    if dest.exists():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    parziale = dest.with_name(dest.name + ".parziale")
    if chiave:
        cb.cifra(sorgente, parziale, chiave)
    else:
        shutil.copyfile(sorgente, parziale)
    parziale.chmod(0o600)
    parziale.replace(dest)


def _blocchi(f, cifrato):
    """Contenuto in chiaro di un file aperto (decifrato se serve), a blocchi."""
    from . import cifratura_backup as cb

    if cifrato:
        yield from cb.decifra_flusso(f, cb.chiave_corrente())
    else:
        yield from iter(lambda: f.read(1024 * 1024), b"")


def _sha_blocchi(blocchi):
    h = hashlib.sha256()
    for b in blocchi:
        h.update(b)
    return h.hexdigest()


class _Contenuto:
    """Accesso al contenuto di un backup di formato 2: membri del .tar e archivio dei file."""

    def __init__(self, tar, manifesto):
        self.tar = tar
        self.manifesto = manifesto
        self.impronta_chiave = manifesto.get("impronta_chiave", "")
        self.membri = {m.name: m for m in tar.getmembers()}

    def database(self):
        cifrato = DATABASE_CIFRATO in self.membri
        return self.tar.extractfile(self.membri[DATABASE_CIFRATO if cifrato else DATABASE]), cifrato

    def elenco_file(self):
        voci = json.loads(self.tar.extractfile(self.membri[ELENCO_FILE]).read())
        for v in voci:
            percorso = Path(v.get("percorso", ""))
            if percorso.is_absolute() or ".." in percorso.parts or not v.get("sha256"):
                raise BackupNonValido("Elenco dei file del backup non valido.")
        return voci

    def apri(self, sha):
        """(file aperto, cifrato) del contenuto: dentro il .tar o nell'archivio."""
        nome = nome_oggetto(sha, self.impronta_chiave)
        interno = f"{OGGETTI}/{nome}"
        if interno in self.membri:
            return self.tar.extractfile(self.membri[interno]), bool(self.impronta_chiave)
        p = percorso_oggetto(sha, self.impronta_chiave)
        if not p.is_file():
            raise BackupNonValido(f"Manca un file del backup nell'archivio ({sha[:12]}…).")
        return open(p, "rb"), bool(self.impronta_chiave)  # noqa: SIM115 - chiuso dal chiamante


def oggetti_usati():
    """Nomi dei file dell'archivio usati da almeno un backup; None se un backup è illeggibile
    (allora non si elimina nulla)."""
    usati = set()
    for b in elenco():
        if b.manifesto.get("motivo") == "illeggibile":
            return None
        if b.manifesto.get("formato") != 2:
            continue
        try:
            with tarfile.open(b.percorso, "r:") as tar:
                c = _Contenuto(tar, b.manifesto)
                if any(n.startswith(f"{OGGETTI}/") for n in c.membri):
                    continue  # completo: i file sono dentro
                usati |= {nome_oggetto(v["sha256"], c.impronta_chiave) for v in c.elenco_file()}
        except (tarfile.TarError, KeyError, json.JSONDecodeError, OSError, BackupNonValido):
            return None
    return usati


def pulisci_archivio():
    """Toglie dall'archivio i file che nessun backup usa più. Restituisce quanti."""
    if (cartella() / ".ripristino.lock").exists():
        return 0
    usati = oggetti_usati()
    if usati is None:
        return 0
    tolti = 0
    for f in archivio().glob("*/*"):
        if f.is_file() and not f.name.endswith(".parziale") and f.name not in usati:
            f.unlink()
            tolti += 1
    return tolti


def dimensione_archivio():
    return sum(f.stat().st_size for f in archivio().glob("*/*") if f.is_file())


def esporta_completo(p):
    """Copia del backup con dentro anche i file (per portarlo altrove): percorso temporaneo."""
    manifesto = leggi_manifesto(p)
    destinazione = cartella() / f".esporta_{p.name}"
    with tarfile.open(p, "r:") as src, tarfile.open(destinazione, "w") as dst:
        for m in src.getmembers():
            dst.addfile(m, src.extractfile(m))
        if manifesto.get("formato") == 2:
            c = _Contenuto(src, manifesto)
            gia = set()
            for v in c.elenco_file():
                nome = nome_oggetto(v["sha256"], c.impronta_chiave)
                if nome in gia or f"{OGGETTI}/{nome}" in c.membri:
                    continue
                gia.add(nome)
                dst.add(percorso_oggetto(v["sha256"], c.impronta_chiave),
                        arcname=f"{OGGETTI}/{nome}")  # fmt: skip
    destinazione.chmod(0o600)
    return destinazione


# --- creazione ---------------------------------------------------------------------------


def crea(motivo="manuale", utente=None):
    """Crea il backup completo e restituisce il percorso del file."""
    from apps.core.models import Organizzazione

    from . import cifratura_backup as cb

    pg_dump = _programma("pg_dump")
    controlla_spazio()
    destinazione = cartella()
    chiave = cb.chiave_corrente()
    chiave_impronta = cb.impronta(chiave) if chiave else ""
    marca = timezone.localtime().strftime("%Y%m%d_%H%M%S")
    tipo = re.sub(r"[^a-z0-9]+", "-", motivo.lower()).strip("-")[:30] or "manuale"
    nome = f"backup_{marca}_{tipo}.tar"
    n = 2
    while (destinazione / nome).exists():  # due backup nello stesso secondo
        nome = f"backup_{marca}_{tipo}-{n}.tar"
        n += 1
    with tempfile.TemporaryDirectory(dir=destinazione) as lavoro:
        lavoro = Path(lavoro)
        argomenti, ambiente = _connessione()
        _esegui([pg_dump, "--format=custom", "--no-owner", "--no-privileges",
                 f"--file={lavoro / DATABASE}", *argomenti], ambiente,
                "Backup del database non riuscito")  # fmt: skip
        impronta_db = _impronta(lavoro / DATABASE)
        membro_db = DATABASE
        if chiave:
            cb.cifra(lavoro / DATABASE, lavoro / DATABASE_CIFRATO, chiave)
            (lavoro / DATABASE).unlink()
            membro_db = DATABASE_CIFRATO
        voci = _censisci_media()
        for v in voci:
            _archivia(Path(settings.MEDIA_ROOT) / v["percorso"], v["sha256"], chiave)
        (lavoro / ELENCO_FILE).write_text(json.dumps(voci, ensure_ascii=False))
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
            "cifrato": bool(chiave),
            "impronta_chiave": chiave_impronta,
            "file": {"numero": len(voci), "dimensione": sum(v["dimensione"] for v in voci)},
            "impronte": {DATABASE: impronta_db, ELENCO_FILE: _impronta(lavoro / ELENCO_FILE)},
        }
        (lavoro / MANIFESTO).write_text(json.dumps(manifesto, indent=2, ensure_ascii=False))
        parziale = destinazione / f".{nome}.parziale"
        with tarfile.open(parziale, "w") as tar:
            for n in (MANIFESTO, membro_db, ELENCO_FILE):
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


def verifica(p, *, file=True):
    """Controlla struttura, impronte (decifrando, se cifrato) e compatibilità con questa versione.
    Restituisce il manifesto, oppure solleva BackupNonValido senza aver modificato nulla.
    `file=False`: non rilegge i file caricati (solo database ed elenco)."""
    from django.db.migrations.loader import MigrationLoader

    from .cifratura_backup import ErroreCifratura

    manifesto = leggi_manifesto(p)
    formato = manifesto.get("formato")
    if formato not in (1, FORMATO) or manifesto.get("applicazione") != settings.APP_NOME:
        raise BackupNonValido("Il file non è un backup di questa applicazione.")
    with tarfile.open(p, "r:") as tar:
        nomi = {m.name: m for m in tar.getmembers()}
        if not all(m.isfile() for m in nomi.values()):
            raise BackupNonValido("Contenuto del backup inatteso.")
        if formato == 1:
            if set(nomi) != {MANIFESTO, DATABASE, FILE}:
                raise BackupNonValido("Contenuto del backup inatteso.")
            for n in (DATABASE, FILE):
                h = hashlib.sha256()
                f = tar.extractfile(nomi[n])
                for blocco in iter(lambda f=f: f.read(1024 * 1024), b""):
                    h.update(blocco)
                if h.hexdigest() != manifesto.get("impronte", {}).get(n):
                    raise BackupNonValido(f"Backup danneggiato: impronta di {n} diversa.")
        else:
            database = {DATABASE_CIFRATO} if manifesto.get("cifrato") else {DATABASE}
            base = {MANIFESTO, ELENCO_FILE} | database
            extra = set(nomi) - base
            if not base <= set(nomi) or any(not n.startswith(f"{OGGETTI}/") for n in extra):
                raise BackupNonValido("Contenuto del backup inatteso.")
            c = _Contenuto(tar, manifesto)
            impronte = manifesto.get("impronte", {})
            try:
                f, cifrato = c.database()
                if _sha_blocchi(_blocchi(f, cifrato)) != impronte.get(DATABASE):
                    raise BackupNonValido("Backup danneggiato: impronta del database diversa.")
                grezzo = tar.extractfile(nomi[ELENCO_FILE]).read()
                if hashlib.sha256(grezzo).hexdigest() != impronte.get(ELENCO_FILE):
                    raise BackupNonValido("Backup danneggiato: elenco dei file non corrispondente.")
                for v in c.elenco_file() if file else ():
                    f, cifrato = c.apri(v["sha256"])
                    with f:
                        if _sha_blocchi(_blocchi(f, cifrato)) != v["sha256"]:
                            raise BackupNonValido(
                                f"Backup danneggiato: file {v['percorso']} non corrispondente."
                            )
            except ErroreCifratura as e:
                raise BackupNonValido(str(e)) from e
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
    pulisci_archivio()
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
    pulisci_archivio()
    return tolti


def occupazione():
    """Spazio dei backup e del disco che li ospita."""
    backup = elenco()
    disco = shutil.disk_usage(cartella())
    archiviati = dimensione_archivio()
    return {"backup": sum(b.dimensione for b in backup) + archiviati, "numero": len(backup),
            "archivio": archiviati, "libero": disco.free, "totale": disco.total}  # fmt: skip


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


def _estrai_database(p, destinazione):
    """Scrive in `destinazione` il dump del database del backup (decifrato se serve)."""
    from .cifratura_backup import ErroreCifratura

    manifesto = leggi_manifesto(p)
    with tarfile.open(p, "r:") as tar:
        if manifesto.get("formato") == 1:
            f = tar.extractfile(DATABASE)
            cifrato = False
        else:
            f, cifrato = _Contenuto(tar, manifesto).database()
        try:
            with open(destinazione, "wb") as dst:
                for blocco in _blocchi(f, cifrato):
                    dst.write(blocco)
        except ErroreCifratura as e:
            raise BackupNonValido(str(e)) from e


def _svuota_media():
    media = Path(settings.MEDIA_ROOT)
    media.mkdir(parents=True, exist_ok=True)
    for voce in media.iterdir():
        if voce.is_dir() and not voce.is_symlink():
            shutil.rmtree(voce)
        else:
            voce.unlink()
    return media


def _scrivi_file(p, media):
    """File caricati dal backup p nella cartella media (svuotata)."""
    from .cifratura_backup import ErroreCifratura

    manifesto = leggi_manifesto(p)
    with tarfile.open(p, "r:") as tar:
        if manifesto.get("formato") == 1:
            with tarfile.open(fileobj=tar.extractfile(FILE), mode="r:gz") as interno:
                interno.extractall(media, filter="data")
            return
        c = _Contenuto(tar, manifesto)
        for v in c.elenco_file():
            dest = media / v["percorso"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            f, cifrato = c.apri(v["sha256"])
            try:
                with f, open(dest, "wb") as uscita:
                    for blocco in _blocchi(f, cifrato):
                        uscita.write(blocco)
            except ErroreCifratura as e:
                raise BackupNonValido(str(e)) from e


def _sostituisci(p, pg_restore, passo):
    """Database e file dal backup p, poi le migrazioni mancanti (backup di versioni precedenti)."""
    from django.core.management import call_command

    with tempfile.TemporaryDirectory(dir=cartella()) as lavoro:
        dump = Path(lavoro) / DATABASE
        _estrai_database(p, dump)
        passo("Ripristino del database")
        svuota_database()
        argomenti, ambiente = _connessione()
        _esegui([pg_restore, "--no-owner", "--no-privileges", "--exit-on-error",
                 "--single-transaction", *argomenti, str(dump)], ambiente,
                "Ripristino del database non riuscito")  # fmt: skip
        connection.close()
        passo("Aggiornamento dello schema")
        call_command("migrate", interactive=False, verbosity=0)
        passo("Ripristino dei file")
        _scrivi_file(p, _svuota_media())


def estrai(p, destinazione):
    """Per un ripristino a mano: database.dump e media/ decifrati nella cartella indicata."""
    verifica(p)
    dest = Path(destinazione)
    (dest / "media").mkdir(parents=True, exist_ok=False)
    _estrai_database(p, dest / DATABASE)
    _scrivi_file(p, dest / "media")
    return dest


# --- prova di ripristino -------------------------------------------------------------------

VERIFICHE = ".verifiche.json"
TABELLE_CONTEGGI = {
    "soggetti": "anagrafica_soggetto", "soci": "soci_socio",
    "protocolli": "protocollo_protocollo", "movimenti": "tesoreria_movimento",
}  # fmt: skip


def verifiche():
    """Esito dell'ultima prova di ripristino di ciascun backup."""
    try:
        dati = json.loads((cartella() / VERIFICHE).read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return dati if isinstance(dati, dict) else {}


def _salva_verifica(nome, esito, dettaglio):
    dati = {n: v for n, v in verifiche().items() if (cartella() / n).exists()}
    dati[nome] = {"il": timezone.localtime().isoformat(timespec="seconds"), "esito": esito,
                  "dettaglio": dettaglio[:500]}  # fmt: skip
    q = cartella() / VERIFICHE
    parziale = q.with_name(VERIFICHE + ".parziale")
    parziale.write_text(json.dumps(dati, indent=2, ensure_ascii=False))
    parziale.chmod(0o600)
    parziale.replace(q)


def prova_ripristino(p, utente=None):
    """Prova il backup senza toccare i dati: impronte di database e file (decifrando), lettura
    del dump con pg_restore e, se l'utente PostgreSQL può creare database, ripristino completo in
    un database temporaneo con il confronto dei conteggi. Restituisce (esito, dettaglio)."""
    import secrets

    try:
        manifesto = verifica(p)
        pg_restore = _programma("pg_restore")
        with tempfile.TemporaryDirectory(dir=cartella()) as lavoro:
            dump = Path(lavoro) / DATABASE
            _estrai_database(p, dump)
            argomenti, ambiente = _connessione()
            _esegui([pg_restore, "--list", str(dump)], ambiente, "Dump del database illeggibile")
            n_file = manifesto.get("file", {}).get("numero", "tutti i")
            dettaglio = f"impronte di database e {n_file} file corrette; dump leggibile"
            prova = f"{settings.DATABASES['default']['NAME']}_prova_{secrets.token_hex(4)}"
            try:
                with connection.cursor() as c:
                    c.execute(f"CREATE DATABASE {connection.ops.quote_name(prova)}")
            except Exception as e:  # noqa: BLE001 - manca il permesso CREATEDB
                dettaglio += (f"; ripristino di prova non eseguito (non si può creare un database "
                              f"temporaneo: {str(e).splitlines()[0][:120]})")  # fmt: skip
                _salva_verifica(p.name, "ok", dettaglio)
                _registra("Prova di ripristino", utente, file=p.name, esito="ok")
                return "ok", dettaglio
            try:
                prova_arg = [a for a in argomenti if not a.startswith("--dbname=")]
                _esegui([pg_restore, "--no-owner", "--no-privileges", "--exit-on-error",
                         *prova_arg, f"--dbname={prova}", str(dump)], ambiente,
                        "Ripristino di prova del database non riuscito")  # fmt: skip
                diversi = _confronta_conteggi(prova, manifesto.get("conteggi", {}))
            finally:
                with connection.cursor() as c:
                    c.execute(f"DROP DATABASE IF EXISTS {connection.ops.quote_name(prova)}")
            if diversi:
                raise BackupNonValido("conteggi diversi dopo il ripristino: " + ", ".join(diversi))
            dettaglio += "; ripristino completo in un database temporaneo riuscito, conteggi uguali"
    except BackupNonValido as e:
        dettaglio = " ".join(e.messages)
        _salva_verifica(p.name, "errore", dettaglio)
        _registra("Prova di ripristino non riuscita", utente, file=p.name, errore=dettaglio)
        return "errore", dettaglio
    _salva_verifica(p.name, "ok", dettaglio)
    _registra("Prova di ripristino", utente, file=p.name, esito="ok")
    return "ok", dettaglio


def _confronta_conteggi(nome_db, attesi):
    import psycopg

    db = settings.DATABASES["default"]
    diversi = []
    with psycopg.connect(
        host=db.get("HOST") or "localhost", port=db.get("PORT") or 5432, user=db.get("USER"),
        password=db.get("PASSWORD") or None, dbname=nome_db,
    ) as conn, conn.cursor() as c:  # fmt: skip
        for chiave, tabella in TABELLE_CONTEGGI.items():
            if chiave not in attesi:
                continue
            c.execute(f'SELECT count(*) FROM "{tabella}"')  # noqa: S608 - nomi fissi
            trovati = c.fetchone()[0]
            if trovati != attesi[chiave]:
                diversi.append(f"{chiave} {trovati} invece di {attesi[chiave]}")
    return diversi


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
