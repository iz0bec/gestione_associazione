<!--
******************************************************
* Progetto:    Gestione Associazione
* Autore:      Bartolomeo Santoro aka IZ0BEC
* Email:       info@iz0bec.info
* Descrizione: Configurazione dell'API di interoperabilità: proxy, rete interna, impronte TLS
* Licenza:     CC0 1.0 Universal (pubblico dominio)
* SPDX-License-Identifier: CC0-1.0
******************************************************
-->

# API di interoperabilità

L'API v1 collega le installazioni fra loro (federazione ↔ sezioni) e con integrazioni esterne. Le
decisioni sono nell'[ADR-030](../architettura/decisioni.md), il contratto in
[`docs/api/openapi.yaml`](../api/openapi.yaml), la guida per chi scrive un adattatore in
[`docs/api/README.md`](../api/README.md). L'uso quotidiano è nel manuale operativo
(*Collegamenti API*).

## Cosa serve

- **`CHIAVE_CIFRATURA`** nel `.env`: senza, l'istanza non crea le proprie chiavi e l'API risponde
  `503 non-configurata`. Le chiavi private si conservano cifrate con questa chiave: **conservatela
  con i backup**. Un backup ripristinato altrove porta con sé l'identità dell'istanza.
- **Orologio sincronizzato** (NTP) su tutte le installazioni: una firma vale ±5 minuti.
- Il **pianificatore** attivo. Ogni minuto esegue:
  - `pulizia_api`: cancella i nonce vecchi, il registro delle chiamate oltre 90 giorni e i
    cambiamenti del feed oltre 400 giorni; toglie le chiavi ritirate e sospende le controparti
    scadute;
  - `invia_notifiche_api`: consegna gli avvisi dei cambiamenti.

  Ogni notte esegue `aggiorna_collegamenti`, che rilegge chiavi e impronte TLS delle installazioni
  collegate.

## Indirizzi esposti

| Percorso | Autenticazione | Contenuto |
|---|---|---|
| `/.well-known/gestione-associazione` | nessuna | UUID, denominazione, versioni dell'API, versione del software, impronte SPKI |
| `/.well-known/gestione-associazione/jwks.json` | nessuna | chiavi pubbliche (JWKS) |
| `/api/v1/abbinamenti` | invito monouso + firma | abbinamento |
| `/api/v1/prova` | firma | diagnosi del collegamento |
| `/api/v1/chiavi` (PUT) | firma | la controparte presenta chiavi nuove |
| `/api/v1/cambiamenti?flusso=…&dopo=…` | firma + ambito del flusso | feed dei cambiamenti (`eventi`, `sezioni`) |
| `/api/v1/riepiloghi/{flusso}` | firma + ambito | numero e impronta delle risorse, per la riconciliazione |
| `/api/v1/eventi`, `/api/v1/eventi/{uuid}` | firma + `eventi:lettura` | eventi; alle integrazioni solo quelli con modulo pubblico |
| `/api/v1/sezioni` | firma + `sezioni:lettura` | sezioni |
| `/api/v1/eventi/{uuid}/adesioni` (GET/POST), `/api/v1/adesioni/{uuid}` (DELETE) | firma + `adesioni:…`, **cifrato** | adesioni inviate dalla controparte |
| `/api/v1/domande` (POST) | firma + `domande:scrittura`, **cifrato** | domanda di iscrizione, in attesa |
| `/api/v1/contatti` (POST) | firma + `contatti:scrittura`, **cifrato** | messaggio tra la posta da protocollare |
| `/api/v1/documenti`, `/api/v1/documenti/{id}/file` | firma + `documenti:lettura` | documenti pubblici |
| `/api/v1/organigramma` | firma + `organigramma:lettura` | cariche in corso (ruolo e nome) |
| `/api/v1/tessere/{codice}` | firma + `tessere:verifica` | validità, anno e sezione di una tessera (nient'altro) |

Le risposte, comprese quelle pubbliche e gli errori, sono **firmate** con la chiave dell'istanza.

## Dietro un reverse proxy (NPM e simili)

La firma copre metodo, percorso, query, `Destinatario-Istanza` e `Content-Digest`, **non** il nome
host. Il proxy quindi:

- deve inoltrare **senza riscrivere il percorso**: niente prefissi aggiunti o tolti. Il gestionale
  deve stare alla radice del nome (`https://gestionale.example.org/`);
- deve lasciar passare le intestazioni `Signature`, `Signature-Input`, `Content-Digest`,
  `Destinatario-Istanza` e `Invito`. Nginx Proxy Manager lo fa senza configurazioni aggiuntive;
- non deve modificare il corpo, né in ingresso né in uscita: niente compressioni o riscritture.

L'IP della controparte, usato per l'elenco «IP ammessi», si ricava come per il resto del
gestionale da `PROXY_COUNT` e `PROXY_FIDATI`.

## Rete interna (stesso host, stesso Proxmox)

Due installazioni nella stessa rete si chiamano direttamente, senza passare dal proxy pubblico:

1. Su chi riceve, aggiungere l'indirizzo interno (IP o nome) ad **`ALLOWED_HOSTS`**.
2. **HTTPS anche in rete interna**, consigliato: `installa.sh --tls-step …`, `--tls-acme …` o
   `--tls-autofirmato` (vedi [HTTPS anche in rete interna](https-rete-interna.md)). L'installatore
   stampa l'**impronta SPKI** da usare con la verifica «impronta».
3. Sulla controparte, in *Collegamenti API*, indicare l'**indirizzo interno** con la modalità di
   verifica: *CA interna* (radice della CA) o *impronta*.

Il trasporto in uscita segue queste regole fisse:

- il certificato si verifica sempre;
- i redirect non si seguono;
- il nome si risolve e si controlla a ogni chiamata, quindi un indirizzo privato è ammesso solo per
  le controparti segnate «rete interna»;
- `http://` è ammesso solo verso IP privati, con il consenso esplicito.

### Impronte SPKI dell'istanza

`/.well-known` pubblica l'impronta del certificato servito direttamente dal gestionale, letta da
`API_TLS_CERTIFICATO`. Se l'HTTPS interno lo fornisce invece un proxy locale, la sua impronta si
indica in `API_TLS_SPKI`.

| Variabile | Default | Descrizione |
|---|---|---|
| `API_TLS_CERTIFICATO` | `/etc/gestione-associazione/tls/cert.pem` | certificato da cui calcolare l'impronta (quello installato da `installa.sh --tls-…`) |
| `API_TLS_SPKI` | - | altre impronte SPKI (base64, separate da virgola), ad esempio del certificato del proxy locale |

L'impronta di un certificato si calcola con:

```bash
openssl x509 -in cert.pem -pubkey -noout | openssl pkey -pubin -outform DER \
  | openssl dgst -sha256 -binary | base64
```

Rinnovando il certificato con la **stessa chiave** l'impronta non cambia. `step ca renew` e certbot
creano invece una chiave nuova a ogni rinnovo. L'installazione chiamante la rilegge ogni notte dalla
`/.well-known` firmata (`aggiorna_collegamenti`), passando dall'indirizzo pubblico se quello interno
non è più verificabile. Senza indirizzo pubblico conviene la verifica **CA interna**.

## Dati personali e scritture

- I dati personali viaggiano solo **cifrati** per il destinatario (JWE `ECDH-ES+A256KW` /
  `A256GCM`, chiavi X25519), sia in ingresso che in uscita. Un corpo in chiaro su questi indirizzi
  è rifiutato (`415 cifratura-richiesta`).
- Ogni scrittura richiede `Idempotency-Key`. La stessa chiave con lo stesso contenuto restituisce
  la risposta già data e non crea doppioni. Le chiavi si conservano 30 giorni.
- **Limiti per controparte**: `API_LIMITE_MINUTO` chiamate al minuto e `API_LIMITE_SCRITTURE_ORA`
  scritture all'ora (predefiniti 120). Oltre si risponde `429` con `Retry-After`.
- **Adesioni e domande** passano dagli stessi servizi del modulo pubblico, con le stesse regole e
  gli stessi consensi obbligatori. Le domande restano «in attesa» e non sono mai accolte in
  automatico. Restano registrate l'origine «integrazione» e la controparte che le ha inviate.
- **Contatti**: ogni messaggio diventa un `.eml` nella casella interna «Modulo contatti (API)» e
  compare tra la posta da protocollare. La casella non si configura e non si scarica.

## Feed dei cambiamenti

Ogni creazione, modifica o annullamento di un evento o di una sezione scrive un **cambiamento**
nella stessa transazione del salvataggio, da qualunque parte arrivi: interfaccia, importazioni,
configurazione guidata. Anche ogni adesione o rinuncia scrive un cambiamento sull'evento, perché
cambiano i posti liberi.

I cambiamenti hanno un progressivo senza buchi per flusso (sequenza `feed_<flusso>`) e una catena
di impronte, quindi chi legge si accorge di voci mancanti o alterate. Si conservano 400 giorni:
un cursore più vecchio riceve `410` e serve una nuova lettura completa.

## Rotazione delle chiavi

- **Nostra** (*Collegamenti API → Ruota le chiavi*): per 7 giorni le risposte sono firmate sia con
  la chiave nuova sia con quella in uscita. Le altre installazioni accettano le chiavi nuove
  rileggendo la nostra JWKS, firmata con una chiave che già conoscono. Lo fanno da sole alla prima
  chiamata o con `aggiorna_collegamenti`.
- **Della controparte**:
  - un'altra installazione si rilegge nello stesso modo (*Aggiorna chiavi e impronte* nella scheda);
  - un'integrazione presenta le proprie chiavi con `PUT /api/v1/chiavi`, firmata con quella vecchia.
- Ogni cambio di chiavi o di impronte TLS finisce nel registro attività.

## Notifiche

Nella scheda della controparte (*Modifica*) si scelgono i **flussi notificati** e l'**indirizzo
delle notifiche**. A ogni cambiamento parte un `POST` firmato con il CloudEvent, senza dati
personali.

- Se non va a buon fine, si ripete con attesa crescente: 1, 2, 4… minuti, fino a 24 ore.
- Dopo l'ultimo tentativo la notifica resta **fallita** e visibile nella scheda, dove si può
  rimettere in coda con *Riprova*.
- Le notifiche sono solo un avviso: chi integra deve comunque leggere il feed periodicamente.

L'indirizzo delle notifiche segue le stesse regole degli altri:

- https verso Internet;
- un indirizzo privato solo se la controparte è segnata «rete interna»;
- http solo con il consenso esplicito.

## Diagnosi

- *Collegamenti API → scheda → Prova il collegamento* mostra l'esito; le ultime chiamate ricevute
  hanno un codice d'errore Problem Details (es. `firma-scaduta`, `nonce-riusato`,
  `destinatario-errato`, `controparte-non-attiva`).
- Da terminale: `curl -s https://gestionale.example.org/.well-known/gestione-associazione`.
