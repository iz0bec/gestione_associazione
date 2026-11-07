<!--
******************************************************
* Progetto:    Gestione Associazione
* Autore:      Bartolomeo Santoro aka IZ0BEC
* Email:       info@iz0bec.info
* Descrizione: Analisi dei progetti di origine, finalità e perimetro funzionale
* Licenza:     CC0 1.0 Universal (pubblico dominio)
* SPDX-License-Identifier: CC0-1.0
******************************************************
-->

# Analisi e finalità

## 1. Progetti di origine

Gestione Associazione nasce dall'unione di tre applicazioni in uso presso una sezione ANCR
(Associazione Nazionale Combattenti e Reduci), sviluppate separatamente e oggi in esercizio
sullo stesso server.

| | Protocollo ANCR | Gestione Soci | Gestione Assemblee |
|---|---|---|---|
| Repository | `Protocollo_ANCR` | `Gestione_Soci_v0` | `ANCR` (cartella locale `ANCR - Assemblee`) |
| Tecnologia | Node.js, Express, EJS, Sequelize, PostgreSQL | Python, Flask, SQLAlchemy, SQLite | Python, Flask, SQLAlchemy, SQLite |
| Dimensione | ~9.000 righe in 11 controller | `app.py` da ~190 KB + moduli | `app.py` da ~3.900 righe |
| Ruoli | admin, responsabile, protocollatore | admin, segretario, operatore | admin, presidente, vicepresidente, segretario |

### 1.1 Protocollo ANCR

- Registro di protocollo in entrata, uscita e interno, numerazione annuale `AAAA-NNNNN`, annullamento.
- Allegati ai protocolli; invio del protocollo via email ai destinatari.
- Rubrica contatti (persone ed enti) con import/export CSV; liste di distribuzione (lista "Soci" automatica).
- Caselle email IMAP/POP3: le email ricevute si protocollano con un clic.
- Registri giornalieri, settimanali e mensili in PDF.
- API REST con token (usata dall'app Assemblee per protocollare verbali e comunicazioni).
- Configurazioni, modelli email, voci di menu personalizzate.

### 1.2 Gestione Soci

- Anagrafica soci con calcolo del codice fiscale, foto, sezione, anno di iscrizione.
- Tessere annuali: numero, quota, rinnovo singolo e massivo, ricevute PDF via email.
- Modulo di iscrizione pubblico con CAPTCHA e notifica; "Allegato A" (domanda di iscrizione) in PDF.
- Tesoreria: anni contabili con apertura/chiusura e riporto saldi, prima nota (movimenti),
  bilancio previsionale, consuntivo e libro giornale in PDF, sincronizzazione quote tessere.
- Patrimonio: beni inventariati, valutazioni, cessioni/prestiti/donazioni con restituzione,
  passaggio di consegne con fotografia immutabile del patrimonio, schede QR pubbliche dei beni.
- Email ai soci (singole, multiple, auguri di compleanno), export CSV/Excel, export rubrica
  verso Protocollo e Assemblee.

### 1.3 Gestione Assemblee

- Organi sociali: riunioni del direttivo e assemblee dei soci con prima e seconda convocazione e ordine del giorno.
- Verbali strutturati (presenti, presidente e segretario, punti discussi, decisioni e votazioni, provvedimenti) in PDF.
- Rubrica per categorie: soci, autorità, amici della sezione, altre associazioni, sezioni consorelle; consenso privacy.
- Comunicazioni email con modelli (auguri, compleanni, inviti) e segnaposto.
- Protocollazione automatica di convocazioni, verbali e comunicazioni tramite l'API del Protocollo.
- Dati dell'organizzazione (denominazione, sede, CF, PEC, logo, informativa privacy).

## 2. Punti in comune e duplicazioni

| Elemento | Dove compare oggi | Problema | Nell'applicazione unica |
|---|---|---|---|
| Utenti, login, ruoli | 3 volte, 3 modelli di ruolo diversi | 3 account per persona, password e permessi non coerenti | Un solo account, ruoli per funzione (vedi §4) |
| Persone ed enti | `Contatto` (Protocollo), `Contatto` (Assemblee), `Socio` (Soci) | Stessa persona in 3 archivi, allineati a mano con export CSV | **Anagrafica unica**: un soggetto, più ruoli (socio, autorità, fornitore, ...) |
| Liste di destinatari | liste (Protocollo), categorie (Assemblee), filtri soci (Soci) | Logiche diverse | Liste statiche e dinamiche (es. "soci in regola 2026") |
| Invio email e modelli | 3 implementazioni SMTP e 3 sistemi di modelli | Configurazione SMTP triplicata | Un solo servizio di comunicazioni con coda e registro invii |
| Numerazioni | protocollo, tessere, inventario, cessioni | Ogni app ha la sua logica (nel Protocollo con errori di concorrenza) | **Sequenze** centralizzate, annuali, atomiche |
| Protocollazione | API HTTP tra Assemblee e Protocollo | Integrazione fragile, token in chiaro | Chiamata interna: ogni documento può essere protocollato direttamente |
| Generazione PDF | ReportLab (Soci, Assemblee), PDFKit (Protocollo) | Layout scritti in codice, difficili da modificare | Modelli HTML + CSS stampati in PDF, con intestazione unica dell'ente |
| Dati dell'ente | Assemblee (completi), Protocollo (parziali), Soci (`.env`) | Intestazioni diverse | Una sola scheda Organizzazione |
| Privacy | campo consenso (Assemblee), testo GDPR nelle email (Soci) | Nessun registro dei consensi | Consensi con data, finalità e base giuridica; esercizio dei diritti |

## 3. Finalità

L'applicazione è il **gestionale unico di un'associazione**, pensato per una sezione ANCR ma
utilizzabile da qualunque associazione o Ente del Terzo Settore (ETS) di piccole dimensioni.

Finalità, in ordine di importanza:

1. **Tenere i libri e i registri dell'associazione** in modo ordinato e verificabile:
   libro soci, registro di protocollo, libri dei verbali di assemblea e consiglio,
   prima nota e rendiconto, inventario dei beni.
2. **Gestire la vita associativa**: iscrizioni, tesseramento e quote, convocazioni, verbali,
   delibere, cariche sociali.
3. **Comunicare** con soci, autorità e altre associazioni, conservando traccia di ciò che si invia e riceve.
4. **Rendere conto** a soci, revisori e controlli esterni (RUNTS, autorità): documenti ufficiali,
   storicizzazione, passaggi di consegne.
5. **Proteggere i dati personali** dei soci (GDPR) e garantire continuità quando cambiano le cariche.

## 4. Perimetro funzionale (moduli)

| Modulo | Contenuto | Da |
|---|---|---|
| **Organizzazione** | dati dell'ente, sedi, logo, cariche sociali in corso, impostazioni | Assemblee + nuovo |
| **Utenti e accessi** | account, ruoli, autenticazione a due fattori, registro accessi | tutti |
| **Anagrafica** | persone fisiche ed enti, categorie, recapiti, consensi privacy, liste | tutti |
| **Soci** | libro soci, domande di iscrizione (pubbliche), tesseramento, quote, ricevute | Soci |
| **Protocollo** | registro, allegati, annullamento, registri giornalieri, ricezione email/PEC | Protocollo |
| **Organi sociali** | organi, riunioni, convocazioni, presenze, verbali, delibere, libri verbali | Assemblee |
| **Comunicazioni** | modelli, invii singoli e massivi, auguri automatici, registro invii | tutti |
| **Tesoreria** | esercizi, conti (cassa/banca), prima nota, previsionale, rendiconto, chiusure | Soci |
| **Patrimonio** | inventario, valutazioni, prestiti e cessioni, passaggio consegne, schede QR | Soci |
| **Documenti** (trasversale) | allegati con controllo accessi, modelli di stampa, archivio | nuovo |

Ruoli proposti (configurabili): **Amministratore di sistema**, **Presidente**, **Segretario**,
**Tesoriere**, **Addetto protocollo**, **Consigliere** (consultazione), **Revisore** (sola lettura
di tesoreria e verbali). Un utente può avere più ruoli.

## 5. Funzionalità nuove proposte

Non presenti nei progetti di origine, ordinate per utilità stimata.

**Conformità e tutela**
- Libri sociali previsti dal Codice del Terzo Settore (art. 15 D.Lgs. 117/2017): libro soci,
  libro verbali assemblee, libro verbali consiglio, stampabili con numerazione pagine.
- Rendiconto per cassa secondo il **Modello D** (DM 5 marzo 2020), per gli ETS con entrate sotto
  la soglia dell'art. 13 del Codice del Terzo Settore (da verificare con il commercialista al momento dell'uso).
- Registro dei consensi GDPR, esportazione dei dati di una persona, cancellazione/anonimizzazione,
  termini di conservazione.
- Registro delle attività (audit) consultabile: chi ha visto o modificato cosa e quando.
- Protocollo non modificabile dopo la registrazione (solo annullamento motivato), come richiesto dal DPR 445/2000.

**Vita associativa**
- Scadenzario e calendario: assemblee, rinnovi, ricorrenze e cerimonie (oggi in fogli separati: `calendari_ANCR`).
- Eventi e cerimonie con partecipanti e adesioni.
- Promemoria automatici per il rinnovo della quota; elenco morosi.
- Cariche sociali con storico (chi è stato presidente, quando) e scadenze dei mandati.
- Area personale del socio (fase successiva): tessera digitale con QR verificabile, dati, quote pagate.

**Operatività**
- Ricerca globale (persone, protocolli, verbali, beni).
- Import guidato dai tre gestionali attuali (migrazione dati senza perdite).
- Backup automatici del database e degli allegati, con verifica del ripristino.
- Pagamenti delle quote tracciati in tesoreria (contanti, bonifico, POS), con ricevuta numerata.

## 6. Problemi dei progetti di origine da non ripetere

Dalle analisi dei tre progetti:

- numerazioni calcolate con "ultimo + 1" senza transazione (duplicati e buchi);
- contenuti esterni (email, URL) inseriti nelle pagine senza neutralizzazione (XSS);
- allegati pubblicamente accessibili;
- nessuna protezione CSRF, nessun limite ai tentativi di login;
- password e token in chiaro nel database o nel codice;
- schema del database modificato all'avvio (`sync`) invece che con migrazioni versionate;
- file di codice da migliaia di righe, logica nelle viste, nessun test automatico.

Le contromisure sono descritte in [Sicurezza](../sistema/sicurezza.md) e nelle
[decisioni di architettura](../architettura/decisioni.md).
