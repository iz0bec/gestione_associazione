<!--
******************************************************
* Progetto:    Gestione Associazione - connettore WordPress
* Autore:      Bartolomeo Santoro aka IZ0BEC
* Email:       info@iz0bec.info
* Descrizione: Guida per chi sviluppa il connettore WordPress
* Licenza:     CC0 1.0 Universal (pubblico dominio)
* SPDX-License-Identifier: CC0-1.0
******************************************************
-->

# Connettore WordPress di Gestione Associazione

Plugin WordPress che usa le [API v1](../../../docs/api/README.md) del gestionale come
«integrazione esterna». È pensato per diventare un progetto a sé: non dipende dal codice del
gestionale, solo dal contratto (`docs/api/openapi.yaml`).

| File | Cosa fa |
|---|---|
| `includes/cripto.php` | base64url, impronte RFC 7638, Ed25519, X25519, Concat KDF, AES Key Wrap, JWE |
| `includes/firma.php` | firma RFC 9421 delle richieste, verifica delle risposte, Content-Digest |
| `includes/connettore.php` | abbinamento, richieste firmate, coda cifrata degli invii |
| `includes/eventi.php` | eventi e organigramma in cache, articoli degli eventi |
| `includes/moduli.php` | shortcode e moduli (domanda, contatti, adesioni, verifica tessera) |
| `includes/amministrazione.php` | Impostazioni → Gestione Associazione |
| `assets/blocchi.js` | blocchi dell'editor (senza compilazione) |
| `assets/moduli.js` | rinnovo del gettone anti-spam al caricamento della pagina |

## Prove

```bash
php tests/esegui.php                                 # vettori RFC 9421, RFC 3394, JWE
uv run pytest apps/api/tests/test_connettore_wordpress.py   # dal gestionale: prova incrociata
```

La prova incrociata fa firmare e cifrare al PHP e verifica con il codice del gestionale (e
viceversa): le due implementazioni non possono divergere.

Licenza: CC0 1.0 Universal (compatibile con la GPL di WordPress).
