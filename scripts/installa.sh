#!/usr/bin/env bash
# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Installazione e aggiornamento su Debian/Ubuntu con systemd, senza Docker:
# *              pacchetti, PostgreSQL, utente di sistema, ambiente Python (uv), .env con
# *              segreti generati, migrazioni, servizi applicazione e pianificatore.
# *              Rieseguibile: negli aggiornamenti non tocca .env, database, file e backup.
# *              HTTPS servito direttamente da Gunicorn con un certificato dato (es. da step-ca)
# *              o autofirmato; riavvio automatico quando il certificato viene rinnovato.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
set -euo pipefail
# uv va in /usr/local/bin, che manca dal PATH minimo di «pct exec» e di alcuni sudo.
export PATH="/usr/local/bin:${PATH}"

NOME="gestione-associazione"
DIR_APP="/opt/${NOME}"
DIR_DATI="/var/lib/${NOME}"
UTENTE="gestione"
DB_NOME="gestione_associazione"
PORTA=""      # vuoti: in un aggiornamento restano quelli del servizio installato
INDIRIZZO=""
HOST_EXTRA=""
ADMIN="admin"
ADMIN_EMAIL=""
SORGENTE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SI=0
DIR_TLS="/etc/${NOME}/tls"
TLS_CERT=""
TLS_KEY=""
TLS_AUTOFIRMATO=0
TLS_NOMI=""
TLS_DISATTIVA=0
TLS_ACME=""
TLS_STEP=""
TLS_STEP_TOKEN=""
TLS_CA=""
TLS_CA_IMPRONTA=""
DIR_SCRIPT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ISTANZA=""     # più installazioni sullo stesso host (es. una per sezione): --istanza potenza
WORKER=3
DB_SCELTO=""
DOMINIO=""     # nome pubblico dietro un reverse proxy HTTPS (es. Nginx Proxy Manager)
PROXY=""       # IP del reverse proxy, unico da cui si accetta X-Forwarded-For

uso() {
  cat <<EOF
Uso: $0 [opzioni]
  --porta N           porta del servizio web (predefinita 8000; negli aggiornamenti resta quella in uso)
  --indirizzo IP      indirizzo di ascolto (predefinito 0.0.0.0; 127.0.0.1 dietro reverse proxy;
                      negli aggiornamenti resta quello in uso)
  --host NOMI         nomi o IP aggiuntivi per ALLOWED_HOSTS, separati da virgola
  --dominio NOME      nome pubblico (es. gestione.associazione.it) servito in HTTPS da un reverse
                      proxy: va in ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS e URL_PUBBLICO
  --proxy IP          reverse proxy davanti all'applicazione: HTTPS=true, PROXY_COUNT=1, PROXY_FIDATI.
                      Con --dominio e --proxy anche un aggiornamento corregge il .env esistente
  --db NOME           nome del database (predefinito ${DB_NOME})
  --istanza NOME      una di più installazioni sullo stesso host (lettere minuscole, cifre, «-»):
                      servizio gestione-NOME, codice in /opt/sezione-NOME, dati in
                      /var/lib/sezione-NOME, utente e database sezione_NOME
  --worker N          processi del servizio web (predefinito 3)
  --admin UTENTE      amministratore creato alla prima installazione (predefinito ${ADMIN})
  --email EMAIL       email dell'amministratore
  --sorgente DIR      cartella del codice (predefinita: quella dello script)
HTTPS servito direttamente dall'applicazione (consigliato anche in rete interna), un modo a scelta:
  --tls-step URL      certificato da step-ca (es. https://ca.associazione.lan), con rinnovo automatico;
    --tls-step-token T  token monouso creato da chi amministra la CA, valido pochi minuti:
                        step ca token NOME --san NOME --san IP
  --tls-acme URL      certificato da una CA ACME (es. https://ca.associazione.lan/acme/acme/directory)
                      con certbot e rinnovo automatico; serve la porta 80 libera e i nomi in --tls-nomi
  --tls-cert FILE     certificato PEM con la catena (es. emesso con MyCert)
    --tls-key FILE      chiave privata del certificato
  --tls-autofirmato   certificato autofirmato (825 giorni) per nome e IP del server; riusa la chiave
                      esistente, così l'impronta non cambia
  --senza-tls         torna a servire HTTP (sconsigliato, se non dietro un proxy HTTPS)
  --tls-nomi NOMI     nomi (e IP, non per ACME) del certificato, separati da virgola
  --tls-ca FILE       radice di una CA privata, aggiunta all'archivio del sistema
  --tls-ca-impronta F impronta SHA-256 della radice di step-ca: la radice si scarica dalla CA e si
                      accetta solo se coincide (alternativa a --tls-ca)
  Negli aggiornamenti l'HTTPS resta com'è. Con --tls-cert o --tls-autofirmato, per rinnovare basta
  sovrascrivere ${DIR_TLS}/key.pem e poi cert.pem: il servizio si riavvia da solo.
  -y                  nessuna domanda
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --porta) PORTA="$2"; shift 2 ;;
    --indirizzo) INDIRIZZO="$2"; shift 2 ;;
    --host) HOST_EXTRA="$2"; shift 2 ;;
    --dominio) DOMINIO="$2"; shift 2 ;;
    --proxy) PROXY="$2"; shift 2 ;;
    --db) DB_SCELTO="$2"; shift 2 ;;
    --istanza) ISTANZA="$2"; shift 2 ;;
    --worker) WORKER="$2"; shift 2 ;;
    --admin) ADMIN="$2"; shift 2 ;;
    --email) ADMIN_EMAIL="$2"; shift 2 ;;
    --sorgente) SORGENTE="$(cd "$2" && pwd)"; shift 2 ;;
    --tls-cert) TLS_CERT="$2"; shift 2 ;;
    --tls-key) TLS_KEY="$2"; shift 2 ;;
    --tls-autofirmato) TLS_AUTOFIRMATO=1; shift ;;
    --tls-nomi) TLS_NOMI="$2"; shift 2 ;;
    --senza-tls) TLS_DISATTIVA=1; shift ;;
    --tls-acme) TLS_ACME="$2"; shift 2 ;;
    --tls-step) TLS_STEP="$2"; shift 2 ;;
    --tls-step-token) TLS_STEP_TOKEN="$2"; shift 2 ;;
    --tls-ca) TLS_CA="$2"; shift 2 ;;
    --tls-ca-impronta) TLS_CA_IMPRONTA="$2"; shift 2 ;;
    -y) SI=1; shift ;;
    -h|--help) uso; exit 0 ;;
    *) echo "Opzione sconosciuta: $1"; uso; exit 1 ;;
  esac
done

if [[ -n "$ISTANZA" ]]; then
  [[ "$ISTANZA" =~ ^[a-z0-9]([a-z0-9-]{0,38}[a-z0-9])?$ ]] || { echo "Istanza non valida: ${ISTANZA}"; exit 1; }
  NOME="gestione-${ISTANZA}"
  DIR_APP="/opt/sezione-${ISTANZA}"
  DIR_DATI="/var/lib/sezione-${ISTANZA}"
  DIR_TLS="/etc/sezione-${ISTANZA}/tls"
  UTENTE="sezione_${ISTANZA//-/_}"
  DB_NOME="sezione_${ISTANZA//-/_}"
fi
[[ -n "$DB_SCELTO" ]] && DB_NOME="$DB_SCELTO"
[[ "$WORKER" =~ ^[1-9][0-9]?$ ]] || { echo "Numero di worker non valido."; exit 1; }
[[ -z "$DOMINIO" || "$DOMINIO" =~ ^[a-z0-9]([a-z0-9.-]*[a-z0-9])?$ ]] || { echo "Dominio non valido: ${DOMINIO}"; exit 1; }
[[ -z "$PROXY" || "$PROXY" =~ ^[0-9a-fA-F.:/]+$ ]] || { echo "Proxy non valido: ${PROXY}"; exit 1; }
DESCRIZIONE="Gestione Associazione${ISTANZA:+ (${ISTANZA})}"

passo() { echo -e "\n\033[1;34m==> $*\033[0m"; }
errore() { echo -e "\033[1;31mERRORE: $*\033[0m" >&2; exit 1; }
# shellcheck source=scripts/tls.sh
. "${DIR_SCRIPT}/tls.sh"

[[ $EUID -eq 0 ]] || errore "eseguire come root."
[[ -f "${SORGENTE}/manage.py" ]] || errore "codice non trovato in ${SORGENTE}."
command -v systemctl >/dev/null || errore "serve systemd."
[[ -r /etc/os-release ]] && . /etc/os-release
case "${ID:-}" in debian|ubuntu) ;; *) errore "sistema non supportato (${ID:-?}): servono Debian o Ubuntu." ;; esac
AGGIORNAMENTO=0
[[ -f "${DIR_APP}/.env" ]] && AGGIORNAMENTO=1
# in un aggiornamento porta e indirizzo restano quelli del servizio installato (es. 8003 dietro
# un reverse proxy), salvo indicarli di nuovo con --porta / --indirizzo
UNITA_WEB="/etc/systemd/system/${NOME}.service"
if [[ -f "$UNITA_WEB" ]]; then
  ASCOLTO="$(grep -o -- '--bind [^ ]*' "$UNITA_WEB" | head -1 | cut -d' ' -f2)"
  [[ -z "$PORTA" && "$ASCOLTO" == *:* ]] && PORTA="${ASCOLTO##*:}"
  [[ -z "$INDIRIZZO" && "$ASCOLTO" == *:* ]] && INDIRIZZO="${ASCOLTO%:*}"
fi
PORTA="${PORTA:-8000}"
INDIRIZZO="${INDIRIZZO:-0.0.0.0}"
[[ "$PORTA" =~ ^[0-9]+$ ]] || errore "porta non valida."
tls_controlla_opzioni
if [[ $AGGIORNAMENTO -eq 0 && $SI -eq 0 ]]; then
  echo "Installazione di Gestione Associazione in ${DIR_APP}, dati in ${DIR_DATI}, porta ${PORTA}."
  read -r -p "Procedere? [s/N] " r; [[ "$r" =~ ^[sS]$ ]] || exit 1
fi

passo "Pacchetti di sistema"
export DEBIAN_FRONTEND=noninteractive
PACCHETTI=(ca-certificates curl openssl rsync postgresql postgresql-client
  libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 shared-mime-info
  fonts-dejavu-core fonts-liberation2)
# solo quelli mancanti: su un server condiviso non si aggiornano (né riavviano) i servizi esistenti
MANCANTI=()
for p in "${PACCHETTI[@]}"; do
  dpkg-query -W -f='${Status}' "$p" 2>/dev/null | grep -q "install ok installed" || MANCANTI+=("$p")
done
if [[ ${#MANCANTI[@]} -gt 0 ]]; then
  echo "Da installare: ${MANCANTI[*]}"
  apt-get update -qq
  apt-get install -y -qq --no-install-recommends "${MANCANTI[@]}" >/dev/null
fi
systemctl enable --now postgresql >/dev/null

if ! command -v uv >/dev/null; then
  passo "uv (gestione di Python)"
  curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin UV_NO_MODIFY_PATH=1 sh >/dev/null
fi

passo "Utente e cartelle"
id -u "$UTENTE" >/dev/null 2>&1 || useradd --system --home-dir "$DIR_APP" --shell /usr/sbin/nologin "$UTENTE"
install -d -o "$UTENTE" -g "$UTENTE" -m 750 "$DIR_APP" "$DIR_DATI" "$DIR_DATI/media" "$DIR_DATI/static"
install -d -o "$UTENTE" -g "$UTENTE" -m 700 "$DIR_DATI/backup"

passo "HTTPS"
tls_prepara

passo "Codice"
rsync -a --delete \
  --exclude .git --exclude .env --exclude .venv --exclude .python --exclude var --exclude tmp \
  --exclude __pycache__ --exclude '*.pyc' --exclude .pytest_cache --exclude .ruff_cache \
  "${SORGENTE}/" "${DIR_APP}/"

passo "Database PostgreSQL"
if [[ $AGGIORNAMENTO -eq 0 ]]; then
  DB_PASSWORD="$(head -c 32 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 32)"
  runuser -u postgres -- psql -q -v ON_ERROR_STOP=1 <<SQL
SET password_encryption = 'scram-sha-256';
DO \$\$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${UTENTE}') THEN
    CREATE ROLE ${UTENTE} LOGIN;
  END IF;
END \$\$;
ALTER ROLE ${UTENTE} PASSWORD '${DB_PASSWORD}';
SQL
  if ! runuser -u postgres -- psql -Atqc "SELECT 1 FROM pg_database WHERE datname='${DB_NOME}'" | grep -q 1; then
    runuser -u postgres -- createdb -O "$UTENTE" "$DB_NOME"
  fi
fi

passo "Ambiente Python"
export UV_PYTHON_INSTALL_DIR="${DIR_APP}/.python" UV_CACHE_DIR="/var/cache/${NOME}/uv"
cd "$DIR_APP"
uv sync --frozen --no-dev --python 3.13 --quiet

if [[ $AGGIORNAMENTO -eq 0 ]]; then
  passo "Configurazione (.env)"
  SEGRETO="$(head -c 64 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 50)"
  CHIAVE="$("${DIR_APP}/.venv/bin/python" -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
  HOSTS="localhost,127.0.0.1,$(hostname)"
  for ip in $(hostname -I 2>/dev/null); do [[ "$ip" == *:* ]] || HOSTS="${HOSTS},${ip}"; done
  [[ -n "$HOST_EXTRA" ]] && HOSTS="${HOSTS},${HOST_EXTRA}"
  umask 077
  cat > "${DIR_APP}/.env" <<EOF
# Generato da scripts/installa.sh il $(date '+%d/%m/%Y %H:%M'). Conservarne una copia con i backup.
SECRET_KEY=${SEGRETO}
DATABASE_URL=postgres://${UTENTE}:${DB_PASSWORD}@127.0.0.1:5432/${DB_NOME}
ALLOWED_HOSTS=${HOSTS}
DEBUG=false
HTTPS=$([[ $TLS -eq 1 ]] && echo true || echo false)
PROXY_COUNT=0
CSRF_TRUSTED_ORIGINS=
CHIAVE_CIFRATURA=${CHIAVE}
MEDIA_ROOT=${DIR_DATI}/media
STATIC_ROOT=${DIR_DATI}/static
BACKUP_ROOT=${DIR_DATI}/backup
# Email in uscita: completare per inviare comunicazioni
# EMAIL_HOST=smtp.example.com
# EMAIL_PORT=587
# EMAIL_HOST_USER=
# EMAIL_HOST_PASSWORD=
# DEFAULT_FROM_EMAIL=Associazione <noreply@example.com>
# URL_PUBBLICO=https://gestione.example.it
EOF
  umask 022
fi

# reverse proxy: valori impostati (o aggiunti alle liste) anche nel .env di un'installazione esistente
env_imposta() {
  if grep -q "^$1=" "${DIR_APP}/.env"; then sed -i "s|^$1=.*|$1=$2|" "${DIR_APP}/.env"
  else echo "$1=$2" >> "${DIR_APP}/.env"; fi
}
env_aggiungi() {
  local attuale; attuale="$(grep -m1 "^$1=" "${DIR_APP}/.env" | cut -d= -f2- || true)"
  [[ ",${attuale}," == *",$2,"* ]] || env_imposta "$1" "${attuale:+${attuale},}$2"
}
if [[ -n "$DOMINIO" || -n "$PROXY" ]]; then
  passo "Reverse proxy (.env)"
  if [[ -n "$DOMINIO" ]]; then
    env_aggiungi ALLOWED_HOSTS "$DOMINIO"
    env_aggiungi CSRF_TRUSTED_ORIGINS "https://${DOMINIO}"
    env_imposta URL_PUBBLICO "https://${DOMINIO}"
  fi
  if [[ -n "$PROXY" ]]; then
    env_imposta HTTPS true
    env_imposta PROXY_COUNT 1
    env_aggiungi PROXY_FIDATI "$PROXY"
  fi
  grep -E '^(ALLOWED_HOSTS|CSRF_TRUSTED_ORIGINS|URL_PUBBLICO|HTTPS|PROXY_COUNT|PROXY_FIDATI)=' "${DIR_APP}/.env"
fi
chown -R "$UTENTE:$UTENTE" "$DIR_APP" "$DIR_DATI"
chmod 600 "${DIR_APP}/.env"

gestisci() { runuser -u "$UTENTE" -- "${DIR_APP}/.venv/bin/python" "${DIR_APP}/manage.py" "$@"; }

if [[ $AGGIORNAMENTO -eq 1 ]] && systemctl is-active --quiet "$NOME"; then
  passo "Backup prima dell'aggiornamento"
  gestisci backup --motivo "prima dell'aggiornamento" || errore "backup non riuscito: aggiornamento interrotto."
fi

passo "Migrazioni e file statici"
gestisci migrate --noinput
gestisci collectstatic --noinput --verbosity 0
gestisci check --deploy --fail-level ERROR >/dev/null 2>&1 || errore "controllo della configurazione non superato: manage.py check --deploy"

PASSWORD_ADMIN=""
if [[ "$(gestisci shell -c 'from django.contrib.auth import get_user_model as g; print(g().objects.exists())' 2>/dev/null | tail -1)" != "True" ]]; then
  passo "Amministratore"
  PASSWORD_ADMIN="$(head -c 32 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 16)"
  runuser -u "$UTENTE" -- env DJANGO_SUPERUSER_PASSWORD="$PASSWORD_ADMIN" \
    "${DIR_APP}/.venv/bin/python" "${DIR_APP}/manage.py" createsuperuser --noinput \
    --username "$ADMIN" --email "${ADMIN_EMAIL:-${ADMIN}@localhost}" >/dev/null
  umask 077
  printf '%s\nutente: %s\npassword: %s\n' "$DESCRIZIONE" "$ADMIN" "$PASSWORD_ADMIN" > "/root/${NOME}-credenziali.txt"
  umask 022
fi

# password predefinite per «manage.py utenti --reimposta»: «admin» = password iniziale
# dell'installazione (per quelle esistenti, dal file delle credenziali in /root); le altre (cariche)
# si aggiungono a mano. Leggibile solo da root e dal gestionale; mai sovrascritto.
FILE_PREDEFINITE="/etc/${NOME}/password-predefinite.json"
mkdir -p "/etc/${NOME}"
if [[ ! -f "$FILE_PREDEFINITE" ]]; then
  INIZIALE="$PASSWORD_ADMIN"
  if [[ -z "$INIZIALE" && -f "/root/${NOME}-credenziali.txt" ]]; then
    INIZIALE="$(sed -n 's/^password:[[:space:]]*//p' "/root/${NOME}-credenziali.txt" | head -1)"
  fi
  umask 077
  if [[ -n "$INIZIALE" ]]; then printf '{"admin": "%s"}\n' "$INIZIALE" > "$FILE_PREDEFINITE"
  else echo '{}' > "$FILE_PREDEFINITE"; fi
  umask 022
fi
chown "root:${UTENTE}" "$FILE_PREDEFINITE" && chmod 640 "$FILE_PREDEFINITE"
grep -q "^PASSWORD_PREDEFINITE=" "${DIR_APP}/.env" || echo "PASSWORD_PREDEFINITE=${FILE_PREDEFINITE}" >> "${DIR_APP}/.env"

passo "Servizi systemd"
cat > "/etc/systemd/system/${NOME}.service" <<EOF
[Unit]
Description=${DESCRIZIONE}
After=network-online.target postgresql.service
Wants=network-online.target postgresql.service

[Service]
User=${UTENTE}
Group=${UTENTE}
WorkingDirectory=${DIR_APP}
ExecStart=${DIR_APP}/.venv/bin/gunicorn config.wsgi --bind ${INDIRIZZO}:${PORTA} --workers ${WORKER} --timeout 300 --access-logfile -${OPZ_TLS}
Restart=on-failure
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true

[Install]
WantedBy=multi-user.target
EOF
cat > "/etc/systemd/system/${NOME}-pianificatore.service" <<EOF
[Unit]
Description=${DESCRIZIONE} - lavori periodici (email, posta, registri, backup notturno)
After=${NOME}.service

[Service]
User=${UTENTE}
Group=${UTENTE}
WorkingDirectory=${DIR_APP}
ExecStart=${DIR_APP}/.venv/bin/python manage.py pianificatore
Restart=on-failure
RestartSec=30
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true

[Install]
WantedBy=multi-user.target
EOF
# certificato rinnovato (sovrascritto in ${DIR_TLS}) => riavvio del servizio web
cat > "/etc/systemd/system/${NOME}-tls.path" <<EOF
[Unit]
Description=${DESCRIZIONE} - sorveglia il certificato HTTPS

[Path]
PathChanged=${DIR_TLS}/cert.pem
Unit=${NOME}-tls.service

[Install]
WantedBy=multi-user.target
EOF
cat > "/etc/systemd/system/${NOME}-tls.service" <<EOF
[Unit]
Description=${DESCRIZIONE} - riavvio dopo il rinnovo del certificato HTTPS

[Service]
Type=oneshot
ExecStart=/bin/systemctl restart ${NOME}.service
EOF
systemctl daemon-reload
systemctl enable "$NOME" "${NOME}-pianificatore" >/dev/null 2>&1
if [[ $TLS -eq 1 ]]; then systemctl enable --now "${NOME}-tls.path" >/dev/null 2>&1
else systemctl disable --now "${NOME}-tls.path" >/dev/null 2>&1 || true; fi
systemctl restart "$NOME" "${NOME}-pianificatore"

passo "Controllo"
PROTO="http"; [[ $TLS -eq 1 ]] && PROTO="https"
for _ in $(seq 1 20); do
  # solo per sapere se risponde: il certificato può non riportare 127.0.0.1
  if curl -fsSk "${PROTO}://127.0.0.1:${PORTA}/salute/" >/dev/null 2>&1; then OK=1; break; fi
  sleep 1
done
[[ "${OK:-0}" == 1 ]] || errore "il servizio non risponde: journalctl -u ${NOME}"

VERSIONE="$(grep -m1 '^APP_VERSIONE' "${DIR_APP}/config/settings.py" | cut -d'"' -f2)"
echo -e "\n\033[1;32m${DESCRIZIONE} ${VERSIONE} attiva su ${PROTO}://$(hostname -I | awk '{print $1}'):${PORTA}/\033[0m"
tls_riepilogo
if [[ -n "$PASSWORD_ADMIN" ]]; then
  echo "Primo accesso: utente ${ADMIN}, password ${PASSWORD_ADMIN}"
  echo "(salvate anche in /root/${NOME}-credenziali.txt: cambiarla al primo accesso e cancellare il file)"
fi
[[ -n "$DOMINIO" ]] && echo "Indirizzo pubblico: https://${DOMINIO}/ (reverse proxy${PROXY:+ ${PROXY}} → ${PROTO}://$(hostname -I | awk '{print $1}'):${PORTA})"
echo "Configurazione: ${DIR_APP}/.env  ·  Log: journalctl -u ${NOME}  ·  Backup: ${DIR_DATI}/backup"
