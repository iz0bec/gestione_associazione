# Changelog

Tutte le modifiche rilevanti del progetto. Formato: [Keep a Changelog](https://keepachangelog.com/it/1.1.0/);
versioni: [Semantic Versioning](https://semver.org/lang/it/).

## [Non rilasciato]

### Aggiunto

- Modulo **Progetti** (in sviluppo, ramo `progetti`): finalità statutarie e criteri di valutazione
  configurabili; idee e necessità, anche da un protocollo in entrata o dalla posta da protocollare;
  valutazione con media pesata, priorità e delibera; progetti con stati e storico, gruppo di lavoro
  con i volontari, scadenze nel calendario, documenti e discussione; ruolo combinabile «Progettista»;
  comando `importa_finalita`.

## [1.0.99] - 2026-11-25

### Modificato

- **Menu laterale riordinato per argomenti**: in alto Cruscotto, Calendario e Chat, poi i gruppi
  *Soci* (anagrafica, soci, domande, tesseramento, campagna delle tessere), *Segreteria* (protocollo,
  posta da protocollare, comunicazioni, documenti), *Vita associativa* (organi, eventi, anniversari)
  e *Amministrazione* (tesoreria, patrimonio); in *Sistema* le voci sono divise in configurazione,
  accessi e collegamenti, dati e manutenzione. Un gruppo compare solo se l'utente ne vede almeno una voce;
  i gruppi si chiudono e si riaprono con un clic sull'intestazione (scelta ricordata nel browser, il
  gruppo della pagina aperta resta sempre aperto).

## [1.0.98] - 2026-11-25

### Aggiunto
- **Connettore WordPress 0.2.0**: un proprio **calendario degli eventi**, senza plugin esterni come
  The Events Calendar. Gli eventi «pubblica sui siti collegati» diventano eventi del sito con archivio
  (viste elenco, mese e giorno), pagina dell'evento con data, luogo e mappa, posti e modulo di
  adesione dal gestionale, iCal (feed e singolo evento) e Google Calendar, dati strutturati
  schema.org/Event; blocchi «Calendario degli eventi» e «Prossimi eventi»; aggancio
  `ga_evento_sincronizzato`. La modalità ad articoli resta disponibile.

## [1.0.97] - 2026-11-25

### Aggiunto
- **Importazione dai gestionali precedenti completata**: da Gestione Soci le **foto dei soci** (solo
  per le schede senza foto; opzione `--file` per la cartella dei file), i **passaggi di consegne**
  del patrimonio (con l'elenco dei beni di allora e il PDF) e le **cessioni dei beni** (prestiti con
  la restituzione, donazioni, alienazioni); da Gestione Assemblee le **assemblee e riunioni del
  direttivo** con l'ordine del giorno e i **verbali**, importati aperti da rivedere e chiudere.
  Tutto rieseguibile.

## [1.0.96] - 2026-11-25

### Aggiunto
- **F5, collegamenti fra sezioni**: **trasferimento di un socio** a un'altra sezione (o federazione)
  collegata, con il **consenso** del socio registrato: richiesta dalla scheda del socio, accoglimento o
  rifiuto in *Soci → Trasferimenti* nell'installazione di arrivo, esito che torna indietro (il socio
  cessa con la nuova causa «trasferimento ad altra sezione»); la **federazione sposta** il socio fra le
  due sezioni con l'allineamento automatico. Nuovi endpoint `POST /api/v1/trasferimenti` e
  `/trasferimenti/{uuid}/esito` (ambito `trasferimenti:scrittura`).
- Eventi condivisi e cariche anche fra **installazioni pari** (sezione ↔ sezione), mai i numeri dei soci.
- **Verifica di una tessera** di un'altra installazione dall'interno del gestionale (codice o
  indirizzo del QR).
- **Kit per chi integra** (`docs/api/kit-integrazione.md`): passi, firma, cifratura, errori,
  implementazioni di riferimento e prove.

## [1.0.95] - 2026-11-25

### Aggiunto
- **F4 completata**: dalle installazioni collegate (federazione e sezioni) si leggono ogni 15 minuti
  (lavoro `aggiorna_condivisi`) le **cariche** e i **numeri del tesseramento** (nuovo endpoint
  `GET /api/v1/tesseramento`, solo conteggi), mostrati in *Soci → Sezioni → Installazioni
  collegate* accanto ai numeri locali, con le differenze evidenziate.
- **Eventi condivisi**: nuova scelta «Condividi con le installazioni collegate»; gli eventi condivisi
  dagli altri compaiono fra gli eventi e nel calendario e si possono **iscrivere i propri soci**
  (solo cognome e nome, cifrati); presso l'organizzatore l'adesione indica l'installazione che l'ha
  inviata.
- Avvisi (Telegram, SMS, WhatsApp): registrati nel log anche quelli riusciti.
- API: campo `condiviso` negli eventi (aggiunta compatibile del contratto v1).

## [1.0.94] - 2026-11-24

### Aggiunto
- **Guide rapide per ruolo** nel manuale operativo (e nell'aiuto in linea): amministratore,
  presidente, segretario, tesoriere, presidente di sezione, addetto al protocollo, consigliere e
  revisore, con i flussi essenziali per passaggi chiave e le schermate; nuove schermate del manuale
  (domande, rinnovo annuale, campagna delle tessere, protocollo, prima nota, riunioni, comunicazioni,
  eventi, registro attività, rinnovi degli organi, collegamenti).

## [1.0.93] - 2026-11-24

### Aggiunto
- **Allineamento automatico dei soci fra federazione e sezione** (F4): dopo una prima *Verifica
  soci* applicata si attiva dalla scheda della controparte; ogni 15 minuti (lavoro `allinea_soci`
  del pianificatore) i soci si allineano da soli in **ordine di tempo** rispetto all'ultimo
  allineamento, con le regole di *chi aggiorna cosa*. Un socio cambiato da entrambe le parti è
  un'**incongruenza**: vale la modifica più recente e parte un'email; le voci che non si sistemano
  da sole restano da verificare a mano. Ogni giro con novità lascia un allineamento consultabile e
  un'**email a chi gestisce i soci** (supervisione della federazione su rinnovi, nuovi soci e
  cessazioni). Pulsanti *Allinea ora* e *Disattiva*.
- **Soci a spinta** (`POST /api/v1/consegne`, flusso `soci`): la sezione che la federazione non
  raggiunge le invia l'elenco dei suoi soci quando cambia; la federazione lo applica da sé o ne fa
  una verifica da decidere.
- Roadmap: eventi del connettore WordPress come tipo di contenuto proprio; guide rapide per ruolo.

## [1.0.92] - 2026-11-24

### Corretto
- **Connettore WordPress 0.1.2**: quando il cron aggiorna il titolo dell'articolo di un evento,
  dal testo del redattore non spariscono più video incorporati, iframe e altro HTML consentito solo
  agli amministratori (prima WordPress risalvava tutto l'articolo passandolo al filtro kses).

## [1.0.91] - 2026-11-24

### Corretto
- **Connettore WordPress 0.1.1**:
  - **coda degli invii**: una voce per invio; prima una domanda, un contatto o un'adesione
    accodati mentre il cron svuotava la coda potevano andare persi. Gli errori transitori
    (collegamento sospeso, orologio, richiesta gemella in corso, pagine d'errore del proxy) si
    ritentano con attesa crescente per 7 giorni; poi l'invio resta «non consegnato» nelle
    impostazioni, da rimettere in coda o eliminare, mai scartato in silenzio;
  - **adesione agli eventi**: dopo un invio riuscito o accodato non compare più un errore (che
    portava a rimandarla, con adesioni doppie);
  - **articoli degli eventi**: un articolo cestinato o eliminato dal redattore non viene ricreato
    (con «Pubblicato subito» tornava online); titolo come testo semplice;
  - **anti-spam**: il gettone del modulo si rinnova al caricamento della pagina, così i moduli non
    scadono con la cache di pagina.

## [1.0.90] - 2026-11-24

### Aggiunto
- **Connettore WordPress** (`integrazioni/wordpress/gestione-associazione`, plugin 0.1.0, CC0):
  collega un sito al gestionale come integrazione delle API v1, con richieste firmate (RFC 9421) e
  dati personali cifrati (JWE). Shortcode e blocchi per **domanda di iscrizione**, **modulo
  contatti**, **eventi con adesione**, **organigramma** e **verifica della tessera**; **articoli degli
  eventi** (in bozza per default, aggiornati, «ANNULLATO» se annullati, mai cancellati); **coda
  cifrata** se il gestionale non risponde; anti-spam senza servizi esterni. PHP puro (sodium e
  openssl), provato con i vettori ufficiali e con una prova incrociata contro il gestionale. Guida in
  *docs/sistema/connettore-wordpress.md*.
- Eventi: nuova scelta **«Pubblica sui siti collegati»**; l'API degli eventi espone il campo `sito`
  (aggiunta compatibile del contratto v1).

## [1.0.89] - 2026-11-24

### Corretto
- Campagna delle tessere: le conferme di ricezione **in bozza** non contano più come inviate
  («confermate N su M (K in bozza)»); accanto alla richiesta l'etichetta distingue «confermata» da
  «conferma in bozza».

## [1.0.88] - 2026-11-24

### Corretto
- **Conferma di ricezione della richiesta di tessere**: non si poteva confermare («Segnaposto
  sconosciuti: data_richiesta, riferimento»). I segnaposto della conferma ora sono registrati
  (`data_richiesta`, `riferimento_richiesta`).

## [1.0.87] - 2026-11-24

### Corretto
- Campagna delle tessere nella federazione: le **richieste arrivate dal collegamento** e ancora da
  registrare compaiono nella **fase 2** («da registrare», con il pulsante «Registra la richiesta»),
  nel riepilogo della fase e, nella fase 1, come «arrivata, da registrare»; prima stavano solo nel
  riquadro dei documenti in arrivo in cima alla pagina.

## [1.0.86] - 2026-11-24

### Corretto
- Campagna delle tessere: articoli nei titoli della direzione verso l'ente sovraordinato («Invito
  ricevuto dalla Federazione», «Pagamento alla sede nazionale»).

## [1.0.85] - 2026-11-24

### Modificato
- **Campagna delle tessere divisa per direzione e per fasi**: *verso le sezioni* (solo nella
  federazione: invito alla richiesta con lo stato di ogni sezione, richieste ricevute con la
  conferma, consegne, incassi) e *verso l'ente sovraordinato* (sezione → Federazione, federazione →
  sede nazionale: invito ricevuto, richiesta o ordine, tessere ricevute, pagamento), con lo stato
  di ogni fase in cima. Il gestionale di una sezione non mostra più avvisi, ordini e magazzino della
  federazione, né la federazione l'importazione della consegna. Nuovo **invito ricevuto** collegato
  al protocollo in entrata (proposto in automatico dall'oggetto), citato dalla richiesta per email.

## [1.0.84] - 2026-11-24

### Corretto
- **Richiesta di tessere da una sezione senza soci nel gestionale**: il fabbisogno calcolato era zero
  e non c'era modo di inviarla (il pulsante «Registra» la segnava come già inviata). Ora, nel
  gestionale di una sezione, «Registra» prepara la richiesta con la quantità scritta a mano, da
  inviare alla federazione dal riquadro *Richieste in preparazione*; l'aggiornamento dei rinnovi non
  la toglie più (solo «Ricalcola»).

## [1.0.83] - 2026-11-24

### Corretto
- **Campagna tessere nella federazione**: il pulsante accanto alle richieste delle sezioni preparava
  l'email «richiesta di tessere alla federazione» (pensata per il gestionale di una sezione), che
  nella federazione partiva verso la federazione stessa. Ora nella federazione prepara la
  **conferma di ricezione alla sezione** (casella della sezione e presidente in carica, con il
  riepilogo della richiesta allegato); l'email «alla federazione» resta solo nei gestionali delle
  sezioni.

### Aggiunto
- **Rinnovo degli organi a scadenza del mandato** (nuovo modulo, *Organi sociali → Rinnovo degli
  organi*): procedura elettorale guidata con i **profili elettorali** (ANCR congresso sezionale e
  provinciale, assemblea ETS generica; modificabili): termini calcolati dalla scadenza dei mandati,
  indizione, assemblea, convocazione con gli **aventi diritto fissati all'avviso** (soci in regola;
  per la federazione le sezioni con i voti dei loro soci) e avviso in bozza in Comunicazioni,
  **compilazione delle liste** con il controllo della composizione per soglia di soci, dei supplenti,
  delle doppie candidature, delle quote e delle accettazioni, modulo da firmare, presentazione
  protocollata, ammissione o esclusione motivata, esiti del voto (alzata di mano o scrutinio, deleghe,
  schede, parità), proclamazione, rinunce, ricorsi, **insediamento automatico** delle nuove cariche
  negli organi sociali, passaggio di consegne, trasmissione dei verbali protocollata. Verbali dai
  modelli del Regolamento ANCR (B1/B2, C1/C2/C3, D1/D2, D3/D4, G/G1), scheda e aventi diritto in PDF;
  scadenze nel calendario e nel cruscotto.
- **Decadenza anticipata degli organi e commissariamento**: dall'elenco dei rinnovi si registra la
  fine anticipata del consiglio (dimissioni, scioglimento, nuova sezione): decadono consiglio e
  sindaci (cariche chiuse) e subentra il **commissario** (nuova carica degli organi sociali, che firma
  al posto del presidente) o, finché l'ente sovraordinato non lo nomina, il presidente decaduto come **commissario provvisorio**; si apre il **rinnovo straordinario** entro dodici mesi (prorogabili), chiuso
  all'insediamento dei nuovi organi.
- **Conformità al Regolamento ANCR nel rinnovo**: registro dei votanti al seggio con le deleghe (al
  massimo due, al socio presente), commissione elettorale obbligatoria con più liste, avviso oltre
  le tre ore di voto, schede di peso diverso per il congresso provinciale (commissario come
  rappresentante delle sezioni commissariate), adempimenti (elenco soci alla Federazione, schede
  depositate, vidimazione, ratifica), subentro dei supplenti a chi non accetta, prima riunione del
  nuovo consiglio, cooptazione dei supplenti, determinazioni numerate e relazione del commissario,
  commissario amministrativo.
- **Fornitori di posta**: in *Sistema → Servizi di posta*, creando una casella (IMAP) o un servizio di
  invio (SMTP), il menu **Fornitore** compila server, porta, cifratura e PEC: Aruba (email e PEC),
  Legalmail, Poste PEC, Libero, Virgilio, Tiscali, TIM, Gmail e Microsoft 365, con le note utili
  (password per le app, accesso dalla sola rete TIM…). Gli amministratori aggiungono **fornitori
  personalizzati** (es. la posta del proprio dominio), proposti in cima al menu. Nuova spunta
  **Verifica l'accesso dopo il salvataggio** per provare subito il collegamento.
- **Inoltro della email di sezione dal gestionale**: in *Sistema → Servizi di posta*, pulsante
  **Inoltro** di una casella. I messaggi scaricati vanno alle persone scelte dall'anagrafica (più
  indirizzi liberi) con un reindirizzo trasparente (mittente originale, intestazioni `Resent-*`); se il
  server lo rifiuta, «Inoltro: …» con l'originale allegato. I messaggi **riservati** (credenziali «per
  conto», ora segnate con `X-Gestione-Riservato`) vanno solo all'**incaricato della trattazione**.
  Coda rieseguibile con i tentativi, ultimi inoltri nella pagina, registro attività.
- **Esenzione dal secondo fattore per singolo utente**: dalla scheda in *Sistema → Utenti*, per chi non
  può attivarlo (niente smartphone né chiave di sicurezza) anche se il ruolo lo richiede; motivo
  obbligatorio e scadenza facoltativa, indicata nell'elenco degli utenti, nel registro attività e
  negli avvisi di sicurezza; revocabile; mai per l'Amministratore di sistema né per se stessi.

## [1.0.82] - 2026-11-22

### Modificato
- **Comunicazioni della campagna tessere riconoscibili**: gli avvisi alle sezioni (tesseramento,
  sollecito, attribuzione) hanno l'oggetto con la sezione («… – Sezione di Ruoti»), anche nel
  protocollo. L'elenco *Comunicazioni* mostra sotto l'oggetto **a chi va** (la sezione, il
  destinatario o «N destinatari», anche per gli invii già fatti), con la **ricerca** per oggetto o
  destinatario e il **filtro per origine** (campagna tessere, convocazioni, auguri, promemoria,
  domande, tessere, credenziali, scritte a mano).
- Roadmap: tabella dei rilasci aggiornata fino alla 1.0.82.

## [1.0.81] - 2026-11-22

### Corretto
- **Modulo di richiesta delle tessere aperto con Numbers** (Mac, iPad): non veniva riconosciuto,
  perché Numbers toglie il foglio nascosto con la firma e rinomina il foglio. Ora il modulo porta
  anche un **codice di controllo visibile** (in fondo al foglio) che resta dopo l'esportazione in
  Excel; i moduli già inviati senza firma si riconoscono dalla struttura come **non verificati**, con
  l'avviso di controllare il mittente; un allegato `.numbers`, `.ods` o `.xls` sulla posta da
  protocollare viene segnalato con le istruzioni (prima era ignorato in silenzio). Le istruzioni del
  modulo spiegano come rispondere da Numbers (File → Esporta come → Excel).

## [1.0.80] - 2026-11-22

### Aggiunto
- **Composizione degli organi**: anche in forma di **organigramma con le foto** dei componenti (una
  pagina per organo, senza recapiti, utile per riconoscerli), scelta nella stessa pagina della stampa
  unica.
- **Sezioni**: indirizzo della sede, CAP e **PEC** (*Sistema → Sezioni*).
- Roadmap: **rinnovo degli organi a scadenza del mandato** (fasi, termini e modelli dallo Statuto e
  dal Regolamento ANCR, generalizzati in profili elettorali per altre associazioni).

### Corretto
- **Composizione degli organi (PDF)**: il gruppo principale porta il nome dell'ente (non più
  «Associazione») e ogni gruppo riporta i recapiti dell'ente o della sezione: indirizzo postale,
  email e PEC.

## [1.0.79] - 2026-11-22

### Aggiunto
- **Composizione degli organi in un unico PDF** (*Organi sociali → Composizione (PDF)*): cariche in
  corso di tutti gli organi (o solo dell'associazione, o di una sezione) alla data scelta, raggruppate
  per associazione e sezioni, con nominativo, data di nomina ed **email e telefono di contatto** per
  chi vede i recapiti in anagrafica (documento a uso interno, stampa nel registro attività).

## [1.0.78] - 2026-11-22

### Aggiunto
- **Utenti da riga di comando**: `manage.py utenti` elenca gli utenti (ruoli, secondo fattore,
  ultimo accesso, email vera o segnaposto, password predefinita disponibile); `--reimposta NOME`
  riporta la password alla **predefinita** (per gli amministratori quella iniziale dell'installazione,
  per gli altri quella della carica) e come ultimo passo chiede se inviare subito l'email con le
  credenziali (`--invia`, `--senza-email`; altrimenti resta in bozza). `sezioni.sh utenti` per tutte
  le sezioni di un host.
- L'installatore crea `/etc/<installazione>/password-predefinite.json` con la password iniziale
  dell'admin (ripresa dal file delle credenziali per le installazioni esistenti) e la indica nel `.env`
  (`PASSWORD_PREDEFINITE`).

## [1.0.77] - 2026-11-22

### Modificato
- **Utenti dalle cariche**: le credenziali di chi non ha l'email vanno alla **casella istituzionale
  dell'ente**, all'attenzione dell'incaricato della trattazione (di norma il presidente); la carica
  più alta dello stesso organo con un'email resta solo se l'ente non ha una casella.
- Roadmap: in programma la gestione dell'**inoltro della casella di sezione** dal gestionale (oggi lo
  fa il fornitore della posta).

## [1.0.76] - 2026-11-22

### Modificato
- **Utenti dalle cariche**: per chi non ha l'email la bozza con le credenziali va **per conto** alla
  carica più alta dello stesso organo con un'email (o alla casella dell'ente), con l'invito a
  consegnarle, a dotarsi di un'email e a usare quei dati solo per la consegna. Le bozze non dicono più
  che la password è uguale per chi ha la stessa carica e indicano dove trovare il manuale (pulsante
  **?**, menu → *Manuale* → *Manuale in PDF*, PDF pubblico).

## [1.0.75] - 2026-11-22

### Aggiunto
- **Utenti dalle cariche** (*Sistema → Utenti*): crea in una volta gli utenti di chi ha una carica in
  corso negli organi sociali e non ha ancora un utente, con i ruoli dalla carica (presidente e
  vice → Presidente, segretario → Segretario e Tesoriere, consiglieri → Consigliere, organo di
  controllo → Revisore), una password per tipo di carica (scelta o generata, mostrata una volta),
  utenti attivi solo per le cariche scelte (predefinite: presidente, vice, segretario), obbligo di
  cambio facoltativo, sezione limitata nelle installazioni con più sezioni e **bozze di comunicazione**
  con le credenziali e i passaggi per cambiare la password.

## [1.0.74] - 2026-11-21

### Aggiunto
- **Ambiente dimostrativo** (`DEMO=true` nel `.env`, solo in un'installazione dedicata): fascia in
  ogni pagina, credenziali pubbliche dei ruoli nella pagina di accesso (non dell'amministratore),
  `manage.py demo --conferma` che cancella database e file e ricarica i dati di fantasia con un logo
  generato, azzeramento automatico il 1° di ogni mese dal pianificatore. Nessun messaggio parte e gli
  utenti dei ruoli non possono cambiare la password. Vedi *docs/sistema/ambiente-dimostrativo.md*.

## [1.0.73] - 2026-11-21

### Corretto
- **Portale dei servizi**: i colori vanno in un file `colori.css` generato invece che in uno stile in
  linea, che la CSP rigorosa del server web bloccava (testata e pulsanti senza colori).

## [1.0.72] - 2026-11-21

### Aggiunto
- **Portale dei servizi** (`scripts/portale/`): genera la pagina comune che elenca federazione e
  sezioni leggendo **da ogni gestionale** servizi attivi (gestionale, area soci, iscrizione online)
  e recapiti; configurazione TOML, veste come le email, timer systemd orario, dati dell'ultima
  lettura se un gestionale non risponde. Documentazione in *docs/sistema/portale-servizi.md*.
- La scheda pubblica dell'istanza (`/.well-known/gestione-associazione`) indica i **servizi attivi**
  e, se l'ente lo consente (*Sistema → Organizzazione*, **recapiti nella scheda pubblica**), i
  **recapiti istituzionali**.

## [1.0.71] - 2026-11-21

### Aggiunto
- **Servizi di posta**: si **eliminano le caselle IMAP** (solo se non hanno mai scaricato messaggi;
  altrimenti si rendono «non usate» in *Protocollo → Caselle*) e si **rimuove il bot Telegram**.
  Caselle, server SMTP e servizi SMS/WhatsApp hanno anche un pulsante **Elimina** in fondo alla
  pagina di modifica, oltre al cestino nell'elenco.

### Corretto
- Il messaggio di un server SMTP non eliminabile ora spiega che è stato usato anche per le
  comunicazioni, non solo per i protocolli.

## [1.0.70] - 2026-11-21

### Aggiunto
- **Avvisi personali** (menu utente → *Avvisi*), su Telegram, SMS o WhatsApp:
  - **posta da protocollare** a chi gestisce la posta e **nuove domande di iscrizione** a chi le
    valuta (presidente, segretario, presidente di sezione, per le sezioni che vede): arrivano **da
    soli su Telegram** a chi l'ha collegato, salvo la scelta di *Nessuno* o di un altro canale;
  - **sicurezza**, per gli amministratori che li scelgono: accessi falliti ripetuti, accesso di un
    amministratore da un indirizzo nuovo, operazioni sugli utenti fatte da un altro amministratore,
    lavori periodici non riusciti (backup compreso).

### Modificato
- La pagina *Avvisi della posta* diventa la pagina personale *Avvisi*, con una scelta per tipo.

## [1.0.69] - 2026-11-21

### Modificato
- **Cruscotto**: nel riquadro dei protocolli, «N messaggi da protocollare» porta alla **posta da
  protocollare**; il resto del riquadro continua a portare all'elenco dei protocolli.
- **Consenso implicito per la rubrica** (*Sistema → Organizzazione*, attivo per default): chi è in
  anagrafica senza essere socio (enti, autorità, personaggi pubblici, contatti) riceve per email
  comunicazioni associative e auguri senza un consenso registrato, salvo diniego o revoca. Non vale
  per gli ex soci né per le altre finalità; la scheda lo mostra come «implicito: in rubrica».

## [1.0.68] - 2026-11-20

### Aggiunto
- **Veste delle email** (*Sistema → Aspetto*): testata con **logo incorporato** nel messaggio, titolo e
  sottotitolo, colori di testata, accento e sfondo, fascia in alto (nessuna, tricolore, colore),
  carattere dei titoli, firma con i dati dell'ente e **informativa breve** in calce. Anteprima nella
  pagina e **email di prova** al proprio indirizzo. Vale per comunicazioni, auguri, area personale,
  recupero password e promemoria; le spedizioni del protocollo hanno una veste sobria.

### Modificato
- **Testo delle email**: le righe spezzate (testo incollato da un PDF) si ricompongono in paragrafi,
  con l'a capo conservato dopo `.` `!` `?` `:`; indirizzi web ed email diventano collegamenti (anche
  quelli spezzati dopo una `/`); ammessi grassetto, corsivo ed elenchi (Markdown).

## [1.0.67] - 2026-11-19

### Aggiunto
- **Campagna delle tessere**: le richieste registrate a mano o dal modulo Excel si **correggono**
  (quantità, data, note) e si **annullano** (es. doppione della richiesta arrivata via API), con
  l'evento nel registro delle attività. Quelle arrivate via API sono segnate e restano intoccabili.

## [1.0.66] - 2026-11-19

### Aggiunto
- **Segnatura di protocollo AgID** (Linee guida, Allegato 6, schema 3.0.0): `Segnatura.xml` con
  identificatore (codice amministrazione, AOO, registro, numero a 7 cifre, data e ora), oggetto,
  classifica, corrispondenti e impronte SHA-256 dei documenti, firmata **XAdES baseline B**. Parte
  con ogni spedizione per email o PEC e si scarica dalla scheda del protocollo. L'originale non si
  modifica: **copia PDF con il timbro** della segnatura per la stampa.
- **Segnatura e sigillo** (*Protocollo → Altro*): si carica il sigillo dell'ente (`.p12`, anche
  qualificato) oppure si usa il certificato generato dall'installazione; codici IPA facoltativi in
  *Sistema → Organizzazione* (altrimenti codice fiscale e «AOO»). Il manuale di gestione li riporta.

### Corretto
- **Rubrica dai collegamenti API**: sezioni con lo stesso codice fiscale (quello della sede
  nazionale) finivano tutte nella stessa voce, riscritta a ogni aggiornamento. Ora c'è una voce per
  controparte: il codice fiscale non identifica più l'ente e una voce condivisa per errore si divide
  al primo aggiornamento.
- **Sistema → Organizzazione**: salvare la pagina spegneva i *consensi impliciti dei soci* e svuotava
  le email della federazione e della sede nazionale e l'archivio centrale, che non erano mostrati;
  ora sono nella pagina. La configurazione guidata non li tocca più.

## [1.0.65] - 2026-11-19

### Aggiunto
- **Rubrica dai collegamenti API**: collegando una federazione o una sezione (attivazione o ruolo
  impostato) si crea o aggiorna il suo **ente in anagrafica** con denominazione, codice fiscale,
  indirizzo postale, telefono, email e PEC letti dalla controparte (nuovo `/api/v1/ente`). Senza
  duplicati, mai valori non validi; pulsante *Aggiorna la voce di rubrica* nella scheda.

### Modificato
- **Soci → Importa e verifica**: nuovo menu dell'elenco dei soci con *Importa da file*, la
  **Verifica soci via API** con ogni installazione collegata (federazione o sezione) e la
  **Verifica codici fiscali**, spostata qui dall'anagrafica.
- **Sistema → Importa soci**: riquadro *Verifica soci via API* con le controparti collegate e le
  verifiche recenti, accanto all'importazione da file.

## [1.0.64] - 2026-11-19

### Modificato
- **Richiesta di tessere per email**: resta in bozza finché l'email non è davvero spedita da
  *Comunicazioni*; solo allora risulta inviata, con data e protocollo dell'email. Con l'email in
  bozza quantità e note sono bloccate (anche dai rinnovi); annullando l'email la richiesta torna
  modificabile. La campagna mostra «Email in bozza» con il collegamento.

## [1.0.63] - 2026-11-19

### Aggiunto
- **Dal rinnovo alla richiesta di tessere**: ogni sessione di rinnovo aggiorna la **richiesta in
  preparazione** dell'anno, per differenza: rinnovati senza tessera, meno disponibili, meno già
  chieste in arrivo. Non parte mai da sola: nella campagna si corregge e si invia sul canale
  previsto (collegamento API, bozza email alla federazione, fabbisogno della federazione per una
  sua sezione). Finché è in preparazione non conta nella quadratura né negli ordini.
- **Ordine alla sede nazionale per email**: bozza con il PDF allegato (modello «Ordine di tessere
  alla sede nazionale», email della sede nazionale in *Sistema → Organizzazione*).
- **Pagamenti delle tessere al livello superiore**: uscite in prima nota sulla voce U.A.1.2,
  rinominata «Acquisto delle tessere (sede nazionale o federazione)», anche in più versamenti e
  separate dall'ordine, con dovuto, pagato e da pagare. Nella sezione la ricevuta arrivata dal
  collegamento propone l'uscita già compilata, con la ricevuta come giustificativo.

## [1.0.62] - 2026-11-19

### Aggiunto
- **Registrazione in blocco dei consensi impliciti** (`manage.py consensi_impliciti --esegui`):
  per i soci attivi e sospesi, ogni finalità senza registrazioni diventa un consenso prestato con
  la data di ammissione e la modalità «implicito: ammissione a socio». Dinieghi e revoche restano;
  rieseguibile; senza `--esegui` solo il conteggio.

## [1.0.61] - 2026-11-19

### Corretto
- **Verifica soci e importazione, luogo di nascita**: «San Severo (FG)» e «San Severo» risultavano
  diversi. Al popolamento la provincia si aggiunge dal codice fiscale, l'altra installazione
  può non averla: ora la provincia tra parentesi non conta nel confronto.

## [1.0.60] - 2026-11-19

### Aggiunto
- **Consensi impliciti per i soci**: l'ammissione comporta l'accettazione delle regole sulla
  privacy, quindi per i soci attivi e sospesi ogni finalità senza registrazioni vale come consenso
  prestato. Un diniego o una revoca registrati valgono sempre. La scheda anagrafica mostra i
  consensi impliciti; il modulo di adesione stampato riporta solo quelli espressi. Opzione in
  *Sistema → Organizzazione*, attiva per default.

## [1.0.59] - 2026-11-19

### Corretto
- **Telefono e cellulare negli scambi fra installazioni** (verifica soci e file Excel): lo stesso
  numero presente in entrambi i campi veniva sommato («X, X»), raddoppiava a ogni scambio e il
  campo finiva troncato. Ora i numeri si confrontano per cifre (spazi, trattini e +39 non contano),
  i doppioni e i pezzi troncati si scartano, e un numero già presente qui (in telefono o
  cellulare) non è più una differenza.
- Migrazione di pulizia: dalle schede si tolgono i numeri ripetuti e i frammenti troncati; le
  schede senza doppioni restano come sono.

## [1.0.58] - 2026-11-19

### Corretto
- **Verifica soci, soci doppi**: i soci senza codice fiscale né data di nascita non venivano
  riconosciuti alla verifica successiva e si proponevano (e creavano) di nuovo. Ora si
  riconoscono nella sezione per numero di tessera o per nome e cognome se unico; gli omonimi non
  distinguibili si escludono con il motivo, e prima di creare un socio si ricontrolla che non
  esista già (anche applicando una verifica vecchia).

## [1.0.57] - 2026-11-19

### Corretto
- **Ruoli invertiti fra federazione e sezione**: con le due schede impostate al contrario, la
  verifica di una sezione mostrava i soci della sezione principale della federazione. Ora:
  - un'installazione con più sezioni non risponde come sezione a chi ha indicato come «nostra
    federazione», né accetta quel ruolo nella scheda;
  - chi legge i soci controlla come lo vede l'altra parte e, se i ruoli non sono opposti, si
    ferma con «Ruoli incoerenti» senza leggere nulla;
  - la scheda spiega il ruolo: «che cosa è l'altra installazione per noi».

## [1.0.56] - 2026-11-19

### Corretto
- **Verifica soci**: il pulsante compariva anche per le controparti «pari» (senza ruolo di
  federazione o sezione) e portava a un errore. Ora la scheda spiega quale ruolo impostare, con
  il collegamento a *Modifica*.

## [1.0.55] - 2026-11-19

### Aggiunto
- **Verifica soci fra federazione e sezione via API** (F4), nei due sensi: nella scheda della
  controparte *Verifica soci* legge i soci della sezione presso l'altra installazione:
  - i soci che mancano si **popolano** (anagrafica, ammissione, stato, tessere recenti);
  - per quelli presenti mostra le **modifiche campo per campo** e si sceglie a chi applicarle,
    con l'avviso quando il dato locale è più recente;
  - dalla federazione arrivano le anagrafiche; dalla sezione anche stato, cessazioni e rinnovi
    (quote come incassate altrove);
  - nuovo indirizzo `/api/v1/soci` (ambito `soci:lettura`, sempre cifrato, ognuno vede solo la
    propria sezione).

- **Promemoria per l'archivio centrale**: quando la federazione (per una sezione) o il registro
  nazionale (per la federazione) non sono collegati via API, ogni nuovo socio e ogni rettifica
  dell'anagrafica diventa un promemoria da riportare a mano: pulsante *Da riportare all'archivio*
  nei Soci, pagina da spuntare, riepilogo email ogni notte (`promemoria_archivio`). Nome
  dell'archivio in *Sistema → Organizzazione*.

### Modificato
- **Rinnovo annuale**: dopo *Mostra i soci da rinnovare* si scelgono i soci da rinnovare (per
  default tutti); chi non intende rinnovare resta senza tessera dell'anno.
- Importazione dei soci: la fonte dei dati (delibera di ammissione, nota della quota, registro
  attività) indica da dove arrivano, non sempre «registro soci nazionale».

## [1.0.54] - 2026-11-19

### Corretto
- **Token del bot Telegram con testo in più**: incollando insieme al token altro testo di BotFather
  (es. «… Keep your token secure») si otteneva un errore 500; ora il formato `numero:chiave` si
  controlla prima di contattare Telegram e si mostra un messaggio. Ogni errore di connessione verso
  Telegram diventa un messaggio, mai un errore del server.

## [1.0.53] - 2026-11-18

### Aggiunto
- **Reverse proxy nel `.env` generato**: `installa.sh --dominio NOME --proxy IP` imposta nome
  pubblico (`ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `URL_PUBBLICO`), `HTTPS`, `PROXY_COUNT` e
  `PROXY_FIDATI`, anche in un aggiornamento; `sezioni.sh imposta DOMINIO 'schema-{sezione}'` e
  `imposta PROXY IP` li applicano a tutte le sezioni.

## [1.0.52] - 2026-11-18

### Aggiunto
- **Più sezioni sullo stesso host**:
  - `installa.sh --istanza NOME` installa una sezione con servizio, porta, cartelle, utente e
    database propri, sullo stesso PostgreSQL (`--worker N` per i processi web);
  - `scripts/proxmox/sezioni.sh` le gestisce insieme (`aggiungi`, `aggiorna`, `stato`, `motd`);
  - il messaggio di benvenuto riepiloga tutte le sezioni, con servizi, versione e backup.

## [1.0.51] - 2026-11-18

### Aggiunto
- **Modulo di richiesta tessere scaricabile dall'elenco dei soci**: con la sezione scelta nel
  filtro, *Stampa ed esporta → Modulo di richiesta tessere (Excel)* scarica il modulo della
  campagna in preparazione. Con più sezioni bisogna sceglierne una; si rispettano le sezioni
  assegnate all'utente.

## [1.0.50] - 2026-11-18

### Aggiunto
- **Modulo Excel della richiesta di tessere** per le sezioni senza gestionale, allegato da solo
  all'avviso di tesseramento e al sollecito, intestato a ogni sezione:
  - dati bloccati: sezione, codice, anno, importo per tessera, termine;
  - per informazione, le tessere dell'anno precedente;
  - celle da compilare: tessere richieste, referente, telefono, note; il totale si calcola da solo;
  - le istruzioni per rispondere, anche nell'email (segnaposto `{{ istruzioni_risposta }}` e
    `{{ tessere_anno_precedente }}`, aggiunti in fondo se il modello non li contiene);
  - un codice di controllo che rifiuta i moduli modificati o di altre installazioni.
- **Recupero del modulo compilato**:
  - dalla posta da protocollare, con «Protocolla e registra la richiesta» in un passo;
  - a mano, con *Importa modulo* nella campagna e l'anteprima;
  - lo stesso file non si registra due volte.

## [1.0.49] - 2026-11-18

### Corretto
- **Comunicazioni protocollate con i segnaposto**: oggetto del protocollo e allegato
  `comunicazione.txt` riportavano il modello («Tesseramento {{ anno }}…») invece del testo
  spedito. Le email erano corrette. Ora si registrano oggetto e testo con i valori dell'invio; con
  un solo destinatario, esattamente il messaggio spedito.

## [1.0.48] - 2026-11-18

### Corretto
- **Richiesta di tessere firmata dal presidente sbagliato**: sulla federazione il PDF di una
  richiesta veniva rigenerato e firmato dal presidente della federazione. Ora:
  - una richiesta arrivata via API mostra il **PDF originale della sezione**, con la sua firma e
    la sua intestazione, lo stesso protocollato;
  - una richiesta registrata a mano porta la firma del **presidente della sezione** che chiede,
    vacante se la carica non è registrata.

## [1.0.47] - 2026-11-18

API di interoperabilità, fase F4 blocco A: il ciclo delle tessere passa da solo fra federazione e
sezione.

### Aggiunto
- **Ruolo del collegamento** (*Collegamenti API → Modifica*): «È la nostra federazione», oppure
  «È una nostra sezione» con la sezione del proprio elenco. Nuovo ambito «Ciclo delle tessere».
- **Scambio dei documenti del ciclo**:
  - richieste di tessere dalla sezione alla federazione;
  - consegne con i numeri e ricevute dei versamenti dalla federazione alla sezione, ognuna con il
    PDF;
  - prese in carico dalla sezione alla federazione.

  Ognuno vede solo i documenti della propria sezione. La lettura avviene ogni 15 minuti
  (`sincronizza_collegamenti`) o con *Sincronizza ora*, con la verifica della catena.
- **Documenti in arrivo** nella campagna delle tessere, con PDF, conferma e scarto motivato:
  - la richiesta si registra nella campagna;
  - la consegna carica il lotto della sezione;
  - la ricevuta si archivia;
  - con la conferma si può protocollare in entrata, con il nuovo mezzo «Collegamento telematico
    (API)» e il PDF allegato;
  - la presa in carico si registra da sola sulla consegna della federazione.

## [1.0.46] - 2026-11-18

### Aggiunto
- **Risposta della sezione all'avviso di tesseramento**: dalla richiesta di tessere si prepara
  in bozza l'email alla federazione, con il nuovo modello «Richiesta di tessere alla federazione»
  (modificabile), il PDF della richiesta allegato e la protocollazione in uscita.
- **Email della federazione** in *Sistema → Organizzazione*.

### Modificato
- La **campagna delle tessere** si apre sempre sull'anno successivo a quello in corso. Gli anni
  precedenti si consultano dal selettore, con un rimando alla campagna in preparazione.

### Corretto
- Un test aggiunto nella 1.0.44 svuotava il database di prova e faceva fallire i test di
  ripristino del backup. È sostituito da un controllo equivalente che non lo tocca. Nessun effetto
  sulle installazioni.

## [1.0.45] - 2026-11-18

### Modificato
- **Comunicazioni annullate in un elenco a parte**: non compaiono più fra *Tutte*, ma nella scheda
  *Annullate*, in fondo, con il loro numero.

## [1.0.44] - 2026-11-18

### Corretto
- **Errore 500** con *Annulla* e *Modifica* di una comunicazione, e con l'eliminazione delle bozze
  (dalla 1.0.41): le operazioni avevano perso la transazione che serve a bloccare l'invio durante
  la modifica. Un test ora le esegue fuori da una transazione, come in produzione.

## [1.0.43] - 2026-11-18

### Aggiunto
- **Testo degli avvisi del tesseramento modificabile** dalla pagina dell'avviso: oggetto e testo
  vengono dal modello e si correggono per quell'invio. Chi può modificare i modelli può salvarli
  anche nel modello predefinito, con la traccia nel registro attività. I segnaposto vengono
  controllati e c'è il collegamento diretto al modello.

## [1.0.42] - 2026-11-18

### Aggiunto
- **Modifica delle bozze** (*Comunicazioni → comunicazione in bozza → Modifica*): oggetto, testo,
  testo breve, data di invio, protocollazione, destinatari da togliere e indirizzi da aggiungere,
  con il controllo dei segnaposto e la traccia nel registro attività.

### Corretto
- **«Seleziona tutte»** nell'elenco delle comunicazioni non selezionava nulla: le caselle sono
  collegate al modulo con l'attributo `form` e lo script le cercava solo dentro il modulo.

## [1.0.41] - 2026-11-18

### Aggiunto
- **Azioni su più comunicazioni** (*Comunicazioni*): si selezionano bozze e invii in coda e si
  possono confermare e inviare, annullare o eliminare (solo le bozze, con gli allegati) tutti
  insieme. Le operazioni finiscono nel registro attività e gli invii non elaborabili vengono
  segnalati con il motivo.

### Modificato
- L'**email istituzionale** della sezione è obbligatoria nel modulo (*Sistema → Sezioni*). La
  campagna delle tessere elenca le sezioni che non ce l'hanno ancora, con il collegamento per
  completarla.

### Corretto
- Avvisi e documenti del ciclo delle tessere scrivevano «Alla Direzione della Ruoti». Ora usano la
  denominazione «Sezione di Ruoti», o il nome com'è se comincia già con «Sezione».

## [1.0.40] - 2026-11-18

### Corretto
- La **campagna delle tessere** non aveva una voce nel menu laterale: era raggiungibile solo dai
  pulsanti in cima a *Tesseramento → Tessere fisiche*. Ora c'è la voce **Campagna delle tessere**
  sotto *Tesseramento*, per chi ha il permesso; *Importa consegna* è anche nella pagina della
  campagna.

## [1.0.39] - 2026-11-18

Ciclo delle tessere fra federazione e sezioni, dalla richiesta alla distribuzione.

### Aggiunto
- **Campagna delle tessere con le sezioni** (*Soci → Tessere fisiche*), il ciclo completo dalla
  richiesta alla distribuzione, utilizzabile anche senza collegamenti fra installazioni:
  - listino con quota federale, delibera del direttivo, termine delle richieste e modalità di
    pagamento;
  - richieste delle sezioni anche integrative;
  - ordine alla sede nazionale in PDF con il dettaglio per sezione;
  - magazzino dei blocchi ricevuti (le tessere non si attribuiscono finché non sono consegnate);
  - consegne anche parziali che creano il lotto della sezione, con documento di consegna in PDF e
    file dei numeri;
  - presa in carico;
  - versamenti delle sezioni come incassi con ricevuta numerata;
  - quadratura per sezione (richieste, consegnate, dovuto, versato, saldo e avvisi).
- **Avvisi alle sezioni** con tre modelli predefiniti e modificabili (nuovo tesseramento,
  sollecito a chi non ha chiesto, attribuzione delle tessere con le modalità di distribuzione):
  un messaggio per sezione all'indirizzo della sezione e al presidente in carica, in bozza e
  protocollabile.
- **Importa consegna**: la sezione carica, con anteprima, il file dei numeri ricevuto dalla
  federazione.

## [1.0.38] - 2026-11-18

API di interoperabilità (ADR-030), fasi F1-F3: collegamenti firmati fra installazioni e con sistemi esterni.

API di interoperabilità, fase F1: identità, abbinamento e firma di ogni messaggio (ADR-030, approvata).

### Aggiunto
- **Identità dell'istanza**:
  - UUID creato alla migrazione;
  - chiavi Ed25519 (firma) e X25519 (cifratura), con le private cifrate con `CHIAVE_CIFRATURA`;
  - JWKS pubblica e rotazione con 7 giorni di sovrapposizione;
  - `/.well-known/gestione-associazione`, con le impronte SPKI del certificato servito
    dall'installatore (`API_TLS_CERTIFICATO`, `API_TLS_SPKI`).
- **Firma di ogni richiesta e risposta** con HTTP Message Signatures (RFC 9421, ed25519):
  - integrità del corpo con `Content-Digest` (RFC 9530);
  - destinatario firmato (`Destinatario-Istanza`) al posto del nome host;
  - nonce non riutilizzabili e tolleranza dell'orologio di ±5 minuti;
  - risposte legate alla richiesta;
  - errori in formato Problem Details (RFC 9457).
  - L'implementazione è verificata con i vettori ufficiali dell'RFC 9421 (Appendice B.2.6).
- **Abbinamento con invito monouso** (24 ore, il codice si vede una volta):
  - prova di possesso delle chiavi e impronta comune alle due parti, da confermare per una seconda
    via prima di attivare;
  - stati *in prova*, *attiva*, *sospesa* (anche da sola alla scadenza) e *revocata*;
  - ambiti e indirizzi IP ammessi;
  - per un'integrazione esterna, i dati dei soci solo con la conferma del trattamento.
- **`POST /api/v1/prova`**: diagnosi del collegamento (firma, orologio, stato, ambiti, IP visto).
- **Sistema → Collegamenti API** (solo Amministratore di sistema):
  - identità dell'istanza, controparti, nuovo invito e uso di un invito ricevuto;
  - conferma dell'impronta, prova del collegamento, sospensione, revoca, rotazione delle chiavi;
  - registro delle chiamate ricevute.
- **Client verso le altre installazioni** (`apps/collegamenti`), che usa solo l'API pubblica:
  - prova prima l'indirizzo interno e poi quello pubblico;
  - verifica sempre il certificato: CA di sistema, CA interna (PEM) o impronta SPKI, anche per
    i certificati autofirmati;
  - http in chiaro solo verso IP privati, con consenso esplicito;
  - niente redirect;
  - controllo degli indirizzi privati a ogni risoluzione del nome, contro SSRF e DNS rebinding.
- Lavoro periodico `pulizia_api` nel pianificatore.

API di interoperabilità, fase F2: feed dei cambiamenti, eventi e sezioni, notifiche.

- **Feed dei cambiamenti** (`GET /api/v1/cambiamenti`):
  - CloudEvents senza dati personali, scritti nella stessa transazione di ogni creazione, modifica
    o annullamento di eventi e sezioni, anche da importazioni e configurazione guidata;
  - progressivo senza buchi per flusso e catena di impronte SHA-256;
  - conservazione di 400 giorni (`410` per i cursori più vecchi);
  - ogni adesione o rinuncia fa avanzare la versione dell'evento.
- Eventi e sezioni hanno `uuid` e `versione` (assegnati anche a quelli esistenti).
- **Risorse**:
  - `GET /api/v1/eventi`, a pagine con cursore e filtro `dal`, e `GET /api/v1/eventi/{uuid}` con
    `ETag`; alle integrazioni solo gli eventi con modulo pubblico;
  - `GET /api/v1/sezioni`;
  - `GET /api/v1/riepiloghi/{flusso}` per la riconciliazione.
- **Notifiche** alle controparti:
  - CloudEvent firmato all'indirizzo indicato, per i flussi scelti nella scheda;
  - ripetizioni da 1 minuto a 24 ore, poi restano visibili come non consegnate e si possono
    riprovare;
  - lavoro `invia_notifiche_api`.
- **Rotazione delle chiavi** senza interruzioni:
  - durante la sovrapposizione le risposte sono firmate anche con la chiave in uscita;
  - le altre installazioni rileggono da sole la JWKS firmata (anche alla prima chiamata con una
    chiave sconosciuta);
  - le integrazioni presentano le chiavi nuove con `PUT /api/v1/chiavi`.
- **Impronte TLS aggiornate** ogni notte (`aggiorna_collegamenti`) dalla `/.well-known` firmata
  delle installazioni collegate, ad esempio dopo un rinnovo con chiave nuova.
- Documentazione:
  - manuale operativo *Collegamenti API*;
  - manuale di sistema *API di interoperabilità* (proxy, rete interna, impronte);
  - guida per chi integra in `docs/api/README.md`;
  - contratto OpenAPI aggiornato.

API di interoperabilità, fase F3: cifratura dei dati personali e sistemi esterni (siti, app).

- **Cifratura per il destinatario** (JWE `ECDH-ES+A256KW` / `A256GCM` su X25519), senza dipendenze
  nuove e verificata con i vettori ufficiali (RFC 7518, 8037, 3394). I dati personali in ingresso
  devono essere cifrati; quelli in uscita sono cifrati per la controparte. `/prova` verifica la
  cifratura in andata e ritorno.
- **`Idempotency-Key`** su ogni scrittura (30 giorni) e **limiti di frequenza** per controparte
  (`API_LIMITE_MINUTO`, `API_LIMITE_SCRITTURE_ORA`, risposta 429 con `Retry-After`).
- **Dall'esterno verso il gestionale**:
  - adesioni agli eventi con lettura delle proprie e annullamento con `If-Match`, con le regole del
    modulo pubblico e solo sugli eventi pubblici;
  - domande di iscrizione, che restano in attesa, con gli stessi consensi obbligatori del modulo;
  - messaggi del modulo contatti, tra la posta da protocollare (casella «Modulo contatti (API)»).
- **Dal gestionale verso l'esterno**:
  - documenti pubblici con il file;
  - organigramma (ruolo e nome delle cariche in corso);
  - verifica di una tessera (validità, anno e sezione, senza il nome).
- Origine «Integrazione (API)» e controparte registrate su adesioni e domande; la scheda della
  controparte riporta i dati ricevuti.

## [1.0.37] - 2026-11-18

Certificati HTTPS con rinnovo automatico e CA interna su Proxmox in un solo comando.

### Aggiunto
- **`installa.sh --tls-step`**: certificato dalla propria step-ca con un **token monouso** (creato da chi
  amministra la CA, valido pochi minuti) e **rinnovo automatico** con `step ca renew`, che si autentica con
  il certificato in corso: sul server non resta nessuna password. Funziona anche con un proxy sulla
  stessa macchina. Timer `gestione-associazione-tls-rinnovo` due volte al giorno, rinnovo dopo i due
  terzi della validità, riavvio automatico del servizio.
- **`installa.sh --tls-acme`**: certificato da una CA ACME (step-ca, Let's Encrypt…) con certbot e
  rinnovo con `certbot.timer`; controlla che la porta 80 sia libera.
- Radice della CA privata con `--tls-ca FILE` oppure `--tls-ca-impronta` (scaricata dalla CA e accettata
  solo se l'impronta coincide), installata nell'archivio del sistema. Scegliendo un modo nuovo i rinnovi
  del precedente si spengono. Logica dell'HTTPS in `scripts/tls.sh`.
- **`scripts/proxmox/crea-ca.sh`**: container LXC con step-ca pronta (repository Smallstep, durata dei
  certificati, nomi ammessi limitati al dominio interno e alle reti indicate, provisioner ACME, servizio
  systemd, comando `token-certificato` per l'installatore del gestionale).

### Corretto
- Guida *HTTPS anche in rete interna*: l'unità systemd di esempio di step-ca non partiva
  (`ProtectSystem=full` rendeva di sola lettura il database in `/etc/step-ca/db`).

## [1.0.36] - 2026-11-18

HTTPS servito direttamente dall'applicazione e guida all'HTTPS in rete interna.

### Aggiunto
- **HTTPS dall'installatore** (`scripts/installa.sh`): `--tls-cert`/`--tls-key` per un certificato
  della propria CA (step-ca, MyCert, …) oppure `--tls-autofirmato` (nome e IP del server, `--tls-nomi`
  per altri nomi; rinnovando riusa la chiave, così l'impronta non cambia). Controlli su coppia chiave/
  certificato e scadenza, file in `/etc/gestione-associazione/tls/`, **riavvio automatico** quando il
  certificato viene sovrascritto (rinnovo), scelta mantenuta negli aggiornamenti, `--senza-tls` per
  tornare indietro. Alla fine stampa emittente, scadenza e impronta SPKI. Anche
  `crea-lxc.sh --tls-autofirmato`; il messaggio di benvenuto del container segnala se l'HTTPS manca.

### Documentazione
- Proposta dell'**API di interoperabilità** (ADR-030) e bozza del contratto OpenAPI in
  `docs/api/openapi.yaml`, da approvare prima dello sviluppo.
- Nuova guida **HTTPS anche in rete interna** nel manuale di sistema: autorità di certificazione
  interna con step-ca (installazione, inizializzazione, rilascio automatico ACME, certificato radice
  sui dispositivi) oppure certificato autofirmato con OpenSSL e impronta per i collegamenti fra
  installazioni, gestione della vita dei certificati con MyCert. HTTPS raccomandato sempre, anche in LAN.

## [1.0.35] - 2026-11-18

Chat interna fra gli utenti del gestionale.

### Aggiunto
- **Chat interna** (menu *Chat* e icona nella barra in alto) fra gli utenti del gestionale, non i soci:
  conversazioni a due e di gruppo, messaggi che arrivano senza ricaricare la pagina, numero dei non
  letti nella barra, chi è connesso, aggiunta di persone e uscita dai gruppi, ritiro dei propri
  messaggi. Le conversazioni le leggono solo i partecipanti, nemmeno l'amministratore; il registro
  attività non contiene mai il testo dei messaggi.

## [1.0.34] - 2026-11-18

Traduzione dei messaggi della password e manuale dei backup aggiornato.

### Corretto
- Il messaggio «password troppo corta» compariva in inglese nel cambio della password e nella
  creazione degli utenti: Django 6.1 ne ha cambiato il testo senza aggiornare la traduzione italiana.

### Documentazione
- Manuale di sistema dei backup aggiornato al formato della 1.0.30: documenti salvati una volta sola
  nell'archivio comune (da copiare insieme ai backup), contenuto del `.tar`, cifratura con
  `CHIAVE_BACKUP` al posto di `gpg`, tetto di spazio, prova di ripristino. Corretti anche il riepilogo
  nel manuale operativo e la roadmap.

## [1.0.33] - 2026-11-17

Area personale dei soci.

### Aggiunto
- **Area personale dei soci** (`/area/`, da attivare nei dati dell'organizzazione): accesso senza
  password con un collegamento via email valido 30 minuti e usabile una volta; dati, tessere e quote
  con le ricevute, consensi, eventi con adesione e rinuncia, collegamento a Telegram, richieste di
  correzione dei dati che la segreteria vede nel cruscotto e nella scheda.

## [1.0.32] - 2026-11-17

Eventi e cerimonie con adesioni.

### Aggiunto
- **Eventi e cerimonie** (nuovo modulo, menu *Eventi*): data, luogo, programma, posti, accompagnatori,
  chiusura delle adesioni; **adesioni** dalla segreteria (collegate all'anagrafica quando la persona è
  riconoscibile) e da un **modulo pubblico** con collegamento segreto e protezioni anti-spam; foglio
  presenze in PDF ed elenco in Excel; eventi nel calendario e nell'iCal.

## [1.0.31] - 2026-11-17

Incassi, note di storno e registro incassi.

### Aggiunto
- **Incassi diversi dalle quote** (donazioni, contributi, quote di partecipazione, altro): ricevuta
  numerata nella stessa numerazione delle quote, PDF e prima nota con la voce adatta.
- **Note di storno e rimborsi** di quote e incassi: annullamento del movimento registrato per errore
  oppure rimborso come uscita; per le quote anche l'annullamento del tesseramento. Ricevute segnate
  come stornate.
- **Registro incassi e quadratura**: ricevute e storni di un periodo con i totali per metodo e per
  conto, in PDF ed Excel.

## [1.0.30] - 2026-11-17

Backup incrementali, cifrati e con prova di ripristino.

### Aggiunto
- **Backup incrementali**: i documenti si salvano una volta sola in un archivio per contenuto; ogni
  backup aggiunge solo le novità. Lo scaricato resta completo.
- **Backup cifrati** con la chiave dedicata `CHIAVE_BACKUP` (AES-256-GCM, comando
  `genera_chiave_backup`, istruzioni da copiare nella pagina).
- **Prova di ripristino** senza toccare i dati (pulsante, `backup --prova`, settimanale automatica) ed
  estrazione decifrata per il ripristino a mano (`backup --estrai`).

### Corretto
- Due backup creati nello stesso secondo non si sovrascrivono più.

## [1.0.29] - 2026-11-17

Scadenza dei mandati e utenti connessi.

### Aggiunto
- **Scadenza dei mandati**: durata del mandato e preavviso per organo; la scadenza di ogni carica in
  corso compare nell'organo, nel cruscotto (*Mandati in scadenza*) e nel calendario (anche iCal).
- **Utenti connessi** in *Sistema → Utenti*: chi ha usato il programma negli ultimi 5 minuti, filtro
  *Connessi ora* e ultima attività di ciascuno (l'uscita con *Esci* lo toglie subito).

## [1.0.28] - 2026-11-17

Avvisi della posta da protocollare su Telegram, SMS o WhatsApp.

### Aggiunto
- **Avvisi della posta da protocollare** su Telegram, SMS o WhatsApp, scelti da ciascun utente che
  gestisce la posta (*Posta da protocollare → Avvisi* o menu dell'utente): un riepilogo per ogni
  scaricamento con messaggi nuovi (quanti, mittente e oggetto dei primi cinque, collegamento alla
  posta), con *Collega il mio Telegram* e *Manda un avviso di prova*.

### Modificato
- L'interruttore *Invio delle email* si chiama **Invio dei messaggi** e gli avvisi dicono che, spento,
  ferma anche Telegram, SMS e WhatsApp (era già così, ma non era scritto: un messaggio Telegram restava
  in coda senza un motivo evidente).

## [1.0.27] - 2026-11-17

Comunicazioni via PEC, su Telegram, per SMS e su WhatsApp Business.

### Aggiunto
- **Comunicazioni via PEC**: in *Spedisci da* si sceglie un servizio di invio (anche PEC). Con la PEC, chi
  ha la PEC in anagrafica la riceve per PEC, gli altri per email dal server generale, chi non ha nessuno
  dei due resta su carta. Le ricevute di accettazione e consegna si agganciano al destinatario («PEC
  consegnata»...) e non finiscono fra la posta da protocollare. Anche un servizio email diverso dal
  generale (es. quello del presidente) si può scegliere come mittente.
- **Telegram**: bot dell'associazione configurato in *Sistema → Servizi di posta* (token da @BotFather,
  cifrato, con verifica). Dalla scheda anagrafica si genera l'**invito** personale (link e QR): la persona
  si collega con *Avvia* e smette con `/stop`. Le comunicazioni con **Anche su Telegram** arrivano lì
  (testo e allegati), anche a chi non ha l'email. Nessun webhook: i comandi si leggono ogni minuto.
- **SMS e WhatsApp Business** (preparati, da provare con un account reale): fornitori in *Sistema →
  Servizi di posta* (Skebby, Aruba SMS, Twilio; API Cloud di Meta con modello approvato), credenziali
  cifrate e **Verifica**. Le comunicazioni con **Anche per SMS** / **Anche su WhatsApp** mandano un
  **testo breve** (con segnaposto) al cellulare dell'anagrafica; WhatsApp solo a chi ha registrato il
  consenso nella scheda. Esito per destinatario e canale, tre tentativi.
- **Comunicazioni senza email**: togliendo **Per email** si spedisce solo per SMS, WhatsApp o
  Telegram (il testo lungo serve solo per Telegram).

## [1.0.26] - 2026-11-17

Spostamenti sul server anche per i messaggi rimasti nella posta in arrivo.

### Corretto
- Gli scartati scaricati prima della cartella `PROCESSATA` (1.0.19), o più vecchi dei giorni da
  scaricare, sono ancora nella posta in arrivo: la 1.0.25 li cercava solo in `PROCESSATA` e li segnava
  «non trovato». Ora si cercano anche nella cartella letta; quelli segnati vengono rimessi in coda e
  spostati al prossimo scaricamento. Un nuovo spostamento cancella l'errore del tentativo precedente.

## [1.0.25] - 2026-11-17

Etichette adesive, pulizia della posta scartata, niente email ordinarie verso le PEC per errore.

### Aggiunto
- **Pulizia della posta scartata**: nell'elenco *Scartati* filtri per motivo e data dello scarto,
  **Elimina definitivamente** sui messaggi spuntati o su tutti quelli filtrati. Si elimina il contenuto
  (testo, allegati, file `.eml`); resta una riga minima per non riscaricarli, e il registro attività
  documenta cosa è stato eliminato. Nuovo permesso, a segretario e amministratore di sistema. Con la
  spunta **anche dalla casella** il messaggio va anche nel **cestino** della casella email (riconosciuto
  dal server o per nome: Trash, Cestino...); le PEC mai, restano come prova di ricezione.
- **Cartella `SCARTATA` sul server**: i messaggi scartati si spostano dalla cartella `PROCESSATA` a
  `SCARTATA` (`INBOX.SCARTATA` su Aruba, creata se manca) e tornano indietro se ripristinati; gli
  scartati già presenti si spostano al primo scaricamento dopo l'aggiornamento. Gli spostamenti
  avvengono con lo scaricamento (ogni 15 minuti o *Scarica ora*), ritrovando i messaggi per Message-ID;
  la scheda del messaggio dice dove si trova e gli eventuali errori. La verifica della casella indica
  anche la cartella degli scartati e il cestino trovato.
- **Etichette adesive in PDF** per la spedizione postale: dai destinatari su carta di un protocollo
  (menu *Buste ed etichette*), dai destinatari senza email di una comunicazione e da una **lista di
  distribuzione**. Fogli A4 di formato comune (70 × 37, 70 × 36, 63,5 × 38,1, 99,1 × 38,1 mm), con la
  possibilità di partire da un'etichetta qualsiasi per riusare un foglio già iniziato; solo chi ha
  l'indirizzo postale completo. Ogni scaricamento è annotato nel registro attività.

### Corretto
- **Email ordinaria verso una PEC**: un protocollo registrato con mezzo PEC, o con destinatari che hanno
  un indirizzo PEC, non si spedisce più da un servizio email ordinario senza accorgersene (la casella PEC
  lo riceveva come «anomalia», senza valore legale). *Spedisci* lo segnala e chiede di scegliere il
  servizio PEC o di confermare *Spedisci comunque come email ordinaria*.

## [1.0.24] - 2026-11-17

Risposte dal servizio giusto e interruttore dei servizi di invio.

### Aggiunto
- **Rispondi con** nella scheda di ogni casella (*Sistema → Servizi di posta*): il servizio di invio con
  cui si risponde ai messaggi arrivati lì. Si compila da solo con il servizio dello stesso indirizzo e
  tipo (anche per le caselle esistenti); l'elenco mostra «risponde con: …» o un avviso se manca.
- **Spedire una risposta**: *Spedisci* propone il servizio *Rispondi con* della casella in cui era
  arrivato il messaggio (a una PEC dalla stessa PEC, a un'email dallo stesso indirizzo), poi la PEC per
  il mezzo PEC, poi il server generale. *Rispondi* copia anche il **mezzo** dell'originale.
- *Sistema → Servizi di posta*: interruttore **attivo/disattivato** accanto a ogni servizio di invio, senza aprire la scheda (il server generale non si disattiva).

### Corretto
- *Sistema → Servizi di posta*: senza la chiave di cifratura il pulsante «Nuova casella» spariva senza spiegazione; ora resta visibile (disattivato) con un avviso che riporta, pronti da copiare, il comando che crea `CHIAVE_CIFRATURA` nel `.env` dell'installazione e quello per riavviare.

## [1.0.23] - 2026-11-17

Tutta la configurazione della posta in Sistema → Servizi di posta.

### Modificato
- **Configurazione della posta tutta in *Sistema → Servizi di posta***: oltre ai servizi di invio, anche
  le **caselle** email e PEC (server, credenziali, cartelle) si creano e si modificano lì, con la
  **Verifica** dell'accesso. *Protocollo → Caselle* mostra solo l'elenco con l'interruttore **Usata dal
  protocollo**: solo le caselle usate vengono lette. Una casella nuova resta spenta finché il protocollo
  non la abilita. I ruoli del protocollo non creano più caselle.

## [1.0.22] - 2026-11-17

Servizi di invio separati dalle caselle di lettura.

### Modificato
- **Servizi di posta riorganizzati**: *Protocollo → Caselle* serve solo a **leggere** (IMAP);
  **come si spedisce** si configura in *Sistema → Servizi di posta*, con i nuovi **servizi di invio**
  (SMTP, email o PEC, password cifrata, verifica dell'accesso). Il servizio **server generale** spedisce
  comunicazioni, email dell'accesso e protocolli per email; gli altri (es. la PEC) si scelgono in
  *Spedisci*. Il server del file `.env` resta come riserva.
- Aggiornando, il server SMTP del `.env` diventa il server generale e le caselle «anche invio» della
  1.0.18 diventano servizi di invio con le stesse credenziali: nulla da riconfigurare.

## [1.0.21] - 2026-11-17

Mittente delle PEC ricevute e risposte via PEC.

### Corretto
- **Mittente delle PEC** ricevute: con le buste firmate di Aruba (`multipart/signed`) il messaggio
  originale `postacert.eml` non veniva trovato e il mittente risultava
  «Per conto di: … <posta-certificata@pec.aruba.it>». Ora l'originale si cerca a ogni livello della
  busta; se manca, il mittente si ricava da «Per conto di:» o dal `Reply-To`.
- **Risposta a un protocollo**: il destinatario proposto non ripete più l'indirizzo già presente nel
  nome e mette il nome tra virgolette, così l'indirizzo email/PEC viene riconosciuto (prima restava
  vuoto e compariva l'avviso «Indirizzo postale mancante» per le buste).

## [1.0.20] - 2026-11-16

Cartella PROCESSATA nel namespace del server (Aruba).

### Corretto
- La cartella dei messaggi scaricati si crea nel **namespace personale** del server, letto con il
  comando NAMESPACE: con Aruba (e i server Courier) diventa `INBOX.PROCESSATA`. Con la 1.0.19 la
  creazione di `PROCESSATA` era rifiutata («nonexistent namespace») e i messaggi, pur scaricati,
  restavano nella posta in arrivo.

## [1.0.19] - 2026-11-16

Posta scaricata spostata nella cartella PROCESSATA della casella.

### Modificato
- **Posta scaricata spostata nella cartella `PROCESSATA`** della casella IMAP (email e PEC), creata al
  primo scaricamento se manca: nella posta in arrivo restano solo i messaggi non ancora acquisiti. Nulla
  viene cancellato né segnato come letto; si usa MOVE (o copia e cancellazione dei soli messaggi
  copiati, con UIDPLUS). La cartella si cambia nella scheda della casella; vuota, i messaggi restano dove
  sono. *Verifica* in *Servizi di posta* indica la cartella e se sarà creata.

## [1.0.18] - 2026-11-16

Spedizione dei protocolli in uscita per email e PEC, con le ricevute PEC agganciate.

### Aggiunto
- **Spedizione per email e PEC dei protocolli in uscita** (scheda del protocollo → *Spedisci*): da una
  casella configurata per l'invio (la PEC dell'ente) o dal server generale, un messaggio per
  destinatario con l'indirizzo proposto dall'anagrafica (PEC o email) e modificabile, oggetto con
  numero e data di protocollo, testo e documenti scelti. Nella scheda il riquadro *Spedizioni* riporta
  l'esito di ognuno; gli errori di invio si ritentano da soli (tre volte) e poi con *Riprova*. Segue
  l'interruttore dell'invio in *Sistema → Servizi di posta* (spento: resta in coda).
- **Ricevute PEC agganciate**: accettazione, avvenuta consegna e mancata consegna, lette dalla casella
  PEC, aggiornano l'esito del destinatario e diventano documenti del protocollo, senza passare dalla
  posta da protocollare.
- Caselle di posta: *usata anche per spedire*, con server SMTP, porta, SSL e indirizzo del mittente
  (stesse credenziali della lettura; per Aruba PEC `smtps.pec.aruba.it`, 465). *Verifica* in
  *Servizi di posta* prova anche l'invio. Nuovo permesso `protocollo.spedisci_protocollo`
  (amministratore di sistema, segretario, addetto al protocollo); impostazione
  `PROTOCOLLO_SPEDIZIONE_MAX_MB` (20).

## [1.0.17] - 2026-11-16

Timbri degli enti in Sistema → Organizzazione, solo per l'amministratore di sistema.

### Modificato
- **Timbri degli enti in Sistema → Organizzazione**, solo per l'amministratore di sistema (nuovo
  permesso `organi.gestisci_timbri`): caricamento, uso nelle stampe, timbro generico, foglio di
  acquisizione. In *Firme e timbri* restano le firme; i timbri si vedono in anteprima. Presidente,
  segretario e presidente di sezione non cambiano più i timbri.

### Corretto
- *Non usare* e *Togli* di un timbro non funzionavano: l'indirizzo coincideva con quello del
  caricamento.

## [1.0.16] - 2026-11-16

Sezioni nelle liste e nel libro soci; stampe ed esportazioni che seguono i filtri.

### Corretto
- Elenco dei soci: **Stampa ed esporta** segue i filtri scelti. Il libro soci in PDF stampava sempre
  tutto anche con una sezione selezionata, e dopo un filtro applicato senza ricaricare la pagina
  CSV ed Excel usavano ancora i filtri precedenti: ora gli indirizzi si compongono al clic.

### Aggiunto
- **Elenco filtrato in PDF**: i soli soci mostrati, con i criteri (sezione, stato, tipologia, quota,
  ricerca) scritti in testa.
- **Libro soci per sezione**: con più sezioni il PDF ha una parte per sezione (nome, codice, numero
  di iscrizioni), ciascuna da una pagina nuova e in ordine di numero, più il riepilogo per sezione;
  anche il CSV del libro soci è ordinato per sezione. Con una sola sezione non cambia nulla.
- Liste di destinatari: **Solo i soci delle sezioni** per limitare «tutti i soci» e «soci in regola»
  a una o più sezioni (federazione); vale per invii, protocollo in uscita ed Excel (riga *Sezioni dei
  soci*, per nome o codice). Chi è abilitato solo ad alcune sezioni sceglie fra le proprie e, se
  include i soci, deve indicarle. Nel foglio Destinatari il motivo riporta la sezione.

## [1.0.15] - 2026-11-16

Lettere e buste per chi non ha l'email; indirizzi dei soci nelle liste esportate.

### Aggiunto
- **Comunicazioni su carta** per chi non ha l'email: nella pagina dell'invio, lettere in PDF (una
  per persona, con i segnaposto risolti e l'indirizzo nella finestra della busta), buste DL in Word
  compilate o per stampa unione ed elenco CSV, con l'indirizzo attuale dell'anagrafica e il numero
  di protocollo se l'invio è protocollato. Rispetta i consensi come le email.

### Corretto
- Liste in Excel: il foglio **Destinatari** (chi riceve davvero: soci, categorie, organo e persone
  scelte) ha ora codice, email, **indirizzo postale** e il motivo per cui ciascuno è nella lista.
  Prima l'indirizzo c'era solo nel foglio Persone, che contiene i soli scelti uno per uno: una lista
  di soci risultava senza indirizzi.

## [1.0.14] - 2026-11-16

Indirizzo postale nelle liste di destinatari in Excel.

### Aggiunto
- Liste in Excel: **indirizzo postale** nel foglio Persone (indirizzo, CAP, comune, provincia,
  nazione). All'importazione completa solo i campi vuoti delle schede esistenti e segnala i valori
  diversi senza cambiarli; le schede nuove nascono con l'indirizzo del file.

## [1.0.13] - 2026-11-16

Liste di destinatari in Excel, conservazione dei backup a rotazione, ripristino che torna indietro.

### Aggiunto
- **Liste di destinatari in Excel**: *Esporta in Excel* dalla pagina della lista (fogli Lista,
  Persone, Destinatari attuali, Istruzioni) per modificarla fuori linea; *Liste → Importa da Excel*
  con anteprima di impostazioni, persone abbinate (per codice, codice fiscale o email univoca),
  aggiunte, tolte, righe ambigue o non trovate; il codice nel file indica la lista da aggiornare,
  senza codice se ne crea una nuova. Su richiesta crea in anagrafica le schede mancanti con i soli
  dati del file. Esportazione e importazione nel registro attività.
- **Conservazione dei backup a rotazione**: degli automatici l'ultimo di ciascuno degli ultimi
  `BACKUP_GIORNALIERI` (7) giorni, `BACKUP_SETTIMANALI` (4) settimane e `BACKUP_MENSILI` (12) mesi;
  degli altri (manuali, caricati, prima del ripristino o dell'aggiornamento) gli ultimi
  `BACKUP_ALTRI` (10); tetto facoltativo `BACKUP_SPAZIO_MASSIMO`. La pulizia gira dopo ogni backup,
  anche manuale, e con `manage.py backup --pulisci`.
- **Backup esclusi dalla rotazione** (puntina nella pagina dei backup, oppure
  `manage.py backup --conserva NOME --nota ...` / `--rilascia NOME`): non vengono mai eliminati da soli.
- **Ripristino sicuro**: se il ripristino non riesce (database, aggiornamento dello schema di un
  backup di una versione precedente, file), si rimette da sé lo stato salvato «prima del ripristino»
  e la pagina di avanzamento dice che nulla è cambiato. Test del ripristino di un backup creato con
  una versione precedente (migrazioni mancanti applicate) e del ritorno allo stato precedente.
- Controllo dello spazio su disco: un backup (anche quello prima di un ripristino) non parte se
  lascerebbe meno di `BACKUP_SPAZIO_LIBERO_MINIMO` (1G) liberi. La pagina dei backup mostra perché
  ciascuno è conservato, lo spazio occupato e quello libero.

### Modificato
- `BACKUP_CONSERVA` diventa `BACKUP_GIORNALIERI` (il vecchio nome vale ancora); il valore predefinito
  passa da 14 backup automatici a 7 giorni + 4 settimane + 12 mesi. **Al primo backup dopo
  l'aggiornamento** si eliminano gli automatici fuori dalla nuova rotazione e i backup manuali oltre
  i 10 più recenti: escludere prima dalla rotazione quelli da tenere.

## [1.0.12] - 2026-11-16

Conferma di ricezione delle domande di iscrizione arrivate per email.

### Aggiunto
- **Conferma di ricezione delle domande di iscrizione arrivate per email**: registrando la domanda dal
  messaggio, una casella (spuntata) mette in coda l'email al mittente con il richiedente, il numero e la
  data di protocollo. Modello *Conferma di ricezione della domanda* con i nuovi segnaposto
  `{{ richiedente }}`, `{{ protocollo }}`, `{{ data_protocollo }}`; finalità istituzionale; con l'invio
  spento resta in coda; un problema con la conferma non annulla la domanda.

## [1.0.11] - 2026-11-16

Manuale di gestione documentale e pubblicazione nel catalogo del riuso.

### Aggiunto
- **Manuale di gestione documentale** (Protocollo → Altro → *Manuale di gestione*), sul modello delle
  Linee guida AgID: composto dalla configurazione reale (sezioni, ruoli e utenti abilitati, caselle,
  regole del registro, annullamento, riservati, registro giornaliero, backup, titolario) più i dati
  organizzativi (responsabile e vicario, conservazione, atto di adozione, disposizioni aggiuntive);
  bozza in PDF con le parti da completare; **Adotta e protocolla** registra ogni versione come
  protocollo interno con il PDF allegato. Indica anche cosa il sistema non copre delle regole tecniche
  per le pubbliche amministrazioni. Le versioni adottate sono **consultabili da tutti gli utenti**
  (storico nella pagina del manuale e collegamento nell'aiuto); la versione in vigore si **pubblica**
  fra i documenti pubblici all'adozione o in qualsiasi momento dopo (e si ritira), nella variante senza
  l'elenco degli utenti né gli account delle caselle conservata all'adozione; una nuova versione
  sostituisce quella pubblicata.
- `publiccode.yml` per il catalogo del riuso di Developers Italia.

## [1.0.10] - 2026-11-16

Liste di distribuzione e buste nel protocollo, modelli di registrazione, firme e timbri nelle stampe.

### Aggiunto
- **Modelli di registrazione del protocollo** (Protocollo → Altro → *Modelli di registrazione*):
  direzione, mezzo, classificazione, oggetto, testo e liste di distribuzione; in *Nuova registrazione*
  il pulsante **Parti da un modello** li precompila (segnaposto `{{ anno }}`, `{{ anno_precedente }}`,
  `{{ data }}`, `{{ organizzazione }}`). Sette modelli di base da adattare.
- **Firme e timbri nelle stampe** (Organi sociali → *Firme e timbri*): immagine della firma per
  persona (vale in ogni carica e come rappresentante legale, con l'autorizzazione annotata) e timbro
  dell'associazione e di ogni sezione. Le immagini (PNG o JPEG, da scanner o telefono) sono ripulite:
  sfondo bianco reso trasparente, margini ritagliati, metadati tolti. Compaiono in calce a ricevute,
  convocazioni, rendiconto, libro soci, inventario, lettere e attestati; si possono sospendere o
  togliere, mai pubblicate in rete. Stampa di prova in PDF e guida su come acquisirle.
- **Firma e timbro generici**, se manca l'immagine: nome in corsivo sopra la riga (font Great Vibes,
  OFL) e timbro tondo con denominazione e località o sezione. Accesi in partenza (si spengono in
  *Firme e timbri*); le cariche vacanti restano senza firma.
- **Foglio prestampato** in PDF per firma (riquadri 60 × 20 mm, con la dichiarazione di autorizzazione
  da firmare) e timbro (45 × 45 mm), bordi in azzurro chiaro tolti con lo sfondo; indicazioni per lo
  scanner (300 dpi, colore o grigi, PNG) e rifiuto delle immagini troppo piccole.
- Permesso *Firme e timbri* per amministratore di sistema, presidente e segretario; il **presidente
  di sezione** gestisce il timbro della propria sezione e le firme di chi vi ricopre una carica.
- **Liste di distribuzione nel protocollo**: nella registrazione in uscita si scelgono una o più
  liste (Comunicazioni → Liste); i componenti diventano destinatari, una volta sola e senza le persone
  decedute.
- **Buste DL e destinatari in CSV** (scheda del protocollo → *Buste*): buste 220 × 110 mm in Word già
  compilate, oppure documento per la stampa unione con l'elenco dei destinatari in CSV. Per posta,
  raccomandata e consegna a mano valgono per tutti i destinatari; per email e PEC solo per quelli senza
  indirizzo email. Avviso per gli indirizzi postali mancanti o incompleti.
- Destinatari non in anagrafica con indirizzo postale: `Nome; indirizzo`.

### Modificato
- Per posta, raccomandata e consegna a mano il protocollo registra l'**indirizzo postale** dei
  destinatari dell'anagrafica (prima l'email, quando c'era); così anche le lettere protocollate dai
  modelli di stampa.

## [1.0.9] - 2026-11-16

Testo del protocollo.

### Aggiunto
- **Testo del protocollo**: nella nuova registrazione un campo per il corpo di email, PEC o messaggi
  (o la trascrizione di una comunicazione) quando il contenuto non è in un file da allegare. Come
  l'oggetto non si modifica dopo la registrazione; è mostrato nel dettaglio e si cerca nel registro e
  nella ricerca globale. Protocollando un messaggio della posta il testo viene riportato in automatico.

## [1.0.8] - 2026-11-10

Correzione nelle comunicazioni.

### Corretto
- Comunicazioni: nell'elenco e nel dettaglio l'oggetto di un invio con un solo destinatario mostra
  i segnaposto personali risolti (es. «Buon compleanno, Alessandra!» invece di
  «Buon compleanno, {{ nome }}!»), come nell'email effettivamente inviata.

## [1.0.7] - 2026-11-09

Rappresentante legale, modelli di convocazione e modelli per la privacy.

### Aggiunto
- **Rappresentante legale** (Organi sociali → Rappresentante legale): persona anche esterna agli
  organi gestiti (es. il presidente nazionale), per l'associazione o per una sezione, con qualifica,
  periodo e atto di nomina; «vale per tutta la struttura» la estende alle sezioni senza una nomina
  propria. Tabella «Chi firma oggi» per ente. Segnaposto `{{ rappresentante_legale }}` e
  `{{ qualifica_rappresentante }}` nei modelli di stampa.
- **Modelli di convocazione** (Organi sociali → Modelli di convocazione): testo e ordine del giorno
  tipici (assemblea ordinaria per il rendiconto, elettiva, straordinaria per lo statuto; consiglio
  ordinario, per il rendiconto, di insediamento; organo di controllo), con `{{ anno }}` e
  `{{ anno_precedente }}`. In *Nuova riunione* il pulsante «Parti da un modello» li precompila.
- **Modelli di stampa per la privacy (GDPR)**, da adattare: informativa (art. 13), autorizzazione
  al trattamento con istruzioni (art. 29), nomina del responsabile (art. 28), riscontri alle
  richieste di accesso (art. 15) e di cancellazione (art. 17), comunicazione di violazione
  (art. 34), consenso a foto e video. Opzione «Firma il rappresentante legale» nei modelli e
  segnaposto `{{ sede }}`, `{{ codice_fiscale_ente }}`, `{{ email_ente }}`, `{{ pec_ente }}`.

### Modificato
- Il riepilogo dei dati personali (GDPR) è firmato dal rappresentante legale del titolare del
  trattamento (se non indicato, dal presidente in carica come prima); le altre stampe restano
  firmate dal presidente.

## [1.0.6] - 2026-11-09

Coriandoli per i compleanni nel calendario.

### Aggiunto
- **Coriandoli nel calendario**: con «Mostra i compleanni», se nei prossimi 60 giorni ci sono
  compleanni, all'apertura scendono i coriandoli di Tabler (non con «riduci movimento» del sistema).

## [1.0.5] - 2026-11-09

Stampa dei codici fiscali da sistemare e menu laterale nascondibile.

### Aggiunto
- **Stampa PDF dei codici fiscali da sistemare** (Anagrafica → Codici fiscali): riepilogo della
  scheda scelta (non validi, non corrispondenti, mancanti o tutti) con problema e codice calcolato,
  raggruppato per sezione quando le sezioni attive sono più d'una.
- **Menu laterale nascondibile**: pulsante nella barra superiore (schermi larghi); la scelta resta
  nel browser.

## [1.0.4] - 2026-11-09

Aggiornamenti sicuri per le installazioni su porta diversa dalla 8000.

### Corretto
- **Aggiornamento con `installa.sh`** (e `crea-lxc.sh --aggiorna`): senza `--porta`/`--indirizzo`
  il servizio tornava sulla porta 8000 e su `0.0.0.0`, mettendo fuori linea le installazioni dietro
  reverse proxy su un'altra porta. Ora restano porta e indirizzo del servizio installato.
- **Messaggio di benvenuto dei container**: mostra l'indirizzo pubblico (`URL_PUBBLICO`) quando è
  configurato, con quello interno tra parentesi.

## [1.0.3] - 2026-11-09

Codice fiscale assistito, firme in calce alle stampe e domande di iscrizione arrivate per email;
correzioni all'immagine Docker e all'installazione in container Proxmox.

### Aggiunto
- **Codice fiscale assistito**: pulsante **Calcola** nelle schede dell'anagrafica e nelle domande di
  iscrizione (scelta fra comuni omonimi, comune valido alla data di nascita, stati esteri, grafie degli
  archivi con apostrofi e nomi bilingui); controllo anche di cognome e nome; avviso nella scheda;
  pagina **Anagrafica → Codici fiscali** con i codici non validi, non corrispondenti o mancanti (soci) e
  la correzione calcolata da applicare, annotata nel registro attività.
- **Firme in calce alle stampe**: qualifica, spazio per la firma e nome di chi era in carica alla data
  del documento, dalle cariche degli Organi sociali (carica vacante: spazio senza nome). Su ricevute
  delle quote (tesoriere o, se manca, presidente), rendiconto (tesoriere se c'è, e presidente), libro
  soci, inventario, ricevuta di protocollo, dati personali e convocazioni (con il nome del presidente).
- **Domande di iscrizione arrivate per email**: etichetta *iscrizione?* nella posta da protocollare;
  dal messaggio, **Domanda di iscrizione** apre la domanda già compilata con i dati trovati nel testo,
  nei PDF allegati e nel mittente (nulla di inventato), segnala i doppioni e, in un'unica operazione,
  protocolla il messaggio in entrata e registra la domanda collegata. Le domande hanno ora la
  **richiesta di adesione firmata** (dagli allegati, o caricata a mano), che all'accoglimento passa
  alla scheda del socio con il riferimento al protocollo di arrivo. Nuova dipendenza `pypdf` (BSD).
- **Container Proxmox**: messaggio di benvenuto al login (versione, indirizzo, stato dei servizi,
  ultimo backup, comandi utili), installato da `crea-lxc.sh` anche negli aggiornamenti.

### Corretto
- `crea-lxc.sh` sceglieva il template Debian **arm64** su host x86_64 (il container non si avviava).
- `installa.sh` lanciato da `crea-lxc.sh` non trovava `uv` («uv: comando non trovato»).
- **Docker**: file statici illeggibili (pagine senza stile ed errori), backup impossibili
  (`pg_dump` mancante: l'immagine passa a Debian 13 con il client PostgreSQL 17) e salvati fuori
  dai volumi (nuovo volume `backup`), errore del socket di controllo di gunicorn, pianificatore
  segnalato come non funzionante dal controllo di salute del web server.

## [1.0.2] - 2026-11-09

Scambio simmetrico fra installazioni e trasferimento di sezione dei soci.

### Aggiunto
- **Scambio simmetrico** fra installazioni: opzione dell'importazione **Aggiorna anche i dati
  diversi** (dati anagrafici, matricola, sospensione e riattivazione prendono il valore del file;
  nome, cognome e codice fiscale invariati; nessuna riattivazione dei cessati) e colonna **Stato
  socio** nell'esportazione di scambio.
- **Trasferimento di sezione** di un socio (scheda del socio → *Trasferisci di sezione*): data,
  motivo e storico dei passaggi; numero, tessere e quote invariati; le cariche in corso negli organi
  della sezione di provenienza si chiudono alla stessa data a scelta, altrimenti vengono segnalate.
  Permesso nuovo `soci.trasferisci_socio` (Amministratore di sistema, Segretario). Nella modifica
  del socio la sezione non è più modificabile.
- **Anteprima** dell'importazione più chiara: ogni differenza è indicata come *valore attuale →
  valore del file*.

## [1.0.1] - 2026-11-09

Scambio dei soci fra installazioni (federazione e sezioni).

### Aggiunto
- **Scambio dei soci fra installazioni** (federazione e sezioni, nei due sensi): *Soci → Stampa ed
  esporta → Per un'altra installazione (Excel)* con le stesse colonne dell'importazione (anagrafica,
  sezione, tessere dell'anno e del precedente, Valido, data del pagamento), da reimportare così
  com'è; l'importazione riconosce le nuove colonne **Data pagamento** e **Causa di cessazione**.
  Il file comprende sempre anche i soci cessati, così la cessazione (con la causa, es. decesso)
  passa all'altra installazione.

### Corretto
- Importazione dei soci: un telefono fisso con il prefisso internazionale (+39 0971…) veniva
  registrato come cellulare.

## [1.0.0] - 2026-11-09

**Prima versione stabile.** Comprende tutto quanto rilasciato nelle release candidate 0.0.1-rc.1 … rc.16 e le novità seguenti. Requisiti: Python 3.13, Django 6.1, PostgreSQL; installazione su Debian/Ubuntu o in un container LXC (la build Docker non è ancora verificata).

### Aggiunto
- **Termini di conservazione** (*Sistema → Conservazione dei dati*): anni di conservazione dopo la
  cessazione o l'archiviazione, elenco delle persone oltre il termine con anonimizzazione in blocco
  e, se attivata, automatica ogni notte (`manage.py conservazione_dati`); esclusi i defunti. Data di
  archiviazione registrata nelle schede.
- **GDPR** nella scheda della persona: **esportazione di tutti i dati** (ZIP con riepilogo PDF, JSON
  e foto) e **anonimizzazione** irreversibile con motivo e conferma; restano i documenti ufficiali e
  il registro attività. Nuovi permessi *esporta_dati_personali* (Amministratore, Segretario) e
  *anonimizza_soggetto* (Amministratore).
- **Tessera digitale**: PDF in formato carta con QR di verifica dalla scheda del socio, e invio per
  email in bozza (nuovo modello *Tessera digitale*); la tessera ufficiale resta quella prestampata.
- **Verifica pubblica della tessera** dal QR o con numero e cognome (anche nella pagina pubblica):
  solo validità, nome, anno e sezione; limite di tentativi per indirizzo.
- **Ricerca globale** dalla barra in alto: persone ed enti, soci, protocolli, riunioni, delibere, beni,
  appuntamenti e comunicazioni, raggruppati per modulo, secondo i permessi (soci della propria
  sezione, riservati solo con il permesso).

## [0.0.1-rc.16] - 2026-11-08

Pagina pubblica di presentazione.

### Aggiunto
- **Pagina pubblica di presentazione** (*Sistema → Organizzazione*): all'indirizzo principale, per
  chi non ha fatto l'accesso, finalità dell'associazione, documenti pubblici, contatti, pulsanti
  *Accedi* e *Chiedi l'iscrizione*; spenta per impostazione predefinita, con anteprima.

## [0.0.1-rc.15] - 2026-11-08

Manuale con immagini e in PDF, password impostata dall'amministratore, sezione del socio.

### Aggiunto
- **Manuale con immagini**: 22 schermate (con dati di esempio) nelle pagine del manuale in linea e
  **Manuale in PDF** scaricabile dalla pagina del Manuale (copertina, indice, un capitolo per
  sezione) o con `manage.py manuale_pdf`.
- Utenti: **Imposta password** (scelta dall'amministratore, con l'opzione del cambio al primo
  accesso) e casella **Può cambiare la propria password** (tolta: niente cambio né recupero via
  email da parte dell'utente).
- **Sezione del socio** nella scheda del socio e nel riquadro *Socio* della scheda in anagrafica;
  nelle cariche degli organi di sezione compare il nome della sezione.
- Menu utente: **Statuto e regolamento** quando sono pubblicati.

### Corretto
- Aggiunte le note della 0.0.1-rc.14, mancanti nella release.
- Organi sociali: elenco ordinato per associazione e sezioni (i gruppi comparivano mescolati) e,
  per l'assemblea di una sezione, «formata dai soci della sezione».

## [0.0.1-rc.14] - 2026-11-08

Organi delle sezioni, ruolo Presidente di sezione, documenti pubblici.

### Aggiunto
- **Organi delle sezioni**: ogni organo è dell'associazione o di una sezione (assemblea di sezione con
  i soli soci della sezione); lo stesso socio può avere cariche in sezione e in federazione;
  **Nuovo organo**; in *Sezioni*, **Crea gli organi** (consiglio e assemblea con le regole
  dell'associazione) e **Organigramma** in PDF della sezione.
- Ruolo **Presidente di sezione**: anagrafica, soci, tesseramento e domande della sola propria
  sezione, calendario e stampa documenti; nessun accesso ai moduli della federazione.
- **Documenti pubblici** (*Sistema → Documenti pubblici*): statuto, regolamento e altri PDF
  consultabili da chiunque in `/documenti-pubblici/`, collegati dalla pagina di accesso e dalle
  pagine pubbliche; caricati e sostituiti dal gestore.

## [0.0.1-rc.13] - 2026-11-08

Modifica delle cariche negli organi sociali.

### Aggiunto
- Organi sociali: **modifica delle cariche** (date di inizio e cessazione, atto di nomina, note),
  anche nello storico, con controllo delle sovrapposizioni e registro dei valori prima e dopo.

## [0.0.1-rc.12] - 2026-11-08

Verifica dei servizi di posta e azioni in blocco sulla posta da protocollare.

### Aggiunto
- *Posta da protocollare*: **azioni in blocco** sui messaggi selezionati (con «seleziona tutti»):
  scarto con un motivo comune (motivi frequenti proposti) e ripristino degli scartati; ripristino
  anche dalla scheda del messaggio.
- *Servizi di posta*: pulsante **Verifica** per ogni casella IMAP (accesso in sola lettura con il
  conteggio dei messaggi, nulla scaricato) e per il server di invio (accesso, nessuna email spedita).

## [0.0.1-rc.11] - 2026-11-08

Interruttori dei servizi di posta.

### Aggiunto
- **Sistema → Servizi di posta** (solo Amministratore di sistema): interruttori generali
  dell'**invio delle email** (spento: nulla parte, i messaggi confermati restano in coda, auguri e
  promemoria automatici non vengono preparati, niente email di recupero password) e della
  **lettura delle caselle IMAP**; stato del server SMTP, coda e caselle; avvisi nelle pagine.

## [0.0.1-rc.10] - 2026-11-08

Calendario completo (appuntamenti, scadenze, vista mensile) e promemoria di rinnovo della quota.

### Aggiunto
- **Promemoria di rinnovo della quota** (*Tesseramento → Promemoria di rinnovo*): email automatiche
  nelle date scelte ai soci non in regola, con l'importo dovuto; mai due volte nello stesso giorno;
  *Prepara ora* crea un invio in bozza da confermare. Modello di messaggio pronto (spenti
  dopo l'installazione).
- Calendario: **appuntamenti e scadenze** inseriti a mano (evento, cerimonia, scadenza,
  promemoria; anche su più giorni o ogni anno), scadenze da segnare come fatte, in rosso se
  superate; **vista mensile**; riquadro **Prossimi impegni** nel cruscotto (14 giorni e scadenze
  superate) al posto di *Prossime riunioni*. Gli appuntamenti sono anche nel file iCal.

## [0.0.1-rc.9] - 2026-11-08

### Corretto
- La 0.0.1-rc.8 non conteneva il modulo dell'IP reale (`apps/core/rete.py`), richiesto dalla
  configurazione: **non installarla**, usare questa.

## [0.0.1-rc.8] - 2026-11-08

IP reale dei visitatori dietro reverse proxy.

### Corretto
- Dietro un reverse proxy il blocco dei tentativi di accesso e il registro attività usano l'**IP
  reale** del visitatore (`X-Forwarded-For`, solo dai proxy indicati in `PROXY_FIDATI`) invece
  di quello del proxy: prima `PROXY_COUNT` non aveva effetto.

## [0.0.1-rc.7] - 2026-11-08

Calendario con esportazione iCal, anagrafica da e verso le rubriche (vCard), colonna «Valido»
del registro nazionale, novità nella pagina Informazioni. Prima pubblicazione anche su GitHub.

### Aggiunto
- Importazione dal registro nazionale: opzione **«Tieni conto della colonna Valido»** (socio
  validato = attivo e in regola): validato → quota dell'anno incassata, non validato → da
  incassare, vuota → scelta generale.
- **Calendario** (nuova voce di menu): prossimi impegni da riunioni, ricorrenze, restituzioni dei
  prestiti e, a scelta, compleanni dei soci, secondo i permessi; esportazione **iCal** in un file
  `.ics` o con un **collegamento personale** segreto a cui abbonare i calendari di telefono e
  computer (si aggiorna da solo; revocabile; nel database solo l'impronta).
- **Anagrafica ↔ rubrica (vCard)**: *Esporta in rubrica* (elenco filtrato) e *vCard* dalla scheda
  per i contatti del telefono, Google, iCloud, Outlook; *Importa da rubrica* da file `.vcf`
  (2.1/3.0/4.0) con anteprima, abbinamento per email, telefono o nome e completamento dei soli
  campi vuoti. Nuovo permesso *importa_soggetti* (Amministratore di sistema, Segretario).
- Pagina *Informazioni*: riquadro **Novità** con le ultime cinque versioni del registro delle
  modifiche (la versione installata è evidenziata).

## [0.0.1-rc.6] - 2026-11-08

Attestato solenne / benemerenza.

### Aggiunto
- **Attestato solenne / benemerenza** fra i modelli di stampa: A4 orizzontale con cornice dorata
  e angoli ornati, stemmi (logo dell'ente e stemma caricato sul modello), filigrana, titolo in
  capitali, alloro, coccarda tricolore e seconda firma facoltativa; modello *Attestato di benemerenza* pronto.
- Segnaposto `{{ intestazione }}` (titolo, nome e cognome).

### Modificato
- Il nome del firmatario dei documenti è nella forma «Mario Rossi» (con il titolo).

## [0.0.1-rc.5] - 2026-11-08

Incasso massivo delle quote.

### Aggiunto
- **Incasso massivo delle quote** (*Tesseramento → Incasso quote*): si spuntano le quote da pagare
  dell'anno e si indicano una volta data, metodo e riferimento; ricevuta numerata e prima nota per
  ognuna.

### Corretto
- In sviluppo il browser non usa più copie vecchie degli script dopo un aggiornamento.

## [0.0.1-rc.4] - 2026-11-08

Modelli di stampa, utenti collegati all'anagrafica, coerenza fra ruoli e funzioni, cariche e
organigramma degli organi sociali, ricevuta su una pagina.

### Aggiunto - Documenti e modelli di stampa
- Modelli di lettere, attestati e documenti con segnaposto, grassetto ed elenchi, stampati su
  carta intestata; firma del presidente in carica; tre modelli pronti.
- Stampa per una persona (dalla scheda in anagrafica), una lista o una categoria: un PDF con una
  pagina per destinatario, esclusi archiviati e deceduti.
- Protocollazione in uscita facoltativa con il numero stampato sul documento e il PDF allegato.

### Modificato
- Menu *Sistema* compatto ed espandibile.
- Ogni utente deve essere collegato a una scheda dell'anagrafica (scelta o creata con l'utente);
  numero di socio nell'elenco degli utenti.

- Cariche sociali (in corso e concluse) nella scheda del socio e in quella dell'anagrafica; le
  cariche in corso accanto al nome del socio.

- Organi sociali: **organigramma in PDF** dei componenti in carica, per livelli e con le foto.

### Corretto
- Ricevuta della quota su una sola pagina A5 (la firma del tesoriere finiva su una seconda pagina).
- Fine di una carica: la data indicata è quella di cessazione (con la data di oggi la persona esce
  subito dai componenti); una carica chiusa non si chiude due volte; errori del modulo mostrati.

### Sicurezza
- Il protocollo rifiuta le registrazioni di chi non ha il permesso di protocollare, qualunque
  modulo le chieda; negli invii email l'opzione di protocollazione richiede quel permesso.
- Invii email di ricevute, esiti e convocazioni: serve anche il permesso di consultare tessera,
  domanda o riunione, e solo nelle proprie sezioni.
- Test di coerenza: ogni pagina protetta, ogni voce di menu apribile dal ruolo che la vede,
  chi modifica può consultare, permessi collegati fra moduli.

## [0.0.1-rc.3] - 2026-11-08

Gestione degli utenti dall'interfaccia, importazione dai tre gestionali precedenti, aiuto in linea.

### Modificato - Stampe
- Le stampe PDF non aprono più una scheda vuota durante la preparazione: una finestra di attesa
  con il tempo trascorso e la possibilità di annullare; a documento pronto il PDF si apre (o si
  offrono «Apri» e «Scarica»), e gli errori vengono spiegati.
- Tempo massimo delle richieste portato a 300 secondi nei servizi creati dall'installatore.

### Aggiunto - Aiuto in linea e informazioni
- Pulsante **?** nella barra in alto: apre il manuale operativo alla pagina della sezione in uso
  (il manuale è lo stesso di `docs/operativo`, mostrato nell'applicazione con indice e paragrafi).
- Nome, versione e autore nella barra in alto; pagina *Informazioni* con versione, crediti, licenza
  e componenti di terze parti.

### Aggiunto - Importazione dai gestionali precedenti
- Comando `importa_gestionale` (anteprima predefinita, `--esegui` applica, rieseguibile senza
  doppioni) per **Gestione Soci** (soci, tessere con la quota versata, esercizi passati chiusi con la
  prima nota, beni), **Gestione Assemblee** (rubrica, modelli email) e **Protocollo ANCR**
  (rubrica, liste, registrazioni con il numero originale, annullamenti, documenti).
- Prevalgono i dati già presenti: delle schede esistenti si completano solo i campi vuoti.
- Abbinamento dei soci anche per tessera e data di nascita (codici fiscali errati in un archivio).

### Aggiunto - Utenti e ruoli
- **Sistema → Utenti e ruoli**: elenco con ricerca e filtri, creazione, modifica di dati, ruoli e
  sezioni, collegamento alla scheda anagrafica; disattivazione e riattivazione (mai eliminazione).
- Password temporanea generata alla creazione o su richiesta, mostrata una sola volta e da
  cambiare al primo accesso (fino ad allora sono consentite solo le pagine dell'account).
- Azzeramento del secondo fattore per chi ha perso telefono o passkey.
- **Secondo fattore obbligatorio per ruolo** (pagina *Ruoli*): chi ha quei ruoli deve configurare
  app di autenticazione o passkey prima di usare il programma.
- Protezioni: niente auto-disattivazione, niente perdita dei propri permessi di gestione utenti,
  superutenti modificabili solo da superutenti; tutte le operazioni nel registro attività.

## [0.0.1-rc.2] - 2026-11-08

Correzioni dal primo collaudo in produzione: installatore su server condivisi, backup automatici,
importazione dal registro nazionale senza limite di tempo e con le sezioni abbinate per comune.

### Modificato
- Importazione dal registro nazionale: anteprima ed esecuzione in un processo separato, con una
  finestra modale di avanzamento («riga N di M») aggiornata ogni secondo; avanzamento anche nel
  comando `importa_registro_soci`.
- Importazione: la sezione del file si riconosce **per comune** (predefinito), per nome o per
  codice, a scelta; solo sezioni attive; l'anteprima mostra l'abbinamento di ogni valore.
- Un comune può avere una sola sezione attiva (pagina Sezioni e configurazione guidata).

### Corretto
- Importazioni lunghe dall'interfaccia interrotte dal tempo massimo delle richieste (120 s) e quindi
  annullate per intero: ora girano in un processo separato senza limite di tempo.
- Configurazione guidata: «Comune, PR» scritto con la virgola viene separato in comune e provincia.
- Installatore: installa solo i pacchetti mancanti (server condivisi con altri servizi).
- `collectstatic` in produzione: riferimenti alle mappe sorgente di Tabler.
- Intestazione COOP inviata solo con HTTPS (in HTTP il browser la ignorava con un avviso).
- Un solo backup automatico al giorno anche dopo i riavvii del pianificatore; il backup fatto
  dall'installatore si chiama «prima dell'aggiornamento».

## [0.0.1-rc.1] - 2026-11-08

Prima release candidate: tutti i moduli di base, installazione su server (script per Debian/Ubuntu e
per container LXC su Proxmox), backup e ripristino.

**Limiti noti** (previsti per le prossime RC): importazione dai tre gestionali precedenti
(Protocollo ANCR, Gestione Soci, Gestione Assemblee); gestione degli utenti dall'interfaccia
principale (per ora da *Amministrazione tecnica*); installatore per RHEL/Rocky; immagine Docker non
ancora verificata.

### Aggiunto - Installazione
- `scripts/installa.sh`: installazione e aggiornamento su Debian/Ubuntu con systemd, senza Docker
  (PostgreSQL, Python con uv, segreti generati, servizi applicazione e pianificatore, backup prima
  di ogni aggiornamento).
- `scripts/proxmox/crea-lxc.sh`: crea su Proxmox VE un container LXC Debian non privilegiato con
  l'applicazione installata; `--aggiorna` per gli aggiornamenti.


### Aggiunto - Backup e ripristino
- Backup completi (database e file caricati) in un unico file con manifesto e impronte; creazione,
  scaricamento, caricamento ed eliminazione da *Sistema → Backup*; backup automatico notturno con
  conservazione degli ultimi N.
- Ripristino dall'interfaccia (conferma e password, avanzamento in tempo reale) o con
  `manage.py ripristina`: verifica, backup di sicurezza dello stato attuale, migrazioni mancanti.
- `inizializza` usa lo stesso backup completo prima di cancellare.

### Aggiunto - Modulo di adesione (Allegato A) e registro nazionale
- Domanda di iscrizione (online e da segreteria) con gli stessi campi, dichiarazioni e consensi del
  modulo di richiesta di adesione e consenso: cellulare, statuto con articoli richiamati, dichiarazione
  SI/NO, consenso al trattamento (obbligatorio), dati particolari, immagine; testi configurabili.
- PDF dell'Allegato A in tre pagine (richiesta, consenso, informativa): in bianco, compilato dalla
  domanda o dai dati del socio.
- Richiesta di adesione firmata nella scheda del socio, consultabile nella pagina; caricamento di un
  PDF o delle foto delle pagine (unite in PDF).
- Comando `inizializza`: azzera database e file e riporta a una nuova installazione, con conferma
  e backup obbligatorio prima della cancellazione.
- Importazione: scelta delle quote da incassare o già incassate (senza ricevuta né prima nota);
  luogo di nascita con la provincia ricavata dal codice fiscale.
- Logo proprio del modulo di adesione (es. quello della presidenza nazionale).
- Importazione adattata all'estratto «Gestione Registro Soci»: date in italiano, anno sociale, tessera
  dell'anno precedente, annullamenti come cessazioni, incarichi, telefoni, sezioni riconosciute per nome.

### Aggiunto - Configurazione, aspetto, sezioni, listino, importazione
- Configurazione iniziale guidata in sei passi (ente, logo e colori, sezioni, tesseramento, tesoreria,
  riepilogo), proposta al primo accesso e ripetibile; manuale con l'elenco dei dati da preparare.
- Personalizzazione dell'interfaccia: logo (anche nei PDF e come icona), colore principale con testo
  leggibile calcolato, menu scuro, chiaro o colorato.
- Foto nelle schede di anagrafica e soci, ripulite dai metadati e visibili solo agli autorizzati.
- Sezioni: soci, tessere fisiche e domande divise per sezione, utenti limitabili alle proprie sezioni,
  matricola nazionale del socio, gestione delle sezioni.
- Listino annuale del tesseramento: costo d'acquisto delle tessere e quote per tipologia, creato
  all'apertura dell'esercizio.
- Importazione dei soci dall'estratto Excel/CSV del registro nazionale con anteprima esatta, abbinamento
  per codice fiscale/matricola, completamento senza sovrascritture, creazione delle sezioni,
  attribuzione delle tessere; comando `importa_registro_soci`.

### Aggiunto - Patrimonio
- Inventario numerato con categorie, quantità, ubicazione, conservazione, provenienza, valore e foto
  (ridimensionata e senza metadati); valutazioni con storico.
- Prestiti con restituzione e scadenze segnalate; uscite definitive (donazione, vendita, comodato
  restituito, dismissione, smarrimento) senza cancellazioni.
- Schede pubbliche dei cimeli con QR (solo dati scelti), etichette da stampare, inventario in PDF e CSV.
- Passaggio di consegne con fotografia immutabile, verbale PDF con impronta e protocollazione facoltativa.
- Traduzione italiana della scelta vuota nei menu a tendina; impostazione `URL_PUBBLICO`.

### Aggiunto - Tesoreria
- Esercizi con saldi per conto, chiusura con riporto dei saldi e riapertura motivata.
- Piano dei conti del rendiconto per cassa ETS (Modello D) con sottovoci personalizzabili.
- Prima nota numerata (entrate, uscite, giroconti) con giustificativi, annullamento motivato, CSV.
- Quote sociali registrate in prima nota all'incasso (cassa per i contanti, banca per bonifico/POS).
- Preventivo con confronto sul consuntivo; rendiconto Modello D a video, PDF e CSV.

### Aggiunto - Comunicazioni e anniversari
- Comunicazioni email con modelli e segnaposto, liste dinamiche (persone, categorie, soci attivi o in
  regola, componenti di un organo), indirizzi liberi, allegati, invio programmato.
- Bozza con anteprima ed elenco degli esclusi con motivo; finalità istituzionale, associativa o auguri
  con verifica dell'ultimo consenso; un messaggio per destinatario; coda con tentativi e registro.
- Protocollazione in uscita facoltativa al termine dell'invio.
- Invio per email di convocazioni (con lettera PDF), ricevute delle quote ed esiti delle domande.
- Anniversari: compleanni, onomastici (calendario modificabile di oltre 100 nomi), anniversari di
  iscrizione, ricorrenze nazionali e della sezione, anniversari di scomparsa; cruscotto aggiornato.
- Auguri automatici per compleanni, onomastici e anniversari di iscrizione e messaggi automatici per le
  ricorrenze, senza doppioni; comando `invia_coda` nel pianificatore.
- Comunicazioni ricevute nella scheda anagrafica; manuale operativo, ruoli, ADR-018.

### Aggiunto - Organi sociali
- Organi (assemblea, consiglio direttivo, organo di controllo) con quorum di prima e seconda
  convocazione, deleghe e voto ai soli soci in regola configurabili; cariche con storico.
- Riunioni con prima e seconda convocazione, modalità in presenza o a distanza, ordine del giorno,
  numerazione per organo e anno, lettera di convocazione in PDF, protocollazione in uscita.
- Foglio presenze con aventi diritto calcolati (soci o componenti in carica), deleghe con limite e
  decadenza, numero legale sempre aggiornato (HTMX).
- Verbale con seduta, discussione per punto e delibere (votazione, voti, esito); chiusura con numero
  nel libro dei verbali, delibere numerate, PDF con impronta e protocollo interno; registro delle delibere.
- Prossime riunioni sul cruscotto; manuale operativo, ruoli, ADR-017.

### Modificato - Tessere dalla sede centrale
- Le tessere non sono più numerate dall'applicazione: si caricano i **lotti di tessere prestampate**
  ricevuti dalla sede centrale (anno, serie, intervallo di numeri, cifre, data, riferimento, costo per
  tessera) e si **attribuiscono** ai soci: al rinnovo, in blocco in seguito (per numero socio o cognome),
  o singolarmente con il numero stampato.
- Giacenza per anno (disponibili, attribuite, annullate, smarrite, restituite) con costo verso la sede
  centrale; elenco dei tesserati in CSV da inviare alla sede centrale.
- Annullando un tesseramento la tessera fisica si annulla o, se non consegnata, torna disponibile.

### Aggiunto - Protocollo
- Registro di protocollo in entrata, uscita e interno con numerazione annuale `AAAA-NNNNN`, mezzo,
  classificazione (titolario di base modificabile), data e protocollo del mittente, collegamento
  «in risposta a», protocolli riservati, ricerca istantanea, esportazione CSV.
- Corrispondenti scelti dall'anagrafica con ricerca o scritti liberamente; testo fissato alla registrazione.
- Documenti multipli con impronta SHA-256, nomi su disco non controllabili dall'utente, estensioni e
  dimensione configurabili, download protetto; si aggiungono e non si tolgono.
- Annullamento motivato; modifica dei soli dati accessori; ricevuta di protocollazione in PDF.
- Registro giornaliero in PDF generato ogni notte e conservato con impronta.
- Posta da protocollare: caselle IMAP email/PEC in sola lettura, password cifrate (`CHIAVE_CIFRATURA`),
  estrazione del messaggio originale delle PEC, testo sempre in chiaro senza HTML, protocollazione con
  riconoscimento del mittente e scarto motivato.
- Comando `pianificatore` (servizio systemd o container) per posta e registri; `genera_chiave_cifratura`.
- Protocolli nella scheda anagrafica e sul cruscotto; manuale operativo, ruoli, ADR-015 e ADR-016.

### Aggiunto - Soci e tesseramento
- Libro soci con numero di iscrizione progressivo mai riutilizzato, tipologie con quota annua,
  ammissione dalla scheda anagrafica (categoria «Socio» automatica), sospensione, cessazione con causa
  (il decesso aggiorna l'anagrafica), riammissione con lo stesso numero.
- Tessere annuali numerate per anno, quota della tipologia modificabile, incasso con metodo e
  riferimento, ricevute numerate per anno in PDF, annullamento motivato senza riuso dei numeri.
- Rinnovo annuale massivo, pagina Tesseramento con riepilogo incassi, filtro soci in regola/morosi.
- Domande di iscrizione da segreteria e dal **modulo pubblico** `/iscrizione/` (attivabile), con
  campo trappola, tempo minimo, limite per IP; accoglimento con deduplica per codice fiscale e
  registrazione dei consensi, rigetto motivato.
- Stampa del libro soci in PDF ed esportazione CSV; generazione PDF con sole risorse locali.
- Riquadro socio nella scheda anagrafica, indicatori soci e domande sul cruscotto.
- Manuale operativo «Soci e tesseramento», tabella ruoli, ADR-013 e ADR-014.

### Aggiunto - Fondamenta
- Analisi dei progetti di origine (Protocollo ANCR, Gestione Soci, Gestione Assemblee), finalità e perimetro.
- Registro delle decisioni di architettura (Django 6.1, PostgreSQL, HTMX, Tabler, CC0).
- Accesso con django-allauth: login con username o email, recupero password, verifica in due
  passaggi (TOTP, passkey, codici di recupero); registrazione libera disattivata.
- Blocco dei tentativi di accesso ripetuti (django-axes), password Argon2 di almeno 12 caratteri.
- Sette ruoli predefiniti con permessi per funzione, allineati automaticamente dopo ogni migrazione.
- Dati dell'organizzazione, registro attività non modificabile, numerazioni atomiche condivise.
- Anagrafica unica di persone ed enti: categorie, codice fiscale con compilazione automatica e
  controllo di coerenza, partita IVA, data di decesso, consensi privacy, archiviazione,
  storia delle modifiche, ricerca istantanea, esportazione CSV protetta e registrata.
- Interfaccia Tabler con menu per ruolo, tema chiaro/scuro, uso da smartphone, CSP senza script inline.
- Manuale operativo, manuale di sistema, roadmap.
- Test automatici, lint, verifica intestazioni, pipeline GitLab CI.
- Dockerfile e compose di produzione (build ancora da verificare).
