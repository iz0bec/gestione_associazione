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
   *Da fare*: invio dei protocolli in uscita per email/PEC; API REST (fase 2).
3. ✅ **Organi sociali** - organi, riunioni con 1ª/2ª convocazione e ordine del giorno, presenze dai
   soci, verbali con delibere e votazioni, PDF, protocollazione automatica, libri dei verbali.
   Comprende le **cariche sociali con storico** (previste in fase 2). ✅ *Fatto in seguito*: invio
   delle convocazioni per email (Comunicazioni). *Da fare*: firma digitale dei verbali, votazioni
   elettroniche.
4. ✅ **Comunicazioni e anniversari** - modelli con segnaposto, invii a persone/categorie/liste, coda di
   invio, registro invii, anniversari (compleanni, onomastici, ricorrenze, anzianità da socio, scomparse)
   con auguri automatici (rispettando consensi e decessi), invio di convocazioni, ricevute ed esiti.
   *Da fare*: invio tramite PEC, SMS/messaggistica, stampa di etichette e lettere per posta.
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
  - **collegamento diretto** fra installazioni, senza file: ogni installazione espone un'API in
    sola lettura dei soci della propria sezione (HTTPS, token per installazione con scadenza e
    revoca, elenco degli indirizzi ammessi, registro di ogni richiesta); l'altra la interroga a
    orari fissi, mostra le differenze e le applica con le stesse regole dell'importazione (o dopo
    conferma). Nessun dato viaggia senza cifratura e nessuna installazione scrive nell'altra.

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
  *Da fare*: immagine della firma (caricata nella carica, servita solo ai PDF).
- ✅ **Domande di iscrizione arrivate per email** (`apps/soci/estrazione.py`): etichetta
  *iscrizione?* sulla posta, dati recuperati dal testo, dai PDF allegati (campi e testo) e dal mittente
  senza inventare nulla, avviso dei doppioni, domanda e protocollazione in entrata in un'unica
  operazione, **richiesta firmata** sulla domanda (anche per quelle a mano o online) che passa al socio
  all'accoglimento con il riferimento al protocollo. *Da fare*: risposta di conferma di ricezione al
  mittente (modello di Comunicazioni).
- Eventi e cerimonie con adesioni.
- Scadenza dei mandati delle cariche (lo storico c'è già, punto 3 della fase 1): durata per organo,
  avvisi prima della scadenza nel cruscotto e nello scadenzario.
- Area personale del socio: dati e quote (la tessera digitale con QR è già fatta, voce sotto).
- ✅ Tessera digitale (formato carta) con QR di verifica, inviata per email; verifica pubblica.
- ✅ Promemoria automatici di rinnovo ai soci non in regola.
- ✅ GDPR: esportazione dei dati di una persona, anonimizzazione, termini di conservazione.
- Backup automatici cifrati con verifica del ripristino.
- ✅ Ricerca globale (persone, soci, protocolli, riunioni, delibere, beni, appuntamenti, comunicazioni).
- API REST con token con scadenza e permessi limitati (per integrazioni esterne).
- Pagamenti delle quote tracciati (contanti, bonifico, POS) con ricevuta numerata.
