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
| `URL_PUBBLICO` | | - | indirizzo pubblico dell'app, usato nei QR stampati delle schede dei beni (altrimenti quello della richiesta) |
| `COMUNICAZIONI_LOTTO` | | `30` | email spedite a ogni giro della coda (ogni minuto): adattarlo ai limiti del proprio server SMTP |
| `CHIAVE_CIFRATURA` | per le caselle di posta | - | chiave Fernet per le password salvate nel database; generarla con `manage.py genera_chiave_cifratura`. Più chiavi separate da virgola per la rotazione (la prima cifra). **Conservarla con i backup.** |
| `PROTOCOLLO_ALLEGATO_MAX_MB` | | `25` | dimensione massima di un documento protocollato |
| `PROTOCOLLO_ESTENSIONI` | | pdf, p7m, xml, eml, office, immagini, zip | estensioni ammesse per i documenti (separate da virgola) |

Solo con Docker (`compose.yaml`): `DB_PASSWORD` (obbligatoria), `APP_PORT` (default 8000).

## Lavori periodici

| Comando | Quando | Cosa fa |
|---|---|---|
| `manage.py pianificatore` | sempre attivo (servizio) | esegue i comandi seguenti alle scadenze |
| `manage.py invia_coda` | ogni minuto | prepara auguri e promemoria di rinnovo del giorno e spedisce le email in coda (se l'invio è attivo) |
| `manage.py scarica_posta` | ogni 15 minuti | scarica i nuovi messaggi dalle caselle del protocollo (sola lettura) |
| `manage.py registro_giornaliero` | ogni notte | genera e conserva il PDF del registro di protocollo dei giorni conclusi |
| `manage.py conservazione_dati` | ogni notte | con l'anonimizzazione automatica attiva, anonimizza le persone oltre il termine di conservazione (`--elenco`: solo il conteggio) |
| `manage.py manuale_pdf` | a richiesta | genera il manuale operativo in PDF (`--uscita file.pdf`) |
| `manage.py backup --automatico` | ogni notte (`BACKUP_ORA`) | backup completo, conserva gli ultimi `BACKUP_CONSERVA` |
| `manage.py genera_chiave_cifratura` | una volta | stampa una chiave per `CHIAVE_CIFRATURA` |

Con Docker il pianificatore è il servizio `pianificatore` di `compose.yaml`; senza Docker vedi
[Installazione](installazione.md).

## Comandi

| Comando | Cosa fa |
|---|---|
| `manage.py importa_registro_soci FILE [opzioni]` | importa i soci dall'estratto `.xlsx`/`.csv` del registro nazionale. **Senza `--esegui` mostra solo l'anteprima.** Opzioni: `--sezione CODICE` (righe senza sezione), `--tipologia NOME` (predefinita `Ordinario`), `--crea-sezioni`, `--allinea-sezione`, `--anno-tessere ANNO`, `--quote-pagate` (quote già incassate),
`--senza-tessere`, `--non-creare-tessere`, `--senza-cessazioni`, `--utente USERNAME` (autore nel registro attività), `--dettagli` (una riga per socio) |
| `manage.py backup` / `ripristina` | backup completo e ripristino (vedi [Backup](backup.md)) |
| `manage.py inizializza` | **cancella tutti i dati** e riporta a una nuova installazione, dopo conferma e backup (vedi [Backup](backup.md#inizializzazione-azzerare-tutto)) |
| `manage.py configura_ruoli` | riallinea i permessi dei ruoli predefiniti (eseguito anche dalle migrazioni) |

Esempio, con l'estratto in `tmp/` (cartella esclusa dal versionamento: contiene dati personali):

```bash
uv run python manage.py importa_registro_soci tmp/registro_soci.xlsx --sezione 085 --dettagli
uv run python manage.py importa_registro_soci tmp/registro_soci.xlsx --sezione 085 --esegui --utente admin
```
