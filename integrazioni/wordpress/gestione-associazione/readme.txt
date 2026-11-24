=== Gestione Associazione ===
Contributors: iz0bec
Tags: associazione, iscrizione, eventi, terzo settore, ANCR
Requires at least: 6.4
Tested up to: 7.1
Requires PHP: 8.1
Stable tag: 0.1.2
License: CC0-1.0
License URI: https://creativecommons.org/publicdomain/zero/1.0/

Collega il sito al gestionale Gestione Associazione: domanda di iscrizione, contatti, eventi con adesione e articoli, organigramma, verifica della tessera.

== Description ==

Il connettore parla con il gestionale tramite le API v1 di Gestione Associazione: ogni richiesta è firmata (RFC 9421, Ed25519) e i dati personali viaggiano cifrati per il gestionale (JWE, X25519 + AES-GCM). Il sito non conserva i dati personali: se il gestionale non risponde, l'invio resta in coda già cifrato e riparte da solo.

Sul sito (shortcode e blocchi):

* `[ga_domanda sezione="codice" statuto="url" informativa="url"]` - domanda di iscrizione, che il consiglio direttivo esamina nel gestionale;
* `[ga_contatti]` - il messaggio arriva fra la posta da protocollare;
* `[ga_eventi]` - eventi pubblici con il modulo di adesione e i posti liberi;
* `[ga_organigramma sezione="codice"]` - cariche in corso (solo ruolo e nome);
* `[ga_verifica_tessera]` - verifica di una tessera dal codice della tessera digitale.

Per gli eventi segnati «pubblica sui siti collegati» il connettore crea un articolo (in bozza per default) e lo aggiorna quando l'evento cambia.

Richiede le estensioni PHP sodium e openssl (presenti nelle installazioni comuni).

== Installation ==

1. Caricate la cartella `gestione-associazione` in `wp-content/plugins` e attivate il plugin.
2. Nel gestionale, *Sistema → Collegamenti*, create un invito per un'«integrazione esterna» con gli ambiti necessari.
3. In WordPress, *Impostazioni → Gestione Associazione*, inserite indirizzo del gestionale e codice d'invito.
4. Confrontate l'impronta mostrata dalle due parti e attivate il collegamento nel gestionale.

== Changelog ==

= 0.1.2 =
* Articoli degli eventi: aggiornando il titolo dal cron non si tolgono più dal testo del redattore video incorporati, iframe e altro HTML consentito solo agli amministratori.

= 0.1.1 =
* Coda degli invii: una voce per invio (prima un invio arrivato mentre il cron svuotava la coda poteva andare perso); attesa crescente fino a 6 ore per 7 giorni; gli errori transitori (collegamento sospeso, orologio, richiesta gemella in corso, risposte non verificabili del proxy) si ritentano; ciò che non si consegna resta «non consegnato» nelle impostazioni, da rimettere in coda o eliminare, mai scartato in silenzio.
* Adesione agli eventi: dopo un invio riuscito o messo in coda non compare più un errore (che portava a rimandarla e a doppioni).
* Articoli degli eventi: un articolo cestinato o eliminato dal redattore non viene ricreato; titolo come testo semplice; niente doppioni se cron e «Aggiorna ora» lavorano insieme.
* Anti-spam: il gettone del modulo si rinnova al caricamento della pagina, così i moduli funzionano anche con la cache di pagina.

= 0.1.0 =
* Prima versione: abbinamento, domanda, contatti, eventi e adesioni, articoli degli eventi, organigramma, verifica della tessera, coda cifrata.
