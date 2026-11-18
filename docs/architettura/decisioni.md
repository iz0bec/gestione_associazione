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

## ADR-016 - Posta in ingresso: IMAP senza cancellazioni, solo testo

- **Scelta**: lettura IMAP con `BODY.PEEK` (i messaggi non diventano «letti»); dalla 1.0.19 i messaggi
  scaricati si **spostano** nella cartella `PROCESSATA` (vedi ADR-027), altrimenti `readonly`; deduplica per Message-ID; per la PEC si estrae il messaggio originale da
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

## ADR-018 - Comunicazioni: coda, consensi e anniversari

- **Invio**: bozza con anteprima → conferma → coda smaltita a lotti (`COMUNICAZIONI_LOTTO`) dal
  pianificatore; i primi messaggi partono subito. Un messaggio per destinatario, con stato, tentativi
  (massimo 3) e motivo; nessuna dipendenza da code esterne (Celery, Redis): basta il database.
- **Testi**: segnaposto `{{ nome }}` sostituiti con un'espressione regolare e un elenco chiuso di chiavi;
  i testi scritti dagli utenti non passano mai dal motore dei template (niente accesso ad attributi o
  codice). La versione HTML usa il testo escapato.
- **Consensi**: la finalità dell'invio decide il consenso richiesto (nessuno per l'istituzionale); vale
  l'ultimo consenso registrato per la finalità.
- **Anniversari** calcolati al momento dai dati esistenti (nascita, nome, ammissione, ricorrenze, decesso);
  gli auguri automatici registrano chi li ha ricevuti (`DestinatarioRegistrato`) per non duplicarli.
- **Onomastici**: calendario modificabile con la data più diffusa per nome; ricerca del nome intero e poi
  del primo nome, senza accenti.

## ADR-019 - Tesoreria per cassa e Modello D

- **Scelta**: contabilità per cassa a partita semplice, adatta agli ETS non commerciali con entrate sotto
  220.000 euro; piano dei conti = voci del rendiconto per cassa (Modello D, D.M. 5 marzo 2020), non
  modificabili, con **sottovoci** dell'associazione che confluiscono nella voce. Niente partita doppia né
  stato patrimoniale (fuori portata per le piccole sezioni).
- **Movimenti**: numerati per esercizio; i **giroconti** spostano fondi tra conti senza toccare il
  rendiconto; annullamento al posto della cancellazione.
- **Saldi**: calcolati dai movimenti; alla chiusura si fissano i finali e si riportano come iniziali
  dell'anno seguente (creato se manca). La riapertura è consentita solo se l'anno successivo è aperto.
- **Quote**: l'incasso registrato nel modulo Soci crea il movimento (OneToOne con la tessera) dentro la
  stessa transazione, in un punto di salvataggio: se la tesoreria non può registrarlo l'incasso resta
  valido e la quota compare tra quelle da registrare.

## ADR-020 - Patrimonio: inventario, uscite e passaggio di consegne

- **Inventario** con numero progressivo unico (`inventario`), mai riutilizzato; il numero dei registri
  cartacei si conserva come «numero precedente». Le uscite (prestiti e definitive) sono righe storiche:
  il bene cambia stato e non si cancella.
- **Valore**: valore di acquisizione + valutazioni datate; vale la più recente per data.
- **Passaggio di consegne**: fotografia JSON dei beni (in dotazione e in prestito) salvata nel record e nel
  PDF con impronta; il modello rifiuta le modifiche dopo il primo salvataggio.
- **Scheda pubblica**: raggiungibile con un token casuale (`secrets.token_urlsafe(12)`) solo se attivata;
  mostra i soli campi pubblici. QR generato con `segno` (BSD) in SVG, senza servizi esterni; l'indirizzo
  usa `URL_PUBBLICO` se impostato, per le etichette stampate.
- **Foto**: ricodificate in JPEG con Pillow (massimo 1600 px), che elimina i metadati.

## ADR-021 - Sezioni per soci e tessere

- L'applicazione può servire una federazione: soci, lotti di tessere (e quindi le tessere fisiche) e
  domande di iscrizione appartengono a una **sezione**. Protocollo, organi, tesoreria e patrimonio restano
  dell'ente che installa l'applicazione (scelta dell'utente: multisezione solo per soci e tessere).
- Una sezione predefinita è creata dalle migrazioni: un'associazione singola non vede mai la scelta della
  sezione (campo nascosto e precompilato quando le sezioni attive sono una).
- Visibilità: `Utente.sezioni` (vuoto = tutte). Il filtro è applicato nelle viste tramite
  `apps.soci.sezioni.filtra()` e passato ai servizi massivi come insieme di id (`sezioni=`); i servizi non
  conoscono l'utente.
- Il numero del libro soci resta unico per tutta l'installazione; la matricola del registro nazionale è un
  campo a parte (unico se valorizzato). Le tessere fisiche si attribuiscono solo ai soci della sezione del
  lotto.

## ADR-022 - Listino annuale del tesseramento

- Costo d'acquisto (verso la sede centrale) e prezzo di distribuzione (quota per tipologia) cambiano ogni
  anno: `ListinoTessere` per anno + `QuotaListino` per tipologia. La quota della tipologia resta solo come
  valore di riferimento per i listini nuovi.
- Il listino si crea all'apertura dell'esercizio in tesoreria copiando l'anno precedente; le tessere e i
  carichi già registrati conservano i propri importi (nessun ricalcolo retroattivo).

## ADR-023 - Importazione dal registro nazionale con anteprima esatta

- Il formato dell'estratto nazionale non è fisso: colonne riconosciute per **intestazione** (sinonimi
  normalizzati), con ricerca della riga d'intestazione nelle prime 20.
- L'anteprima esegue **lo stesso codice** dell'importazione dentro una transazione poi annullata
  (`transaction.set_rollback`): ciò che si vede è ciò che accadrà. Ogni riga ha il suo punto di ripristino,
  così un errore salta la riga e non l'importazione.
- Abbinamento: codice fiscale, poi matricola, poi cognome+nome+data di nascita se univoci. Dei dati
  esistenti si completano solo i campi vuoti.
- `openpyxl` con `defusedxml`; `.xls` non supportato (richiederebbe un'altra libreria per un formato
  obsoleto).

## ADR-024 - Personalizzazione dell'interfaccia e configurazione guidata

- Colore e stile del menu sono campi di `Organizzazione`; il CSS è generato da una vista (`/aspetto.css`,
  versione nell'indirizzo per la cache) invece che con stili inline, per mantenere la CSP rigorosa. Il
  colore del testo sui pulsanti è calcolato con la luminanza WCAG.
- Logo ricodificato in PNG (trasparenza conservata), servito pubblicamente perché compare nella pagina di
  accesso; SVG esclusi.
- Configurazione guidata in sei passi che salvano subito (nessuno stato in sessione); il cruscotto vi
  rimanda finché `Organizzazione.configurata` è falso e l'utente può configurare. Le installazioni
  esistenti risultano già configurate (migrazione).

## ADR-025 - Modulo di adesione (Allegato A) e richiesta firmata

- La domanda di iscrizione ha gli stessi campi, dichiarazioni e consensi del modulo nazionale; i testi
  propri dell'associazione (intestazione, articoli dello statuto, dichiarazione SI/NO, piè di pagina,
  informativa) sono campi di `Organizzazione`, così il codice resta generico e i testi dell'ANCR non
  entrano nel repository.
- Consensi registrati per finalità: trattamento, dati particolari, immagine; le comunicazioni associative
  seguono il consenso al trattamento perché comprese nelle finalità dell'informativa.
- Il PDF (WeasyPrint) si compila da domanda o socio, oppure esce in bianco: stessa impaginazione in tre
  pagine dell'originale.
- La richiesta firmata è un file per socio (non un allegato generico) mostrato in un riquadro della scheda:
  la risposta che serve il file sovrascrive per sé sola `X-Frame-Options`/`frame-ancestors` con
  `SAMEORIGIN`/`'self'`; tutte le altre pagine restano `DENY`.

## ADR-026 - Backup e ripristino nell'applicazione; installazione senza Docker

- Un backup è **un solo file** `.tar` (non compresso fuori, compressi dentro): `pg_dump` in formato custom,
  archivio dei file caricati, manifesto con versione, migrazioni applicate e impronte SHA-256. È portabile tra
  server e verificabile prima del ripristino.
- Il ripristino rifiuta backup con migrazioni sconosciute (versione più recente del codice) e applica quelle
  mancanti (versione precedente); prima salva sempre lo stato attuale.
- Dal web il ripristino gira in un **processo separato** (sostituisce anche utenti e sessioni, e può superare
  il timeout delle richieste); la pagina di avanzamento legge un file di stato e non usa il database, con
  indirizzo firmato.
- Nessuna cifratura dei backup nell'applicazione: restano sul server con permessi 700/600; la cifratura è
  raccomandata per le copie esterne (documentazione).
- Installazione su host con uno script bash rieseguibile (stesso approccio del Protocollo ANCR) e un secondo
  script per Proxmox che crea un LXC non privilegiato e lo riusa: un solo percorso di installazione da
  mantenere.

## ADR-027 - Posta scaricata spostata nella cartella PROCESSATA

- **Scelta**: dopo lo scaricamento i messaggi (nuovi o già presenti nel programma) si spostano nella cartella
  della casella indicata in `cartella_processata` (predefinita `PROCESSATA`, creata e sottoscritta se manca,
  con il prefisso del namespace personale letto con NAMESPACE: `INBOX.PROCESSATA` su Aruba/Courier);
  vuota = comportamento precedente in sola lettura. Si usa `UID MOVE`; in mancanza `UID COPY` + `\Deleted` +
  `UID EXPUNGE` dei soli messaggi copiati (UIDPLUS). Senza nessuna delle due non si sposta nulla e la casella
  va in errore: un `EXPUNGE` generico cancellerebbe anche messaggi eliminati dall'utente.
- **Motivo**: nella posta in arrivo restano solo i messaggi non ancora acquisiti, anche guardandola dalla
  webmail o dal client; nulla viene cancellato e la deduplica per Message-ID resta.
- Lo spostamento avviene dopo il salvataggio nel database, anche se lo scaricamento si interrompe a metà;
  i messaggi troppo grandi (oltre 50 MB) restano dove sono.

## ADR-028 - Servizi di invio separati dalle caselle di lettura

- **Scelta**: i server SMTP sono `core.ServizioInvio` (tipo email o PEC, credenziali cifrate come le caselle),
  gestiti in *Sistema → Servizi di posta*; le caselle (`protocollo.CasellaPosta`) servono solo a leggere.
  Il servizio «server generale» (uno solo, email) è usato dal backend Django `apps.core.invio.Backend`
  per comunicazioni, email dell'accesso e protocolli per email: con lui il mittente predefinito
  (`DEFAULT_FROM_EMAIL`) diventa il suo indirizzo. Senza servizio generale vale il server del `.env`.
- **Motivo**: un solo punto in cui si decide *come si spedisce* e un solo punto in cui si decide *cosa
  si legge*; prima l'SMTP generale stava nel `.env` e quello della PEC dentro la casella IMAP.
- **Migrazione**: il server del `.env` (se configurato davvero) diventa il servizio generale; le caselle
  «anche invio» della 1.0.18 diventano servizi con le stesse credenziali e le spedizioni passate vi restano
  collegate. Un servizio che ha spedito non si elimina (si disattiva).
- **Aggiornamento (1.0.23)**: anche la configurazione delle caselle IMAP passa in *Sistema → Servizi di
  posta* (permesso `core.gestisci_servizi_posta`); il protocollo decide solo quali usare (`attiva`,
  «usata dal protocollo», permesso `protocollo.change_casellaposta`). Una casella nuova nasce spenta.
- **Aggiornamento (1.0.24)**: ogni casella ha *Rispondi con* (`servizio_risposta`, compilato per indirizzo e
  tipo); `spedizioni.servizio_proposto` propone per una risposta il servizio della casella di arrivo, poi la
  PEC per il mezzo PEC, poi il server generale. La scelta resta all'utente.
- **Aggiornamento (1.0.25)**: gli scartati vanno nella cartella `cartella_scartata` (`SCARTATA`) e, se
  ripuliti con «anche dalla casella», nel cestino (attributo `\Trash` di LIST o nomi comuni; mai creato,
  mai per le PEC). Ancora nessuna cancellazione sul server. Gli spostamenti si accodano sul messaggio
  (`spostare_in`) e li esegue `posta.applica_spostamenti` dentro `scarica_casella`, cercando per Message-ID:
  niente IMAP durante le richieste web, ripetizione automatica in caso di errore.

## ADR-029 - Comunicazioni via PEC e su Telegram

- **PEC**: l'invio sceglie un servizio (`Invio.servizio`); con un servizio PEC il canale si decide per
  destinatario (`Destinatario.canale`): PEC a chi ce l'ha, email dal server generale agli altri, carta a chi
  non ha nessuno dei due. Le ricevute si agganciano per `X-Riferimento-Message-ID` (`esito_pec`, la consegna
  non torna indietro) e il messaggio della ricevuta si archivia fra gli scartati, senza protocollarlo.
- **Telegram** invece di WhatsApp: gratuito, nessuna approvazione di modelli né account aziendale. Un bot
  per organizzazione (`core.CanaleTelegram`, token cifrato); la persona si collega da sola con un link
  personale monouso (`/start <codice>`), `/stop` scollega. Comandi letti con `getUpdates` dal giro di
  `invia_coda`: niente webhook, quindi nessun indirizzo pubblico né porta da esporre. «Anche su Telegram»
  si aggiunge all'email (stesse regole di finalità e consenso); chi non ha l'email lo riceve solo lì.
- **SMS e WhatsApp Business** preparati senza un account di prova: `core.ServizioMessaggi` (Skebby e Aruba,
  stessa API REST v1.0; Twilio; API Cloud di Meta) e `comunicazioni.ConsegnaMessaggio` (una per destinatario e
  canale). Testo breve dedicato (l'email è troppo lunga); numeri portati a E.164; WhatsApp solo con modelli
  approvati (unico parametro `{{1}}`) e con il consenso registrato della persona (`whatsapp_consenso_il`),
  come richiede Meta. Indirizzo dell'API modificabile, perché le integrazioni sono provate solo con server finti.


## ADR-030 - API di interoperabilità (v1) *(approvata il 18/11/2026; F1 e F2 completate)*

**Contesto.** Servono due cose con lo stesso strumento: l'allineamento fra installazioni di questo
software (federazione 1:N sezioni, finora con file Excel) e l'interazione con «altri mondi» (siti
WordPress, app, gestionali) tramite adattatori **non inclusi in questo progetto**, scritti da terzi in
qualsiasi linguaggio. Requisito vincolante: canale **sicuro e affidabile**. Il TLS da solo non basta: in
produzione termina sul proxy (NPM) e prosegue in chiaro sulla LAN; più installazioni possono stare sulla
stessa rete interna (caso reale: lo stesso Proxmox) e parlarsi senza passare dal proxy.

### 1. Un contratto pubblico, non dei connettori

- Il prodotto è il **contratto**: `docs/api/openapi.yaml` (OpenAPI 3.1) è la fonte di verità; un test
  confronta viste e contratto. Gli adattatori stanno fuori; qui c'è solo il kit per scriverli
  (guida, vettori di prova, endpoint di verifica).
- Risorse **generiche**, non modellate su un sistema esterno: `eventi`, `adesioni`, `sezioni`, `soci`
  (con le tessere), `lotti`, `domande`, più il feed `cambiamenti`.
- Il client fra installazioni (federazione ↔ sezioni) è l'unico consumatore interno e usa **solo** l'API
  pubblica, senza scorciatoie: è la prova continua che il contratto basta.
- Versioni: `/api/v1`; in una versione solo aggiunte compatibili (campi nuovi, risorse nuove, valori
  nuovi negli elenchi aperti). Una rottura richiede `/api/v2`, con almeno 12 mesi di convivenza
  annunciati con `Deprecation` e `Sunset` (RFC 8594/9745).

### 2. Standard al posto di schemi propri

| Esigenza | Standard |
|---|---|
| Firma di richieste e risposte | HTTP Message Signatures (RFC 9421), `ed25519` |
| Integrità del corpo | `Content-Digest` (RFC 9530), `sha-256` |
| Cifratura per il destinatario | JWE compatto (RFC 7516), `ECDH-ES+A256KW` + `A256GCM`, chiavi X25519 (RFC 8037) |
| Pubblicazione delle chiavi | JWKS (RFC 7517) |
| Cambiamenti e notifiche | CloudEvents 1.0, formato JSON |
| Errori | Problem Details (RFC 9457) |
| Scritture ripetibili | intestazione `Idempotency-Key` |

### 3. Identità, controparti e abbinamento

- Ogni installazione ha un'**identità**: UUID d'istanza (creato alla prima migrazione) e due coppie di
  chiavi, Ed25519 per firmare e X25519 per ricevere dati cifrati. Le chiavi private stanno nel DB cifrate
  con `CHIAVE_CIFRATURA`; la rotazione mantiene la chiave precedente valida per un periodo di
  sovrapposizione (`kid` distinti). L'identità **non** dipende da indirizzo IP o nome host.
- **`ClienteApi`** (controparte): tipo `installazione` o `integrazione`, stato (`in_prova`, `attiva`,
  `sospesa`, `revocata`), chiavi pubbliche, **ambiti**, sezioni visibili, indirizzi IP ammessi,
  scadenza, indirizzi di raggiungibilità (§6), sottoscrizioni alle notifiche.
- Ambiti iniziali: `eventi:lettura`, `adesioni:lettura`, `adesioni:scrittura`, `sezioni:lettura`,
  `soci:lettura`, `lotti:lettura`, `domande:scrittura`, `consegne:scrittura` (modalità a spinta, §7).
  Un'integrazione non riceve mai `soci:lettura` senza una scelta esplicita dell'amministratore, con
  avviso sul trattamento dei dati.
- **Abbinamento**: l'amministratore crea un *invito monouso* (validità 24 ore); la controparte lo usa
  per presentare le proprie chiavi pubbliche e ricevere le nostre. Entrambe le parti mostrano
  l'**impronta** delle chiavi (SHA-256, a gruppi di cifre), da confermare per una seconda via (telefono,
  atto protocollato). Fino alla conferma la controparte resta `in_prova`: solo `/prova` e dati finti.
  Il passaggio ad `attiva` richiede un permesso nuovo (`api.gestisci_controparti`, solo all'amministratore).
- Revoca immediata; sospensione automatica alla scadenza; tutto nel registro attività.

### 4. Firma di ogni messaggio

- Richieste **e risposte** firmate (RFC 9421). Componenti coperti nella richiesta: `@method`, `@path`,
  `@query`, `content-digest` (se c'è un corpo), `destinatario-istanza`; parametri `created`, `expires`,
  `nonce`, `keyid`, `alg="ed25519"`, `tag="ga-v1"`.
- **`@authority` non è firmato**, perché la stessa installazione si raggiunge per nome pubblico o per
  indirizzo interno (§6). Al suo posto l'intestazione firmata **`Destinatario-Istanza`** (UUID
  dell'istanza destinataria): chi riceve rifiuta i messaggi indirizzati ad altri. Così un messaggio
  per un'installazione non può essere dirottato su un'altra, anche sullo stesso host.
- La risposta firma `@status`, `content-digest` e la firma della richiesta (`"signature";req`): una
  risposta non si può riusare per un'altra richiesta.
- Rifiuti: firma non valida, `created` fuori da ±300 secondi, `expires` superato, **nonce già visto**
  (conservato 10 minuti nel DB), controparte non attiva, IP non ammesso, ambito mancante.
- L'elenco degli IP ammessi è un livello in più, non l'identità: dietro il proxy l'IP viene da
  `rete.ip_client` (solo da `PROXY_FIDATI`), nelle chiamate dirette è `REMOTE_ADDR`.

### 5. Cifratura dei dati personali

- I corpi con dati personali (soci, tessere, adesioni, domande, consegne) viaggiano **sempre** come JWE
  per la chiave X25519 del destinatario (`Content-Type: application/jose`), in entrambe le direzioni e
  indipendentemente dal trasporto. Il proxy, i suoi log e la LAN vedono solo dati cifrati.
- La firma HTTP copre il corpo cifrato e identifica il mittente; la cifratura autenticata (AES-GCM)
  garantisce il contenuto. I dati pubblici (eventi pubblici, sezioni) sono solo firmati.

### 6. Trasporto e rete interna

- Ogni controparte ha fino a due indirizzi: **interno** (preferito, se impostato) e **pubblico** (riserva).
  Se l'interno non risponde si passa al pubblico, e il passaggio finisce nel registro.
- **HTTPS è la regola anche in rete interna.** Ogni indirizzo ha la propria **modalità di verifica del
  certificato**, mai disattivabile:
  - `pubblica`: autorità di certificazione del sistema e nome dell'host (indirizzi pubblici, ma anche
    interni con certificati Let's Encrypt ottenuti via DNS);
  - `ca_interna`: autorità di certificazione dell'organizzazione (PEM salvato sulla controparte, es.
    una CA del Proxmox o di `step-ca`) e nome dell'host o IP presente nel certificato;
  - `impronta`: certificato anche autofirmato, accettato solo se l'impronta SHA-256 della sua chiave
    pubblica (SPKI) coincide con quella registrata. L'impronta si scambia durante l'abbinamento
    (campo `tls_spki` dell'istanza) e si conferma con quella delle chiavi; rinnovando il certificato
    con la stessa chiave non cambia, con una chiave nuova la controparte la ripresenta firmata con la
    propria chiave Ed25519 e il cambio finisce nel registro.
- Verso indirizzi pubblici: solo HTTPS con modalità `pubblica`.
- **`http://` in chiaro** resta un'eccezione per la rete interna: solo se l'indirizzo è privato o locale
  (RFC 1918, `fc00::/7`, loopback), la controparte è segnata «rete interna» **e** l'amministratore
  abilita esplicitamente il trasporto in chiaro, con avviso nel cruscotto *Collegamenti*. Firma, nonce e
  cifratura dei dati personali non cambiano, ma si perde la riservatezza dei metadati (percorsi, dati
  pubblici).
- Ordine dei tentativi: interno HTTPS → interno HTTP (solo se abilitato) → pubblico HTTPS.
- Il TLS reciproco (mTLS) non è richiesto: l'identità è già data dalla firma, che attraversa anche i
  proxy. Resta possibile come livello in più sulle connessioni dirette.
- Lato server, HTTPS in rete interna si ottiene con il proxy locale (NPM o simili) oppure con Gunicorn
  direttamente (`installa.sh --tls-cert/--tls-key` o `--tls-autofirmato`, dalla 1.0.36).
  La guida [HTTPS anche in rete interna](../sistema/https-rete-interna.md) spiega come creare la CA
  (step-ca) o il certificato autofirmato e come calcolare l'impronta SPKI; la documentazione e
  l'interfaccia consigliano sempre HTTPS anche in LAN.
- Più installazioni sullo stesso host (porte o container diversi) si distinguono per
  `Destinatario-Istanza`, non per indirizzo. L'indirizzo interno va aggiunto ad `ALLOWED_HOSTS`.
- Protezione dalle richieste forgiate (SSRF): le chiamate in uscita vanno **solo** agli indirizzi
  registrati sulla controparte; gli indirizzi privati solo con il segno «rete interna»; i redirect non
  si seguono; il nome si risolve e si ricontrolla a ogni chiamata (contro il DNS rebinding).

### 7. Affidabilità: feed dei cambiamenti

- Ogni operazione rilevante dei servizi scrive un **`Cambiamento` nella stessa transazione** (outbox):
  se l'operazione c'è, c'è anche il cambiamento, e viceversa. I servizi restano l'unico punto di scrittura.
- **Flussi** separati (`eventi`, `sezioni`, `soci:<codice sezione>`, `lotti:<codice sezione>`), ognuno
  con un **numero progressivo senza buchi** (`numerazione.prossimo_numero`, sequenza `feed_<flusso>`) e
  una **catena di impronte**: `impronta = SHA-256(impronta precedente ‖ JSON canonico dell'evento)`.
  Chi legge si accorge di voci mancanti, alterate o riordinate e si ferma.
- Gli eventi (CloudEvents) dicono **cosa** è cambiato (tipo, UUID, versione), non portano i dati: la
  risorsa si legge a parte, con i propri ambiti. Tipi: `it.gestioneassociazione.<risorsa>.<azione>.v1`
  (`creato`, `modificato`, `annullato`, `cessato`, `anonimizzato`, …). `anonimizzato` obbliga chi
  legge ad anonimizzare la propria copia (GDPR).
- Ogni risorsa esposta ha `uuid` (nuovo campo) e `versione` (intero crescente, anche come `ETag`).
- **Consegna almeno una volta, applicazione una volta sola**: chi legge salva il cursore nella stessa
  transazione in cui applica. Le scritture in ingresso richiedono `Idempotency-Key` (conservata 30
  giorni con l'impronta del corpo: stessa chiave e corpo diverso ⇒ 422).
- Conservazione del feed: 400 giorni. Un cursore più vecchio riceve **410** e va fatta una
  **risincronizzazione** completa, sempre con anteprima.
- **Riconciliazione**: `GET /riepiloghi/{flusso}` restituisce numero e impronta delle coppie
  (uuid, versione) ordinate; se divergono, si propone la risincronizzazione.
- **Notifiche** (opzionali): un CloudEvent firmato e senza dati personali verso l'indirizzo della
  controparte. Sono solo un avviso: se si perdono, la lettura periodica recupera tutto. Ripetizioni
  con attesa crescente (da 1 minuto a 24 ore), poi coda degli errori visibile, mai scarto silenzioso.
- **Modalità a spinta** per chi non è raggiungibile (sezione dietro NAT o senza HTTPS pubblico):
  la sezione invia i propri cambiamenti, con le risorse cifrate, a `POST /consegne`. Stesso formato,
  stessa catena; il destinatario risponde con l'ultimo progressivo applicato. Chi riceve **non**
  applica alla cieca: memorizza e applica con le regole dell'importazione (anteprima o automatica,
  a scelta). Resta valido il principio «nessuna installazione scrive nei dati di un'altra».
- Cruscotto *Collegamenti*: ultima sincronizzazione riuscita, ritardo, errori, scadenza delle chiavi;
  avviso agli amministratori dopo N fallimenti consecutivi.

### 8. Autorità del dato fra installazioni

- Socio, tessere attribuite e cessazioni: **della sezione**. Lotti e carte (numerazione della sede
  centrale): **della federazione**. Ognuno legge l'altro e applica con lo stesso codice
  dell'importazione (`soci.importazione`): abbinamento per codice fiscale, matricola, nominativo.

### 9. Scritture dai sistemi esterni

- **Adesioni agli eventi** (`adesioni:scrittura`): `POST /eventi/{uuid}/adesioni` passa da
  `eventi.servizi.aderisci` con una nuova origine `integrazione` (stesse regole del modulo pubblico:
  adesioni aperte, posti, accompagnatori) e la controparte registrata. Solo eventi visibili alla
  controparte (per un'integrazione: `pubblico=True`). Annullamento con `DELETE` e `If-Match`.
- **Domande di iscrizione** (`domande:scrittura`): `POST /domande` crea una domanda `in_attesa` con
  origine nuova `integrazione`, stessi campi e consensi obbligatori del modulo pubblico; **mai**
  accolta in automatico. L'anti-spam del modulo è sostituito da identità della controparte e limiti
  di frequenza.
- Limiti di frequenza per controparte (429 con `Retry-After`); ogni scrittura nel registro attività.

### 10. Implementazione

- Nuovo modulo `apps/api` con **viste Django semplici** (niente framework REST): firma, verifica,
  cifratura e controlli in un unico punto, sul modello di `cifratura.py`. Ed25519, X25519 e AES-GCM
  da `cryptography` (già presente). RFC 9421 scritta qui, verificata con gli esempi dell'RFC
  (Appendice B); per il JWE si valuta `joserfc` (BSD-3), altrimenti un'implementazione minima della
  sola combinazione ammessa, verificata con vettori di prova.
- Client fra installazioni in un modulo a parte (`apps/collegamenti`), con lavori rieseguibili nel
  `pianificatore`.
- Fasi: **F1** identità, controparti, abbinamento, firma, `/prova`, registro → **F2** feed, `eventi`,
  `sezioni`, notifiche → **F3** adesioni e domande in ingresso → **F4** cifratura, `soci`, `lotti`,
  client federazione (lettura e spinta), riconciliazione, cruscotto → **F5** kit per chi integra
  (guida in `docs/api/`, vettori di prova, dati finti per lo stato `in_prova`).

**Dettagli fissati con la F1.**

- Il `kid` di ogni chiave, nostra e delle controparti, è la sua impronta **RFC 7638**: si rifiutano
  JWKS con `kid` scelti a mano. Così la chiave si trova senza ambiguità e non si può «prestare» un
  `kid` altrui.
- **Impronta dell'abbinamento**: SHA-256 delle impronte RFC 7638 di tutte le chiavi in uso delle due
  parti, ordinate e unite da `\n`, mostrata come 8 gruppi di 4 cifre esadecimali. È identica sulle
  due installazioni e l'abbinamento si interrompe se le due parti non la calcolano uguale.
- Il codice d'invito si conserva solo come impronta SHA-256 e si mostra una volta.
- Il nonce si registra **dopo** la verifica della firma, perché chi non ha la chiave non deve poter
  «bruciare» nonce altrui. Si conserva 10 minuti.
- Ogni risposta è firmata, anche quelle senza autenticazione (`/.well-known`) e gli errori.
- Con la verifica **impronta**, un certificato rinnovato con chiave nuova (`step ca renew`, certbot)
  cambia l'impronta. Fino all'aggiornamento automatico delle impronte, previsto in F2, per i
  certificati che si rinnovano da soli è da preferire **CA interna**. `/.well-known` è firmato e
  pubblica già le impronte correnti (`tls_spki`).

**Dettagli fissati con la F2.**

- L'outbox sta nel `save()` dei modelli esposti (`apps.api.risorse.RisorsaApi`): salvataggio,
  versione e cambiamento sono nella stessa transazione da qualunque punto di scrittura. Restano
  fuori solo gli `update()` di massa, che non si usano su questi modelli. La versione si aumenta
  con un `UPDATE … + 1` atomico e non viene mai scritta dal `save()` ordinario, così una copia in
  memoria non aggiornata non la riporta indietro.
- Le adesioni fanno avanzare la versione dell'evento, perché cambiano `posti_liberi`.
- Il feed porta tutte le voci del flusso. Le risorse non visibili alla controparte, ad esempio gli
  eventi non pubblici per le integrazioni, rispondono 404 e il riepilogo conta solo quelle
  visibili.
- Rotazione delle chiavi dell'istanza: firme multiple sulle risposte (`ga` per la chiave in uso,
  `ga1`… per quelle in uscita). Il client accetta una JWKS nuova solo se è firmata da una chiave
  già nota e la rilegge da solo quando incontra un `keyid` sconosciuto. Le integrazioni usano
  `PUT /chiavi`.
- Impronte TLS: `aggiorna_collegamenti` le rilegge ogni notte dalla `/.well-known` firmata.
- Notifiche come outbox: righe `NotificaApi` create nella stessa transazione del cambiamento e
  consegnate dal pianificatore.

**Perimetro deciso il 18/11/2026** (sostituisce l'elenco delle fasi del §10).

| Fra | Direzione | Cosa |
|---|---|---|
| Esterno (sito, app) | dal gestionale | eventi pubblici e sezioni (F2), **documenti pubblici**, **organigramma pubblico**, **verifica di una tessera** (valida sì/no, anno, sezione) |
| Esterno | verso il gestionale | **adesioni** agli eventi (e annullamento), **domande di iscrizione** (mai accolte in automatico), **messaggi del modulo contatti** (tra la posta da protocollare) |
| Federazione ↔ sezione | sezione → federazione | soci e tessere, cessazioni, anonimizzazioni; **cariche sociali**; **numeri del tesseramento** (conteggi senza dati personali) |
| Federazione ↔ sezione | federazione → sezione | lotti e carte; **eventi provinciali** a cui le sezioni iscrivono i propri soci (adesioni come installazione) |
| Sezione ↔ sezione | in entrambe le direzioni | **trasferimento di un socio** con consenso (consegna della scheda, accolta dalla sezione di arrivo), **eventi condivisi**, **verifica di una tessera**; mai elenchi dei soci altrui |

**Principio (18/11/2026): l'interoperabilità è sempre facoltativa.** Ogni processo che coinvolge più
installazioni deve funzionare per intero anche senza API: documenti stampabili e spedibili dal
protocollo (email, PEC), file importabili con anteprima, registrazioni a mano. L'API automatizza
lo scambio degli stessi documenti, non introduce passaggi propri. Il primo processo analizzato
così è il ciclo delle tessere ([analisi](../analisi/ciclo-tessere.md)): si realizza prima come
funzione del gestionale, poi lo scambio via API in F4.

Esclusi per ora: documenti protocollati fra installazioni, iscrizione alle liste da sistemi esterni,
pagamenti online.

Fasi: **F3** cifratura JWE, `Idempotency-Key`, limiti di frequenza, tutto il perimetro «esterno»
(primo collaudo in produzione fra 192.168.0.34 e la sezione di Avigliano) → **F4** federazione ↔
sezione → **F5** sezione ↔ sezione e kit per chi integra.

**Conseguenze.** Lo scambio Excel resta come riserva. Le integrazioni con WordPress e simili non si
sviluppano qui. Ogni modello esposto riceve `uuid` e `versione`. Nuovi permessi in `ruoli.py` e pagine
in `docs/operativo/` e `docs/sistema/` (abbinamento, rete interna, `ALLOWED_HOSTS`).
