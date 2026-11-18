# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Messaggio di benvenuto dell'host con più istanze (scripts/proxmox/sezioni.sh):
# *              per ogni sezione indirizzo, versione, servizi e ultimo backup, più carico,
# *              memoria, disco e PostgreSQL. Installato in /etc/profile.d; sintassi POSIX.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

case $- in *i*) ;; *) return 0 2>/dev/null || exit 0 ;; esac

_gs_motd() {
  b=$(printf '\033[1m'); g=$(printf '\033[1;32m'); r=$(printf '\033[1;31m')
  y=$(printf '\033[1;33m'); c=$(printf '\033[1;36m'); d=$(printf '\033[2m'); n=$(printf '\033[0m')
  ip=$(hostname -I 2>/dev/null | awk '{print $1}')
  sistema=$(. /etc/os-release 2>/dev/null && echo "$NAME $(cat /etc/debian_version 2>/dev/null)")
  pallino() { if systemctl is-active --quiet "$1" 2>/dev/null; then printf '%s●%s' "$g" "$n"; else printf '%s●%s' "$r" "$n"; fi; }
  carico=$(cut -d' ' -f1-3 /proc/loadavg)
  memoria=$(free -m | awk '/^Mem:/ {printf "%d/%d MB", $3, $2}')
  disco=$(df -h / | awk 'NR==2 {print $3"/"$2" ("$5")"}')
  pg=$(systemctl is-active --quiet postgresql && echo "${g}● attivo${n}" || echo "${r}● fermo${n}")

  echo
  echo "  ${c}${b}Gestione Associazione${n} ${b}· sezioni${n}  ${d}· $(hostname) · ${ip}${n}"
  echo "  ${d}──────────────────────────────────────────────────────────────────────${n}"
  echo "  Sistema     ${sistema:-Debian} · carico ${carico} · RAM ${memoria} · disco ${disco}"
  echo "  PostgreSQL  ${pg}  ${d}(un database per sezione)${n}"
  echo "  ${d}──────────────────────────────────────────────────────────────────────${n}"
  printf "  ${d}%-20s %-30s %-8s %-5s %s${n}\n" "sezione" "indirizzo" "versione" "w p" "ultimo backup"
  grep -Ev '^[[:space:]]*(#|$)|=' /etc/gestione-sezioni.conf 2>/dev/null | while read -r i p _; do
    v=$(grep -m1 '^APP_VERSIONE' "/opt/sezione-$i/config/settings.py" 2>/dev/null | cut -d'"' -f2)
    proto=http; [ -f "/etc/sezione-$i/tls/cert.pem" ] && proto=https
    bk=$(ls -1t "/var/lib/sezione-$i/backup" 2>/dev/null | head -1)
    if [ -n "$bk" ]; then bk=$(date -r "/var/lib/sezione-$i/backup/$bk" '+%d/%m %H:%M'); else bk="${y}nessuno${n}"; fi
    printf "  %-20s %-30s %-8s %s %s  %s\n" "$i" "${proto}://${ip}:${p}/" "${v:-?}" \
      "$(pallino "gestione-$i")" "$(pallino "gestione-$i-pianificatore")" "$bk"
  done
  echo "  ${d}──────────────────────────────────────────────────────────────────────${n}"
  echo "  Stato       bash /root/gestione-associazione-src/scripts/proxmox/sezioni.sh stato"
  echo "  Aggiornare  cd /root/gestione-associazione-src && git fetch --tags && git checkout <tag>"
  echo "              && bash scripts/proxmox/sezioni.sh aggiorna"
  echo "  Log         journalctl -u gestione-<sezione> -f"
  echo "  Comandi     runuser -u sezione_<sezione> -- /opt/sezione-<sezione>/.venv/bin/python \\"
  echo "                /opt/sezione-<sezione>/manage.py <comando>"
  if ls /root/gestione-*-credenziali.txt >/dev/null 2>&1; then
    echo
    echo "  ${y}Attenzione:${n} in /root/gestione-*-credenziali.txt ci sono le password iniziali"
    echo "  degli amministratori: dopo il primo accesso cancellarle."
  fi
  echo
}
_gs_motd
unset -f _gs_motd pallino
