<!--
******************************************************
* Progetto:    Gestione Associazione
* Autore:      Bartolomeo Santoro aka IZ0BEC
* Email:       info@iz0bec.info
* Descrizione: Variabili di configurazione
* Licenza:     CC0 1.0 Universal (pubblico dominio)
* SPDX-License-Identifier: CC0-1.0
******************************************************
-->

# Configurazione

Tutta la configurazione dipendente dall'installazione si legge da variabili d'ambiente o dal
file `.env` nella cartella del progetto (modello: `.env.example`). Il file `.env` contiene segreti:
permessi `600`, mai nel repository.

| Variabile | Obbl. | Default | Descrizione |
|---|---|---|---|
| `SECRET_KEY` | sì | - | chiave segreta di Django (firma di sessioni e token). Cambiarla invalida le sessioni. |
| `DATABASE_URL` | sì | - | `postgres://utente:password@host:porta/database` |
| `ALLOWED_HOSTS` | sì | `localhost,127.0.0.1` | nomi host ammessi, separati da virgola |
| `DEBUG` | | `false` | **mai** `true` in produzione |
| `HTTPS` | | `false` | `true` se l'app è raggiungibile solo via HTTPS (cookie sicuri) |
| `SECURE_SSL_REDIRECT` | | `false` | con `HTTPS=true`, reindirizza http→https dall'app |
| `SECURE_HSTS_SECONDS` | | `0` | con `HTTPS=true`, durata HSTS (es. 31536000) |
| `CSRF_TRUSTED_ORIGINS` | | - | origini https ammesse per i moduli, es. `https://gestione.example.it` |
| `PROXY_COUNT` | | `0` | numero di reverse proxy fidati (per IP reali e protocollo) |
| `EMAIL_HOST`, `EMAIL_PORT` | | `localhost`, `587` | server SMTP |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | | - | credenziali SMTP |
| `EMAIL_USE_TLS` / `EMAIL_USE_SSL` | | `true` / `false` | cifratura SMTP (STARTTLS su 587 / SSL su 465) |
| `EMAIL_BACKEND` | | smtp (console con DEBUG) | backend email Django |
| `DEFAULT_FROM_EMAIL` | | `noreply@localhost` | mittente predefinito |
| `MEDIA_ROOT` | | `var/media` | cartella degli allegati (**non** servita dal web server) |
| `STATIC_ROOT` | | `var/static` | cartella dei file statici raccolti |
| `AXES_FAILURE_LIMIT` | | `5` | tentativi di accesso falliti prima del blocco |
| `AXES_COOLOFF_ORE` | | `0.25` | durata del blocco in ore |
| `SESSION_DURATA_SECONDI` | | `28800` | durata massima della sessione (8 ore) |
| `MFA_TOTP_ISSUER` | | `Gestione Associazione` | nome mostrato nell'app di autenticazione |
| `LOG_LEVEL` | | `INFO` | livello dei log su console |
| `DB_CONN_MAX_AGE` | | `60` | riuso delle connessioni al database (secondi) |

Solo con Docker (`compose.yaml`): `DB_PASSWORD` (obbligatoria), `APP_PORT` (default 8000).
