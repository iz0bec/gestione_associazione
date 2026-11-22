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
allinea i ruoli. I dati stanno in tre volumi: `db` (PostgreSQL), `media` (allegati) e
`backup` (backup dell'applicazione, anche quello automatico notturno del pianificatore).

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
| `--tls-step URL` `--tls-step-token T` | **HTTPS** con un certificato della propria step-ca e **rinnovo automatico** (token monouso, nessuna password sul server); con `--tls-ca-impronta` o `--tls-ca` |
| `--tls-acme URL` | **HTTPS** da una CA ACME con certbot e rinnovo automatico (porta 80 libera; nomi in `--tls-nomi`) |
| `--tls-cert FILE` `--tls-key FILE` | **HTTPS** con un certificato fatto altrove (es. con MyCert) |
| `--tls-autofirmato` | HTTPS con un certificato autofirmato per nome e IP del server (825 giorni); `--tls-nomi` aggiunge nomi o IP |
| `--senza-tls` | torna all'HTTP (solo dietro un proxy HTTPS) |
| `-y` | nessuna domanda |

**HTTPS consigliato sempre, anche in rete interna** (vedi [HTTPS anche in rete interna](https-rete-interna.md)).
Con le opzioni `--tls-*` i file vanno in `/etc/gestione-associazione/tls/` e il servizio risponde solo in
HTTPS; gli aggiornamenti lo mantengono. Per rinnovare basta sovrascrivere `key.pem` e poi `cert.pem`:
il servizio si riavvia da solo (`gestione-associazione-tls.path`).

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
| `--tls-autofirmato` | - | HTTPS con certificato autofirmato (consigliato; poi sostituibile con uno della propria CA) |

Per una **CA interna** sullo stesso Proxmox c'è `scripts/proxmox/crea-ca.sh` (step-ca in un container
dedicato): vedi [HTTPS anche in rete interna](https-rete-interna.md).

Alla fine lo script stampa l'indirizzo, la password di root del container e le credenziali
dell'amministratore dell'applicazione. Il container si avvia con l'host (`onboot`).
Il template Debian scaricato è quello dell'architettura dell'host (amd64 o arm64).

All'accesso (SSH o console) il container mostra un **messaggio di benvenuto** al posto di quello di
Debian: versione, indirizzo dell'applicazione, stato dei servizi web e pianificatore, ultimo backup e
comandi utili, più un avviso finché esiste il file con la password iniziale dell'amministratore.
È il file `/etc/profile.d/00-gestione-associazione.sh` (sorgente `scripts/proxmox/motd.sh`), riscritto
a ogni `--aggiorna`; non compare con `pct enter`, che non apre una shell di login.

Aggiornamento, con backup automatico prima:

```bash
bash crea-lxc.sh --aggiorna --id 120 --versione v1.0.37
```

Per i backup conviene anche il backup del container di Proxmox (snapshot o vzdump), in aggiunta ai
backup dell'applicazione.

## Più sezioni sullo stesso host

Una federazione può ospitare su un solo server le sezioni che non hanno un'installazione
propria: ogni sezione ha il suo servizio, la sua porta, le sue cartelle e il suo database,
tutti sullo **stesso PostgreSQL**. Sono installazioni del tutto separate: altri utenti, altri dati,
altri backup, e si collegano fra loro e con la federazione con le API come qualsiasi altra.

`installa.sh --istanza NOME` installa una di queste istanze:

| | Istanza `potenza` |
|---|---|
| Servizi | `gestione-potenza`, `gestione-potenza-pianificatore` |
| Codice e configurazione | `/opt/sezione-potenza` (`.env`) |
| Dati e backup | `/var/lib/sezione-potenza` |
| Utente di sistema e del database | `sezione_potenza` |
| Database | `sezione_potenza` |
| Certificato HTTPS | `/etc/sezione-potenza/tls` |

`scripts/proxmox/sezioni.sh` le gestisce insieme. L'elenco è in `/etc/gestione-sezioni.conf`,
una riga per istanza con il nome e la porta:

```bash
cd /root/gestione-associazione-src
# nuova sezione (2 worker; le opzioni HTTPS sono quelle di installa.sh)
bash scripts/proxmox/sezioni.sh aggiungi potenza 8083 --tls-autofirmato
bash scripts/proxmox/sezioni.sh stato          # servizi, versioni e ultimo backup
bash scripts/proxmox/sezioni.sh motd           # messaggio di benvenuto con tutte le sezioni
# aggiornamento di tutte (o solo di quelle indicate) alla versione scaricata
git fetch --tags && git checkout vX.Y.Z && bash scripts/proxmox/sezioni.sh aggiorna
```

Se le sezioni sono pubblicate da un reverse proxy HTTPS (es. Nginx Proxy Manager) con un nome
per sezione, basta indicare una volta lo schema del nome (`{sezione}` diventa il nome
dell'istanza) e l'indirizzo del proxy:

```bash
bash scripts/proxmox/sezioni.sh imposta DOMINIO 'sez-{sezione}.associazione.it'
bash scripts/proxmox/sezioni.sh imposta PROXY 192.168.1.10
bash scripts/proxmox/sezioni.sh aggiorna      # corregge anche il .env delle sezioni esistenti
```

`aggiungi` e `aggiorna` passano a `installa.sh` le opzioni `--dominio` e `--proxy`, che nel `.env`
aggiungono il nome ad `ALLOWED_HOSTS` e `https://nome` a `CSRF_TRUSTED_ORIGINS`, impostano
`URL_PUBBLICO`, `HTTPS=true`, `PROXY_COUNT=1` e aggiungono il proxy a `PROXY_FIDATI`. Le stesse
opzioni valgono per una installazione singola (`installa.sh --dominio … --proxy …`). Nel proxy,
ogni nome punta alla porta della sua sezione (in `https` se l'istanza ha il certificato).

Prima di ogni aggiornamento si fa un backup per istanza; se una non riesce, le altre proseguono e
in fondo compare l'elenco di quelle non aggiornate. Con 2 worker, ogni sezione occupa circa
400 MB di RAM fra servizio web e pianificatore: 8 GB bastano per una decina di sezioni.

## Configurazione manuale dei servizi

Per installazioni particolari, i servizi creati dallo script sono:

```ini
# /etc/systemd/system/gestione-associazione.service
[Service]
User=gestione
WorkingDirectory=/opt/gestione-associazione
ExecStart=/opt/gestione-associazione/.venv/bin/gunicorn config.wsgi --bind 0.0.0.0:8000 --workers 3 --timeout 300
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
PROXY_FIDATI=192.168.0.26
CSRF_TRUSTED_ORIGINS=https://gestione.example.it
ALLOWED_HOSTS=gestione.example.it
```

- `HTTPS=true`: i cookie di sessione viaggiano solo su connessioni cifrate e gli indirizzi
  generati (es. il collegamento al calendario) sono in `https://`. Le passkey funzionano solo in
  HTTPS (o su `localhost`). **Da quel momento non si entra più dall'indirizzo in chiaro**
  (`http://server:porta`): anche dalla rete interna si usa il nome in HTTPS.

> **Usare HTTPS anche in rete interna.** In LAN il traffico in chiaro (password, cookie, dati dei
> soci) è leggibile da qualunque dispositivo collegato. La guida
> [HTTPS anche in rete interna](https-rete-interna.md) spiega passo passo come creare una CA interna
> con step-ca (consigliata) o un certificato autofirmato, e come configurare proxy e `.env`.

- `PROXY_COUNT`: quanti proxy ci sono in catena (di solito 1, es. Nginx Proxy Manager). Serve a
  ricavare l'**IP reale** del visitatore da `X-Forwarded-For`, usato dal blocco dei tentativi di
  accesso e dal registro attività: senza, tutte le richieste sembrano arrivare dal proxy e chi
  sbaglia 5 volte la password di un utente lo blocca per tutti.
- `PROXY_FIDATI`: IP o reti (separati da virgola) da cui accettare `X-Forwarded-For`; le richieste
  che arrivano direttamente da altri indirizzi usano il loro IP e non possono spacciarsi per altri.
  Per conoscere l'IP del proxy: nel log del servizio (`journalctl -u gestione-associazione`) è il
  primo campo delle richieste che arrivano dal nome pubblico.

## Primo accesso

1. Accedere con l'amministratore creato (credenziali in `/root/gestione-associazione-credenziali.txt`),
   cambiare subito la password e cancellare il file.
2. Parte la [configurazione guidata](../operativo/configurazione-iniziale.md): dati dell'ente, logo e
   colori, sezioni, tesseramento, tesoreria.
3. Attivare la verifica in due passaggi (menu utente → *Verifica in due passaggi*).
4. Creare gli utenti e assegnare i ruoli da *Sistema → Utenti e ruoli*; in *Ruoli* scegliere
   per quali ruoli il secondo fattore è obbligatorio (vedi [Utenti e ruoli](../operativo/utenti.md)).

## Utenti da riga di comando

Per l'amministratore del server, senza aprire l'interfaccia (come utente del servizio):

```bash
cd /opt/gestione-associazione
sudo -u gestione .venv/bin/python manage.py utenti            # elenco (--tutti: anche i non attivi)
sudo -u gestione .venv/bin/python manage.py utenti --reimposta mario.rossi
```

L'elenco mostra nome utente, persona, ruoli, se è attivo, il secondo fattore, l'ultimo accesso,
l'email (vera o segnaposto) e la **categoria** della password predefinita (✓ se è disponibile).
`--reimposta NOME` riporta la password a quella **predefinita**: per gli amministratori la password
**iniziale dell'installazione**, per gli altri quella della **carica più alta** in corso negli organi
(presidente, vicepresidente, segretario, …) o, senza cariche, del ruolo. Se non c'è una predefinita
ne genera una e la mostra una volta; `--password` ne usa una indicata, `--obbligo-cambio` obbliga a
cambiarla al primo accesso. Come **ultimo passo** chiede se inviare subito l'**email con le
credenziali** (passaggi per cambiarla e dove trovare il manuale): sì → parte subito; no → resta in
bozza in *Comunicazioni*. `--invia` risponde sì senza domanda, `--senza-email` non la prepara. A chi
non ha l'email la notifica va alla casella dell'ente «per conto». Nel registro attività finisce solo
l'operazione, mai la password.

Le password predefinite sono nel file indicato da `PASSWORD_PREDEFINITE` nel `.env`
(`/etc/<installazione>/password-predefinite.json`, leggibile solo da root e dal gestionale). Lo crea
l'installatore con la password iniziale dell'admin (per le installazioni esistenti la riprende da
`/root/<installazione>-credenziali.txt`); le altre si aggiungono a mano, come root:

```json
{"admin": "…", "presidente": "…", "vicepresidente": "…", "segretario": "…", "consigliere": "…"}
```

Categorie: `admin`, `presidente`, `vicepresidente`, `segretario`, `tesoriere`, `consigliere`,
`supplente`, `controllo` (organo di controllo), `altro`. Con più sezioni sullo stesso host:
`sezioni.sh utenti` elenca tutte; `sezioni.sh utenti ruoti --reimposta NOME` agisce su una.

## Aggiornamento

Docker:

```bash
git pull && docker compose up -d --build
```

Senza Docker, dalla copia del repository usata per l'installazione:

```bash
cd /root/gestione-associazione-src && git fetch --tags && git checkout v1.0.37
./scripts/installa.sh -y      # backup automatico, migrazioni, riavvio dei servizi
```

Fare sempre un [backup](backup.md) prima di aggiornare.

## Controllo di funzionamento

`GET /salute/` risponde `ok` (HTTP 200) se applicazione e database funzionano:
utilizzabile da sistemi di monitoraggio.
