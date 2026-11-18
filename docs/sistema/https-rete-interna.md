<!--
******************************************************
* Progetto:    Gestione Associazione
* Autore:      Bartolomeo Santoro aka IZ0BEC
* Email:       info@iz0bec.info
* Descrizione: Guida passo passo all'HTTPS in rete interna: CA con step-ca o certificato autofirmato
* Licenza:     CC0 1.0 Universal (pubblico dominio)
* SPDX-License-Identifier: CC0-1.0
******************************************************
-->

# HTTPS anche in rete interna

> **Raccomandazione: usare sempre HTTPS, anche in LAN.** Una rete «interna» non è una rete fidata:
> ci passano PC personali, telefoni, ospiti del Wi-Fi, dispositivi non aggiornati. In chiaro,
> chiunque sia sulla stessa rete può leggere password, cookie di sessione e dati dei soci.
> Con `HTTPS=true` il gestionale **non accetta più l'accesso in chiaro** (cookie solo su connessioni
> cifrate): per entrare dalla LAN serve un indirizzo interno in HTTPS.

Questa guida mostra come ottenerlo senza servizi esterni, in due modi:

| | **A. CA interna con step-ca** (consigliata) | **B. Certificato autofirmato** |
|---|---|---|
| Cosa si ottiene | una propria autorità di certificazione che rilascia certificati per tutti i servizi interni | un certificato per un solo servizio |
| Browser | nessun avviso, dopo aver installato **una volta** il certificato radice sui dispositivi | avviso finché il certificato non è installato su ogni dispositivo |
| Rinnovo | automatico (`installa.sh --tls-step` o `--tls-acme`) | a mano, alla scadenza |
| Collegamenti fra installazioni ([ADR-030](../architettura/decisioni.md)) | modalità `ca_interna` | modalità `impronta` |
| Adatta a | più servizi o più installazioni (es. un Proxmox con vari container) | prove, una sola installazione, collegamenti macchina-macchina |

Se l'associazione possiede un **dominio** (es. `esempio.it`), c'è anche una terza via: certificati
Let's Encrypt per nomi interni (`gestionale.int.esempio.it`) con la verifica via DNS, che Nginx Proxy
Manager supporta per molti fornitori DNS. Nessun certificato da installare sui dispositivi; serve
però che il fornitore del dominio offra un'API DNS supportata.

Gli esempi usano nomi e indirizzi di fantasia: CA su `ca.associazione.lan` (192.168.0.40), gestionale
su `gestionale.associazione.lan` (192.168.0.34). Sostituirli con i propri.

## 0. Prerequisito: un nome interno

HTTPS lega il certificato a un **nome**. Serve quindi che i dispositivi della rete risolvano il nome
interno del gestionale:

- nel DNS locale (router, Pi-hole, AdGuard Home, dnsmasq): una voce `gestionale.associazione.lan →
  192.168.0.34`;
- in mancanza, nel file `hosts` di ogni PC (soluzione di ripiego).

Evitare il suffisso `.local` (è riservato a mDNS/Bonjour e dà problemi). Vanno bene un sottodominio di
un dominio proprio (preferibile) oppure `.lan` o `home.arpa`.

## A. CA interna con step-ca

[step-ca](https://smallstep.com/docs/step-ca/) è un'autorità di certificazione open source (licenza
Apache 2.0) di Smallstep. Va su una macchina sempre accesa: un piccolo container LXC basta
(1 CPU, 256 MB di RAM, 2 GB di disco).

> **Su Proxmox in un solo comando.** `scripts/proxmox/crea-ca.sh` (sull'host Proxmox, come root) fa
> tutti i passi da A.1 a A.5: container Debian, step-ca dal repository Smallstep, inizializzazione,
> durata dei certificati, nomi ammessi limitati al dominio interno, provisioner ACME, servizio systemd
> e il comando `token-certificato` per l'installatore del gestionale.
>
> ```bash
> bash crea-ca.sh --dominio associazione.lan --ip 192.168.0.40/24 --gw 192.168.0.1
> ```
>
> Alla fine stampa l'indirizzo della CA, l'**impronta della radice** e il comando da usare sul server
> del gestionale. Opzioni: `--reti` (reti di cui firmare gli IP, predefinita quella di `--ip`),
> `--nome-ca`, `--nomi-ca`, `--durata`, `--durata-max`, più quelle del container (`--id`, `--storage`,
> …, come `crea-lxc.sh`). Restano da fare a mano il nome nel DNS locale (A.0) e la radice sui
> dispositivi (A.6). I passi seguenti spiegano cosa fa, o come farlo su una macchina qualsiasi.

### A.1 Container e installazione

Sul Proxmox creare un container Debian 13 (es. `ca`, IP fisso 192.168.0.40), entrarvi e installare i
pacchetti dal repository ufficiale di Smallstep (controllare la [pagina di installazione](https://smallstep.com/docs/step-ca/installation/)
per eventuali aggiornamenti delle istruzioni):

```bash
apt-get update && apt-get install -y curl gpg ca-certificates
curl -fsSL https://packages.smallstep.com/keys/apt/repo-signing-key.gpg \
  -o /etc/apt/trusted.gpg.d/smallstep.asc
echo 'deb [signed-by=/etc/apt/trusted.gpg.d/smallstep.asc] https://packages.smallstep.com/stable/debian debs main' \
  > /etc/apt/sources.list.d/smallstep.list
apt-get update && apt-get install -y step-cli step-ca
```

### A.2 Inizializzazione

La CA gira con un utente dedicato e tiene i dati in `/etc/step-ca`:

```bash
useradd --system --home /etc/step-ca --shell /bin/false step
export STEPPATH=/etc/step-ca
mkdir -p $STEPPATH && chmod 700 $STEPPATH

# password della CA: generata, salvata in un file leggibile solo dall'utente step
openssl rand -base64 32 > $STEPPATH/password.txt

step ca init \
  --deployment-type standalone \
  --name "Associazione - CA interna" \
  --dns ca.associazione.lan --dns 192.168.0.40 \
  --address ":9000" \
  --provisioner admin \
  --password-file $STEPPATH/password.txt \
  --provisioner-password-file $STEPPATH/password.txt

chown -R step:step $STEPPATH
```

Il comando crea il **certificato radice** (`certs/root_ca.crt`), un certificato intermedio e la
configurazione (`config/ca.json`). Annotare l'**impronta del certificato radice**, che serve per
verificarlo sugli altri dispositivi:

```bash
step certificate fingerprint /etc/step-ca/certs/root_ca.crt
```

> **Custodia.** La cartella `/etc/step-ca` contiene le chiavi della CA: chi le possiede può emettere
> certificati validi per tutta la rete. Includerla nei backup (cifrati) del container e non copiarla
> altrove. La password in `password.txt` serve all'avvio automatico; per una sicurezza maggiore si
> può conservare la chiave radice fuori linea (vedi la documentazione di Smallstep).

### A.3 Durata dei certificati e nomi ammessi

Di base step-ca rilascia certificati di 24 ore, pensati per il rinnovo automatico. Per poterli anche
caricare a mano (es. in Nginx Proxy Manager) conviene alzare la durata massima e limitare la CA ai soli
nomi interni. In `/etc/step-ca/config/ca.json`, dentro `"authority"`, aggiungere:

```json
"claims": {
  "minTLSCertDuration": "5m",
  "maxTLSCertDuration": "2160h",
  "defaultTLSCertDuration": "720h"
},
"policy": {
  "x509": {
    "allow": {
      "dns": ["associazione.lan", "*.associazione.lan"],
      "ip": ["192.168.0.0/24"]
    }
  }
}
```

(2160 ore = 90 giorni; 720 ore = 30 giorni.) Con `policy` la CA si rifiuta di firmare nomi esterni:
anche se qualcuno ne ottenesse l'uso, non potrebbe falsificare siti Internet.

### A.4 Servizio systemd

```bash
cat > /etc/systemd/system/step-ca.service <<'EOF'
[Unit]
Description=step-ca - autorità di certificazione interna
After=network-online.target
Wants=network-online.target

[Service]
User=step
Group=step
Environment=STEPPATH=/etc/step-ca
ExecStart=/usr/bin/step-ca /etc/step-ca/config/ca.json --password-file /etc/step-ca/password.txt
Restart=on-failure
NoNewPrivileges=true
ProtectSystem=full
ReadWritePaths=/etc/step-ca/db
ProtectHome=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload && systemctl enable --now step-ca
systemctl status step-ca --no-pager
```

(Il percorso dell'eseguibile può essere `/usr/bin/step-ca` o `/usr/local/bin/step-ca`: verificarlo
con `command -v step-ca`.)

### A.5 Rilascio automatico (ACME)

Aggiungere un provisioner ACME, lo stesso protocollo di Let's Encrypt:

```bash
sudo -u step STEPPATH=/etc/step-ca step ca provisioner add acme --type ACME
systemctl restart step-ca
```

L'indirizzo ACME della CA è `https://ca.associazione.lan:9000/acme/acme/directory`.

### A.6 Installare il certificato radice sui dispositivi

Si fa **una volta per dispositivo**. Copiare `root_ca.crt` (è pubblico: si può distribuire liberamente,
per esempio su una chiavetta o da una cartella condivisa) e verificare che l'impronta coincida con
quella annotata al punto A.2.

| Sistema | Procedura |
|---|---|
| Debian/Ubuntu | `cp root_ca.crt /usr/local/share/ca-certificates/associazione-root.crt && update-ca-certificates` |
| Windows | da amministratore: `certutil -addstore -f Root root_ca.crt` (oppure doppio clic → *Installa certificato* → *Computer locale* → *Autorità di certificazione radice attendibili*) |
| macOS | `sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain root_ca.crt` |
| Firefox | usa un archivio proprio: *Impostazioni → Privacy e sicurezza → Certificati → Mostra certificati → Autorità → Importa* (su Windows e macOS, in alternativa, `security.enterprise_roots.enabled = true` in `about:config`) |
| Android | *Impostazioni → Sicurezza → Crittografia e credenziali → Installa un certificato → Certificato CA* |
| iPhone/iPad | aprire il file per installare il profilo, poi *Impostazioni → Generali → Info → Impostazioni certificati attendibili* e attivarlo |

Su un'altra macchina Linux con `step` installato basta anche:

```bash
step ca bootstrap --ca-url https://ca.associazione.lan:9000 --fingerprint <impronta> --install
```

### A.7 Certificato per il gestionale

**Con Nginx Proxy Manager** (che non supporta CA ACME diverse da Let's Encrypt): rilasciare il
certificato a mano e caricarlo.

```bash
# su una macchina con step e la radice installata (es. il container della CA)
step ca certificate gestionale.associazione.lan gestionale.crt gestionale.key \
  --san gestionale.associazione.lan --san 192.168.0.34 \
  --not-after 2160h --provisioner admin
```

In NPM: *SSL Certificates → Add SSL Certificate → Custom*, caricare `gestionale.key` (chiave) e
`gestionale.crt` (contiene già il certificato e l'intermedio). Poi nel *Proxy Host*
`gestionale.associazione.lan` scegliere questo certificato e attivare *Force SSL*.
Annotare la **scadenza** (90 giorni) e ripetere il rilascio qualche settimana prima.

**Con nginx e certbot** (rinnovo automatico): con la radice installata nel sistema (punto A.6),

```bash
certbot --nginx -d gestionale.associazione.lan \
  --server https://ca.associazione.lan:9000/acme/acme/directory
```

certbot salva l'indirizzo della CA e rinnova da solo con il suo timer, come per Let's Encrypt.

### A.8 Gestire la vita dei certificati con MyCert

[MyCert](https://mygitlab.iz0bec.info/sbart64/gestione-certificati) è uno strumento separato, dello
stesso autore, che gestisce i certificati emessi da una step-ca: creazione con nomi alternativi,
elenco con le scadenze, rinnovo, rigenerazione, avvisi. Ha un'interfaccia da terminale
(`certificati.sh`) e un'app desktop per macOS, Linux e Windows, e usa la CLI `step` già collegata alla
CA (`step ca bootstrap`).

```bash
# nuovo certificato per il gestionale, con nome breve e IP
certificati.sh -n gestionale.associazione.lan gestionale 192.168.0.34
# elenco con le scadenze, rinnovo di uno, controllo per cron (avviso sul desktop)
certificati.sh -l
certificati.sh -R gestionale.associazione.lan
certificati.sh -s
```

I file finiscono in `<cartella certificati>/<nome>/cert.pem` e `key.pem`: si caricano in Nginx Proxy
Manager (punto A.7) oppure si passano all'installatore (sotto, *HTTPS servito direttamente*). Dopo un
rinnovo basta ricopiarli sul server.

## B. Certificato autofirmato

Un unico comando, con OpenSSL (già presente su Debian e macOS). Il certificato deve riportare il nome
**e** l'indirizzo IP con cui il servizio sarà raggiunto:

```bash
openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:P-256 -sha256 -days 825 -nodes \
  -keyout gestionale.key -out gestionale.crt \
  -subj "/CN=gestionale.associazione.lan" \
  -addext "subjectAltName=DNS:gestionale.associazione.lan,IP:192.168.0.34" \
  -addext "basicConstraints=critical,CA:FALSE" \
  -addext "extendedKeyUsage=serverAuth"
chmod 600 gestionale.key
```

- 825 giorni è la durata massima accettata dai dispositivi Apple; alla scadenza si rigenera.
- Si carica in Nginx Proxy Manager come al punto A.7 (*Custom*).
- I browser mostrano un avviso finché il certificato non viene installato come attendibile su ogni
  dispositivo (stesse procedure del punto A.6). Per l'uso quotidiano da browser è quindi preferibile
  la CA interna; l'autofirmato è comodo soprattutto per i **collegamenti fra installazioni**, dove
  si verifica per impronta.

**Impronta della chiave pubblica (SPKI)**, da comunicare all'altra installazione per la modalità
`impronta` dell'API. Resta la stessa se si rinnova il certificato riusando la chiave:

```bash
openssl x509 -in gestionale.crt -pubkey -noout \
  | openssl pkey -pubin -outform der \
  | openssl dgst -sha256 -binary | openssl enc -base64
```

Per rinnovare mantenendo la stessa chiave (e quindi la stessa impronta) sostituire nel comando di
creazione `-newkey ec -pkeyopt ec_paramgen_curve:P-256 -nodes -keyout gestionale.key` con
`-key gestionale.key`.

## HTTPS servito direttamente dal gestionale

Senza un proxy (o per cifrare anche il tratto proxy → gestionale) l'installatore configura Gunicorn
in HTTPS. Quattro modi, uno a scelta:

| Modo | Rinnovo | Quando |
|---|---|---|
| `--tls-step URL --tls-step-token T` | **automatico** (`step ca renew`) | CA step-ca: funziona anche con un proxy sulla stessa macchina |
| `--tls-acme URL` | **automatico** (certbot) | CA con ACME (step-ca, Let's Encrypt…), porta 80 libera |
| `--tls-cert F --tls-key F` | a mano (si ricopiano i file) | certificato fatto altrove (MyCert, OpenSSL…) |
| `--tls-autofirmato` | a mano (si riesegue) | senza CA; verifica per impronta |

**step-ca con token monouso (consigliato).** Chi amministra la CA crea un token, valido pochi minuti e
usabile una volta, con i nomi del certificato; sul server lo si passa all'installatore insieme
all'impronta della radice:

```bash
# sulla CA creata con crea-ca.sh
token-certificato gestionale.associazione.lan 192.168.0.34
# oppure da qualsiasi macchina con step collegata alla CA (es. quella dove si usa MyCert)
step ca token gestionale.associazione.lan --san gestionale.associazione.lan --san 192.168.0.34

# sul server del gestionale, entro pochi minuti
./scripts/installa.sh -y --tls-step https://ca.associazione.lan \
  --tls-ca-impronta <impronta della radice> --tls-step-token <token>
```

L'installatore aggiunge step-cli (repository Smallstep), scarica la radice dalla CA e la accetta solo
se l'impronta coincide (in alternativa `--tls-ca root_ca.crt`), la installa nell'archivio del sistema,
ottiene il certificato e attiva `gestione-associazione-tls-rinnovo.timer`: due volte al giorno
controlla il certificato e, passati i due terzi della validità, lo rinnova con `step ca renew`, che si
autentica **con il certificato in corso**. Sul server non resta nessuna password né il token. Se il
server resta spento oltre la scadenza (e la CA non ammette il rinnovo dei certificati scaduti) basta un
nuovo token.

**ACME con certbot.** La CA verifica i nomi collegandosi a **questo server sulla porta 80**: la porta
deve essere libera (con Nginx Proxy Manager o un altro proxy sulla stessa macchina usare `--tls-step`)
e i nomi devono essere risolti dalla CA. Gli indirizzi IP non sono ammessi.

```bash
./scripts/installa.sh -y --tls-acme https://ca.associazione.lan/acme/acme/directory \
  --tls-ca-impronta <impronta> --tls-nomi gestionale.associazione.lan
```

Il rinnovo lo fa `certbot.timer` del sistema; un hook copia il certificato nuovo al suo posto.

**Da file o autofirmato:**

```bash
# certificato della propria CA (es. MyCert): file PEM con la catena e chiave senza password
./scripts/installa.sh -y --tls-cert gestionale.crt --tls-key gestionale.key
# oppure autofirmato, per nome e IP del server (più eventuali altri nomi)
./scripts/installa.sh -y --tls-autofirmato --tls-nomi gestionale.associazione.lan
```

- I file vanno in `/etc/gestione-associazione/tls/` (chiave leggibile solo dal servizio); da quel
  momento la porta del gestionale risponde **solo in HTTPS**. Gli aggiornamenti mantengono la scelta;
  scegliendo un modo nuovo, i rinnovi del precedente si spengono.
- L'installatore controlla che la chiave corrisponda al certificato e che non sia scaduto; alla fine
  stampa modo, emittente, scadenza e **impronta SPKI** (per i collegamenti fra installazioni).
- **Rinnovo a mano** (da file o autofirmato): sovrascrivere prima `key.pem` e poi `cert.pem` (es. con
  `scp` da MyCert): il servizio si riavvia da solo (`gestione-associazione-tls.path`). L'autofirmato si
  rinnova rieseguendo `--tls-autofirmato`, che riusa la chiave: l'impronta non cambia.
- In una nuova installazione il `.env` nasce con `HTTPS=true`; in un'installazione esistente
  l'installatore ricorda di impostarlo.
- Se davanti c'è comunque un proxy (es. NPM), nel *Proxy Host* scegliere lo schema `https` verso il
  gestionale.
- `--senza-tls` torna all'HTTP (i file restano come `*.disattivato`).

## Configurare il gestionale

Con un proxy davanti, il gestionale può restare in HTTP verso il proxy e il proxy espone l'HTTPS. Nel
`.env` indicare **tutti** i nomi con cui si raggiunge (pubblico e interno):

```
HTTPS=true
ALLOWED_HOSTS=gestione.example.it,gestionale.associazione.lan
CSRF_TRUSTED_ORIGINS=https://gestione.example.it,https://gestionale.associazione.lan
PROXY_COUNT=1
PROXY_FIDATI=192.168.0.26
```

Se il proxy interno è su un'altra macchina rispetto a quello pubblico, aggiungere anche il suo IP a
`PROXY_FIDATI`. Poi `systemctl restart gestione-associazione`. Per ridurre la superficie esposta, con il
proxy sulla stessa macchina conviene installare il gestionale con `--indirizzo 127.0.0.1`
([Installazione](installazione.md)), così l'HTTP in chiaro non è raggiungibile dalla rete; altrimenti
attivare l'HTTPS anche sul gestionale (sezione precedente).

## Verificare

```bash
# il certificato presentato, la catena e la scadenza
openssl s_client -connect gestionale.associazione.lan:443 -servername gestionale.associazione.lan </dev/null \
  | openssl x509 -noout -subject -issuer -enddate

# la verifica completa, come la farà un client
curl --cacert root_ca.crt -I https://gestionale.associazione.lan/salute/
```

Dal browser: nessun avviso e il lucchetto con l'emittente «Associazione - CA interna».

## Collegamenti fra installazioni (API, ADR-030)

Quando sarà disponibile l'API di interoperabilità, ogni indirizzo interno di una controparte si
configura con una modalità di verifica:

- **`ca_interna`**: incollare il contenuto di `root_ca.crt` della CA dell'altra installazione (o della
  propria, se condivisa sullo stesso Proxmox);
- **`impronta`**: l'impronta SPKI calcolata come sopra, scambiata durante l'abbinamento;
- **`pubblica`**: per i certificati Let's Encrypt.

L'HTTP in chiaro fra installazioni resta possibile solo come eccezione esplicita, con un avviso fisso
nel cruscotto: **non è consigliato**.

## Scadenze e manutenzione

- Segnare nel calendario del gestionale (*Calendario → Nuova scadenza*) la scadenza di ogni
  certificato caricato a mano, con un preavviso di qualche settimana.
- La radice di step-ca dura 10 anni, l'intermedio pure: annotare anche queste scadenze.
- Se la CA viene compromessa (chiavi copiate), crearne una nuova, reinstallare la radice sui
  dispositivi e rimuovere la vecchia.
