# Changelog

Tutte le modifiche rilevanti del progetto. Formato: [Keep a Changelog](https://keepachangelog.com/it/1.1.0/);
versioni: [Semantic Versioning](https://semver.org/lang/it/).

## [Non rilasciato]

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
