<!--
******************************************************
* Progetto:    Gestione Associazione
* Autore:      Bartolomeo Santoro aka IZ0BEC
* Email:       info@iz0bec.info
* Descrizione: Guida per chi scrive un adattatore sull'API di interoperabilità v1
* Licenza:     CC0 1.0 Universal (pubblico dominio)
* SPDX-License-Identifier: CC0-1.0
******************************************************
-->

# API v1: guida per chi integra

Il contratto è [`openapi.yaml`](openapi.yaml) (OpenAPI 3.1); le scelte sono motivate
nell'[ADR-030](../architettura/decisioni.md). Gli adattatori si scrivono su questo contratto, in
qualsiasi linguaggio. Un esempio completo, in PHP senza librerie esterne, è il
[connettore WordPress](../../integrazioni/wordpress/gestione-associazione/) (guida in
[docs/sistema](../sistema/connettore-wordpress.md)): non dipende dal codice del gestionale e
diventerà un progetto separato.

Disponibile oggi:

- descrizione dell'istanza, chiavi, abbinamento, `/prova` e `PUT /chiavi` (fase F1);
- feed dei cambiamenti, riepiloghi, lettura di `eventi` e `sezioni`, notifiche (fase F2);
- cifratura, adesioni, domande di iscrizione, messaggi del modulo contatti, documenti pubblici,
  organigramma, verifica di una tessera (fase F3).

`soci` e `lotti`, che servono fra installazioni, arrivano con le fasi successive.

## 1. Le vostre chiavi

Generate due coppie di chiavi: **Ed25519** per firmare e **X25519** per ricevere dati cifrati.
Pubblicatele come JWKS con `kty: OKP`, `use: sig` / `enc`. Il **`kid` deve essere l'impronta
RFC 7638** della chiave, cioè lo SHA-256 in base64url di `{"crv":…,"kty":"OKP","x":…}` con le
chiavi ordinate e senza spazi. La chiave privata non lascia mai il vostro sistema.

## 2. Firmare ogni richiesta (RFC 9421)

| Elemento | Valore |
|---|---|
| Etichetta | `ga` |
| Componenti | `"@method" "@path" "@query" "destinatario-istanza"`, più `"content-digest"` se c'è un corpo |
| Parametri | `created`, `expires` (al massimo `created` + 300), `nonce` (16-64 caratteri, mai ripetuto), `keyid` (il vostro `kid`), `alg="ed25519"`, `tag="ga-v1"` |
| `Destinatario-Istanza` | UUID dell'istanza chiamata (da `/.well-known/gestione-associazione`) |
| `Content-Digest` | `sha-256=:<base64>:` del corpo esatto (RFC 9530) |

Esempio di `Signature-Input`:

```
ga=("@method" "@path" "@query" "destinatario-istanza" "content-digest");created=1763460000;expires=1763460300;nonce="q3v…";keyid="Xc4…";alg="ed25519";tag="ga-v1"
```

`@query` vale `?` quando non c'è query. L'orologio deve essere sincronizzato entro ±300 secondi.
La vostra implementazione si verifica con gli esempi dell'RFC 9421, Appendice B.2.6 (chiave
`test-key-ed25519`): la stessa prova fa parte dei test del progetto
(`apps/api/tests/test_firma.py`).

## 3. Verificare ogni risposta

Ogni risposta, compresi gli errori, ha un `Content-Digest` e una firma con etichetta `ga` sui
componenti `"@status" "content-digest" "signature";req;key="ga"`. L'ultimo componente lega la
risposta alla **vostra** richiesta: una risposta non si può riusare per un'altra. La chiave è nella
JWKS dell'istanza. **Scartate** le risposte senza firma valida.

## 4. Abbinamento

1. L'amministratore dell'associazione crea un **invito** e vi comunica codice e indirizzo.
2. `GET /.well-known/gestione-associazione` e `/.well-known/gestione-associazione/jwks.json` danno
   UUID e chiavi dell'istanza.
3. `POST /api/v1/abbinamenti` con l'intestazione `Invito: <codice>` e il corpo
   `{"istanza": "<vostro UUID>", "nome": "…", "tipo": "integrazione", "jwks": {…}}`. La richiesta è
   firmata con la chiave presente nel corpo, come prova di possesso.
4. La risposta `201` contiene l'**impronta** dell'abbinamento. Calcolatela anche voi: SHA-256 delle
   impronte RFC 7638 di tutte le chiavi in uso delle due parti, ordinate e unite da `\n`; le prime
   32 cifre esadecimali maiuscole, in gruppi di 4. Confrontatela con l'amministratore per una
   seconda via: lui attiva il collegamento solo se coincide.
5. Fino all'attivazione potete chiamare solo `POST /api/v1/prova`, che restituisce una diagnosi
   (firma, scarto dell'orologio, stato e ambiti).

## 5. Leggere i dati e restare allineati

1. **Prima sincronizzazione**:
   1. leggete `GET /api/v1/riepiloghi/eventi` e prendete il suo `progressivo`;
   2. scaricate tutto `GET /api/v1/eventi`, seguendo `successivo` finché non vale `null`;
   3. salvate `progressivo` come cursore.
2. **Aggiornamenti**: `GET /api/v1/cambiamenti?flusso=eventi&dopo=<cursore>`. Per ogni voce
   rileggete la risorsa indicata da `subject` (`GET /api/v1/eventi/{uuid}`) e salvate il nuovo
   cursore **nella stessa transazione** in cui applicate la modifica. Le regole:
   - una voce con una `data.versione` già applicata si ignora;
   - un `404` significa che la risorsa non vi è più visibile, ad esempio un evento non più
     pubblico: toglietela.
3. **Verificate la catena**:
   - i progressivi sono consecutivi;
   - `ga_precedente` è l'impronta della voce precedente (64 zeri per la prima del flusso);
   - `ga_impronta` = SHA-256 esadecimale di `ga_precedente` seguito dal JSON canonico della voce
     senza `ga_impronta` (RFC 8785: chiavi ordinate, nessuno spazio, UTF-8).

   Se qualcosa non torna, fermatevi e ripartite dalla prima sincronizzazione.
4. **Cursore troppo vecchio**: oltre i 400 giorni di conservazione la risposta è `410
   cursore-scaduto` e si ricomincia dalla prima sincronizzazione.
5. **Riconciliazione**: `GET /api/v1/riepiloghi/{flusso}` restituisce il numero delle risorse
   visibili e lo SHA-256 delle righe `uuid:versione` ordinate e unite da `\n`. Calcolatelo sulla
   vostra copia: se diverge, risincronizzate.

## 6. Notifiche (facoltative)

Se l'amministratore indica un vostro indirizzo delle notifiche, a ogni cambiamento ricevete un `POST`
con il CloudEvent (`application/cloudevents+json`).

- La richiesta è firmata come quelle dell'API: verificatela con la JWKS dell'istanza e controllate
  che `Destinatario-Istanza` sia il **vostro** UUID.
- Rispondete `2xx` subito e leggete il feed in un secondo momento.
- Una notifica può arrivare più volte o non arrivare: il feed resta la fonte.

## 7. Rotazione delle chiavi

- **Le vostre**: `PUT /api/v1/chiavi` con `{"jwks": …}`, firmata con la chiave in uso. Dalla
  risposta in poi firmate con quella nuova.
- **Quelle dell'istanza**: per 7 giorni le risposte portano una seconda firma con etichetta `ga1`
  (`ga2`…), fatta con la chiave in uscita. Se il `keyid` di `ga` non è nella vostra copia della
  JWKS, verificate `ga1` con la chiave che conoscete e poi rileggete la JWKS.

## 8. Inviare dati (adesioni, domande, contatti)

1. **Cifrate il corpo** per la chiave `use: enc` (X25519) della JWKS dell'istanza: JWE compatto,
   `alg: ECDH-ES+A256KW`, `enc: A256GCM`, `kid` della chiave, `Content-Type: application/jose`.
   `Content-Digest` e firma si calcolano sul testo del JWE. Le risposte con dati personali tornano
   cifrate per la **vostra** chiave `enc`.
2. **`Idempotency-Key`**: un valore unico per operazione (consigliato un UUID). Se la risposta si
   perde, ripetete con la stessa chiave: riceverete la stessa risposta, senza doppioni.
3. **Adesione**:
   - `POST /api/v1/eventi/{uuid}/adesioni` con `cognome` (obbligatorio), `nome`, `email`,
     `telefono`, `accompagnatori`, `note`, `riferimento_esterno` (il vostro identificativo);
   - risponde `201` con l'adesione cifrata, `Location` ed `ETag`;
   - `409` se l'evento è annullato, le adesioni sono chiuse o i posti sono finiti, con un
     messaggio da mostrare alla persona;
   - per annullarla, `DELETE /api/v1/adesioni/{uuid}` con `If-Match: "<versione>"`.
4. **Domanda**:
   - `POST /api/v1/domande` con i campi di `NuovaDomanda`: `accetta_statuto` e
     `consenso_trattamento` devono essere `true`;
   - `sezione` è il codice della sezione;
   - `prestato_il` è il momento in cui la persona ha dato i consensi sul vostro sito;
   - un dato non valido (es. il codice fiscale) dà `422` con il motivo.
5. **Contatti**: `POST /api/v1/contatti` con `nome`, `email`, `testo` (e `oggetto`, `telefono`).

## Errori

Formato Problem Details (RFC 9457), `application/problem+json`, con il campo `codice`:

- `firma-non-valida`, `firma-scaduta`, `nonce-riusato`: problemi con la firma e la sua validità;
- `destinatario-errato`, con stato 421;
- `digest-errato`;
- `controparte-non-attiva`, `ip-non-ammesso`, `ambito-mancante`: la controparte non può fare
  questa richiesta;
- `invito-non-valido`, con stato 410;
- `cursore-scaduto`, con stato 410;
- `cifratura-richiesta` (415), `decifratura-fallita` (400), `idempotenza-conflitto` (422 o 409),
  `troppe-richieste` (429, con `Retry-After`);
- `operazione-non-valida`;
- `non-configurata`, con stato 503.
