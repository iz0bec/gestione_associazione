<!--
******************************************************
* Progetto:    Gestione Associazione
* Autore:      Bartolomeo Santoro aka IZ0BEC
* Email:       info@iz0bec.info
* Descrizione: Kit per chi integra: come scrivere un client delle API v1 (passi, firma,
*              cifratura, errori), implementazioni di riferimento e prove
* Licenza:     CC0 1.0 Universal (pubblico dominio)
* SPDX-License-Identifier: CC0-1.0
******************************************************
-->

# Kit per chi integra

Questa guida serve a chi vuole collegare **un proprio programma** (un sito, un'app, un altro
gestionale) a un'installazione di Gestione Associazione. Il contratto è in
[`openapi.yaml`](openapi.yaml); le scelte sono motivate nell'ADR-030. Tutto è in pubblico dominio
(CC0): si può copiare liberamente.

## 1. Cosa serve

- **HTTPS** verso l'installazione (eventualmente con CA interna o certificato verificato per
  impronta, vedi la guida di sistema *API*).
- Una coppia di chiavi **Ed25519** (firma) e una **X25519** (cifratura), conservate dal proprio
  programma; si pubblicano solo le chiavi pubbliche, in formato **JWKS** (RFC 7517) con `kid` =
  impronta RFC 7638.
- Un **codice d'invito** creato dall'amministratore dell'installazione in *Sistema → Collegamenti*,
  con gli **ambiti** necessari.

## 2. I passi

| Passo | Chiamata | Note |
|---|---|---|
| Scoperta | `GET /.well-known/gestione-associazione` | identità (`istanza`), nome, versioni API, `jwks_uri` |
| Abbinamento | `POST /api/v1/abbinamenti` con intestazione `Invito: <codice>` | corpo `{istanza, nome, tipo: "integrazione", jwks}`, firmato con la chiave contenuta nel corpo; risposta `201` con la nostra `impronta` |
| Conferma | a voce o di persona | le due parti confrontano l'**impronta** (otto gruppi di quattro caratteri); l'amministratore attiva il collegamento |
| Prova | `POST /api/v1/prova` | diagnosi: firma, orologio, stato, ambiti concessi |
| Uso | le risorse dell'OpenAPI | secondo gli ambiti concessi |

## 3. Firmare ogni richiesta (RFC 9421)

- Etichetta `ga`, `tag="ga-v1"`, algoritmo Ed25519, `keyid` = `kid` della propria chiave di firma,
  `created` (secondi) e `nonce` casuale. La tolleranza dell'orologio è di 300 secondi.
- Componenti firmati: `"@method" "@path" "@query" "destinatario-istanza"` e, se c'è un corpo,
  `"content-digest"`.
- Intestazioni da inviare: `Destinatario-Istanza` (l'`istanza` dell'installazione), `Content-Digest`
  (RFC 9530, `sha-256`) se c'è un corpo, `Signature-Input`, `Signature`.
- **Verificare sempre la risposta**: è firmata dall'installazione con componenti `"@status"
  "content-digest" "signature";req;key="ga"`, cioè legata alla nostra richiesta. Le chiavi
  pubbliche dell'installazione sono quelle ricevute all'abbinamento.

## 4. Cifrare i dati personali (JWE)

- Domande, contatti, adesioni, soci, consegne e trasferimenti viaggiano come **JWE compatto**
  `ECDH-ES+A256KW` / `A256GCM` con chiave X25519, tipo `application/jose`.
- Si cifra per la chiave `enc` (senza `exp`) dell'installazione; le risposte cifrate arrivano per la
  nostra chiave X25519.

## 5. Scritture sicure

- Ogni `POST`/`PUT` ha l'intestazione **`Idempotency-Key`** (8-64 caratteri): ripetere la stessa
  richiesta non la esegue due volte; usare la stessa chiave solo per lo stesso contenuto.
- Gli errori sono **Problem Details** (RFC 9457) con un `codice` stabile (es.
  `operazione-non-valida`, `firma-non-valida`, `ambito-mancante`).
- In caso di rete assente o errore `5xx`/`429`, conservare la richiesta **già cifrata** e
  riprovare più tardi con la stessa `Idempotency-Key`.

## 6. Implementazioni di riferimento

| Linguaggio | Dove | Cosa contiene |
|---|---|---|
| **Python** | `apps/api/firma.py`, `apps/api/jwe.py`, `apps/api/chiavi.py`; client in `apps/collegamenti/client.py` | lato server e client del gestionale |
| **PHP** (senza librerie esterne, sodium e openssl) | `integrazioni/wordpress/gestione-associazione/includes/cripto.php`, `firma.php`, `connettore.php` | client completo: abbinamento, firma, verifica, JWE, coda cifrata |

Il connettore WordPress è un esempio completo di integrazione «esterna»: si può partire da lì per un
client in un altro linguaggio.

## 7. Provare

- **Vettori ufficiali**: `php integrazioni/wordpress/gestione-associazione/tests/esegui.php` verifica
  la firma con l'esempio RFC 9421 B.2.6, AES Key Wrap con RFC 3394 4.6, il digest RFC 9530 e
  l'impronta RFC 8037.
- **Prova incrociata**: `apps/api/tests/test_connettore_wordpress.py` fa firmare e cifrare a un
  programma esterno (lo script `tests/interop.php`, comandi JSON su standard input) e verifica con il
  codice del gestionale, e viceversa. Lo stesso schema vale per un client in un altro linguaggio.
- **Ambiente dimostrativo**: un'installazione di prova su cui creare un invito, senza dati reali.

## 8. Buone regole

- Chiedere **solo gli ambiti necessari**; le integrazioni non ricevono mai i dati dei soci.
- Non conservare dati personali più del necessario: inviarli cifrati e cancellarli.
- Mostrare all'utente l'**impronta** dell'abbinamento e chiedergli di confrontarla per una seconda
  via.
- Gestire la **rotazione delle chiavi**: le nuove chiavi dell'installazione arrivano firmate con una
  già nota (`/api/v1/chiavi`).
