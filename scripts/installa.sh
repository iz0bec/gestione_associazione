#!/usr/bin/env bash
# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Installazione e aggiornamento su Debian/Ubuntu con systemd, senza Docker:
# *              pacchetti, PostgreSQL, utente di sistema, ambiente Python (uv), .env con
# *              segreti generati, migrazioni, servizi applicazione e pianificatore.
# *              Rieseguibile: negli aggiornamenti non tocca .env, database, file e backup.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
set -euo pipefail

NOME="gestione-associazione"
DIR_APP="/opt/${NOME}"
DIR_DATI="/var/lib/${NOME}"
UTENTE="gestione"
DB_NOME="gestione_associazione"
PORTA="8000"
INDIRIZZO="0.0.0.0"
HOST_EXTRA=""
ADMIN="admin"
ADMIN_EMAIL=""
SORGENTE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SI=0

uso() {
  cat <<EOF
Uso: $0 [opzioni]
  --porta N           porta del servizio web (predefinita ${PORTA})
  --indirizzo IP      indirizzo di ascolto (predefinito ${INDIRIZZO}; 127.0.0.1 dietro reverse proxy)
  --host NOMI         nomi o IP aggiuntivi per ALLOWED_HOSTS, separati da virgola
  --db NOME           nome del database (predefinito ${DB_NOME})
  --admin UTENTE      amministratore creato alla prima installazione (predefinito ${ADMIN})
  --email EMAIL       email dell'amministratore
  --sorgente DIR      cartella del codice (predefinita: quella dello script)
  -y                  nessuna domanda
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --porta) PORTA="$2"; shift 2 ;;
    --indirizzo) INDIRIZZO="$2"; shift 2 ;;
    --host) HOST_EXTRA="$2"; shift 2 ;;
    --db) DB_NOME="$2"; shift 2 ;;
    --admin) ADMIN="$2"; shift 2 ;;
    --email) ADMIN_EMAIL="$2"; shift 2 ;;
    --sorgente) SORGENTE="$(cd "$2" && pwd)"; shift 2 ;;
    -y) SI=1; shift ;;
    -h|--help) uso; exit 0 ;;
    *) echo "Opzione sconosciuta: $1"; uso; exit 1 ;;
  esac
done

passo() { echo -e "\n\033[1;34m==> $*\033[0m"; }
errore() { echo -e "\033[1;31mERRORE: $*\033[0m" >&2; exit 1; }

[[ $EUID -eq 0 ]] || errore "eseguire come root."
[[ -f "${SORGENTE}/manage.py" ]] || errore "codice non trovato in ${SORGENTE}."
command -v systemctl >/dev/null || errore "serve systemd."
[[ -r /etc/os-release ]] && . /etc/os-release
case "${ID:-}" in debian|ubuntu) ;; *) errore "sistema non supportato (${ID:-?}): servono Debian o Ubuntu." ;; esac
[[ "$PORTA" =~ ^[0-9]+$ ]] || errore "porta non valida."

AGGIORNAMENTO=0
[[ -f "${DIR_APP}/.env" ]] && AGGIORNAMENTO=1
if [[ $AGGIORNAMENTO -eq 0 && $SI -eq 0 ]]; then
  echo "Installazione di Gestione Associazione in ${DIR_APP}, dati in ${DIR_DATI}, porta ${PORTA}."
  read -r -p "Procedere? [s/N] " r; [[ "$r" =~ ^[sS]$ ]] || exit 1
fi

passo "Pacchetti di sistema"
export DEBIAN_FRONTEND=noninteractive
PACCHETTI=(ca-certificates curl rsync postgresql postgresql-client
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
HTTPS=false
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
  printf 'Gestione Associazione\nutente: %s\npassword: %s\n' "$ADMIN" "$PASSWORD_ADMIN" > "/root/${NOME}-credenziali.txt"
  umask 022
fi

passo "Servizi systemd"
cat > "/etc/systemd/system/${NOME}.service" <<EOF
[Unit]
Description=Gestione Associazione
After=network-online.target postgresql.service
Wants=network-online.target postgresql.service

[Service]
User=${UTENTE}
Group=${UTENTE}
WorkingDirectory=${DIR_APP}
ExecStart=${DIR_APP}/.venv/bin/gunicorn config.wsgi --bind ${INDIRIZZO}:${PORTA} --workers 3 --timeout 120 --access-logfile -
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
Description=Gestione Associazione - lavori periodici (email, posta, registri, backup notturno)
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
systemctl daemon-reload
systemctl enable "$NOME" "${NOME}-pianificatore" >/dev/null 2>&1
systemctl restart "$NOME" "${NOME}-pianificatore"

passo "Controllo"
for _ in $(seq 1 20); do
  if curl -fsS "http://127.0.0.1:${PORTA}/salute/" >/dev/null 2>&1; then OK=1; break; fi
  sleep 1
done
[[ "${OK:-0}" == 1 ]] || errore "il servizio non risponde: journalctl -u ${NOME}"

VERSIONE="$(grep -m1 '^APP_VERSIONE' "${DIR_APP}/config/settings.py" | cut -d'"' -f2)"
echo -e "\n\033[1;32mGestione Associazione ${VERSIONE} attiva su http://$(hostname -I | awk '{print $1}'):${PORTA}/\033[0m"
if [[ -n "$PASSWORD_ADMIN" ]]; then
  echo "Primo accesso: utente ${ADMIN}, password ${PASSWORD_ADMIN}"
  echo "(salvate anche in /root/${NOME}-credenziali.txt: cambiarla al primo accesso e cancellare il file)"
fi
echo "Configurazione: ${DIR_APP}/.env  ·  Log: journalctl -u ${NOME}  ·  Backup: ${DIR_DATI}/backup"
