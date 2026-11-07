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

## Con Docker (consigliato)

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

## Su server Linux senza Docker

Uno script automatico (come quello del Protocollo ANCR) è previsto per la 0.0.1 RC.
Fino ad allora, i passi manuali su Debian/Ubuntu sono:

```bash
# 1. pacchetti
apt install -y postgresql libpango-1.0-0 libpangoft2-1.0-0 git curl
curl -LsSf https://astral.sh/uv/install.sh | sh        # uv (gestione Python)

# 2. utente e codice
useradd --system --home-dir /opt/gestione-associazione --shell /usr/sbin/nologin gestione
git clone <repository> /opt/gestione-associazione

# 3. database (proprietario = utente applicativo: necessario da PostgreSQL 15)
runuser -u postgres -- psql -c "create role gestione login password 'PASSWORD-CASUALE'"
runuser -u postgres -- psql -c "create database gestione_associazione owner gestione"

# 4. configurazione: .env con SECRET_KEY, DATABASE_URL=postgres://gestione:PASSWORD@127.0.0.1:5432/gestione_associazione,
#    ALLOWED_HOSTS, MEDIA_ROOT=/var/lib/gestione-associazione/media
cd /opt/gestione-associazione && cp .env.example .env && chmod 600 .env

# 5. dipendenze, migrazioni, file statici
uv sync --frozen --no-dev
uv run python manage.py migrate
uv run python manage.py collectstatic --noinput
chown -R gestione:gestione /opt/gestione-associazione /var/lib/gestione-associazione
```

Servizio systemd `/etc/systemd/system/gestione-associazione.service`:

```ini
[Unit]
Description=Gestione Associazione
After=network-online.target postgresql.service
Wants=postgresql.service

[Service]
User=gestione
Group=gestione
WorkingDirectory=/opt/gestione-associazione
ExecStart=/opt/gestione-associazione/.venv/bin/gunicorn config.wsgi --bind 127.0.0.1:8000 --workers 3
Restart=on-failure
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload && systemctl enable --now gestione-associazione
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

1. Accedere con il superutente creato.
2. **Sistema → Organizzazione**: inserire i dati dell'ente.
3. Attivare la verifica in due passaggi (menu utente → *Verifica in due passaggi*).
4. Creare gli utenti e assegnare i ruoli da *Amministrazione tecnica → Utenti*
   (la gestione utenti nell'interfaccia principale è prevista per la 0.0.1 RC).

## Aggiornamento

Docker:

```bash
git pull && docker compose up -d --build
```

Senza Docker:

```bash
cd /opt/gestione-associazione && git pull
uv sync --frozen --no-dev && uv run python manage.py migrate && uv run python manage.py collectstatic --noinput
systemctl restart gestione-associazione
```

Fare sempre un [backup](backup.md) prima di aggiornare.

## Controllo di funzionamento

`GET /salute/` risponde `ok` (HTTP 200) se applicazione e database funzionano:
utilizzabile da sistemi di monitoraggio.
