#!/usr/bin/env bash
# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Più installazioni sullo stesso host (una per sezione, PostgreSQL condiviso):
# *              elenco in /etc/gestione-sezioni.conf («istanza porta» per riga, più le
# *              impostazioni DOMINIO=schema con {sezione} e PROXY=IP del reverse proxy),
# *              aggiornamento di tutte con installa.sh --istanza, stato e motd. Da eseguire come root.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
set -euo pipefail
export PATH="/usr/local/bin:${PATH}"
CONF="/etc/gestione-sezioni.conf"
DIR_SCRIPT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SORGENTE="$(cd "${DIR_SCRIPT}/../.." && pwd)"

uso() {
  cat <<USO
Uso: $0 comando [istanza...]
  aggiungi ISTANZA PORTA [opzioni di installa.sh]   nuova installazione, registrata in ${CONF}
  aggiorna [istanza...]   aggiorna tutte (o quelle indicate) al codice di ${SORGENTE}
  stato                   servizi, porte e ultimo backup di ogni istanza
  motd                    installa il messaggio di benvenuto per tutte le istanze
  imposta CHIAVE VALORE   impostazione comune a tutte le istanze, applicata da aggiungi e aggiorna:
                            DOMINIO  nome pubblico, con {sezione} (es. sez-{sezione}.associazione.it)
                            PROXY    IP del reverse proxy HTTPS (es. 192.168.1.10)
USO
}

istanze() { [[ -f "$CONF" ]] && grep -Ev '^\s*(#|$)|=' "$CONF" || true; }
porta_di() { istanze | awk -v i="$1" '$1==i {print $2}'; }
impostazione() { [[ -f "$CONF" ]] && grep -m1 "^$1=" "$CONF" | cut -d= -f2- || true; }
# opzioni di installa.sh per il reverse proxy, dalle impostazioni comuni
opzioni_rete() {
  local dominio proxy
  dominio="$(impostazione DOMINIO)"; proxy="$(impostazione PROXY)"
  [[ -n "$dominio" ]] && echo "--dominio ${dominio//\{sezione\}/$1}"
  [[ -n "$proxy" ]] && echo "--proxy ${proxy}"
  true
}
crea_conf() { [[ -f "$CONF" ]] || echo "# istanza porta  (gestito da scripts/proxmox/sezioni.sh)" > "$CONF"; }

[[ $EUID -eq 0 ]] || { echo "Eseguire come root."; exit 1; }
comando="${1:-}"; shift || true
case "$comando" in
  aggiungi)
    [[ $# -ge 2 ]] || { uso; exit 1; }
    istanza="$1"; porta="$2"; shift 2
    [[ -z "$(porta_di "$istanza")" ]] || { echo "Istanza ${istanza} già presente."; exit 1; }
    istanze | awk -v p="$porta" '$2==p {f=1} END {exit !f}' && { echo "Porta ${porta} già usata."; exit 1; }
    # shellcheck disable=SC2046
    bash "${SORGENTE}/scripts/installa.sh" --istanza "$istanza" --porta "$porta" --worker 2 -y \
      $(opzioni_rete "$istanza") "$@"
    crea_conf
    echo "${istanza} ${porta}" >> "$CONF"
    ;;
  aggiorna)
    scelte=("$@"); falliti=()
    while read -r istanza porta _; do
      if [[ ${#scelte[@]} -gt 0 && ! " ${scelte[*]} " == *" ${istanza} "* ]]; then continue; fi
      echo -e "\n\033[1;35m######## ${istanza} (porta ${porta})\033[0m"
      # shellcheck disable=SC2046
      bash "${SORGENTE}/scripts/installa.sh" --istanza "$istanza" -y $(opzioni_rete "$istanza") \
        || falliti+=("$istanza")
    done < <(istanze)
    [[ ${#falliti[@]} -eq 0 ]] || { echo -e "\033[1;31mNon aggiornate: ${falliti[*]}\033[0m"; exit 1; }
    ;;
  stato)
    printf '%-22s %-6s %-9s %-13s %s\n' ISTANZA PORTA VERSIONE "WEB/PIANIF." "ULTIMO BACKUP"
    while read -r istanza porta _; do
      v=$(grep -m1 '^APP_VERSIONE' "/opt/sezione-${istanza}/config/settings.py" 2>/dev/null | cut -d'"' -f2)
      w=$(systemctl is-active "gestione-${istanza}" 2>/dev/null || true)
      p=$(systemctl is-active "gestione-${istanza}-pianificatore" 2>/dev/null || true)
      b=$(ls -1t "/var/lib/sezione-${istanza}/backup" 2>/dev/null | head -1)
      [[ -n "$b" ]] && b=$(date -r "/var/lib/sezione-${istanza}/backup/$b" '+%d/%m/%Y %H:%M')
      printf '%-22s %-6s %-9s %-13s %s\n' "$istanza" "$porta" "${v:-?}" "${w}/${p}" "${b:-nessuno}"
    done < <(istanze)
    ;;
  imposta)
    [[ $# -eq 2 && "$1" =~ ^(DOMINIO|PROXY)$ ]] || { uso; exit 1; }
    crea_conf
    if grep -q "^$1=" "$CONF"; then sed -i "s|^$1=.*|$1=$2|" "$CONF"; else echo "$1=$2" >> "$CONF"; fi
    echo "$1=$2 (applicato da «aggiungi» e «aggiorna»)"
    ;;
  motd)
    install -m 644 "${DIR_SCRIPT}/motd-sezioni.sh" /etc/profile.d/00-gestione-sezioni.sh
    : > /etc/motd; chmod -x /etc/update-motd.d/* 2>/dev/null || true
    echo "Messaggio di benvenuto installato."
    ;;
  *) uso; [[ -z "$comando" || "$comando" == -h || "$comando" == --help ]] || exit 1 ;;
esac
