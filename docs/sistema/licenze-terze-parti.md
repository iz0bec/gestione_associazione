<!--
******************************************************
* Progetto:    Gestione Associazione
* Autore:      Bartolomeo Santoro aka IZ0BEC
* Email:       info@iz0bec.info
* Descrizione: Licenze delle componenti di terze parti
* Licenza:     CC0 1.0 Universal (pubblico dominio)
* SPDX-License-Identifier: CC0-1.0
******************************************************
-->

# Licenze di terze parti

Il codice del progetto è in pubblico dominio (CC0 1.0). Le componenti seguenti restano
soggette alle proprie licenze, tutte compatibili con l'uso e la ridistribuzione.

## Strumenti di sviluppo (non installati con l'applicazione)

| Pacchetto | Licenza | Uso |
|---|---|---|
| Playwright | Apache-2.0 | schermate del manuale (`scripts/manuale/schermate.py`) |

## Librerie Python (dipendenze dirette)

| Pacchetto | Versione | Licenza |
|---|---|---|
| Django | 6.1.3 | BSD-3-Clause |
| django-allauth | 65.21.1 | MIT |
| django-axes | 9.0.0 | MIT |
| django-environ | 0.14.0 | MIT |
| django-filter | 26.2 | BSD |
| django-htmx | 1.29.0 | MIT |
| gunicorn | 26.2.0 | MIT |
| psycopg | 3.3.8 | LGPL-3.0 (usata come libreria, non modificata) |
| python-codicefiscale | 0.12.1 | MIT |
| WeasyPrint | 70.0 | BSD |
| WhiteNoise | 6.12.0 | MIT |
| argon2-cffi | 25.1.0 | MIT |
| cryptography | 50.0.2 | Apache-2.0 / BSD |
| Pillow | 13.0.0 | MIT-CMU (HPND) |
| segno | 1.6.6 | BSD |
| openpyxl | 3.1.5 | MIT |
| et-xmlfile (usata da openpyxl) | 2.0.0 | MIT |
| defusedxml | 0.7.1 | PSF-2.0 |
| Markdown (help in linea) | 3.11.3 | BSD-3-Clause |

Versioni esatte di tutte le dipendenze (anche indirette) in `uv.lock`.

## Librerie front-end incluse (`static/vendor`)

| Libreria | Versione | Licenza |
|---|---|---|
| Tabler | 1.7.3 | MIT |
| Tabler Icons | 3.50.0 | MIT |
| htmx | 2.0.11 | 0BSD |
| Cinzel (font, attestati) | 2.000 | SIL OFL 1.1 |
| EB Garamond (font, attestati) | 1.001 | SIL OFL 1.1 |

I font sono distribuiti con i rispettivi testi di licenza in `static/vendor/fonts/`. Gli
ornamenti dell'attestato (`static/img/attestato/*.svg`) sono disegnati per il progetto (CC0) e si rigenerano con
`scripts/ornamenti_attestato.py`.
