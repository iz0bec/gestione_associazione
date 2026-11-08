# Changelog

Tutte le modifiche rilevanti del progetto. Formato: [Keep a Changelog](https://keepachangelog.com/it/1.1.0/);
versioni: [Semantic Versioning](https://semver.org/lang/it/).

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
