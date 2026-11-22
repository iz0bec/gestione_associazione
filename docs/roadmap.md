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
   *Da fare*: foto dei soci, passaggi di consegne e cessioni dei beni, verbali delle assemblee.
9. ✅ **Installazione su host** - `scripts/installa.sh` (Debian/Ubuntu, systemd) e
   `scripts/proxmox/crea-lxc.sh` (container LXC su Proxmox). Backup e ripristino dall'interfaccia.
   *Da fare*: RHEL/Rocky.
10. ✅ **Gestione utenti dall'interfaccia** - creazione con password temporanea, ruoli e sezioni,
   reimpostazione password, azzeramento del secondo fattore, MFA obbligatoria per ruolo.

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
  all'accoglimento con il riferimento al protocollo. *Da fare*: risposta di conferma di ricezione al
  mittente (modello di Comunicazioni). ✅ Fatta: conferma di ricezione con il numero di protocollo.
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
  lotti, cariche, numeri del tesseramento, eventi provinciali) → F5 sezione ↔ sezione
  (trasferimento del socio, eventi condivisi, verifica tessera) e kit per chi integra.
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
  - **Prossimo passo (F4)**: allineamento **automatico** dopo la prima verifica (lettura periodica
    con `sincronizza_collegamenti`), con l'ordine di tempo, l'avviso email delle incongruenze e la
    notifica alla federazione di ogni rinnovo ricevuto; spinta (`POST /consegne`) per le sezioni
    dietro NAT.
    - *Senza API*: lo scambio con file Excel resta come alternativa (interoperabilità facoltativa).
    - *Primo uso*: sezione di Potenza (CT 103, porta 8083), già abbinata alla federazione.
- ✅ Pagamenti tracciati (1.0.31): metodo e ricevuta numerata delle quote, altri incassi, storni e rimborsi, registro incassi con quadratura.
- **Inoltro della email di sezione** (da fare). Oggi la casella istituzionale di ogni sezione
  (es. `sezione.pz.sez@…`) è inoltrata dal fornitore della posta a chi la gestisce. In futuro
  l'inoltro lo governa il gestionale: per ogni sezione chi riceve i messaggi della casella (di norma
  il presidente, o l'incaricato della trattazione), con le regole cambiate dall'interfaccia e non
  più dal fornitore, nel rispetto della riservatezza (ad es. le credenziali inviate «per conto» di
  chi non ha l'email).
- **Esenzione dalla verifica in due passaggi per singolo utente** (da fare). Quando un ruolo la
  rende obbligatoria, l'amministratore può esentarne un utente che non può attivarla (niente
  smartphone né chiave di sicurezza), dalla sua scheda in *Sistema → Utenti*: con motivo e scadenza
  facoltativa, registrata nel registro attività e indicata nell'elenco degli utenti; l'esenzione non
  vale per l'Amministratore di sistema.
- **Connettore per WordPress via API** (da fare). Un plugin WordPress (licenza compatibile, CC0 o
  GPL per il solo plugin) che usa le API di interoperabilità v1 come controparte abbinata: modulo
  di domanda di iscrizione e modulo contatti sul sito che arrivano nel gestionale (`/domande`,
  `/contatti`), calendario degli eventi pubblici con adesioni (`/eventi`), organigramma e recapiti
  della sezione, verifica della tessera. Abbinamento con invito monouso, chiavi conservate da
  WordPress, nessun dato personale dei soci esposto sul sito.
- **Utenti da riga di comando** (da fare), per l'amministratore del server senza aprire l'interfaccia:
  - `manage.py utenti` elenca gli utenti dell'installazione (nome utente, persona, ruoli, attivo,
    secondo fattore, ultimo accesso, email vera o segnaposto); su un host con più installazioni
    `sezioni.sh utenti` lo fa per tutte;
  - `manage.py utenti --reimposta NOME` riporta la password a quella **predefinita del ruolo** (o a
    una generata); come **ultimo passo** il comando chiede se inviare ora l'**email personale di
    notifica** (`--invia` per rispondere sì senza domanda, `--senza-email` per non mandarla; se non
    si invia resta in bozza in *Comunicazioni*) con le credenziali, i passaggi
    per cambiarla e dove trovare il manuale; a chi non ha l'email la notifica va alla casella della
    sezione «per conto» (stessa regola di *Utenti dalle cariche*). La password non finisce mai nel
    registro attività, che annota solo l'operazione.
