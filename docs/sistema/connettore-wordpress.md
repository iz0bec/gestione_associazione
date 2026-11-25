<!--
******************************************************
* Progetto:    Gestione Associazione
* Autore:      Bartolomeo Santoro aka IZ0BEC
* Email:       info@iz0bec.info
* Descrizione: Connettore WordPress: installazione, abbinamento, moduli sul sito, articoli
* Licenza:     CC0 1.0 Universal (pubblico dominio)
* SPDX-License-Identifier: CC0-1.0
******************************************************
-->

# Connettore WordPress

Il plugin **Gestione Associazione** collega un sito WordPress al gestionale come «integrazione
esterna» delle [API di interoperabilità](api.md). Sul sito mette:

| Shortcode (e blocco) | Cosa fa | Nel gestionale |
|---|---|---|
| `[ga_domanda sezione="codice" statuto="url" informativa="url"]` | domanda di iscrizione con i consensi | tra le **domande** in attesa, mai accolta in automatico |
| `[ga_contatti]` | modulo contatti | nella **posta da protocollare** |
| `[ga_eventi]` | eventi pubblici con i posti liberi e il modulo di adesione | **adesioni** dell'evento (origine «integrazione») |
| `[ga_organigramma sezione="codice"]` | cariche in corso, solo ruolo e nome | — |
| `[ga_verifica_tessera]` | verifica di una tessera dal codice della tessera digitale | solo validità, anno e sezione |
| `[ga_calendario vista="lista\|mese\|giorno"]` | il calendario degli eventi del sito, con le viste | — |
| `[ga_prossimi_eventi quanti="5"]` | i prossimi eventi, per la home o una barra laterale | — |

### Calendario degli eventi (dalla 0.2.0)

Il plugin ha un **proprio gestore degli eventi**, senza bisogno di plugin di calendario esterni
(come The Events Calendar). Per gli eventi con **«Pubblica sui siti collegati»** (scheda dell'evento
nel gestionale, con il modulo pubblico) crea un **evento del sito** (tipo di contenuto «Evento», menu
*Eventi* della bacheca), in bozza per default:

- **archivio** su `/eventi/` con le viste **elenco** (prossimi e passati), **mese** e **giorno**;
  **pagina dell'evento** su `/evento/…` (indirizzi modificabili nelle impostazioni; se The Events
  Calendar è attivo i predefiniti sono `/calendario/` e `/appuntamento/…`, per non sovrapporsi);
- nella pagina dell'evento: data e ora, luogo con il collegamento alla mappa (OpenStreetMap, senza
  mappe incorporate), tipo, quota, **posti disponibili** e **modulo di adesione** presi dal
  gestionale; **Aggiungi al calendario** (iCal e Google); il testo e le foto (immagine in evidenza)
  li cura il redattore e non vengono mai toccati;
- **feed iCal** di tutti gli eventi (`/?ga_ical=tutti`) per abbonarsi da telefono o computer;
- **dati strutturati schema.org/Event** per i motori di ricerca, con lo stato «annullato»;
- se l'evento cambia nel gestionale si aggiornano titolo, data, luogo e tipo; se è annullato il titolo
  diventa «ANNULLATO – …»; gli eventi passati restano in archivio («Evento concluso»); un evento che
  il redattore cestina o elimina non viene ricreato;
- con un **tema a blocchi** l'archivio usa il modello del tema: per le viste del calendario si mette
  il blocco o lo shortcode *Calendario degli eventi* in una pagina;
- chi vuole riversare gli eventi altrove (altri calendari, social) può usare l'aggancio WordPress
  `ga_evento_sincronizzato` (`$id`, `$evento`, `creato|aggiornato`).

In alternativa, nelle impostazioni, la modalità **«Articoli del blog»** crea un articolo per evento
come nelle versioni precedenti, oppure **«Nessuno»** lascia solo shortcode e blocchi. La diffusione
sui social resta ai plugin del sito.

## Sicurezza e riservatezza

- Ogni richiesta è **firmata** (RFC 9421, Ed25519) e ogni risposta del gestionale è verificata,
  legata alla richiesta: una risposta alterata o riusata viene scartata.
- Domande, contatti e adesioni partono **cifrati per il gestionale** (JWE, X25519 + AES-GCM): il
  sito non li conserva. Se il gestionale non li può ricevere (irraggiungibile, in errore,
  collegamento sospeso o non ancora attivato, orologio sfasato), l'invio resta in una **coda già
  cifrata** (illeggibile anche per chi amministra il sito) e riparte da solo, a intervalli crescenti
  da 15 minuti a 6 ore, senza doppioni (`Idempotency-Key`). Dopo 7 giorni, o se il gestionale
  rifiuta i dati, l'invio diventa **«non consegnato»**: resta elencato in *Impostazioni → Gestione
  Associazione*, dove si rimette in coda (**Riprova ora tutti gli invii**) o si elimina; non viene
  mai scartato in silenzio.
- Le chiavi del sito stanno nel database di WordPress **cifrate** con le chiavi segrete di
  `wp-config.php`: cambiando quelle chiavi va rifatto l'abbinamento.
- Anti-spam senza servizi esterni: campo nascosto e tempo minimo di compilazione (il gettone si
  rinnova al caricamento della pagina, quindi i moduli funzionano anche con la cache di pagina;
  senza JavaScript una pagina in cache da più di 3 ore va ricaricata); la verifica delle tessere è
  limitata a 10 al minuto per indirizzo.
- Nessun dato personale dei soci passa al sito: l'integrazione non riceve mai l'ambito
  `soci:lettura`.

## Installazione

Requisiti: WordPress 6.4 o successivo, PHP 8.1 o successivo con le estensioni **sodium** e
**openssl** (presenti nelle installazioni comuni).

1. Copiare la cartella `integrazioni/wordpress/gestione-associazione` del repository (o lo zip
   allegato alla release) in `wp-content/plugins/` e attivare il plugin.
2. Nel gestionale, **Sistema → Collegamenti → Nuovo invito**: tipo **Integrazione esterna**, con gli
   ambiti che servono: `domande:scrittura`, `contatti:scrittura`, `eventi:lettura`,
   `adesioni:scrittura`, `organigramma:lettura`, `tessere:verifica`. Il codice vale 24 ore.
3. In WordPress, **Impostazioni → Gestione Associazione**: indirizzo `https://` del gestionale e
   codice d'invito, poi **Abbina**.
4. Confrontare per telefono o di persona l'**impronta** mostrata dalle due parti (otto gruppi di
   quattro caratteri) e **attivare** il collegamento nel gestionale.
5. **Prova il collegamento** mostra firma, scarto dell'orologio, stato e ambiti;
   **Aggiorna ora** legge subito eventi, organigramma e articoli (altrimenti ogni 15 minuti con il
   cron di WordPress).

Il collegamento si toglie da *Impostazioni → Gestione Associazione* e va revocato anche nel
gestionale. Disinstallando il plugin si cancellano chiavi, coda e copie in cache; gli articoli
restano.

## Prove

Il connettore è provato con i vettori ufficiali (RFC 9421, RFC 3394, RFC 8037) e con una **prova
incrociata** contro il codice del gestionale: il PHP firma e cifra, il gestionale verifica e decifra,
e viceversa (`apps/api/tests/test_connettore_wordpress.py`, eseguita da `pytest` se `php` è
disponibile). Da riga di comando: `php integrazioni/wordpress/gestione-associazione/tests/esegui.php`.

Il codice sta nel repository del gestionale ma non ne dipende: usa solo il contratto
(`docs/api/openapi.yaml`) ed è pronto per diventare un progetto separato.
