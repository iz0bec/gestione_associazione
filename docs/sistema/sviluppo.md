<!--
******************************************************
* Progetto:    Gestione Associazione
* Autore:      Bartolomeo Santoro aka IZ0BEC
* Email:       info@iz0bec.info
* Descrizione: Ambiente di sviluppo, test e convenzioni
* Licenza:     CC0 1.0 Universal (pubblico dominio)
* SPDX-License-Identifier: CC0-1.0
******************************************************
-->

# Sviluppo

## Ambiente

Requisiti: [uv](https://docs.astral.sh/uv/), PostgreSQL 15+ (con Docker: `compose.dev.yaml`),
le librerie Pango per WeasyPrint (`brew install pango` su macOS, `libpango-1.0-0` su Debian).

```bash
uv sync                                     # crea .venv con Python 3.13 e tutte le dipendenze
docker compose -f compose.dev.yaml up -d   # PostgreSQL su 127.0.0.1:55432 (utente gestione/sviluppo)
cp .env.example .env                        # SECRET_KEY, DEBUG=true,
                                            # DATABASE_URL=postgres://gestione:sviluppo@127.0.0.1:55432/gestione_associazione
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

## Verifiche (le stesse della pipeline CI)

```bash
uv run ruff check .                          # lint (incluse regole di sicurezza)
uv run ruff format .                         # formattazione
uv run python scripts/verifica_intestazioni.py
uv run python manage.py makemigrations --check --dry-run
uv run pytest                                # test (richiede PostgreSQL)
```

## Struttura

```
config/            impostazioni, URL, WSGI
apps/core/         organizzazione, numerazioni, registro attività, interfaccia comune
apps/accounts/     utenti, ruoli (ruoli.py), accesso
apps/anagrafica/   soggetti, categorie, consensi
templates/         layout, moduli, pagine (le pagine di allauth sono personalizzate qui)
static/            CSS/JS dell'app; static/vendor = librerie di terze parti incluse
deploy/            Dockerfile, entrypoint
docs/              manuali, analisi, decisioni
```

## Convenzioni

- Nomi di dominio, testi e documentazione in **italiano**; commit in italiano (`Feat:`, `Fix:`, `Docs:`).
- Ogni file sorgente inizia con l'**intestazione di progetto** (autore, descrizione, `SPDX-License-Identifier: CC0-1.0`);
  lo verifica `scripts/verifica_intestazioni.py`.
- Logica di dominio nei **servizi** (`servizi.py`), viste sottili; ogni operazione rilevante scrive il registro attività.
- Ogni vista dichiara il permesso (`PermessoMixin`); i nuovi permessi si assegnano ai ruoli in `apps/accounts/ruoli.py`.
- Numeri progressivi solo con `apps.core.numerazione.prossimo_numero` dentro `transaction.atomic()`.
- Nessuno script inline nei template (la CSP lo blocca): comportamenti in `static/js/app.js` con attributi `data-*`.
- Ogni modulo nuovo: test, pagina nel manuale operativo, eventuali variabili nel manuale di sistema, voce nel CHANGELOG.

## Immagini del manuale

Le schermate del manuale (`static/img/manuale/*.jpg`, citate nei testi di `docs/operativo` come
`![didascalia](immagini/nome.jpg)`) si rifanno con **dati di fantasia**, mai con dati reali:

```bash
createdb gestione_demo                       # database vuoto, solo per le schermate
DATABASE_URL=.../gestione_demo uv run python manage.py migrate
DATABASE_URL=.../gestione_demo uv run python manage.py shell < scripts/manuale/dati_demo.py
DATABASE_URL=.../gestione_demo uv run python manage.py runserver 127.0.0.1:8010 --noreload
uv run python scripts/manuale/schermate.py http://127.0.0.1:8010   # Chrome tramite Playwright
dropdb gestione_demo
```

`dati_demo.py` si rifiuta di partire su un database che contiene già dati. A ogni versione si aggiorna
anche la copia nel repository: `manage.py manuale_pdf --uscita docs/manuale/manuale-operativo.pdf`
(sempre con il database dimostrativo). Il PDF del manuale si
genera dall'applicazione (*Manuale → Manuale in PDF*) o con `manage.py manuale_pdf --uscita file.pdf`;
viene conservato in `MEDIA_ROOT/manuale/` e rigenerato solo quando cambiano testi, immagini o versione.
