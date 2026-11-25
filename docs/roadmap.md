<!--
******************************************************
* Progetto:    Gestione Associazione
* Autore:      Bartolomeo Santoro aka IZ0BEC
* Email:       info@iz0bec.info
* Descrizione: Piano di sviluppo e rilasci
* Licenza:     CC0 1.0 Universal (pubblico dominio)
* SPDX-License-Identifier: CC0-1.0
******************************************************
-->

# Roadmap

## Rilasci

| Versione | Contenuto | Pubblicazione |
|---|---|---|
| **0.0.1-rc.1** ✅ | moduli di base, configurazione guidata, importazione dal registro nazionale, backup e ripristino, installazione su host e LXC | GitLab personale (pubblico) |
| **0.0.1-rc.2** ✅ | correzioni del primo collaudo (installatore, backup, importazione dal registro) | GitLab |
| **0.0.1-rc.3** ✅ | gestione utenti dall'interfaccia, import dai tre gestionali attuali, aiuto in linea | GitLab |
| **0.0.1-rc.4** ✅ | modelli di stampa, utenti collegati all'anagrafica, verifica dei permessi, organigramma | GitLab |
| **0.0.1-rc.5** ✅ | incasso massivo delle quote | GitLab |
| **0.0.1-rc.6** ✅ | attestato solenne / benemerenza con coccarda tricolore | GitLab |
| **0.0.1-rc.7** ✅ | calendario e iCal, rubrica vCard, colonna «Valido», novità; prima pubblicazione su GitHub (anteprima) | GitLab, GitHub |
| 0.0.1-rc.8 ⚠️ | incompleta (manca un file): sostituita dalla rc.9 | GitLab, GitHub |
| **0.0.1-rc.9** ✅ | IP reale dietro reverse proxy; produzione pubblicata in HTTPS | GitLab, GitHub |
| **0.0.1-rc.10** ✅ | calendario completo (appuntamenti, scadenze, mese), promemoria di rinnovo | GitLab, GitHub |
| **0.0.1-rc.11** ✅ | interruttori dell'invio delle email e della lettura della posta | GitLab, GitHub |
| **0.0.1-rc.12** ✅ | verifica di caselle IMAP e server di invio, azioni in blocco sulla posta | GitLab, GitHub |
| **0.0.1-rc.13** ✅ | modifica delle date delle cariche negli organi sociali | GitLab, GitHub |
| **0.0.1-rc.14** ✅ | organi delle sezioni, ruolo Presidente di sezione, documenti pubblici (statuto e regolamento) | GitLab, GitHub |
| **0.0.1-rc.15** ✅ | manuale con immagini e in PDF, password impostata dall'amministratore, sezione del socio | GitLab, GitHub |
| **0.0.1-rc.16** ✅ | pagina pubblica di presentazione | GitLab, GitHub |
| 0.x | collaudo presso la sezione, correzioni, funzionalità della fase 2 | GitLab |
| **1.0.0** ✅ | prima release stabile: tutti i moduli della fase 1, ricerca globale, tessera digitale, GDPR e termini di conservazione, manuale con immagini e in PDF | GitHub, GitLab |
| **1.0.1** ✅ | scambio dei soci fra installazioni (federazione e sezioni), cessazioni comprese | GitHub, GitLab |
| **1.0.2** ✅ | scambio simmetrico con anteprima delle differenze; trasferimento di un socio in un'altra sezione | GitHub, GitLab |
| **1.0.3** ✅ | codice fiscale assistito; firme in calce alle stampe; domande di iscrizione arrivate per email; immagine Docker e container Proxmox corretti | GitHub, GitLab |
| **1.0.4** ✅ | aggiornamenti che mantengono porta e indirizzo del servizio; benvenuto dei container con l'indirizzo pubblico | GitHub, GitLab |
| **1.0.5** ✅ | stampa PDF dei codici fiscali da sistemare (per sezione); menu laterale nascondibile | GitHub, GitLab |
| **1.0.6** ✅ | coriandoli nel calendario quando ci sono compleanni | GitHub, GitLab |
| **1.0.7** ✅ | rappresentante legale (anche esterno, per tutta la struttura), modelli di convocazione, modelli privacy/GDPR | GitHub, GitLab |
| **1.0.8** ✅ | correzione: oggetto delle comunicazioni con i segnaposto personali risolti | GitHub, GitLab |
| **1.0.9** ✅ | testo del protocollo (corpo di email, PEC e messaggi), riportato anche dalla posta ricevuta | GitHub, GitLab |
| **1.0.10** ✅ | liste di distribuzione e buste DL nel protocollo, modelli di registrazione; firme e timbri nelle stampe (anche generici), foglio prestampato | GitHub, GitLab |
| **1.0.11** ✅ | manuale di gestione documentale (AgID) composto dalla configurazione, adozione protocollata, consultazione e pubblicazione; publiccode.yml | GitHub, GitLab |
| **1.0.12** ✅ | conferma di ricezione delle domande di iscrizione arrivate per email, con il numero di protocollo | GitHub, GitLab |
| **1.0.13** ✅ | liste di destinatari in Excel (modifica fuori linea e reimportazione), conservazione dei backup a rotazione con backup esclusi, tetto di spazio e controllo del disco, ripristino che torna allo stato precedente se non riesce | GitHub, GitLab |
| **1.0.14** ✅ | indirizzo postale nel foglio Persone delle liste in Excel (completa solo i campi vuoti, segnala i valori diversi) | GitHub, GitLab |
| **1.0.15** ✅ | lettere in PDF e buste DL per i destinatari senza email delle comunicazioni; indirizzi postali e motivo nel foglio Destinatari delle liste in Excel | GitHub, GitLab |
| **1.0.16** ✅ | liste limitate ai soci di una o più sezioni; libro soci raggruppato per sezione; stampe ed esportazioni dell'elenco soci che seguono i filtri, elenco filtrato in PDF | GitHub, GitLab |
| **1.0.17** ✅ | timbri degli enti in Sistema → Organizzazione, solo amministratore di sistema; corretti «Non usare» e «Togli» dei timbri | GitHub, GitLab |
| **1.0.18** ✅ | spedizione dei protocolli in uscita per email e PEC dalla scheda, con le ricevute PEC agganciate; SMTP delle caselle (anche PEC Aruba) | GitHub, GitLab |
| **1.0.19** ✅ | posta scaricata spostata nella cartella PROCESSATA della casella IMAP (email e PEC), creata se manca | GitHub, GitLab |
| **1.0.20** ✅ | cartella PROCESSATA nel namespace del server (INBOX.PROCESSATA su Aruba) | GitHub, GitLab |
| **1.0.21** ✅ | mittente vero delle PEC firmate (Aruba) e risposta con l'indirizzo del destinatario | GitHub, GitLab |
| **1.0.22** ✅ | servizi di invio (SMTP, email e PEC) in Sistema → Servizi di posta; caselle solo per la lettura | GitHub, GitLab |
| **1.0.23** ✅ | caselle configurate in Sistema → Servizi di posta; il protocollo sceglie solo quali usare | GitHub, GitLab |
| **1.0.24** ✅ | «Rispondi con» per casella, risposte dal servizio della casella di arrivo, interruttore dei servizi, comandi per la chiave di cifratura | GitHub, GitLab |
| **1.0.25** ✅ | etichette adesive in PDF, pulizia selettiva della posta scartata (cartella SCARTATA e cestino sul server), blocco delle email ordinarie verso le PEC | GitHub, GitLab |
| **1.0.26** ✅ | spostamenti sul server anche per gli scartati rimasti nella posta in arrivo | GitHub, GitLab |
| **1.0.27** ✅ | comunicazioni via PEC (con ricevute), su Telegram, per SMS e su WhatsApp Business; comunicazioni anche senza email | GitHub, GitLab |
| **1.0.28** ✅ | avvisi della posta da protocollare su Telegram, SMS o WhatsApp scelti da ciascun utente; interruttore «Invio dei messaggi» | GitHub, GitLab |
| **1.0.29** ✅ | scadenza dei mandati nel cruscotto e nel calendario; utenti connessi in Sistema → Utenti | GitHub, GitLab |
| **1.0.30** ✅ | backup incrementali, cifrati con CHIAVE_BACKUP, prova di ripristino settimanale | GitHub, GitLab |
| **1.0.31** ✅ | incassi diversi dalle quote con ricevuta, note di storno e rimborsi, registro incassi con quadratura | GitHub, GitLab |
| **1.0.32** ✅ | eventi e cerimonie con adesioni dalla segreteria e dal modulo pubblico | GitHub, GitLab |
| **1.0.33** ✅ | area personale dei soci con accesso tramite collegamento via email | GitHub, GitLab |
| **1.0.34** ✅ | messaggio della password in italiano, manuale dei backup aggiornato al formato incrementale | GitHub, GitLab |
| **1.0.35** ✅ | chat interna fra gli utenti del gestionale (a due e di gruppo, riservata ai partecipanti) | GitHub, GitLab |
| **1.0.36** ✅ | HTTPS dall'installatore (certificato della propria CA o autofirmato), guida HTTPS anche in rete interna | GitHub, GitLab |
| **1.0.37** ✅ | certificati con rinnovo automatico: `--tls-step` (step-ca) e `--tls-acme` (certbot); CA interna su Proxmox | GitHub, GitLab |
| **1.0.38** ✅ | API di interoperabilità F1: identità dell'istanza, firma di richieste e risposte, abbinamento con invito monouso | GitHub, GitLab |
| **1.0.39** ✅ | campagna delle tessere con le sezioni, avvisi alle sezioni, importazione delle consegne | GitHub, GitLab |
| **1.0.40** ✅ | correzioni della campagna delle tessere | GitHub, GitLab |
| **1.0.41** ✅ | azioni su più comunicazioni insieme; email istituzionale della sezione | GitHub, GitLab |
| **1.0.42** ✅ | modifica delle bozze delle comunicazioni, «Seleziona tutte» | GitHub, GitLab |
| **1.0.43** ✅ | testo degli avvisi del tesseramento modificabile | GitHub, GitLab |
| **1.0.44** ✅ | correzione di un errore 500 | GitHub, GitLab |
| **1.0.45** ✅ | comunicazioni annullate in un elenco a parte | GitHub, GitLab |
| **1.0.46** ✅ | risposta della sezione all'avviso di tesseramento; email della federazione nella campagna | GitHub, GitLab |
| **1.0.47** ✅ | ruolo del collegamento (federazione/sezione), scambio dei documenti del ciclo delle tessere, documenti in arrivo | GitHub, GitLab |
| **1.0.48** ✅ | richiesta di tessere firmata dal presidente della sezione, con il PDF originale | GitHub, GitLab |
| **1.0.49** ✅ | comunicazioni protocollate con i segnaposto risolti | GitHub, GitLab |
| **1.0.50** ✅ | modulo Excel della richiesta di tessere e recupero del modulo compilato dalla posta | GitHub, GitLab |
| **1.0.51** ✅ | modulo di richiesta tessere scaricabile dall'elenco dei soci | GitHub, GitLab |
| **1.0.52** ✅ | più sezioni sullo stesso host (`sezioni.sh`) | GitHub, GitLab |
| **1.0.53** ✅ | reverse proxy nel `.env` generato dall'installatore | GitHub, GitLab |
| **1.0.54** ✅ | correzione del token del bot Telegram | GitHub, GitLab |
| **1.0.55** ✅ | verifica dei soci fra federazione e sezione via API (popolamento e modifiche campo per campo); promemoria per l'archivio centrale | GitHub, GitLab |
| **1.0.56** ✅ | correzioni della verifica dei soci | GitHub, GitLab |
| **1.0.57** ✅ | correzione dei ruoli invertiti fra federazione e sezione | GitHub, GitLab |
| **1.0.58** ✅ | verifica dei soci: soci doppi | GitHub, GitLab |
| **1.0.59** ✅ | telefono e cellulare negli scambi fra installazioni | GitHub, GitLab |
| **1.0.60** ✅ | consensi impliciti per i soci | GitHub, GitLab |
| **1.0.61** ✅ | verifica dei soci e importazione: luogo di nascita | GitHub, GitLab |
| **1.0.62** ✅ | registrazione in blocco dei consensi impliciti | GitHub, GitLab |
| **1.0.63** ✅ | dal rinnovo alla richiesta di tessere; ordine alla sede nazionale per email; pagamenti al livello superiore | GitHub, GitLab |
| **1.0.64** ✅ | richiesta di tessere per email | GitHub, GitLab |
| **1.0.65** ✅ | rubrica dai collegamenti API (ente in anagrafica); verifica dei soci via API da Soci → Importa e verifica | GitHub, GitLab |
| **1.0.66** ✅ | segnatura di protocollo AgID (Segnatura.xml firmata XAdES-B), sigillo dell'ente, copia PDF con il timbro | GitHub, GitLab |
| **1.0.67** ✅ | correzione e annullamento delle richieste di tessere registrate a mano | GitHub, GitLab |
| **1.0.68** ✅ | veste grafica delle email (Sistema → Aspetto): logo incorporato, colori, firma, informativa; email di prova | GitHub, GitLab |
| **1.0.69** ✅ | cruscotto: collegamento alla posta da protocollare; consenso implicito alle email per la rubrica | GitHub, GitLab |
| **1.0.70** ✅ | avvisi personali su Telegram, SMS o WhatsApp: posta, domande di iscrizione, sicurezza | GitHub, GitLab |
| **1.0.71** ✅ | eliminazione delle caselle IMAP e del bot Telegram; pulsante Elimina nei servizi di posta | GitHub, GitLab |
| **1.0.72** ✅ | portale dei servizi generato dalle schede pubbliche dei gestionali; recapiti pubblici facoltativi | GitHub, GitLab |
| **1.0.73** ✅ | correzione dei colori del portale dei servizi (CSP) | GitHub, GitLab |
| **1.0.74** ✅ | ambiente dimostrativo con dati di fantasia e azzeramento mensile (demo pubblica) | GitHub, GitLab |
| **1.0.75** ✅ | utenti dalle cariche degli organi, con password per carica e bozze delle credenziali | GitHub, GitLab |
| **1.0.76** ✅ | credenziali «per conto» a chi non ha l'email; testo delle bozze con il manuale | GitHub, GitLab |
| **1.0.77** ✅ | credenziali per conto alla casella dell'ente | GitHub, GitLab |
| **1.0.78** ✅ | utenti da riga di comando: elenco e reimpostazione alla password predefinita con notifica | GitHub, GitLab |
| **1.0.79** ✅ | composizione di tutti gli organi sociali in un unico PDF, con i recapiti | GitHub, GitLab |
| **1.0.80** ✅ | organigramma con le foto nella stampa unica; recapiti di ente e sezioni (indirizzo, PEC) | GitHub, GitLab |
| **1.0.81** ✅ | modulo di richiesta delle tessere riconosciuto anche dopo Numbers; allegati .numbers segnalati | GitHub, GitLab |
| **1.0.82** ✅ | comunicazioni della campagna tessere riconoscibili: oggetto con la sezione; elenco con destinatario, ricerca e filtro per origine | GitHub, GitLab |
| **1.0.83** ✅ | rinnovo degli organi conforme al Regolamento ANCR (liste, votanti e deleghe, esiti, nomine, decadenza e commissariamento); fornitori di posta; esenzione dal secondo fattore; inoltro della email di sezione; conferma alla sezione della richiesta di tessere | GitHub, GitLab |
| **1.0.84** ✅ | richiesta di tessere preparata a mano dalle sezioni senza soci nel gestionale, da inviare alla federazione | GitHub, GitLab |
| **1.0.85** ✅ | campagna delle tessere divisa per direzione (verso le sezioni, verso l'ente sovraordinato) e per fasi; invito ricevuto collegato al protocollo | GitHub, GitLab |
| **1.0.86** ✅ | campagna delle tessere: titoli corretti verso l'ente sovraordinato | GitHub, GitLab |
| **1.0.87** ✅ | campagna: le richieste arrivate dal collegamento si registrano nella fase 2 | GitHub, GitLab |
| **1.0.88** ✅ | conferma di ricezione della richiesta di tessere: segnaposto registrati | GitHub, GitLab |
| **1.0.89** ✅ | campagna: conferme in bozza distinte da quelle inviate | GitHub, GitLab |
| 1.x | Django 6.2 LTS appena disponibile (aprile 2027), verifica della build Docker, termini di conservazione e collaudi | GitHub, GitLab |

## Fase 0 - Fondamenta ✅ (questa versione)

- [x] Analisi dei tre progetti, finalità, decisioni di architettura
- [x] Progetto Django, configurazione da `.env`, PostgreSQL
- [x] Utenti, ruoli predefiniti, accesso con secondo fattore (TOTP, passkey, codici di recupero)
- [x] Blocco dei tentativi ripetuti, Content Security Policy, intestazioni di sicurezza
- [x] Dati dell'organizzazione, registro attività non modificabile
- [x] Numerazioni atomiche condivise (test di concorrenza)
- [x] **Anagrafica unica**: persone ed enti, categorie, codice fiscale, consensi, archiviazione, esportazione CSV
- [x] Interfaccia: layout, tema chiaro/scuro, ricerca istantanea, uso da smartphone
- [x] Test automatici, lint, pipeline CI
- [x] Dockerfile e compose, build e funzionamento verificati su Docker Desktop (09/11/2026)

## Fase 1 - Moduli per la 0.0.1 RC

Ordine proposto (ognuno con test, manuale operativo e voce nel manuale di sistema):

1. ✅ **Soci e tesseramento** - libro soci, numero socio, domande di iscrizione (anche pubbliche
   con anti-spam), tessere annuali con numerazione, quote, ricevute PDF, rinnovi massivi, morosi.
   ✅ *Fatti in seguito*: invio delle ricevute e dell'esito delle domande per email (Comunicazioni),
   incassi in prima nota (Tesoreria), foto del socio.
2. ✅ **Protocollo** - registro in entrata/uscita/interno (numerazione annuale), allegati privati,
   annullamento motivato, registro giornaliero PDF, ricezione email/PEC da protocollare.
   ✅ *Fatti in seguito*: liste di distribuzione (Comunicazioni), import dal Protocollo ANCR (punto 8).
   ✅ *Fatto in seguito*: spedizione dei protocolli in uscita per email e PEC, con le ricevute PEC
   agganciate. *Da fare*: API REST (fase 2).
3. ✅ **Organi sociali** - organi, riunioni con 1ª/2ª convocazione e ordine del giorno, presenze dai
   soci, verbali con delibere e votazioni, PDF, protocollazione automatica, libri dei verbali.
   Comprende le **cariche sociali con storico** (previste in fase 2). ✅ *Fatto in seguito*: invio
   delle convocazioni per email (Comunicazioni). *Da fare*: firma digitale dei verbali, votazioni
   elettroniche.
4. ✅ **Comunicazioni e anniversari** - modelli con segnaposto, invii a persone/categorie/liste, coda di
   invio, registro invii, anniversari (compleanni, onomastici, ricorrenze, anzianità da socio, scomparse)
   con auguri automatici (rispettando consensi e decessi), invio di convocazioni, ricevute ed esiti.
   ✅ *Fatti in seguito*: lettere e buste DL per chi non ha l'email, indirizzi postali nelle liste in
   Excel; etichette adesive in PDF (protocollo, comunicazioni, liste); comunicazioni via PEC, su
   Telegram, per SMS e su WhatsApp Business (1.0.27); avvisi della posta da protocollare agli utenti
   (1.0.28). *Da fare*: provare SMS e WhatsApp con un account reale.
5. ✅ **Tesoreria** - esercizi, conti cassa/banca, prima nota, previsionale, rendiconto (Modello D),
   chiusura e riapertura con riporto saldi, collegamento con le quote.
6. ✅ **Patrimonio** - inventario numerato, valutazioni, prestiti/cessioni/donazioni e restituzioni,
   passaggio di consegne con fotografia immutabile, schede QR pubbliche (dati minimi).
6b. ✅ **Configurazione e federazione** - configurazione guidata al primo accesso, aspetto
   personalizzabile (logo, colori, menu), foto in anagrafica e soci, **sezioni** con utenti limitati
   alle proprie, matricola nazionale, **listino annuale** (costo d'acquisto e quote per tipologia),
   **importazione dal registro soci nazionale** (Excel/CSV) con anteprima, adattata all'estratto
   reale del registro (✅, con l'opzione per la colonna «Valido»).
7. ✅ **Documenti PDF** - modelli di stampa modificabili (lettere, attestati) su carta intestata,
   per una persona, una lista o una categoria, con protocollazione in uscita (`apps/documenti`).
8. ✅ **Import** - `importa_gestionale` da Gestione Soci e Gestione Assemblee (SQLite) e Protocollo
   ANCR (PostgreSQL), con anteprima, deduplica dell'anagrafica e rapporto finale.
   ✅ *Fatto in seguito* (1.0.97): foto dei soci, passaggi di consegne e cessioni dei beni, riunioni e
   verbali delle assemblee.
9. ✅ **Installazione su host** - `scripts/installa.sh` (Debian/Ubuntu, systemd) e
   `scripts/proxmox/crea-lxc.sh` (container LXC su Proxmox). Backup e ripristino dall'interfaccia.
   *Da fare*: RHEL/Rocky.
10. ✅ **Gestione utenti dall'interfaccia** - creazione con password temporanea, ruoli e sezioni,
   reimpostazione password, azzeramento del secondo fattore, MFA obbligatoria per ruolo.

## Fase 3 - Progetti (dal 25/11/2026)

Il gestionale è considerato completo e passa al **mantenimento**; la nuova linea di sviluppo è la
gestione dei **progetti finalizzati agli scopi statutari**, dall'idea al rendiconto. Analisi e scelte
in [analisi/progetti.md](analisi/progetti.md).

- **P1** Idee, necessità (anche da sollecitazioni esterne) e progetti, finalità statutarie,
  valutazione e priorità, gruppo di lavoro, stati con delibere.
- **P2** Bandi e finanziatori: registro, scadenze e avvisi, requisiti con verifica sui dati
  dell'organizzazione, abbinamento bando ↔ progetto.
- **P3** Raccolta automatica dei bandi: feed RSS/Atom, pagine web sorvegliate, portali noti; parole
  chiave; proposte da vagliare.
- **P4** Progettazione e candidatura, in due passi: **P4a** quadro (obiettivi, risultati, indicatori),
  attività e cronoprogramma, partner, piano economico con i controlli dei limiti del bando; **P4b**
  scrittura guidata (senza IA), documenti di candidatura, delibera, protocollo e PEC.
- **P4-MCP** Connettore MCP per l'assistenza alle valutazioni (dopo P4): il gestionale resta senza IA
  e espone a un client scelto dall'utente (Claude o altri) bandi, requisiti con gli esiti, idee con le
  valutazioni, progetti, finalità e criteri, perché aiuti a confrontare, suggerire punteggi motivati e
  segnalare ciò che manca. Solo lettura all'inizio (al più commenti o bozze firmate «assistente» da
  confermare), spento di norma, token legato a un utente e ai suoi permessi come le API v1, ogni
  chiamata nel registro attività, nessun dato personale dei soci (solo aggregati).
- **P5** Esecuzione: centro di costo in prima nota, preventivo/consuntivo, ore di volontariato
  valorizzate come cofinanziamento in natura, avanzamento.
- **P6** Rendicontazione e chiusura: rendiconto per il finanziatore con giustificativi (PDF, Excel,
  ZIP), relazione finale guidata, archivio e riuso.

Restano aperte, come manutenzione: API REST del protocollo (in parte coperte dalle API v1), prova di
SMS e WhatsApp con un account reale, installazione su RHEL/Rocky, firma digitale dei verbali e
votazioni elettroniche.

## Fase 2 - Dopo la RC (proposte)

- **Allineamento fra installazioni** (federazione ↔ sezioni). ✅ *Fatto*: scambio con file Excel
  nei due sensi. *Da fare*:
  - ✅ opzione **«aggiorna anche i dati diversi»** e passaggio della sospensione (scambio simmetrico);
  - **collegamento diretto** fra installazioni, senza file: assorbito dall'**API di
    interoperabilità** (ADR-030, sotto).

- Scadenzario e calendario (assemblee, rinnovi, ricorrenze, cerimonie) con esportazione iCal.
  ✅ *Fatti*: prossimi impegni, vista mensile, appuntamenti e scadenze inseriti a mano,
  riquadro nel cruscotto, esportazione iCal (file e collegamento personale).
- ✅ Scambio dell'anagrafica con le rubriche (vCard): esportazione e importazione con anteprima.
- ✅ **Codice fiscale assistito** (`apps/anagrafica/codice_fiscale.py`): pulsante **Calcola** nelle
  schede e nelle domande (comuni omonimi da scegliere, comune valido alla data di nascita, stati esteri,
  grafie degli archivi: apostrofi, nomi bilingui), controllo di cognome, nome, sesso, data e luogo,
  avviso nella scheda, elenco **Codici fiscali** con la correzione calcolata da applicare.
- ✅ **Firme in calce alle stampe** (`apps/organi/firme.py`, tag `{% firme %}`): qualifica, spazio e
  nome di chi era in carica **alla data del documento**; firme alternative («tesoriere, altrimenti
  presidente») e facoltative («tesoriere se c'è»); carica vacante = spazio senza nome. Su ricevute,
  rendiconto, libro soci, inventario, ricevuta di protocollo, dati personali, convocazioni.
  ✅ Immagine della firma (per persona) e timbro (per ente), con firma e timbro generici e la
  guida per acquisirli (*Organi sociali → Firme e timbri*).
- ✅ **Domande di iscrizione arrivate per email** (`apps/soci/estrazione.py`): etichetta
  *iscrizione?* sulla posta, dati recuperati dal testo, dai PDF allegati (campi e testo) e dal mittente
  senza inventare nulla, avviso dei doppioni, domanda e protocollazione in entrata in un'unica
  operazione, **richiesta firmata** sulla domanda (anche per quelle a mano o online) che passa al socio
  all'accoglimento con il riferimento al protocollo. ✅ Risposta di conferma di ricezione al mittente,
  con il numero di protocollo.
- ✅ Eventi e cerimonie con adesioni (1.0.32): segreteria, modulo pubblico, area del socio.
- ✅ Scadenza dei mandati delle cariche (1.0.29): durata per organo,
  avvisi prima della scadenza nel cruscotto e nello scadenzario.
- ✅ Area personale del socio (1.0.33): accesso con collegamento via email, dati, tessere, quote e ricevute, eventi, richieste di correzione.
- ✅ Tessera digitale (formato carta) con QR di verifica, inviata per email; verifica pubblica.
- ✅ Promemoria automatici di rinnovo ai soci non in regola.
- ✅ GDPR: esportazione dei dati di una persona, anonimizzazione, termini di conservazione.
- ✅ Backup automatici cifrati con verifica del ripristino (1.0.30). ✅ Fatta la conservazione a rotazione
  (giornalieri, settimanali, mensili), con tetto di spazio, controllo del disco e backup esclusi
  dalla rotazione.
- ✅ Liste di destinatari in Excel: esportazione per la modifica fuori linea e reimportazione con anteprima.
- ✅ **Backup incrementali dei documenti** (1.0.30): ogni documento (allegati del protocollo, foto,
  firme) si salva una volta sola in un archivio comune, indicizzato per impronta; i backup successivi
  contengono il database e l'elenco dei file, non i file stessi (prima ogni backup li copiava tutti,
  ad Avigliano circa 190 MB a backup). Lo scaricamento produce comunque un backup completo.
- ✅ **Utenti connessi** (1.0.29): chi sta usando il gestionale in questo momento (per l'amministratore).
- ✅ **Chat interna** (1.0.35) fra gli utenti del gestionale (non i soci): conversazioni a due e di
  gruppo, aggiornamento automatico, non letti nella barra, riservate ai partecipanti.
- ✅ Ricerca globale (persone, soci, protocolli, riunioni, delibere, beni, appuntamenti, comunicazioni).
- ✅ **HTTPS dall'installatore** (1.0.36): certificato della propria CA o autofirmato, riavvio al rinnovo;
  guida *HTTPS anche in rete interna* (step-ca, MyCert, OpenSSL).
- ✅ **Certificati con rinnovo automatico** (1.0.37): `installa.sh --tls-step` (step-ca, token monouso) e
  `--tls-acme` (certbot); CA interna su Proxmox con `crea-ca.sh`.
- **API di interoperabilità v1** (ADR-030, approvata; contratto in `docs/api/openapi.yaml`): un unico
  contratto pubblico per le installazioni pari (federazione ↔ sezioni) e per adattatori esterni non
  inclusi nel progetto (es. WordPress). Firma RFC 9421 di ogni messaggio, dati personali cifrati per il
  destinatario (JWE), feed dei cambiamenti con catena di impronte, idempotenza, modalità a spinta per
  chi è dietro NAT, rete interna (stesso Proxmox) senza passare dal proxy, in HTTPS anche con CA
  interna o certificato autofirmato verificato per impronta (HTTP in chiaro solo come eccezione esplicita).
  Fasi: ✅ F1 identità e abbinamento → ✅ F2 feed, eventi, sezioni, notifiche, rotazione e
  aggiornamento delle impronte TLS → ✅ F3 cifratura e sistemi esterni (adesioni, domande, contatti;
  documenti pubblici, organigramma, verifica tessera) → F4 federazione ↔ sezione (soci e tessere,
  lotti, cariche, numeri del tesseramento, eventi provinciali) → ✅ F5 sezione ↔ sezione
  (1.0.96: trasferimento del socio con consenso, eventi condivisi, verifica tessera) e kit per chi
  integra (`docs/api/kit-integrazione.md`).
  ✅ Già fatto della F4: ruolo federazione/sezione e ciclo delle tessere (richieste, consegne,
  ricevute, prese in carico).
  - ✅ **Verifica soci fra federazione e sezione** (1.0.55), nei due sensi, al posto del file Excel:
    `/soci` cifrato con l'ambito `soci:lettura`, ogni sezione vede solo i propri soci (cessati
    compresi). *Verifica soci* nella scheda della controparte: chi manca si **popola**, per chi c'è
    si mostrano le **modifiche campo per campo** e si sceglie cosa applicare (con l'indicazione di
    quale dato è più recente). Stesse regole dell'importazione Excel.
    - *Chi aggiorna cosa* (deciso il 19/11/2026):
      - la **sezione** via API aggiorna i soci (anagrafiche) e i **rinnovi** (tessere e quote dell'anno);
      - la **federazione** aggiorna i soci (anagrafiche), ma i rinnovi non li registra: li **riceve**
        dalle sezioni e li **supervisiona**: riceve la notifica di ogni modifica e verifica cosa è
        avvenuto;
      - se federazione e sezione modificano lo stesso socio vale l'**ordine di tempo** (le modifiche
        si applicano nell'ordine in cui sono state fatte) e l'incongruenza si **notifica per email**
        a entrambe le parti.
  - ✅ **Allineamento automatico** (1.0.93) dopo la prima verifica: lavoro `allinea_soci` ogni 15
    minuti, ordine di tempo rispetto all'ultimo allineamento, incongruenze notificate per email,
    ogni novità (rinnovi, nuovi soci, cessazioni) notificata a chi gestisce i soci; **spinta**
    (`POST /consegne`, flusso `soci`) per le sezioni che la federazione non raggiunge.
  - ✅ **Resto della F4** (1.0.95): cariche e numeri del tesseramento delle installazioni collegate
    (pagina *Installazioni collegate*, confronto con i dati locali), eventi condivisi con iscrizione
    dei propri soci, nel calendario.
    - *Senza API*: lo scambio con file Excel resta come alternativa (interoperabilità facoltativa).
    - *Primo uso*: sezione di Potenza (CT 103, porta 8083), già abbinata alla federazione.
- ✅ Pagamenti tracciati (1.0.31): metodo e ricevuta numerata delle quote, altri incassi, storni e rimborsi, registro incassi con quadratura.
- ✅ **Inoltro della email di sezione** (1.0.83: pulsante *Inoltro* della casella; destinatari scelti a mano, reindirizzo trasparente con ripiego, riservati all'incaricato). Oggi la casella istituzionale di ogni sezione
  (es. `sezione.pz.sez@…`) è inoltrata dal fornitore della posta a chi la gestisce. In futuro
  l'inoltro lo governa il gestionale: per ogni sezione chi riceve i messaggi della casella (di norma
  il presidente, o l'incaricato della trattazione), con le regole cambiate dall'interfaccia e non
  più dal fornitore, nel rispetto della riservatezza (ad es. le credenziali inviate «per conto» di
  chi non ha l'email).
- ✅ **Esenzione dalla verifica in due passaggi per singolo utente** (1.0.83). Quando un ruolo la
  rende obbligatoria, l'amministratore può esentarne un utente che non può attivarla (niente
  smartphone né chiave di sicurezza), dalla sua scheda in *Sistema → Utenti*: con motivo e scadenza
  facoltativa, registrata nel registro attività e indicata nell'elenco degli utenti; l'esenzione non
  vale per l'Amministratore di sistema.
- ✅ **Connettore per WordPress via API** (1.0.90; nel repository in `integrazioni/wordpress`, da separare in seguito). Un plugin WordPress (licenza compatibile, CC0 o
  GPL per il solo plugin) che usa le API di interoperabilità v1 come controparte abbinata: modulo
  di domanda di iscrizione e modulo contatti sul sito che arrivano nel gestionale (`/domande`,
  `/contatti`), calendario degli eventi pubblici con adesioni (`/eventi`), organigramma e recapiti
  della sezione, verifica della tessera. Abbinamento con invito monouso, chiavi conservate da
  WordPress, nessun dato personale dei soci esposto sul sito.
- ✅ **Eventi del connettore WordPress come tipo di contenuto proprio** (plugin 0.2.0, deciso il 24/11/2026):
  invece di legarsi a un plugin di calendario (es. The Events Calendar), il connettore registra un
  tipo di contenuto «Evento» con pagina dell'evento e archivio `/eventi/`, blocco calendario (mese e
  elenco), dati strutturati schema.org/Event, feed iCal, adesione e posti liberi dal gestionale; testo
  e foto del redattore, bozza per default; filtro WordPress per chi vuole riversarli altrove; ripiego
  su «articolo normale» per i temi che non mostrano bene un tipo nuovo. Ad Avigliano da decidere se
  affiancarlo a The Events Calendar o sostituirlo.
- ✅ **Guide rapide per ruolo** (1.0.94): una guida breve per ogni ruolo
  (`apps/accounts/ruoli.py`: segreteria, tesoreria, presidenza, protocollo, consiglieri, revisori,
  amministratore…) con i **flussi di lavoro** essenziali spiegati per passaggi chiave (es. accogliere una
  domanda, rinnovare una tessera, protocollare la posta, convocare una riunione, chiudere l'esercizio),
  raggiungibili dall'aiuto in linea e stampabili; le guide complete restano in `docs/operativo/`.
- ✅ **Utenti da riga di comando** (1.0.78), per l'amministratore del server senza aprire l'interfaccia:
  - `manage.py utenti` elenca gli utenti dell'installazione (nome utente, persona, ruoli, attivo,
    secondo fattore, ultimo accesso, email vera o segnaposto); su un host con più installazioni
    `sezioni.sh utenti` lo fa per tutte;
  - `manage.py utenti --reimposta NOME` riporta la password a quella **predefinita del ruolo** (per gli
    amministratori quella **iniziale dell'installazione**, dal file dell'installatore) o a una generata; come **ultimo passo** il comando chiede se inviare ora l'**email personale di
    notifica** (`--invia` per rispondere sì senza domanda, `--senza-email` per non mandarla; se non
    si invia resta in bozza in *Comunicazioni*) con le credenziali, i passaggi
    per cambiarla e dove trovare il manuale; a chi non ha l'email la notifica va alla casella della
    sezione «per conto» (stessa regola di *Utenti dalle cariche*). La password non finisce mai nel
    registro attività, che annota solo l'operazione.
- **Organi sociali**:
  - ✅ (1.0.79) **stampa in un unico PDF di tutti gli organi sociali**: per ogni organo (dell'associazione e, con
    più sezioni, di ogni sezione) le cariche in corso con nome, ruolo, data di nomina e **email di
    contatto**, su carta intestata e con data di stampa; scelta degli organi e dell'eventuale
    sezione, per l'uso interno (i recapiti sono dati personali: stampa riservata ai ruoli che
    gestiscono gli organi).
- ✅ **Decadenza anticipata degli organi e commissariamento** (1.0.83): decadono consiglio e sindaci, commissario (o, fino alla nomina, il presidente decaduto come commissario provvisorio) che firma, rinnovo straordinario entro dodici mesi prorogabili.
- ✅ **Conformità al Regolamento ANCR** (1.0.83): registro dei votanti e deleghe, commissione elettorale, schede di peso, adempimenti, supplenti, prima riunione, cooptazioni, determinazioni e relazione del commissario, commissario amministrativo.
- ✅ **Rinnovo degli organi a scadenza del mandato** (1.0.83, modulo `apps/elezioni`; sezioni e federazione, compilazione delle liste, esiti senza spoglio guidato, avviso senza blocco del tesseramento): la procedura elettorale guidata, dalla
  scadenza alla proclamazione, con i termini calcolati dal programma.
  - *Fasi e termini dell'ANCR* (Statuto artt. 46-47, Regolamento applicativo art. 22 «Sezioni:
    procedure e modalità di votazione»), da usare come profilo predefinito per le sezioni:
    1. **indizione** del Congresso sezionale da parte del Consiglio direttivo uscente almeno **due
       mesi prima** della scadenza quadriennale (sede, ordine del giorno, termine e modalità per le
       liste); l'elettorato è dei soci tesserati **prima dell'invio dell'avviso** e il tesseramento si
       sospende dalla convocazione;
    2. **convocazione** con avvisi personali, lettera/email o bacheca almeno **otto giorni prima**:
       luogo, data e ora, seconda convocazione ad almeno un'ora, giorno delle elezioni, seggio e orari;
    3. **presentazione delle liste** entro **15 giorni prima** del Congresso: candidati soci in regola,
       una sola lista per candidato, incarico indicato accanto a ogni nome; composizione per soglia di
       soci (fino a 100: Presidente, Vice, Segretario, Sindaco controllore; oltre 100: anche quattro
       consiglieri, Collegio dei sindaci e Collegio dei garanti di tre membri); fino a **quattro
       supplenti**; verifica e ammissione delle liste da parte del Consiglio uscente, con i motivi
       delle esclusioni;
    4. **votazione**: voto alla lista (nomi non modificabili), alzata di mano con lista unica,
       scrutinio segreto con più liste e Commissione elettorale (presidente e due componenti), fino a
       **due deleghe** per socio, elenco degli aventi diritto dal presidente uscente;
    5. **proclamazione e verbali** con i modelli del Regolamento (B2 commissione elettorale, C2/C3
       elezione, D2 proclamazione, D4 delega), **ricorsi** al Consiglio provinciale entro **15 giorni**,
       trasmissione dei verbali alla Federazione entro **10 giorni**, non accettazione della carica
       entro la prima convocazione del nuovo Consiglio (subentrano i supplenti);
    6. **insediamento**: nomina delle cariche negli organi dalla lista eletta e **passaggio di
       consegne** entro **10 giorni** (modello G1), con il verbale inviato alla Federazione.
  - *Generalizzazione per altre associazioni*: un **profilo elettorale** per tipo di organo, modificabile
    in *Organi sociali*, con i termini in giorni/mesi rispetto alla scadenza o al congresso (indizione,
    avviso, liste, ricorsi, trasmissione, consegne), le regole delle liste (composizione per soglia di
    soci, supplenti, una lista per candidato), le modalità di voto (alzata di mano/scrutinio, deleghe) e
    i **modelli** come modelli di stampa con segnaposto (`apps/documenti`), così che ogni statuto si
    traduca in configurazione senza toccare il codice. Il profilo ANCR resta come preimpostato;
    gli altri partono da un profilo generico (ETS: assemblea che elegge il consiglio).
  - *Nel programma*: scadenzario e cruscotto con le date di ogni fase (già c'è la scadenza dei
    mandati), convocazione dal modello e invio con Comunicazioni (protocollata), registro delle liste
    presentate con data di arrivo e esito dell'ammissione, elenco degli aventi diritto alla data
    dell'avviso, verbali precompilati, nomina automatica delle nuove cariche e chiusura delle vecchie,
    verbale di passaggio di consegne.
- ✅ **Preimpostazioni dei fornitori di posta** (1.0.83; più i fornitori personalizzati degli amministratori; Register.it escluso: parametri non verificati). In *Sistema → Servizi di posta*, creando una
  casella (IMAP) o un servizio di invio (SMTP), un menu **«Fornitore»** compila da solo server,
  porta, cifratura (SSL/STARTTLS), nome utente (di norma l'indirizzo) e cartelle tipiche, lasciando da
  scrivere solo indirizzo e password; tutto resta modificabile. Fornitori iniziali, email e PEC dove
  previsto: **Aruba** (email `imaps.aruba.it`/`smtps.aruba.it`, PEC `imaps.pec.aruba.it`/
  `smtps.pec.aruba.it`), **Register.it**, **Legalmail (InfoCert)**, **Poste PEC**, **Libero/Virgilio**,
  **Tiscali**, **TIM/Alice**, **Gmail** e **Microsoft 365/Outlook** (con le note su password per le app
  e accesso moderno), più «Altro» per i valori a mano. L'elenco sta in un file di dati del programma
  (facile da aggiornare o estendere da chi installa), la scelta del fornitore segna anche *È una PEC*
  e la verifica di accesso si può lanciare subito dopo. Stessa facilità nella configurazione guidata.
- ✅ **Comunicazioni della campagna tessere riconoscibili** (1.0.82). Gli invii generati dalla campagna
  (avvisi, solleciti, ordini) hanno oggetti tutti uguali («Tesseramento 2027: quota e richiesta delle
  tessere»), quindi nell'elenco delle *Comunicazioni* non si capisce a quale sezione o soggetto vanno.
  L'oggetto si personalizza con il destinatario (es. «… – Sezione di Ruoti», segnaposto `{{ sezione }}`
  nei modelli del tesseramento) e l'elenco mostra comunque la colonna del destinatario (o «N
  destinatari») e il filtro per origine (campagna, anno, sezione), anche per gli invii già fatti.
