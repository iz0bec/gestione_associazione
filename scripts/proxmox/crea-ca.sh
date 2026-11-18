#!/usr/bin/env bash
# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Da eseguire sull'host Proxmox VE: crea un container LXC Debian con step-ca, una
# *              autorità di certificazione interna per l'HTTPS in rete locale (provisioner JWK per
# *              i token e ACME per certbot, durata dei certificati e nomi ammessi limitati).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
set -euo pipefail

CTID=""
NOME="ca"
STORAGE="local-lvm"
STORAGE_TEMPLATE="local"
DISCO=2
RAM=512
CORE=1
BRIDGE="vmbr0"
IP="dhcp"
GW=""
DNS=""
DEBIAN="13"
PASSWORD_ROOT=""
CHIAVE_SSH=""
NOME_CA="Associazione - CA interna"
DOMINIO=""
RETI=""
NOMI_CA=""
DURATA="720h"
DURATA_MAX="2160h"

uso() {
  cat <<EOF
Uso: $0 --dominio DOMINIO [opzioni]
Container:
  --id N                  numero del container (predefinito: il primo libero)
  --nome NOME             hostname (predefinito ${NOME})
  --storage NOME          storage del disco (predefinito ${STORAGE})
  --storage-template NOME storage dei template (predefinito ${STORAGE_TEMPLATE})
  --disco GB, --ram MB, --core N   risorse (predefinite ${DISCO} GB, ${RAM} MB, ${CORE})
  --bridge NOME           bridge di rete (predefinito ${BRIDGE})
  --ip dhcp|IP/CIDR       indirizzo (consigliato fisso), es. 192.168.0.40/24
  --gw IP, --dns IP       gateway e DNS
  --debian 12|13          versione di Debian (predefinita ${DEBIAN})
  --password-root PWD, --chiave-ssh FILE   accesso al container
Autorità di certificazione:
  --dominio DOMINIO       dominio interno (obbligatorio), es. associazione.lan: la CA firma solo
                          DOMINIO e *.DOMINIO
  --reti CIDR,...         reti di cui firmare anche gli IP (predefinita: quella di --ip, se fisso)
  --nome-ca TESTO         nome della CA (predefinito «${NOME_CA}»)
  --nomi-ca NOMI          nomi del servizio CA (predefinito NOME.DOMINIO e l'IP)
  --durata D              durata predefinita dei certificati (predefinita ${DURATA})
  --durata-max D          durata massima (predefinita ${DURATA_MAX})
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --id) CTID="$2"; shift 2 ;;
    --nome) NOME="$2"; shift 2 ;;
    --storage) STORAGE="$2"; shift 2 ;;
    --storage-template) STORAGE_TEMPLATE="$2"; shift 2 ;;
    --disco) DISCO="$2"; shift 2 ;;
    --ram) RAM="$2"; shift 2 ;;
    --core) CORE="$2"; shift 2 ;;
    --bridge) BRIDGE="$2"; shift 2 ;;
    --ip) IP="$2"; shift 2 ;;
    --gw) GW="$2"; shift 2 ;;
    --dns) DNS="$2"; shift 2 ;;
    --debian) DEBIAN="$2"; shift 2 ;;
    --password-root) PASSWORD_ROOT="$2"; shift 2 ;;
    --chiave-ssh) CHIAVE_SSH="$2"; shift 2 ;;
    --nome-ca) NOME_CA="$2"; shift 2 ;;
    --dominio) DOMINIO="$2"; shift 2 ;;
    --reti) RETI="$2"; shift 2 ;;
    --nomi-ca) NOMI_CA="$2"; shift 2 ;;
    --durata) DURATA="$2"; shift 2 ;;
    --durata-max) DURATA_MAX="$2"; shift 2 ;;
    -h|--help) uso; exit 0 ;;
    *) echo "Opzione sconosciuta: $1"; uso; exit 1 ;;
  esac
done

passo() { echo -e "\n\033[1;34m==> $*\033[0m"; }
errore() { echo -e "\033[1;31mERRORE: $*\033[0m" >&2; exit 1; }
nel_ct() { pct exec "$CTID" -- "$@"; }

[[ $EUID -eq 0 ]] || errore "eseguire come root sull'host Proxmox."
command -v pct >/dev/null && command -v pveam >/dev/null || errore "comandi pct/pveam non trovati: eseguire sull'host Proxmox VE."
[[ "$DOMINIO" =~ ^[a-z0-9]([a-z0-9.-]*[a-z0-9])?$ && "$DOMINIO" == *.* ]] \
  || errore "indicare --dominio (es. associazione.lan; evitare .local)."
[[ "$DOMINIO" == *.local ]] && errore "il suffisso .local è riservato a mDNS: usare ad esempio .lan o home.arpa."
[[ "$IP" == "dhcp" || "$IP" == */* ]] || errore "--ip deve essere dhcp oppure IP/CIDR (es. 192.168.0.40/24)."
[[ -n "$CTID" ]] || CTID="$(pvesh get /cluster/nextid)"
pct status "$CTID" >/dev/null 2>&1 && errore "il container ${CTID} esiste già."
if [[ -z "$RETI" && "$IP" != "dhcp" ]]; then
  RETI="$(python3 -c 'import ipaddress,sys; print(ipaddress.ip_interface(sys.argv[1]).network)' "$IP")"
fi
[[ "$IP" == "dhcp" ]] && echo "Consiglio: dare alla CA un indirizzo fisso (--ip), perché i client la cercano sempre lì."

passo "Template Debian ${DEBIAN}"
pveam update >/dev/null
ARCH="$(dpkg --print-architecture)"
TEMPLATE="$(pveam available --section system | awk -v d="debian-${DEBIAN}-standard" -v a="_${ARCH}." '$2 ~ d && index($2, a) {print $2}' | sort -V | tail -1)"
[[ -n "$TEMPLATE" ]] || errore "template debian-${DEBIAN}-standard (${ARCH}) non disponibile."
pveam list "$STORAGE_TEMPLATE" | grep -q "$TEMPLATE" || pveam download "$STORAGE_TEMPLATE" "$TEMPLATE"

passo "Creazione del container ${CTID} (${NOME})"
[[ -n "$PASSWORD_ROOT" ]] || PASSWORD_ROOT="$(head -c 32 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 20)"
RETE="name=eth0,bridge=${BRIDGE},ip=${IP}"
[[ -n "$GW" ]] && RETE="${RETE},gw=${GW}"
OPZIONI=(
  --hostname "$NOME" --cores "$CORE" --memory "$RAM" --swap 256
  --rootfs "${STORAGE}:${DISCO}" --net0 "$RETE" --unprivileged 1 --features nesting=1
  --onboot 1 --timezone host --password "$PASSWORD_ROOT" --searchdomain "$DOMINIO"
  --description "Autorità di certificazione interna (step-ca) per ${DOMINIO}"
)
[[ -n "$DNS" ]] && OPZIONI+=(--nameserver "$DNS")
[[ -n "$CHIAVE_SSH" ]] && OPZIONI+=(--ssh-public-keys "$CHIAVE_SSH")
pct create "$CTID" "${STORAGE_TEMPLATE}:vztmpl/${TEMPLATE}" "${OPZIONI[@]}"
pct start "$CTID"

passo "Attesa della rete"
for _ in $(seq 1 60); do
  nel_ct getent hosts packages.smallstep.com >/dev/null 2>&1 && break
  sleep 2
done
nel_ct getent hosts packages.smallstep.com >/dev/null 2>&1 || errore "il container non raggiunge Internet."

passo "step-ca (repository Smallstep)"
nel_ct bash -c "export DEBIAN_FRONTEND=noninteractive
apt-get update -qq && apt-get -y -qq upgrade >/dev/null
apt-get install -y -qq --no-install-recommends curl gpg ca-certificates jq >/dev/null
curl -fsSL https://packages.smallstep.com/keys/apt/repo-signing-key.gpg -o /etc/apt/trusted.gpg.d/smallstep.asc
echo 'deb [signed-by=/etc/apt/trusted.gpg.d/smallstep.asc] https://packages.smallstep.com/stable/debian debs main' > /etc/apt/sources.list.d/smallstep.list
apt-get update -qq && apt-get install -y -qq --no-install-recommends step-cli step-ca >/dev/null"

INDIRIZZO_CT="$(nel_ct hostname -I | awk '{print $1}')"
[[ -n "$NOMI_CA" ]] || NOMI_CA="${NOME}.${DOMINIO},${INDIRIZZO_CT}"
DNS_INIT=()
IFS=',' read -r -a ELENCO <<< "$NOMI_CA"
for n in "${ELENCO[@]}"; do [[ -n "${n// /}" ]] && DNS_INIT+=(--dns "${n// /}"); done
NOME_PRINCIPALE="${ELENCO[0]// /}"

passo "Inizializzazione della CA «${NOME_CA}»"
nel_ct bash -c "set -e
id -u step >/dev/null 2>&1 || useradd --system --home /etc/step-ca --shell /usr/sbin/nologin step
install -d -m 700 /etc/step-ca
umask 077
head -c 32 /dev/urandom | base64 > /etc/step-ca/password.txt"
nel_ct env STEPPATH=/etc/step-ca step ca init --deployment-type standalone --name "$NOME_CA" \
  "${DNS_INIT[@]}" --address ":443" --provisioner admin \
  --password-file /etc/step-ca/password.txt --provisioner-password-file /etc/step-ca/password.txt >/dev/null
nel_ct env STEPPATH=/etc/step-ca step ca provisioner add acme --type ACME >/dev/null

# durata dei certificati e nomi ammessi: la CA non firma nulla fuori dal dominio interno
POLICY="{\"dns\": [\"${DOMINIO}\", \"*.${DOMINIO}\"]"
if [[ -n "$RETI" ]]; then
  POLICY="${POLICY}, \"ip\": [$(sed 's/[^,][^,]*/"&"/g' <<< "${RETI// /}")]"
fi
POLICY="${POLICY}}"
nel_ct bash -c "set -e; cd /etc/step-ca/config
jq --argjson allow '${POLICY}' '.authority.claims = {
    \"minTLSCertDuration\": \"5m\", \"maxTLSCertDuration\": \"${DURATA_MAX}\",
    \"defaultTLSCertDuration\": \"${DURATA}\", \"disableRenewal\": false,
    \"allowRenewalAfterExpiry\": false }
  | .authority.policy = { \"x509\": { \"allow\": \$allow } }' ca.json > ca.json.nuovo
mv ca.json.nuovo ca.json
chown -R step:step /etc/step-ca"

nel_ct bash -c "cat > /etc/systemd/system/step-ca.service <<'EOF'
[Unit]
Description=step-ca - autorità di certificazione interna
After=network-online.target
Wants=network-online.target

[Service]
User=step
Group=step
Environment=STEPPATH=/etc/step-ca
ExecStart=$(nel_ct bash -c 'command -v step-ca') /etc/step-ca/config/ca.json --password-file /etc/step-ca/password.txt
AmbientCapabilities=CAP_NET_BIND_SERVICE
CapabilityBoundingSet=CAP_NET_BIND_SERVICE
Restart=on-failure
NoNewPrivileges=true
ProtectSystem=full
ReadWritePaths=/etc/step-ca/db
ProtectHome=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload && systemctl enable --now step-ca >/dev/null 2>&1"

# token monouso per l'installatore del gestionale (installa.sh --tls-step)
nel_ct bash -c "cat > /usr/local/bin/token-certificato <<'EOF'
#!/bin/sh
# Uso: token-certificato NOME [NOME_O_IP ...]  -> token monouso (pochi minuti) per un certificato
[ -n \"\$1\" ] || { echo 'Uso: token-certificato NOME [NOME_O_IP ...]' >&2; exit 1; }
nome=\"\$1\"; san=\"--san \$1\"; shift
for s in \"\$@\"; do san=\"\$san --san \$s\"; done
# shellcheck disable=SC2086
STEPPATH=/etc/step-ca exec step ca token \"\$nome\" \$san --provisioner admin \\
  --password-file /etc/step-ca/password.txt --ca-url https://${NOME_PRINCIPALE} --root /etc/step-ca/certs/root_ca.crt 2>/dev/null
EOF
chmod 700 /usr/local/bin/token-certificato"

passo "Controllo"
for _ in $(seq 1 20); do
  # il certificato della CA vale per i suoi nomi, non per 127.0.0.1
  nel_ct curl -fsS --cacert /etc/step-ca/certs/root_ca.crt --resolve "${NOME_PRINCIPALE}:443:127.0.0.1" \
    "https://${NOME_PRINCIPALE}/health" >/dev/null 2>&1 && OK=1 && break
  sleep 1
done
[[ "${OK:-0}" == 1 ]] || errore "la CA non risponde: pct exec ${CTID} -- journalctl -u step-ca"
IMPRONTA="$(nel_ct env STEPPATH=/etc/step-ca step certificate fingerprint /etc/step-ca/certs/root_ca.crt)"

echo -e "\n\033[1;32mCA pronta nel container ${CTID}: https://${NOME_PRINCIPALE}\033[0m"
echo "Impronta della radice:  ${IMPRONTA}"
echo "Radice da installare sui dispositivi: /etc/step-ca/certs/root_ca.crt (pct pull ${CTID} ...)"
echo "Directory ACME:         https://${NOME_PRINCIPALE}/acme/acme/directory"
echo "Nomi ammessi:           ${DOMINIO}, *.${DOMINIO}${RETI:+, IP in ${RETI}}"
echo
echo "Gestionale con rinnovo automatico (token monouso, valido pochi minuti):"
echo "  sul container della CA:  token-certificato gestionale.${DOMINIO} gestionale IP"
echo "  sul server:              installa.sh --tls-step https://${NOME_PRINCIPALE} --tls-ca-impronta ${IMPRONTA} --tls-step-token <token>"
echo
echo "Il nome ${NOME_PRINCIPALE} va registrato nel DNS locale. Le chiavi della CA sono in /etc/step-ca:"
echo "includere il container nei backup e non copiarle altrove. Root del container: ${PASSWORD_ROOT}"
