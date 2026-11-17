# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test di backup e ripristino: contenuto e verifica del file, file danneggiati
# *              o di versioni più recenti, ripristino reale su PostgreSQL, interfaccia.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import io
import json
import shutil
import tarfile
from pathlib import Path
from unittest import mock

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import CommandError, call_command
from django.urls import reverse

from apps.anagrafica.models import Soggetto
from apps.core import backup

richiede_pg = pytest.mark.skipif(not shutil.which("pg_dump"), reason="pg_dump non disponibile")


@pytest.fixture(autouse=True)
def cartelle(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.BACKUP_ROOT = tmp_path / "backup"
    (tmp_path / "media" / "anagrafica").mkdir(parents=True)
    (tmp_path / "media" / "anagrafica" / "foto.jpg").write_bytes(b"foto originale")
    return tmp_path


def _riscrivi(p, sostituzioni):
    """Copia del backup con alcuni membri sostituiti (per simulare file manomessi)."""
    nuovo = p.with_name("backup_manomesso.tar")
    with tarfile.open(p) as src, tarfile.open(nuovo, "w") as dst:
        for m in src.getmembers():
            dati = sostituzioni.get(m.name, src.extractfile(m).read())
            m.size = len(dati)
            dst.addfile(m, io.BytesIO(dati))
    return nuovo


@richiede_pg
@pytest.mark.django_db
class TestFile:
    def test_contenuto_e_verifica(self):
        Soggetto.objects.create(cognome="Rossi")
        p = backup.crea(motivo="manuale")
        assert backup.NOME_VALIDO.match(p.name) and oct(p.stat().st_mode)[-3:] == "600"
        with tarfile.open(p) as tar:
            assert set(tar.getnames()) == {"manifest.json", "database.dump", "file.json"}
        m = backup.verifica(p)
        assert m["conteggi"]["soggetti"] == 1 and "soci" in m["migrazioni"]
        assert [b.nome for b in backup.elenco()] == [p.name]

    def test_file_danneggiato_o_piu_recente(self):
        p = backup.crea()
        with pytest.raises(backup.BackupNonValido, match="danneggiato"):
            backup.verifica(_riscrivi(p, {"database.dump": b"PGDMP rovinato"}))
        m = backup.leggi_manifesto(p)
        m["migrazioni"]["soci"].append("9999_futura")
        with pytest.raises(backup.BackupNonValido, match="più recente"):
            backup.verifica(_riscrivi(p, {"manifest.json": json.dumps(m).encode()}))
        with pytest.raises(backup.BackupNonValido):
            backup.salva_caricato(SimpleUploadedFile("x.tar", b"non un tar"))
        with pytest.raises(backup.BackupNonValido):
            backup.percorso("../../etc/passwd")

    def test_conservazione_applicata(self):
        for _ in range(3):
            p = backup.crea(motivo="automatico")
            p.rename(p.with_name(p.name.replace("automatico", f"automatico-{_}")))
        manuale = backup.crea(motivo="manuale")
        # stesso giorno: dei tre automatici resta solo il più recente
        politica = backup.Politica(1, 0, 0, 10, 0, 0)
        assert len(backup.pulisci(politica=politica)) == 2
        assert manuale.exists() and len(backup.elenco()) == 2

    def test_conserva_da_interfaccia_e_comando(self, client_ruolo):
        p1 = backup.crea(motivo="automatico")
        p1 = p1.rename(p1.with_name(p1.name.replace("automatico", "automatico-1")))
        p2 = backup.crea(motivo="automatico")
        c = client_ruolo("Amministratore di sistema")
        url = reverse("core:conserva_backup", args=[p1.name])
        assert c.post(url, {"conserva": "1", "nota": "fine anno"}).status_code == 302
        assert backup.conservati()[p1.name]["nota"] == "fine anno"
        assert backup.pulisci(politica=backup.Politica(1, 0, 0, 0, 0, 0)) == []
        assert "escluso dalla rotazione" in c.get(reverse("core:backup")).content.decode()
        call_command("backup", rilascia=p1.name, stdout=io.StringIO())
        assert backup.pulisci(politica=backup.Politica(1, 0, 0, 0, 0, 0)) == [p1.name]
        assert p2.exists() and not p1.exists()
        call_command("backup", conserva=p2.name, stdout=io.StringIO())
        backup.elimina(p2.name)
        assert backup.conservati() == {}

    def test_spazio_insufficiente(self):
        disco = shutil.disk_usage("/")._replace(free=10)
        with (
            mock.patch("apps.core.backup.shutil.disk_usage", return_value=disco),
            pytest.raises(backup.BackupNonValido, match="Spazio su disco insufficiente"),
        ):
            backup.crea(motivo="manuale")
        assert backup.elenco() == []


def _finto(giorno, motivo="automatico", dimensione=100, ora=2):
    from datetime import datetime

    creato = datetime(giorno.year, giorno.month, giorno.day, ora)
    nome = f"backup_{creato:%Y%m%d_%H%M%S}_{motivo}.tar"
    return backup.Backup(nome, Path(nome), dimensione,
                         {"creato_il": creato.isoformat(), "motivo": motivo})  # fmt: skip


class TestPolitica:
    def test_rotazione(self):
        from datetime import date, timedelta

        giorni = [date(2026, 1, 1) + timedelta(days=i) for i in range(90)]  # fino al 31/03
        elenco = [_finto(g) for g in reversed(giorni)]
        tenuti = backup.classifica(elenco, backup.Politica(3, 2, 2, 10, 0, 0))
        attesi = {_finto(date(2026, 3, d)).nome: m for d, m in
                  ((31, "giornaliero"), (30, "giornaliero"), (29, "giornaliero"))}  # fmt: skip
        attesi[_finto(date(2026, 2, 28)).nome] = "mensile"
        assert tenuti == attesi

    def test_altri_illeggibili_e_ultimo(self):
        from datetime import date, timedelta

        manuali = [_finto(date(2026, 1, 1) + timedelta(days=i), "manuale") for i in range(12)]
        rotto = backup.Backup("backup_rotto.tar", Path("x"), 1, {"motivo": "illeggibile"})
        auto = _finto(date(2025, 1, 1))
        tenuti = backup.classifica([*manuali, rotto, auto], backup.Politica(0, 0, 0, 10, 0, 0))
        assert sum(1 for b in manuali if b.nome in tenuti) == 10
        assert manuali[0].nome not in tenuti and manuali[-1].nome in tenuti
        assert tenuti["backup_rotto.tar"] == "da controllare"
        assert tenuti[auto.nome] == "il più recente"  # l'ultimo automatico resta sempre

    def test_esclusi_dalla_rotazione(self):
        from datetime import date, timedelta

        elenco = [_finto(date(2026, 3, 10) - timedelta(days=i)) for i in range(5)]
        fisso = elenco[4].nome
        tenuti = backup.classifica(elenco, backup.Politica(1, 0, 0, 0, 250, 0), fissati=[fisso])
        assert tenuti == {elenco[0].nome: "giornaliero", fisso: "escluso dalla rotazione"}

    def test_spazio_massimo(self):
        from datetime import date, timedelta

        elenco = [_finto(date(2026, 3, 10) - timedelta(days=i)) for i in range(5)]
        tenuti = backup.classifica(elenco, backup.Politica(10, 0, 0, 10, 250, 0))
        assert set(tenuti) == {elenco[0].nome, elenco[1].nome}

    def test_dimensioni(self):
        from django.core.exceptions import ImproperlyConfigured

        assert backup.dimensione_byte("") == 0
        assert backup.dimensione_byte("20G") == 20 * 1024**3
        assert backup.dimensione_byte("1.5gb") == int(1.5 * 1024**3)
        assert backup.dimensione_byte("500M") == 500 * 1024**2
        with pytest.raises(ImproperlyConfigured):
            backup.dimensione_byte("tanto")


@richiede_pg
@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_ripristino_reale(cartelle):
    Soggetto.objects.create(cognome="Prima")
    p = backup.crea()
    Soggetto.objects.create(cognome="Dopo")
    (cartelle / "media" / "anagrafica" / "foto.jpg").write_bytes(b"foto modificata")
    (cartelle / "media" / "nuovo.txt").write_text("da togliere")
    with pytest.raises(CommandError):
        call_command("ripristina", p.name, conferma="sbagliato", stdout=io.StringIO())
    from django.conf import settings

    call_command("ripristina", p.name, conferma=settings.DATABASES["default"]["NAME"],
                 stato=True, stdout=io.StringIO())  # fmt: skip
    assert list(Soggetto.objects.values_list("cognome", flat=True)) == ["Prima"]
    media = cartelle / "media"
    assert (media / "anagrafica" / "foto.jpg").read_bytes() == b"foto originale"
    assert not (media / "nuovo.txt").exists()
    assert backup.stato_ripristino()["esito"] == "ok"
    sicurezza = [b for b in backup.elenco() if b.motivo == "prima del ripristino"]
    assert len(sicurezza) == 1 and sicurezza[0].manifesto["conteggi"]["soggetti"] == 2
    assert not (Path(settings.BACKUP_ROOT) / ".ripristino.lock").exists()


@richiede_pg
@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_ripristino_da_versione_precedente(cartelle):
    """Backup senza l'ultima migrazione: dopo il ripristino lo schema viene aggiornato."""
    from django.db import connection
    from django.db.migrations.recorder import MigrationRecorder

    from apps.comunicazioni.models import Modello

    ultima = ("comunicazioni", "0005_modello_ricezione_domanda")
    call_command("migrate", "comunicazioni", "0004", verbosity=0)
    Modello.objects.filter(uso="ricezione").delete()  # i dati della migrazione mancante
    try:
        vecchio = backup.crea()
    finally:
        call_command("migrate", "comunicazioni", verbosity=0)
    assert ultima[1] not in backup.leggi_manifesto(vecchio)["migrazioni"]["comunicazioni"]
    Soggetto.objects.create(cognome="Dopo")

    backup.ripristina(vecchio)
    applicate = MigrationRecorder(connection).applied_migrations()
    assert ultima in applicate
    assert Modello.objects.filter(uso="ricezione").exists()  # migrazione rieseguita
    assert not Soggetto.objects.filter(cognome="Dopo").exists()


@richiede_pg
@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_ripristino_fallito_torna_indietro(cartelle):
    from django.core import management

    Soggetto.objects.create(cognome="Prima")
    p = backup.crea()
    Soggetto.objects.create(cognome="Dopo")
    (cartelle / "media" / "anagrafica" / "foto.jpg").write_bytes(b"foto modificata")
    vero = management.call_command
    chiamate = []

    def migrate_che_fallisce(nome, *args, **kwargs):
        chiamate.append(nome)
        if nome == "migrate" and chiamate.count("migrate") == 1:
            raise RuntimeError("migrazione rotta")
        return vero(nome, *args, **kwargs)

    with (
        mock.patch("django.core.management.call_command", migrate_che_fallisce),
        pytest.raises(backup.RipristinoAnnullato, match="migrazione rotta"),
    ):
        backup.ripristina(p)
    assert set(Soggetto.objects.values_list("cognome", flat=True)) == {"Prima", "Dopo"}
    assert (cartelle / "media" / "anagrafica" / "foto.jpg").read_bytes() == b"foto modificata"
    assert chiamate.count("migrate") == 2


@richiede_pg
@pytest.mark.django_db
class TestInterfaccia:
    @pytest.fixture
    def admin(self, client, crea_utente):
        client.force_login(crea_utente("capo", ruoli=["Amministratore di sistema"]))
        return client

    def test_crea_scarica_elimina(self, admin):
        assert admin.get(reverse("core:backup")).status_code == 200
        admin.post(reverse("core:backup"))
        (b,) = backup.elenco()
        r = admin.get(reverse("core:scarica_backup", args=[b.nome]))
        assert r.status_code == 200 and "attachment" in r["Content-Disposition"]
        f = SimpleUploadedFile("copia.tar", b"".join(r.streaming_content))
        admin.post(reverse("core:backup"), {"azione": "carica", "file": f})
        assert len(backup.elenco()) == 2
        admin.post(reverse("core:elimina_backup", args=[b.nome]))
        assert len(backup.elenco()) == 1

    def test_ripristino_chiede_conferma_e_password(self, admin):
        p = backup.crea()
        url = reverse("core:ripristino", args=[p.name])
        assert "integro e compatibile" in admin.get(url).content.decode()
        with mock.patch("apps.core.viste_backup.subprocess.Popen") as avvio:
            admin.post(url, {"conferma": "RIPRISTINA", "password": "sbagliata"})
            assert not avvio.called
            r = admin.post(url, {"conferma": "RIPRISTINA", "password": "Password-di-prova-123"})
            assert avvio.called and "ripristina" in avvio.call_args.args[0]
        stato = admin.get(r.url)
        assert stato.status_code == 200 and "Avvio" in stato.content.decode()
        admin.logout()
        assert admin.get(r.url).status_code == 200  # senza sessione (il database cambia)
        assert admin.get(reverse("stato_ripristino") + "?t=falso").status_code == 404

    def test_permessi(self, client_ruolo):
        c = client_ruolo("Segretario")
        assert c.get(reverse("core:backup")).status_code == 403


@richiede_pg
@pytest.mark.django_db
def test_un_backup_automatico_al_giorno():
    from django.utils import timezone

    from apps.core.management.commands.pianificatore import backup_di_oggi

    oggi = timezone.localdate()
    assert not backup_di_oggi(oggi)
    call_command("backup", automatico=True, stdout=io.StringIO())
    assert backup_di_oggi(oggi)
    call_command("backup", motivo="prima dell'aggiornamento", stdout=io.StringIO())
    assert {b.motivo for b in backup.elenco()} == {"automatico", "prima dell'aggiornamento"}


# --- incrementali, cifratura, formato precedente, prova di ripristino (1.0.30) ---------------


def _oggetti():
    return sorted(f.name for f in backup.archivio().glob("*/*"))


@richiede_pg
@pytest.mark.django_db
class TestIncrementali:
    def test_file_una_volta_sola(self, cartelle):
        primo = backup.crea()
        assert len(_oggetti()) == 1 and backup.leggi_manifesto(primo)["file"]["numero"] == 1
        (cartelle / "media" / "copia.jpg").write_bytes(b"foto originale")  # stesso contenuto
        (cartelle / "media" / "nuovo.pdf").write_bytes(b"%PDF nuovo")
        secondo = backup.crea()
        assert len(_oggetti()) == 2 and backup.leggi_manifesto(secondo)["file"]["numero"] == 3
        assert primo.stat().st_size < 1024 * 1024  # niente documenti dentro il .tar
        backup.elimina(secondo.name)
        assert len(_oggetti()) == 1  # il pdf non serve più a nessun backup

    def test_scaricato_completo_e_autosufficiente(self, cartelle):
        p = backup.crea()
        completo = backup.esporta_completo(p)
        with tarfile.open(completo) as tar:
            assert any(n.startswith("oggetti/") for n in tar.getnames())
        shutil.rmtree(backup.archivio())  # altrove l'archivio non c'è
        with completo.open("rb") as f:
            caricato = backup.salva_caricato(SimpleUploadedFile("b.tar", f.read()))
        destinazione = cartelle / "estratto"
        backup.estrai(caricato, destinazione)
        assert (
            destinazione / "media" / "anagrafica" / "foto.jpg"
        ).read_bytes() == b"foto originale"
        assert (destinazione / "database.dump").read_bytes().startswith(b"PGDMP")

    def test_file_mancante_nell_archivio(self):
        p = backup.crea()
        for f in backup.archivio().glob("*/*"):
            f.unlink()
        with pytest.raises(backup.BackupNonValido, match="Manca un file"):
            backup.verifica(p)


@richiede_pg
@pytest.mark.django_db
class TestCifratura:
    def test_cifrato_e_chiave_sbagliata(self, settings, cartelle):
        from apps.core import cifratura_backup as cb

        settings.CHIAVE_BACKUP = cb.nuova_chiave()
        p = backup.crea()
        m = backup.leggi_manifesto(p)
        assert m["cifrato"] and m["impronta_chiave"] == cb.impronta(settings.CHIAVE_BACKUP)
        with tarfile.open(p) as tar:
            assert "database.dump.cif" in tar.getnames()
            assert not tar.extractfile("database.dump.cif").read().startswith(b"PGDMP")
        (oggetto,) = backup.archivio().glob("*/*")
        assert oggetto.name.endswith(".cif") and b"foto originale" not in oggetto.read_bytes()
        backup.verifica(p)
        giusta = settings.CHIAVE_BACKUP
        settings.CHIAVE_BACKUP = cb.nuova_chiave()
        with pytest.raises(backup.BackupNonValido, match="altra chiave"):
            backup.verifica(p)
        settings.CHIAVE_BACKUP = ""
        with pytest.raises(backup.BackupNonValido, match="serve la chiave"):
            backup.verifica(p)
        settings.CHIAVE_BACKUP = giusta
        destinazione = cartelle / "estratto"
        backup.estrai(p, destinazione)
        assert (
            destinazione / "media" / "anagrafica" / "foto.jpg"
        ).read_bytes() == b"foto originale"

    def test_flusso_troncato_o_manomesso(self, tmp_path):
        from apps.core import cifratura_backup as cb

        chiave = cb.nuova_chiave()
        chiaro = tmp_path / "chiaro"
        chiaro.write_bytes(b"x" * (cb.BLOCCO * 2 + 10))
        cif = tmp_path / "cif"
        sha = cb.cifra(chiaro, cif, chiave)
        assert cb.decifra(cif, tmp_path / "di_nuovo", chiave) == sha
        dati = cif.read_bytes()
        (tmp_path / "corto").write_bytes(dati[: len(dati) - 40])
        with pytest.raises(cb.ErroreCifratura):
            cb.decifra(tmp_path / "corto", tmp_path / "x", chiave)
        rovinato = bytearray(dati)
        rovinato[100] ^= 1
        (tmp_path / "rovinato").write_bytes(bytes(rovinato))
        with pytest.raises(cb.ErroreCifratura):
            cb.decifra(tmp_path / "rovinato", tmp_path / "x", chiave)


@richiede_pg
@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_ripristino_cifrato_reale(settings, cartelle):
    from apps.core import cifratura_backup as cb

    settings.CHIAVE_BACKUP = cb.nuova_chiave()
    Soggetto.objects.create(cognome="Prima")
    p = backup.crea()
    Soggetto.objects.create(cognome="Dopo")
    (cartelle / "media" / "anagrafica" / "foto.jpg").write_bytes(b"foto modificata")
    backup.ripristina(p)
    assert list(Soggetto.objects.values_list("cognome", flat=True)) == ["Prima"]
    assert (cartelle / "media" / "anagrafica" / "foto.jpg").read_bytes() == b"foto originale"


@richiede_pg
@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_formato_precedente_ancora_ripristinabile(cartelle):
    """Backup della 1.0.29 o prima: file in un unico file.tar.gz."""
    import hashlib
    import tempfile

    from django.conf import settings

    Soggetto.objects.create(cognome="Vecchio")
    with tempfile.TemporaryDirectory() as lavoro:
        lavoro = Path(lavoro)
        argomenti, ambiente = backup._connessione()
        backup._esegui([shutil.which("pg_dump"), "--format=custom", "--no-owner",
                        "--no-privileges", f"--file={lavoro / 'database.dump'}", *argomenti],
                       ambiente, "pg_dump")  # fmt: skip
        with tarfile.open(lavoro / "file.tar.gz", "w:gz") as tar:
            tar.add(cartelle / "media" / "anagrafica", arcname="anagrafica")
        impronte = {n: hashlib.sha256((lavoro / n).read_bytes()).hexdigest()
                    for n in ("database.dump", "file.tar.gz")}  # fmt: skip
        manifesto = {"formato": 1, "applicazione": settings.APP_NOME, "versione": "1.0.29",
                     "creato_il": "2026-11-01T02:00:00+01:00", "motivo": "automatico",
                     "migrazioni": backup._migrazioni_applicate(), "conteggi": {},
                     "impronte": impronte}  # fmt: skip
        (lavoro / "manifest.json").write_text(json.dumps(manifesto))
        vecchio = backup.cartella() / "backup_20261101_020000_automatico.tar"
        with tarfile.open(vecchio, "w") as tar:
            for n in ("manifest.json", "database.dump", "file.tar.gz"):
                tar.add(lavoro / n, arcname=n)
    Soggetto.objects.create(cognome="Nuovo")
    (cartelle / "media" / "anagrafica" / "foto.jpg").write_bytes(b"cambiata")
    backup.ripristina(vecchio)
    assert list(Soggetto.objects.values_list("cognome", flat=True)) == ["Vecchio"]
    assert (cartelle / "media" / "anagrafica" / "foto.jpg").read_bytes() == b"foto originale"
    assert backup.esporta_completo(vecchio).exists()  # anche scaricabile


@richiede_pg
@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_prova_di_ripristino_completa(cartelle, client_ruolo):
    Soggetto.objects.create(cognome="Prova")
    p = backup.crea()
    esito, dettaglio = backup.prova_ripristino(p)
    assert esito == "ok", dettaglio
    assert "database temporaneo riuscito" in dettaglio or "non eseguito" in dettaglio
    assert backup.verifiche()[p.name]["esito"] == "ok"
    for f in backup.archivio().glob("*/*"):
        f.write_bytes(b"rovinato")
    esito, dettaglio = backup.prova_ripristino(p)
    assert esito == "errore" and "danneggiato" in dettaglio
    admin = client_ruolo("Amministratore di sistema")
    pagina = admin.get(reverse("core:backup")).content.decode()
    assert "prova di ripristino non riuscita" in pagina and "non sono cifrati" in pagina


@pytest.mark.django_db
def test_prova_settimanale(cartelle):
    from datetime import timedelta

    from django.utils import timezone

    from apps.core.management.commands.pianificatore import prova_dovuta

    adesso = timezone.localtime()
    assert not prova_dovuta(adesso)  # nessun backup
    (backup.cartella() / "backup_20260101_020000_automatico.tar").write_bytes(b"x")
    assert prova_dovuta(adesso)
    backup._salva_verifica("backup_20260101_020000_automatico.tar", "ok", "")
    assert not prova_dovuta(adesso) and prova_dovuta(adesso + timedelta(days=8))
