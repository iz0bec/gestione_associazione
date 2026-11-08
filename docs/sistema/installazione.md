<!--
******************************************************
* Progetto:    Gestione Associazione
* Autore:      Bartolomeo Santoro aka IZ0BEC
* Email:       info@iz0bec.info
* Descrizione: Installazione in produzione
* Licenza:     CC0 1.0 Universal (pubblico dominio)
* SPDX-License-Identifier: CC0-1.0
******************************************************
-->

# Installazione

Requisiti comuni: un server Linux (o un PC sempre acceso) con almeno 1 GB di RAM libera,
un nome a dominio o un indirizzo fisso nella rete locale, e preferibilmente un reverse proxy
con HTTPS (per esempio nginx o Nginx Proxy Manager).

## Con Docker

```bash
git clone <repository> gestione_associazione && cd gestione_associazione
cp .env.example .env
```

Compilare in `.env` almeno:

| Variabile | Valore |
|---|---|
| `SECRET_KEY` | stringa casuale lunga: `python3 -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `DB_PASSWORD` | password del database (casuale) |
| `ALLOWED_HOSTS` | nomi/indirizzi con cui si raggiunge l'app, es. `gestione.example.it,192.168.0.34` |
| `APP_PORT` | porta pubblicata sull'host (default 8000) |

La variabile `DATABASE_URL` è impostata da `compose.yaml` e non va messa nel `.env`.

```bash
docker compose up -d --build
docker compose exec app python manage.py createsuperuser
```

L'app è su `http://<server>:<APP_PORT>`. All'avvio il container applica le migrazioni e
allinea i ruoli. I dati stanno in due volumi: `db` (PostgreSQL) e `media` (allegati).

## Su server Linux senza Docker (consigliato)

`scripts/installa.sh` installa tutto il necessario su **Debian 12/13** o **Ubuntu 22.04/24.04** con
systemd, senza Docker:

- pacchetti di sistema: PostgreSQL, le librerie per i PDF e i caratteri;
- `uv` e Python 3.13 (scaricato da uv se il sistema ha una versione più vecchia);
- l'utente di sistema `gestione`, con il codice in `/opt/gestione-associazione` e i dati
  (`media`, `static`, `backup`) in `/var/lib/gestione-associazione`;
- il database e il ruolo PostgreSQL, di proprietà dell'utente applicativo, con password generata;
- il file `.env` con i segreti generati (`SECRET_KEY`, password del database,
  `CHIAVE_CIFRATURA`) e `ALLOWED_HOSTS` con il nome e gli IP del server;
- migrazioni, file statici e amministratore con password casuale, salvata in
  `/root/gestione-associazione-credenziali.txt`;
- i servizi `gestione-associazione` (gunicorn) e `gestione-associazione-pianificatore` (email,
  posta, registri e backup notturno).

```bash
git clone https://mygitlab.iz0bec.info/sbart64/gestione_associazione.git /root/gestione-associazione-src
cd /root/gestione-associazione-src && git checkout v0.0.1-rc.1
./scripts/installa.sh --porta 8000
```

| Opzione | |
|---|---|
| `--porta N` | porta del servizio web (predefinita 8000) |
| `--indirizzo IP` | indirizzo di ascolto (predefinito `0.0.0.0`; `127.0.0.1` dietro un reverse proxy sullo stesso server) |
| `--host NOMI` | nomi aggiuntivi per `ALLOWED_HOSTS`, es. `gestione.example.it` |
| `--db NOME` | nome del database (predefinito `gestione_associazione`) |
| `--admin`, `--email` | amministratore creato alla prima installazione |
| `-y` | nessuna domanda |

Lo script è **rieseguibile**: se trova il `.env` lo considera un aggiornamento. In quel caso non
tocca `.env`, database, file e backup, e prima di migrare crea un backup completo. Se il backup non
riesce, l'aggiornamento si ferma.

Su un server che ospita già altri servizi, scegliere una porta libera (`ss -ltn`). Il PostgreSQL già
presente viene usato così com'è: lo script aggiunge solo il proprio ruolo e il proprio database.

## Su Proxmox VE (container LXC)

`scripts/proxmox/crea-lxc.sh` si esegue **sull'host Proxmox** come root. Crea un container
**Debian non privilegiato** e vi installa l'applicazione con `installa.sh`:

```bash
# sull'host Proxmox
curl -fsSLO https://mygitlab.iz0bec.info/sbart64/gestione_associazione/-/raw/main/scripts/proxmox/crea-lxc.sh
bash crea-lxc.sh --versione v0.0.1-rc.1 --ip 192.168.0.40/24 --gw 192.168.0.1 --email segreteria@example.it
```

| Opzione | Predefinito | |
|---|---|---|
| `--id N` | primo libero | numero del container |
| `--nome` | `gestione-associazione` | hostname |
| `--storage`, `--storage-template` | `local-lvm`, `local` | dove creare il disco e scaricare il template |
| `--disco`, `--ram`, `--core` | 8 GB, 2048 MB, 2 | risorse |
| `--bridge`, `--ip`, `--gw`, `--dns` | `vmbr0`, `dhcp` | rete (`--ip 192.168.0.40/24 --gw 192.168.0.1` per un IP fisso) |
| `--debian` | 13 | versione del template |
| `--password-root`, `--chiave-ssh` | generata | accesso al container |
| `--sorgente` | repository GitLab | URL git oppure una cartella locale dell'host con il codice |
| `--versione` | `main` | tag o ramo da installare |
| `--porta` | 8000 | porta web |

Alla fine lo script stampa l'indirizzo, la password di root del container e le credenziali
dell'amministratore dell'applicazione. Il container si avvia con l'host (`onboot`).

Aggiornamento, con backup automatico prima:

```bash
bash crea-lxc.sh --aggiorna --id 120 --versione v0.0.1-rc.2
```

Per i backup conviene anche il backup del container di Proxmox (snapshot o vzdump), in aggiunta ai
backup dell'applicazione.

## Configurazione manuale dei servizi

Per installazioni particolari, i servizi creati dallo script sono:

```ini
# /etc/systemd/system/gestione-associazione.service
[Service]
User=gestione
WorkingDirectory=/opt/gestione-associazione
ExecStart=/opt/gestione-associazione/.venv/bin/gunicorn config.wsgi --bind 0.0.0.0:8000 --workers 3 --timeout 120
Restart=on-failure
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true

# /etc/systemd/system/gestione-associazione-pianificatore.service
[Service]
User=gestione
WorkingDirectory=/opt/gestione-associazione
ExecStart=/opt/gestione-associazione/.venv/bin/python manage.py pianificatore
Restart=on-failure
RestartSec=30
```

## HTTPS e reverse proxy

In produzione l'app va servita **solo in HTTPS**. Dietro un reverse proxy impostare nel `.env`:

```
HTTPS=true
PROXY_COUNT=1
CSRF_TRUSTED_ORIGINS=https://gestione.example.it
ALLOWED_HOSTS=gestione.example.it
```

Con `HTTPS=true` i cookie di sessione viaggiano solo su connessioni cifrate. Le passkey
funzionano solo in HTTPS (o su `localhost`).

## Primo accesso

1. Accedere con l'amministratore creato (credenziali in `/root/gestione-associazione-credenziali.txt`),
   cambiare subito la password e cancellare il file.
2. Parte la [configurazione guidata](../operativo/configurazione-iniziale.md): dati dell'ente, logo e
   colori, sezioni, tesseramento, tesoreria.
3. Attivare la verifica in due passaggi (menu utente → *Verifica in due passaggi*).
4. Creare gli utenti e assegnare i ruoli da *Sistema → Utenti e ruoli*; in *Ruoli* scegliere
   per quali ruoli il secondo fattore è obbligatorio (vedi [Utenti e ruoli](../operativo/utenti.md)).

## Aggiornamento

Docker:

```bash
git pull && docker compose up -d --build
```

Senza Docker, dalla copia del repository usata per l'installazione:

```bash
cd /root/gestione-associazione-src && git fetch --tags && git checkout v0.0.1-rc.2
./scripts/installa.sh -y      # backup automatico, migrazioni, riavvio dei servizi
```

Fare sempre un [backup](backup.md) prima di aggiornare.

## Controllo di funzionamento

`GET /salute/` risponde `ok` (HTTP 200) se applicazione e database funzionano:
utilizzabile da sistemi di monitoraggio.
