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
            assert set(tar.getnames()) == {"manifest.json", "database.dump", "file.tar.gz"}
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

    def test_conservazione_automatici(self):
        for _ in range(3):
            p = backup.crea(motivo="automatico")
            p.rename(p.with_name(p.name.replace("automatico", f"automatico-{_}")))
        manuale = backup.crea(motivo="manuale")
        # nomi diversi ma stesso motivo nel manifesto
        assert backup.pulisci_automatici(1) == 2
        assert manuale.exists() and len(backup.elenco()) == 2


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
