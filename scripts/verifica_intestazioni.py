#!/usr/bin/env python3
# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Verifica che ogni file sorgente abbia l'intestazione di progetto
# *              (autore e licenza SPDX). Usato in CI; exit 1 se manca qualcosa.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import subprocess  # noqa: S404
import sys

ESTENSIONI = (".py", ".html", ".css", ".js", ".sh", ".yaml", ".yml", ".toml", ".md")
ESCLUSI = ("static/vendor/", "apps/accounts/migrations/0001", "apps/accounts/migrations/0002",
           "apps/core/migrations/0001", "apps/anagrafica/migrations/0001",
           "apps/core/migrations/0002_iscrizioni", "apps/soci/migrations/0001",
           "apps/protocollo/migrations/0001")  # fmt: skip
# file brevi senza intestazione (frammenti di template e init vuoti)
SENZA_INTESTAZIONE_OK = ("templates/allauth/elements/", "templates/moduli/", "templates/includes/",
                         "/__init__.py", "templates/errori/", "templates/40", "templates/50",
                         "templates/core/", "templates/anagrafica/", "templates/soci/",
                         "templates/protocollo/", "templates/allauth/layouts/",
                         "CHANGELOG.md", "static/vendor/README.md", ".gitlab-ci.yml")  # fmt: skip


def main():
    file = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],  # noqa: S607
        capture_output=True, text=True, check=True,
    ).stdout.split()  # fmt: skip
    mancanti = []
    for f in file:
        if not f.endswith(ESTENSIONI) or f.startswith(ESCLUSI):
            continue
        if any(s in f for s in SENZA_INTESTAZIONE_OK) and not f.endswith("/migrations/__init__.py"):
            continue
        if "/migrations/" in f and f.endswith("__init__.py"):
            continue
        with open(f, encoding="utf-8") as fh:
            testa = fh.read(1500)
        if "SPDX-License-Identifier: CC0-1.0" not in testa or "IZ0BEC" not in testa:
            mancanti.append(f)
    for f in mancanti:
        print(f"intestazione mancante: {f}")
    return 1 if mancanti else 0


if __name__ == "__main__":
    sys.exit(main())
