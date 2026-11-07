<!--
******************************************************
* Progetto:    Gestione Associazione
* Autore:      Bartolomeo Santoro aka IZ0BEC
* Email:       info@iz0bec.info
* Descrizione: Registro delle decisioni di architettura (ADR)
* Licenza:     CC0 1.0 Universal (pubblico dominio)
* SPDX-License-Identifier: CC0-1.0
******************************************************
-->

# Decisioni di architettura

Ogni decisione riporta contesto, scelta e conseguenze. Una decisione si cambia aggiungendone
una nuova che la sostituisce, non riscrivendo quella vecchia.

## ADR-001 - Monolite modulare in Django

- **Contesto**: tre applicazioni (una Node, due Flask) con dati in comune, mantenute da una persona,
  installate su un solo server; due su tre già in Python.
- **Scelta**: un'unica applicazione **Django 6.1** (poi 6.2 LTS, attesa ad aprile 2027) su **Python 3.13**,
  divisa in app Django per modulo (`apps/<modulo>`). Niente microservizi né SPA.
- **Perché Django**: protezione CSRF, escaping dei template, gestione password e permessi, migrazioni,
  admin, Content Security Policy nativa (dalla 6.0) e un ciclo di rilascio LTS adatto a un software
  che deve durare anni con poca manutenzione.
- **Conseguenze**: un solo processo da installare e aggiornare; le integrazioni fra moduli sono
  chiamate Python dentro una transazione, non API HTTP.

## ADR-002 - Interfaccia: template server-side + HTMX, Tabler

- **Scelta**: pagine generate dal server; **HTMX** per gli aggiornamenti parziali (ricerche, tabelle,
  modali); **Alpine.js** solo per piccoli comportamenti locali; tema **Tabler** (Bootstrap 5).
- Tutte le librerie sono **incluse nel progetto** (`static/vendor`) con versione fissata: nessun CDN,
  così la CSP può vietare script esterni e l'app funziona anche senza Internet.
- **Conseguenze**: nessuna build JavaScript; l'interfaccia resta accessibile e veloce anche su PC vecchi.

## ADR-003 - PostgreSQL unico database

- **Scelta**: PostgreSQL 15+ (in sviluppo e produzione). SQLite non è supportato in produzione.
- **Perché**: transazioni e lock affidabili (numerazioni), ricerca testuale, vincoli; il server ha già PostgreSQL.

## ADR-004 - Anagrafica unica

- **Scelta**: un solo modello `Soggetto` (persona fisica o ente) con categorie multiple.
  Socio, mittente di un protocollo, partecipante a una riunione, destinatario di un prestito
  sono **ruoli** dello stesso soggetto, collegati con chiavi esterne.
- **Conseguenze**: nessun export/import fra archivi; la modifica di un indirizzo vale ovunque.
  I documenti ufficiali (protocolli, verbali) conservano comunque il testo del mittente/destinatario
  com'era al momento della registrazione.

## ADR-005 - Numerazioni centralizzate e atomiche

- **Scelta**: tabella `Sequenza(chiave, anno, ultimo_numero)`; il numero si ottiene con
  `SELECT ... FOR UPDATE` nella stessa transazione che salva il documento.
- **Conseguenze**: nessun duplicato né buco anche con richieste concorrenti; un'unica funzione
  (`apps.core.numerazione.prossimo_numero`) per protocollo, tessere, inventario, ricevute, verbali.

## ADR-006 - Allegati privati

- **Scelta**: gli allegati stanno fuori dalla cartella pubblica (`MEDIA_ROOT` non servita dal web server)
  e si scaricano solo tramite una vista che controlla i permessi. Il tipo è dedotto dal contenuto/estensione
  salvata, mai dal nome fornito dall'utente; i file non sicuri si scaricano e non si aprono nel browser.

## ADR-007 - Sicurezza dell'autenticazione

- **Scelta**: `django-allauth` per login, recupero password e **secondo fattore** (TOTP e chiavi di
  sicurezza/passkey); `django-axes` per bloccare i tentativi ripetuti; password con Argon2/PBKDF2 di Django.
- Il secondo fattore è obbligatorio per i ruoli con accesso a dati personali o a tesoreria
  (attivabile dalle impostazioni).

## ADR-008 - Documenti PDF da modelli HTML

- **Scelta**: WeasyPrint stampa in PDF template HTML/CSS con intestazione unica dell'ente.
- **Conseguenze**: i modelli di stampa si modificano come pagine web; niente coordinate a mano.

- **Sicurezza**: il generatore usa un recuperatore di risorse proprio (`apps/core/pdf.py`) che accetta solo
  `risorsa:static/...` e `risorsa:media/...` verificati: nessun accesso in rete né a file arbitrari, anche
  se un testo inserito dagli utenti finisse nel modello.

## ADR-009 - Registro delle attività

- **Scelta**: tabella `EventoAudit` scritta dai servizi applicativi (non da trigger) per le operazioni
  rilevanti: accessi, creazioni, modifiche, annullamenti, esportazioni, letture di dati sensibili.
- Non modificabile dall'interfaccia; conservazione configurabile.

## ADR-010 - Logica nei servizi, viste sottili

- **Scelta**: ogni modulo ha `services.py` con le operazioni di dominio (es. `registra_protocollo`,
  `chiudi_esercizio`); viste, comandi e API chiamano i servizi. I test coprono i servizi.

## ADR-011 - Due modi di installazione

- **Scelta**: immagine Docker (compose con PostgreSQL) **e** installazione su host con systemd,
  come per il Protocollo. Stessa configurazione via variabili d'ambiente (`.env`).

## ADR-012 - Licenza CC0 1.0

- **Scelta**: il codice e la documentazione sono rilasciati nel **pubblico dominio** con
  [CC0 1.0 Universal](../../LICENSE).
- **Perché CC0 e non Unlicense**: in Italia i diritti morali d'autore non sono rinunciabili;
  CC0 prevede una licenza di ripiego (fallback) amplissima dove la rinuncia non è valida,
  mentre la Unlicense no. Le librerie di terze parti mantengono le proprie licenze (vedi
  `docs/sistema/licenze-terze-parti.md`).

## ADR-013 - Libro soci: numerazioni e immutabilità

- **Scelta**: numero di iscrizione progressivo unico (sequenza `libro_soci`, mai riavviata), ricevute
  numerate per anno di incasso (`ricevuta_quota`). Le **tessere non sono numerate dall'applicazione**:
  sono prestampate dalla sede centrale e si caricano a lotti (`LottoTessere`, una riga `CartaTessera` per
  tessera, unica per anno e codice); il tesseramento annuale (`Tessera`) riceve una tessera fisica
  disponibile (OneToOne), subito o in seguito. Le tessere fisiche hanno uno stato (disponibile, attribuita,
  annullata, smarrita, restituita) per rendere conto alla sede centrale di ogni numero ricevuto. Le cessazioni e
  gli annullamenti cambiano lo stato, non cancellano: i numeri non si riusano.
- **Motivo**: il libro soci e le ricevute sono documenti con valore verso soci, revisori e controlli
  (CTS art. 15); i buchi di numerazione devono essere spiegati da un annullamento motivato e registrato.
- La quota è sulla tessera (non su un pagamento separato): una quota per socio e anno, incassata in
  un'unica soluzione. Pagamenti rateali e collegamento con la prima nota arriveranno con la Tesoreria.

## ADR-014 - Anti-spam senza servizi esterni

- **Scelta**: per il modulo pubblico di iscrizione campo trappola, token firmato con tempo minimo e
  massimo di compilazione e limite di invii per IP calcolato sul database (vale con più processi).
- **Motivo**: i CAPTCHA esterni (reCAPTCHA, hCaptcha) richiedono script di terzi (contrari alla CSP e
  alla scelta di non caricare risorse da Internet) e trasferiscono dati dei visitatori a terzi.
- **Conseguenze**: protezione adeguata contro invii automatici generici, non contro attacchi mirati;
  le domande restano comunque da valutare a mano e il modulo è disattivato di default.

## ADR-015 - Protocollo: immutabilità e prove di integrità

- **Scelta**: dopo la registrazione restano fissi numero, data/ora, direzione, oggetto e corrispondenti
  (DPR 445/2000, art. 53-54 come riferimento di buona pratica); gli errori si correggono con
  l'annullamento motivato. I documenti si aggiungono soltanto e si conservano con impronta SHA-256; il
  registro giornaliero è un PDF generato una volta e conservato con impronta.
- **Corrispondenti**: collegati all'anagrafica ma con descrizione e indirizzo copiati al momento della
  registrazione, così una modifica successiva della scheda non altera il registro.
- **Numerazione**: sequenza annuale `protocollo`; l'ora di registrazione si legge dopo aver ottenuto il
  numero (riga di sequenza bloccata), quindi l'ordine dei numeri coincide con quello degli orari.
- **Non è** conservazione a norma (AgID): per obblighi di conservazione sostitutiva i registri e i
  documenti vanno versati a un conservatore accreditato.

## ADR-016 - Posta in ingresso: IMAP in sola lettura, solo testo

- **Scelta**: lettura IMAP con `readonly` e `BODY.PEEK` (nessuna modifica alla casella, compatibile con
  l'uso del client di posta); deduplica per Message-ID; per la PEC si estrae il messaggio originale da
  `postacert.eml`. Il testo HTML viene ridotto a testo e mai reso nel browser.
- **Motivo**: nel Protocollo ANCR originale il corpo HTML delle email ha richiesto correzioni di sicurezza
  (XSS); mostrare solo testo elimina il problema alla radice. POP3 non è supportato (cancellerebbe o
  non distinguerebbe i messaggi).
- Le password IMAP sono cifrate con una chiave separata dal database (ADR-007).

## ADR-017 - Organi sociali: dalla convocazione al libro dei verbali

- **Aventi diritto** calcolati, non scritti a mano: per l'assemblea i soci attivi alla data (con il voto ai
  soli soci in regola, se previsto), per gli altri organi le cariche in corso; all'apertura delle presenze
  l'elenco viene **fissato** nella riunione (così cambiamenti successivi non alterano il foglio presenze).
- **Quorum e deleghe** configurabili per organo secondo lo statuto (default: più della metà in prima
  convocazione; assemblea valida con qualunque numero in seconda; 3 deleghe come art. 24 D.Lgs. 117/2017).
- **Numerazioni**: riunioni per organo e anno (`riunione_<organo>`), libro dei verbali per organo senza
  azzeramento (`verbale_<organo>`), delibere per organo e anno (`delibera_<organo>`), assegnate alla chiusura.
- **Chiusura** irreversibile: PDF conservato con impronta, protocollazione facoltativa. Un verbale senza
  numero legale non può contenere delibere. Eventuali rettifiche si fanno con una delibera successiva.
- Le cariche sostituiscono la «gestione utenti per ruolo statutario» dell'app Assemblee: il ruolo nell'app
  (permessi) resta distinto dalla carica sociale (ADR sui ruoli).
