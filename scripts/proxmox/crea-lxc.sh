#!/usr/bin/env bash
# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Da eseguire sull'host Proxmox VE: crea un container LXC Debian non privilegiato
# *              e vi installa Gestione Associazione con PostgreSQL e systemd (senza Docker),
# *              usando scripts/installa.sh. Con --aggiorna aggiorna un container esistente.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
set -euo pipefail

REPO_PREDEFINITO="https://mygitlab.iz0bec.info/sbart64/gestione_associazione.git"
CTID=""
NOME="gestione-associazione"
STORAGE="local-lvm"
STORAGE_TEMPLATE="local"
DISCO=8
RAM=2048
CORE=2
BRIDGE="vmbr0"
IP="dhcp"
GW=""
DNS=""
PORTA=8000
EMAIL=""
PASSWORD_ROOT=""
CHIAVE_SSH=""
SORGENTE="$REPO_PREDEFINITO"
VERSIONE="main"
DEBIAN="13"
AGGIORNA=0
SRC_CT="/root/gestione-associazione-src"

uso() {
  cat <<EOF
Uso: $0 [opzioni]
Creazione di un nuovo container:
  --id N                  numero del container (predefinito: il primo libero)
  --nome NOME             hostname (predefinito ${NOME})
  --storage NOME          storage del disco (predefinito ${STORAGE})
  --storage-template NOME storage dei template (predefinito ${STORAGE_TEMPLATE})
  --disco GB              dimensione del disco (predefinita ${DISCO})
  --ram MB                memoria (predefinita ${RAM})
  --core N                CPU (predefinite ${CORE})
  --bridge NOME           bridge di rete (predefinito ${BRIDGE})
  --ip dhcp|IP/CIDR       indirizzo (predefinito dhcp), es. 192.168.0.40/24
  --gw IP                 gateway (con IP statico)
  --dns IP                server DNS (facoltativo)
  --debian 12|13          versione di Debian (predefinita ${DEBIAN})
  --password-root PWD     password di root del container (altrimenti generata)
  --chiave-ssh FILE       chiave pubblica SSH per root (facoltativa)
Applicazione:
  --sorgente URL|DIR      repository git o cartella locale del codice (predefinito ${REPO_PREDEFINITO})
  --versione TAG|RAMO     versione da installare (predefinita ${VERSIONE}), es. v0.0.1-rc.1
  --porta N               porta web (predefinita ${PORTA})
  --email EMAIL           email dell'amministratore
Aggiornamento:
  --aggiorna --id N [--versione TAG] [--sorgente ...]   aggiorna il container N
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
    --sorgente) SORGENTE="$2"; shift 2 ;;
    --versione) VERSIONE="$2"; shift 2 ;;
    --porta) PORTA="$2"; shift 2 ;;
    --email) EMAIL="$2"; shift 2 ;;
    --aggiorna) AGGIORNA=1; shift ;;
    -h|--help) uso; exit 0 ;;
    *) echo "Opzione sconosciuta: $1"; uso; exit 1 ;;
  esac
done

passo() { echo -e "\n\033[1;34m==> $*\033[0m"; }
errore() { echo -e "\033[1;31mERRORE: $*\033[0m" >&2; exit 1; }
nel_ct() { pct exec "$CTID" -- "$@"; }

[[ $EUID -eq 0 ]] || errore "eseguire come root sull'host Proxmox."
command -v pct >/dev/null && command -v pveam >/dev/null || errore "comandi pct/pveam non trovati: eseguire sull'host Proxmox VE."

copia_codice() {
  passo "Codice (${SORGENTE}, ${VERSIONE})"
  nel_ct rm -rf "$SRC_CT"
  if [[ -d "$SORGENTE" ]]; then
    local archivio
    archivio="$(mktemp --suffix=.tar.gz)"
    tar -C "$SORGENTE" --exclude .git --exclude .venv --exclude var --exclude tmp -czf "$archivio" .
    pct push "$CTID" "$archivio" /root/sorgente.tar.gz
    rm -f "$archivio"
    nel_ct bash -c "mkdir -p '$SRC_CT' && tar -xzf /root/sorgente.tar.gz -C '$SRC_CT' && rm /root/sorgente.tar.gz"
  else
    nel_ct git clone --quiet --depth 1 --branch "$VERSIONE" "$SORGENTE" "$SRC_CT"
  fi
}

# Messaggio di benvenuto al login, alla maniera degli script di community-scripts.org:
# sostituisce quello di Debian e si ricalcola a ogni accesso (vedi scripts/proxmox/motd.sh).
installa_motd() {
  passo "Messaggio di benvenuto (motd)"
  nel_ct bash -c "sed 's/@CTID@/${CTID}/g' '${SRC_CT}/scripts/proxmox/motd.sh' > /etc/profile.d/00-gestione-associazione.sh \
    && chmod 644 /etc/profile.d/00-gestione-associazione.sh && : > /etc/motd \
    && { chmod -x /etc/update-motd.d/* 2>/dev/null || true; }"
}

if [[ $AGGIORNA -eq 1 ]]; then
  [[ -n "$CTID" ]] || errore "indicare --id del container da aggiornare."
  pct status "$CTID" | grep -q running || pct start "$CTID"
  copia_codice
  passo "Aggiornamento (con backup automatico prima)"
  nel_ct bash "${SRC_CT}/scripts/installa.sh" -y
  installa_motd
  exit 0
fi

[[ -n "$CTID" ]] || CTID="$(pvesh get /cluster/nextid)"
pct status "$CTID" >/dev/null 2>&1 && errore "il container ${CTID} esiste già (per aggiornarlo: --aggiorna --id ${CTID})."
[[ "$IP" == "dhcp" || "$IP" == */* ]] || errore "--ip deve essere dhcp oppure IP/CIDR (es. 192.168.0.40/24)."

passo "Template Debian ${DEBIAN}"
pveam update >/dev/null
# Solo l'architettura dell'host: il catalogo contiene anche i template arm64, che
# nell'ordinamento seguono gli amd64 e su un host x86_64 non si avviano.
ARCH="$(dpkg --print-architecture)"
TEMPLATE="$(pveam available --section system | awk -v d="debian-${DEBIAN}-standard" -v a="_${ARCH}." '$2 ~ d && index($2, a) {print $2}' | sort -V | tail -1)"
[[ -n "$TEMPLATE" ]] || errore "template debian-${DEBIAN}-standard (${ARCH}) non disponibile."
pveam list "$STORAGE_TEMPLATE" | grep -q "$TEMPLATE" || pveam download "$STORAGE_TEMPLATE" "$TEMPLATE"

passo "Creazione del container ${CTID} (${NOME})"
[[ -n "$PASSWORD_ROOT" ]] || PASSWORD_ROOT="$(head -c 32 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 20)"
RETE="name=eth0,bridge=${BRIDGE},ip=${IP}"
[[ -n "$GW" ]] && RETE="${RETE},gw=${GW}"
OPZIONI=(
  --hostname "$NOME" --cores "$CORE" --memory "$RAM" --swap 512
  --rootfs "${STORAGE}:${DISCO}" --net0 "$RETE" --unprivileged 1 --features nesting=1
  --onboot 1 --timezone host --password "$PASSWORD_ROOT"
  --description "Gestione Associazione (${VERSIONE}) - https://mygitlab.iz0bec.info/sbart64/gestione_associazione"
)
[[ -n "$DNS" ]] && OPZIONI+=(--nameserver "$DNS")
[[ -n "$CHIAVE_SSH" ]] && OPZIONI+=(--ssh-public-keys "$CHIAVE_SSH")
pct create "$CTID" "${STORAGE_TEMPLATE}:vztmpl/${TEMPLATE}" "${OPZIONI[@]}"
pct start "$CTID"

passo "Attesa della rete"
for _ in $(seq 1 60); do
  nel_ct getent hosts deb.debian.org >/dev/null 2>&1 && break
  sleep 2
done
nel_ct getent hosts deb.debian.org >/dev/null 2>&1 || errore "il container non raggiunge Internet."

passo "Pacchetti di base"
nel_ct bash -c "export DEBIAN_FRONTEND=noninteractive; apt-get update -qq && apt-get -y -qq upgrade >/dev/null && apt-get install -y -qq git curl ca-certificates locales >/dev/null"
nel_ct bash -c "sed -i 's/^# *it_IT.UTF-8/it_IT.UTF-8/' /etc/locale.gen && locale-gen >/dev/null && update-locale LANG=it_IT.UTF-8"

copia_codice

passo "Installazione dell'applicazione"
ARG=(-y --porta "$PORTA")
[[ -n "$EMAIL" ]] && ARG+=(--email "$EMAIL")
nel_ct bash "${SRC_CT}/scripts/installa.sh" "${ARG[@]}"
installa_motd

INDIRIZZO_CT="$(nel_ct hostname -I | awk '{print $1}')"
echo -e "\n\033[1;32mContainer ${CTID} pronto: http://${INDIRIZZO_CT}:${PORTA}/\033[0m"
echo "Root del container: password ${PASSWORD_ROOT} (pct enter ${CTID})"
nel_ct cat /root/gestione-associazione-credenziali.txt 2>/dev/null || true
echo "Aggiornare in seguito con: $0 --aggiorna --id ${CTID} --versione <tag>"
