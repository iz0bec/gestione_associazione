# Librerie di terze parti (incluse, non modificate)

| Libreria | Versione | Licenza | File |
|---|---|---|---|
| Tabler (core) | 1.7.3 | MIT | `tabler/` (licenza indicata in package.json, https://github.com/tabler/tabler) |
| Tabler Icons (webfont) | 3.50.0 | MIT | `tabler-icons/` |
| htmx | 2.0.11 | 0BSD | `htmx/` |

Per aggiornare: scaricare con `npm pack <pacchetto>@<versione>`, copiare gli stessi file e
aggiornare questa tabella e `docs/sistema/licenze-terze-parti.md`.

Nei file minificati di Tabler sono stati tolti i commenti `sourceMappingURL`: le mappe sorgente non
sono incluse e `collectstatic` (archiviazione con manifesto) si fermerebbe cercandole.
