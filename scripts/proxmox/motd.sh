# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Messaggio di benvenuto del container LXC (installato da crea-lxc.sh in
# *              /etc/profile.d): versione, indirizzo, stato dei servizi, ultimo backup e
# *              comandi utili, calcolati a ogni accesso. Sintassi POSIX (letto da /etc/profile).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

# Solo nelle shell interattive: niente output per scp, rsync o comandi remoti.
case $- in *i*) ;; *) return 0 2>/dev/null || exit 0 ;; esac

_ga_motd() {
  app=/opt/gestione-associazione
  dati=/var/lib/gestione-associazione
  unita=/etc/systemd/system/gestione-associazione.service
  ctid="@CTID@"

  b=$(printf '\033[1m'); g=$(printf '\033[1;32m'); r=$(printf '\033[1;31m')
  y=$(printf '\033[1;33m'); c=$(printf '\033[1;36m'); d=$(printf '\033[2m'); n=$(printf '\033[0m')

  versione=$(grep -m1 '^APP_VERSIONE' "$app/config/settings.py" 2>/dev/null | cut -d'"' -f2)
  porta=$(grep -o -- '--bind [^ ]*' "$unita" 2>/dev/null | sed 's/.*://')
  ip=$(hostname -I 2>/dev/null | awk '{print $1}')
  sistema=$(. /etc/os-release 2>/dev/null && echo "$NAME $(cat /etc/debian_version 2>/dev/null)")

  stato() {
    if systemctl is-active --quiet "$1" 2>/dev/null; then echo "${g}● attivo${n}"; else echo "${r}● fermo${n}"; fi
  }

  ultimo=$(ls -1t "$dati/backup" 2>/dev/null | head -1)
  if [ -n "$ultimo" ]; then
    ultimo="$(date -r "$dati/backup/$ultimo" '+%d/%m/%Y %H:%M' 2>/dev/null) ${d}($ultimo)${n}"
  else
    ultimo="${y}nessuno${n}"
  fi

  echo
  echo "  ${c}${b}Gestione Associazione${n} ${b}${versione:-?}${n}  ${d}· container LXC ${ctid}${n}"
  echo "  ${d}──────────────────────────────────────────────────${n}"
  echo "  Indirizzo     ${b}http://${ip:-?}:${porta:-8000}/${n}"
  echo "  Sistema       ${sistema:-Debian} · $(hostname)"
  echo "  Servizi       web $(stato gestione-associazione)   pianificatore $(stato gestione-associazione-pianificatore)"
  echo "  Ultimo backup ${ultimo}"
  echo "  ${d}──────────────────────────────────────────────────${n}"
  echo "  Log           journalctl -u gestione-associazione -f"
  echo "  Comandi       runuser -u gestione -- $app/.venv/bin/python $app/manage.py <comando>"
  echo "  Aggiornare    sull'host Proxmox: bash crea-lxc.sh --aggiorna --id ${ctid} --versione <tag>"
  if [ -f /root/gestione-associazione-credenziali.txt ]; then
    echo
    echo "  ${y}Attenzione:${n} /root/gestione-associazione-credenziali.txt contiene la password"
    echo "  iniziale dell'amministratore: dopo il primo accesso cancellarlo."
  fi
  echo
}
_ga_motd
unset -f _ga_motd stato
