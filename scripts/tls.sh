# shellcheck shell=bash
# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: HTTPS dell'installatore (incluso da installa.sh): certificato da file, autofirmato,
# *              da una CA ACME (certbot) o da step-ca con token monouso, con rinnovo automatico e
# *              riavvio del servizio quando il certificato cambia. Nessuna password sul server.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
# shellcheck disable=SC2034  # TLS e OPZ_TLS sono usate da installa.sh
# Usa le variabili di installa.sh: NOME, UTENTE, DIR_TLS, ADMIN_EMAIL, TLS_* e le funzioni
# passo/errore. Tutte le funzioni sono rieseguibili.

DIR_STEP="/etc/${NOME}/step"
CA_SISTEMA="/usr/local/share/ca-certificates/${NOME}-ca.crt"
UNITA_RINNOVO="/etc/systemd/system/${NOME}-tls-rinnovo"
HOOK_CERTBOT="${DIR_TLS}/da-certbot.sh"

tls_controlla_opzioni() {
  local modi=0
  [[ -n "$TLS_CERT" || -n "$TLS_KEY" ]] && modi=$((modi + 1))
  [[ $TLS_AUTOFIRMATO -eq 1 ]] && modi=$((modi + 1))
  [[ -n "$TLS_ACME" ]] && modi=$((modi + 1))
  [[ -n "$TLS_STEP" ]] && modi=$((modi + 1))
  [[ $TLS_DISATTIVA -eq 1 ]] && modi=$((modi + 1))
  [[ $modi -le 1 ]] || errore "scegliere un solo modo per l'HTTPS."
  if [[ -n "$TLS_CERT" || -n "$TLS_KEY" ]]; then
    [[ -n "$TLS_CERT" && -n "$TLS_KEY" ]] || errore "servono sia --tls-cert sia --tls-key."
    [[ -r "$TLS_CERT" && -r "$TLS_KEY" ]] || errore "certificato o chiave non leggibili."
  fi
  if [[ -n "$TLS_STEP" ]]; then
    [[ "$TLS_STEP" == https://* ]] || errore "--tls-step: indirizzo https:// della CA."
    [[ -n "$TLS_STEP_TOKEN" ]] || errore "--tls-step richiede --tls-step-token (step ca token NOME --san ...)."
    [[ -n "$TLS_CA" || -n "$TLS_CA_IMPRONTA" ]] || errore "--tls-step richiede --tls-ca o --tls-ca-impronta."
  fi
  [[ -z "$TLS_ACME" || "$TLS_ACME" == https://* ]] || errore "--tls-acme: indirizzo https:// della directory ACME."
  [[ -z "$TLS_CA" || -r "$TLS_CA" ]] || errore "--tls-ca: file non leggibile."
  if [[ -n "$TLS_CA_IMPRONTA" && -z "$TLS_STEP" && -z "$TLS_ACME" ]]; then
    errore "--tls-ca-impronta si usa con --tls-step o --tls-acme."
  fi
  return 0
}

# impronta SHA-256 (base64) della chiave pubblica: per verificare il certificato «per impronta»
impronta_spki() {
  openssl x509 -in "$1" -pubkey -noout | openssl pkey -pubin -outform der \
    | openssl dgst -sha256 -binary | openssl enc -base64
}

# impronta SHA-256 di un certificato, esadecimale minuscola senza separatori (formato di step)
impronta_cert() {
  openssl x509 -in "$1" -noout -fingerprint -sha256 | cut -d= -f2 | tr -d ':' | tr 'A-F' 'a-f'
}

# prima la chiave, poi il certificato: il riavvio automatico scatta sul certificato
tls_installa_file() {
  install -o root -g "$UTENTE" -m 640 "$2" "${DIR_TLS}/key.pem"
  install -o root -g "$UTENTE" -m 644 "$1" "${DIR_TLS}/cert.pem"
}

tls_apt() {
  local mancanti=() p
  for p in "$@"; do
    dpkg-query -W -f='${Status}' "$p" 2>/dev/null | grep -q "install ok installed" || mancanti+=("$p")
  done
  [[ ${#mancanti[@]} -eq 0 ]] && return 0
  apt-get update -qq
  apt-get install -y -qq --no-install-recommends "${mancanti[@]}" >/dev/null
}

# Radice della CA privata nell'archivio del sistema (servirà anche ai collegamenti fra installazioni).
# Stampa l'impronta della radice installata.
tls_radice() {
  local tmp base atteso
  tmp="$(mktemp)"
  if [[ -n "$TLS_CA" ]]; then
    openssl x509 -in "$TLS_CA" -noout 2>/dev/null || errore "${TLS_CA}: non è un certificato PEM."
    cp "$TLS_CA" "$tmp"
  else
    # step-ca pubblica la radice in /root/<impronta>: scaricata senza verifica (non la si conosce
    # ancora) e accettata solo se l'impronta coincide con quella indicata
    base="$(sed -E 's#^(https://[^/]+).*#\1#' <<< "${TLS_STEP:-$TLS_ACME}")"
    atteso="$(tr -d ': ' <<< "$TLS_CA_IMPRONTA" | tr 'A-F' 'a-f')"
    # risposta JSON {"ca":"-----BEGIN CERTIFICATE-----\n..."}: si estrae il PEM
    curl -fsSk --max-time 20 "${base}/root/${atteso}" \
      | sed -e 's/^[^"]*"ca" *: *"//' -e 's/".*$//' -e 's/\\n/\n/g' > "$tmp" \
      || errore "radice non scaricabile da ${base}/root/${atteso}: impronta errata o CA non raggiungibile."
    openssl x509 -in "$tmp" -noout 2>/dev/null || errore "la CA non ha restituito un certificato."
    [[ "$(impronta_cert "$tmp")" == "$atteso" ]] || errore "l'impronta della radice non coincide con --tls-ca-impronta."
  fi
  install -m 644 "$tmp" "$CA_SISTEMA"
  rm -f "$tmp"
  update-ca-certificates >/dev/null 2>&1 || errore "update-ca-certificates non riuscito."
  impronta_cert "$CA_SISTEMA"
}

# Spegne i rinnovi di un modo precedente (si chiama solo quando si sceglie un modo nuovo).
tls_ferma_rinnovi() {
  if [[ -f "${UNITA_RINNOVO}.timer" ]]; then
    systemctl disable --now "${NOME}-tls-rinnovo.timer" >/dev/null 2>&1 || true
    rm -f "${UNITA_RINNOVO}.timer" "${UNITA_RINNOVO}.service"
    systemctl daemon-reload
  fi
  if [[ -d "/etc/letsencrypt/renewal" && -f "/etc/letsencrypt/renewal/${NOME}.conf" ]] && command -v certbot >/dev/null; then
    certbot delete -n --cert-name "$NOME" >/dev/null 2>&1 || true
  fi
  rm -f "$HOOK_CERTBOT" "${DIR_TLS}/fonte"
}

tls_da_file() {
  openssl x509 -in "$TLS_CERT" -noout 2>/dev/null || errore "${TLS_CERT}: non è un certificato PEM."
  openssl pkey -in "$TLS_KEY" -noout 2>/dev/null || errore "${TLS_KEY}: non è una chiave privata PEM (senza password)."
  [[ "$(openssl x509 -in "$TLS_CERT" -pubkey -noout)" == "$(openssl pkey -in "$TLS_KEY" -pubout)" ]] \
    || errore "la chiave non corrisponde al certificato."
  openssl x509 -in "$TLS_CERT" -noout -checkend 0 >/dev/null || errore "il certificato è scaduto."
  tls_ferma_rinnovi
  tls_installa_file "$TLS_CERT" "$TLS_KEY"
  echo file > "${DIR_TLS}/fonte"
  echo "Certificato installato: $(openssl x509 -in "${DIR_TLS}/cert.pem" -noout -subject -enddate | tr '\n' ' ')"
}

tls_autofirmato() {
  local san fqdn cn n extra=() chiave=()
  san="DNS:$(hostname)"
  fqdn="$(hostname -f 2>/dev/null || true)"
  [[ -n "$fqdn" && "$fqdn" != "$(hostname)" ]] && san="${san},DNS:${fqdn}"
  for n in $(hostname -I 2>/dev/null); do san="${san},IP:${n}"; done
  san="${san},DNS:localhost,IP:127.0.0.1"
  IFS=',' read -r -a extra <<< "$TLS_NOMI"
  for n in "${extra[@]}"; do
    n="${n// /}"; [[ -z "$n" ]] && continue
    if [[ "$n" =~ ^[0-9.]+$ || "$n" == *:* ]]; then san="${san},IP:${n}"; else san="${san},DNS:${n}"; fi
  done
  cn="${fqdn:-$(hostname)}"
  # rinnovando si riusa la chiave: l'impronta SPKI non cambia
  if [[ -f "${DIR_TLS}/key.pem" ]]; then chiave=(-key "${DIR_TLS}/key.pem")
  else chiave=(-newkey ec -pkeyopt ec_paramgen_curve:P-256 -noenc -keyout "${DIR_TLS}/key.pem.nuova"); fi
  ( umask 077
    openssl req -x509 "${chiave[@]}" -sha256 -days 825 \
      -out "${DIR_TLS}/cert.pem.nuovo" -subj "/CN=${cn}" \
      -addext "subjectAltName=${san}" -addext "basicConstraints=critical,CA:FALSE" \
      -addext "extendedKeyUsage=serverAuth" 2>/dev/null ) || errore "creazione del certificato autofirmato non riuscita."
  tls_ferma_rinnovi
  [[ -f "${DIR_TLS}/key.pem.nuova" ]] && mv -f "${DIR_TLS}/key.pem.nuova" "${DIR_TLS}/key.pem"
  chown root:"$UTENTE" "${DIR_TLS}/key.pem"; chmod 640 "${DIR_TLS}/key.pem"
  install -o root -g "$UTENTE" -m 644 "${DIR_TLS}/cert.pem.nuovo" "${DIR_TLS}/cert.pem"
  rm -f "${DIR_TLS}/cert.pem.nuovo"
  echo autofirmato > "${DIR_TLS}/fonte"
  echo "Certificato autofirmato per: ${san}"
}

# step-ca: primo certificato con un token monouso generato da chi amministra la CA
# (step ca token NOME --san ...), rinnovi con «step ca renew», che si autentica con il certificato
# in corso: sul server non resta nessuna password.
tls_step() {
  local fp step sub tmp
  if ! command -v step >/dev/null; then
    echo "Installazione di step-cli (repository Smallstep)"
    tls_apt curl gpg ca-certificates
    curl -fsSL https://packages.smallstep.com/keys/apt/repo-signing-key.gpg -o /etc/apt/trusted.gpg.d/smallstep.asc
    echo 'deb [signed-by=/etc/apt/trusted.gpg.d/smallstep.asc] https://packages.smallstep.com/stable/debian debs main' \
      > /etc/apt/sources.list.d/smallstep.list
    apt-get update -qq
    apt-get install -y -qq --no-install-recommends step-cli >/dev/null
  fi
  step="$(command -v step)"
  fp="$(tls_radice)"
  install -d -o root -g root -m 700 "$DIR_STEP"
  STEPPATH="$DIR_STEP" "$step" ca bootstrap --ca-url "$TLS_STEP" --fingerprint "$fp" --force >/dev/null 2>&1 \
    || errore "collegamento alla CA ${TLS_STEP} non riuscito (step ca bootstrap)."
  sub="$("$step" crypto jwt inspect --insecure <<< "$TLS_STEP_TOKEN" 2>/dev/null \
    | sed -n 's/^ *"sub": *"\([^"]*\)".*/\1/p' | head -1)"
  [[ -n "$sub" ]] || errore "token non valido (step ca token NOME --san ...)."
  tmp="$(mktemp -d)"
  STEPPATH="$DIR_STEP" "$step" ca certificate "$sub" "${tmp}/cert.pem" "${tmp}/key.pem" \
    --token "$TLS_STEP_TOKEN" --force >/dev/null 2>"${tmp}/errore" \
    || { cat "${tmp}/errore" >&2; rm -rf "$tmp"; errore "emissione del certificato non riuscita (il token vale pochi minuti ed è monouso)."; }
  tls_ferma_rinnovi
  tls_installa_file "${tmp}/cert.pem" "${tmp}/key.pem"
  rm -rf "$tmp"
  cat > "${UNITA_RINNOVO}.service" <<EOF
[Unit]
Description=Gestione Associazione - rinnovo del certificato HTTPS (step-ca)
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
Environment=STEPPATH=${DIR_STEP}
# rinnova solo dopo due terzi della validità
ExecCondition=${step} certificate needs-renewal ${DIR_TLS}/cert.pem
ExecStart=/bin/sh -c '${step} ca renew --force --out ${DIR_TLS}/cert.pem.nuovo ${DIR_TLS}/cert.pem ${DIR_TLS}/key.pem && install -o root -g ${UTENTE} -m 644 ${DIR_TLS}/cert.pem.nuovo ${DIR_TLS}/cert.pem && rm -f ${DIR_TLS}/cert.pem.nuovo'
EOF
  cat > "${UNITA_RINNOVO}.timer" <<EOF
[Unit]
Description=Gestione Associazione - controllo del certificato HTTPS due volte al giorno

[Timer]
OnCalendar=*-*-* 03,15:00:00
RandomizedDelaySec=1h
Persistent=true

[Install]
WantedBy=timers.target
EOF
  systemctl daemon-reload
  systemctl enable --now "${NOME}-tls-rinnovo.timer" >/dev/null 2>&1
  echo step > "${DIR_TLS}/fonte"
  echo "Certificato da ${TLS_STEP}: $(openssl x509 -in "${DIR_TLS}/cert.pem" -noout -subject -enddate | tr '\n' ' ')"
}

# ACME (step-ca con provisioner ACME, Let's Encrypt, ...): certbot in modalità standalone, verifica
# http-01 sulla porta 80, rinnovo con certbot.timer.
tls_acme() {
  local nomi=() n extra=() fqdn email=()
  if ss -Hltn 'sport = :80' 2>/dev/null | grep -q .; then
    errore "la porta 80 è occupata (es. da un proxy): la verifica ACME http-01 non può funzionare. Con step-ca usare --tls-step; altrimenti ottenere il certificato dal proxy e usare --tls-cert/--tls-key."
  fi
  tls_apt certbot
  if [[ -n "$TLS_CA" || -n "$TLS_CA_IMPRONTA" ]]; then
    tls_radice >/dev/null
    # certbot (requests) usa l'archivio del sistema, compresa la radice appena aggiunta
    install -d /etc/systemd/system/certbot.service.d
    printf '[Service]\nEnvironment=REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt\n' \
      > "/etc/systemd/system/certbot.service.d/${NOME}.conf"
    systemctl daemon-reload
  fi
  IFS=',' read -r -a extra <<< "$TLS_NOMI"
  for n in "${extra[@]}"; do
    n="${n// /}"; [[ -z "$n" ]] && continue
    if [[ "$n" =~ ^[0-9.]+$ || "$n" == *:* ]]; then echo "Indirizzo IP ${n} ignorato: con ACME solo nomi."; continue; fi
    nomi+=(-d "$n")
  done
  fqdn="$(hostname -f 2>/dev/null || true)"
  [[ ${#nomi[@]} -eq 0 && "$fqdn" == *.* ]] && nomi=(-d "$fqdn")
  [[ ${#nomi[@]} -gt 0 ]] || errore "con --tls-acme indicare i nomi con --tls-nomi (raggiungibili dalla CA sulla porta 80)."
  if [[ -n "$ADMIN_EMAIL" ]]; then email=(--email "$ADMIN_EMAIL"); else email=(--register-unsafely-without-email); fi
  tls_ferma_rinnovi
  cat > "$HOOK_CERTBOT" <<EOF
#!/bin/sh
# Generato da scripts/installa.sh: copia il certificato rinnovato da certbot (riavvio automatico).
set -e
install -o root -g ${UTENTE} -m 640 "\$RENEWED_LINEAGE/privkey.pem" ${DIR_TLS}/key.pem
install -o root -g ${UTENTE} -m 644 "\$RENEWED_LINEAGE/fullchain.pem" ${DIR_TLS}/cert.pem
EOF
  chmod 750 "$HOOK_CERTBOT"
  REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt certbot certonly --standalone -n --agree-tos \
    --server "$TLS_ACME" --cert-name "$NOME" "${email[@]}" "${nomi[@]}" --deploy-hook "$HOOK_CERTBOT" \
    || errore "certbot non ha ottenuto il certificato: la CA deve risolvere i nomi e raggiungere questo server sulla porta 80."
  systemctl enable --now certbot.timer >/dev/null 2>&1 || true
  echo acme > "${DIR_TLS}/fonte"
  echo "Certificato ACME: $(openssl x509 -in "${DIR_TLS}/cert.pem" -noout -subject -issuer -enddate | tr '\n' ' ')"
}

tls_disattiva() {
  local f
  tls_ferma_rinnovi
  for f in cert.pem key.pem; do
    [[ -f "${DIR_TLS}/${f}" ]] && mv -f "${DIR_TLS}/${f}" "${DIR_TLS}/${f}.disattivato"
  done
  echo "HTTPS disattivato (file conservati come *.disattivato in ${DIR_TLS})."
}

# Punto d'ingresso: applica il modo scelto (se c'è) e imposta TLS=1/0 e OPZ_TLS.
tls_prepara() {
  install -d -o root -g root -m 755 "/etc/${NOME}"
  install -d -o root -g "$UTENTE" -m 750 "$DIR_TLS"
  if [[ $TLS_DISATTIVA -eq 1 ]]; then tls_disattiva
  elif [[ -n "$TLS_CERT" ]]; then tls_da_file
  elif [[ $TLS_AUTOFIRMATO -eq 1 ]]; then tls_autofirmato
  elif [[ -n "$TLS_STEP" ]]; then tls_step
  elif [[ -n "$TLS_ACME" ]]; then tls_acme
  fi
  TLS=0
  [[ -f "${DIR_TLS}/cert.pem" && -f "${DIR_TLS}/key.pem" ]] && TLS=1
  OPZ_TLS=""
  [[ $TLS -eq 1 ]] && OPZ_TLS=" --certfile ${DIR_TLS}/cert.pem --keyfile ${DIR_TLS}/key.pem"
  if [[ $TLS -eq 0 && $TLS_DISATTIVA -eq 0 ]]; then
    echo "HTTPS non attivo: il servizio risponde in HTTP. Consigliato anche in rete interna:"
    echo "  --tls-step/--tls-acme (CA interna, rinnovo automatico), --tls-cert/--tls-key o --tls-autofirmato."
  fi
  return 0
}

# Riepilogo finale (dopo il controllo del servizio).
tls_riepilogo() {
  local fonte
  if [[ $TLS -eq 1 ]]; then
    fonte="$(cat "${DIR_TLS}/fonte" 2>/dev/null || echo file)"
    echo "HTTPS ($fonte): $(openssl x509 -in "${DIR_TLS}/cert.pem" -noout -issuer -enddate | tr '\n' ' ')"
    case "$fonte" in
      step) echo "Rinnovo automatico: ${NOME}-tls-rinnovo.timer (step ca renew)." ;;
      acme) echo "Rinnovo automatico: certbot.timer." ;;
      *) echo "Rinnovo: sovrascrivere ${DIR_TLS}/key.pem e poi cert.pem (riavvio automatico)." ;;
    esac
    echo "Impronta SPKI del certificato (per i collegamenti fra installazioni): $(impronta_spki "${DIR_TLS}/cert.pem")"
    if [[ $AGGIORNAMENTO -eq 1 ]] && ! grep -q '^HTTPS=true' "${DIR_APP}/.env"; then
      echo "Attenzione: in ${DIR_APP}/.env impostare HTTPS=true (cookie solo su connessioni cifrate) e riavviare."
    fi
  else
    echo "Consiglio: attivare HTTPS anche in rete interna (vedi docs/sistema/https-rete-interna.md)."
  fi
}
