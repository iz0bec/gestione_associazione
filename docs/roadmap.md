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
| 0.x | collaudo presso la sezione, correzioni, funzionalità della fase 2 | GitLab |
| **1.0** | prima release stabile, documentazione completa, Django 6.2 LTS | GitHub |

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
- [ ] Dockerfile e compose scritti, **build non ancora verificata** (Docker non disponibile durante lo sviluppo)

## Fase 1 - Moduli per la 0.0.1 RC

Ordine proposto (ognuno con test, manuale operativo e voce nel manuale di sistema):

1. ✅ **Soci e tesseramento** - libro soci, numero socio, domande di iscrizione (anche pubbliche
   con anti-spam), tessere annuali con numerazione, quote, ricevute PDF, rinnovi massivi, morosi.
   *Rimandati*: invio delle ricevute e dell'esito delle domande per email (con Comunicazioni),
   collegamento degli incassi alla prima nota (con Tesoreria), foto del socio (fatti).
2. ✅ **Protocollo** - registro in entrata/uscita/interno (numerazione annuale), allegati privati,
   annullamento motivato, registro giornaliero PDF, ricezione email/PEC da protocollare.
   *Rimandati*: invio dei protocolli in uscita per email/PEC (con Comunicazioni), liste di
   distribuzione (con Comunicazioni), API REST (fase 2), import dal Protocollo ANCR (punto 8).
3. ✅ **Organi sociali** - organi, riunioni con 1ª/2ª convocazione e ordine del giorno, presenze dai
   soci, verbali con delibere e votazioni, PDF, protocollazione automatica, libri dei verbali.
   Comprende le **cariche sociali con storico** (previste in fase 2). *Rimandati*: invio delle
   convocazioni per email (con Comunicazioni), firma digitale dei verbali, votazioni elettroniche.
4. ✅ **Comunicazioni e anniversari** - modelli con segnaposto, invii a persone/categorie/liste, coda di
   invio, registro invii, anniversari (compleanni, onomastici, ricorrenze, anzianità da socio, scomparse)
   con auguri automatici (rispettando consensi e decessi), invio di convocazioni, ricevute ed esiti.
   *Rimandati*: invio tramite PEC, SMS/messaggistica, stampa di etichette e lettere per posta.
5. ✅ **Tesoreria** - esercizi, conti cassa/banca, prima nota, previsionale, rendiconto (Modello D),
   chiusura e riapertura con riporto saldi, collegamento con le quote.
6. ✅ **Patrimonio** - inventario numerato, valutazioni, prestiti/cessioni/donazioni e restituzioni,
   passaggio di consegne con fotografia immutabile, schede QR pubbliche (dati minimi).
6b. ✅ **Configurazione e federazione** - configurazione guidata al primo accesso, aspetto
   personalizzabile (logo, colori, menu), foto in anagrafica e soci, **sezioni** con utenti limitati
   alle proprie, matricola nazionale, **listino annuale** (costo d'acquisto e quote per tipologia),
   **importazione dal registro soci nazionale** (Excel/CSV) con anteprima. *Da completare*: adattare le
   colonne all'estratto reale del registro quando disponibile (`tmp/`, non versionato).
7. ✅ **Documenti PDF** - modelli di stampa modificabili (lettere, attestati) su carta intestata,
   per una persona, una lista o una categoria, con protocollazione in uscita (`apps/documenti`).
8. ✅ **Import** - `importa_gestionale` da Gestione Soci e Gestione Assemblee (SQLite) e Protocollo
   ANCR (PostgreSQL), con anteprima, deduplica dell'anagrafica e rapporto finale.
   *Rimandati*: foto dei soci, passaggi di consegne e cessioni dei beni, verbali delle assemblee.
9. ✅ **Installazione su host** - `scripts/installa.sh` (Debian/Ubuntu, systemd) e
   `scripts/proxmox/crea-lxc.sh` (container LXC su Proxmox). Backup e ripristino dall'interfaccia.
   *Rimandati*: RHEL/Rocky.
10. ✅ **Gestione utenti dall'interfaccia** - creazione con password temporanea, ruoli e sezioni,
   reimpostazione password, azzeramento del secondo fattore, MFA obbligatoria per ruolo.

## Fase 2 - Dopo la RC (proposte)

- Scadenzario e calendario (assemblee, rinnovi, ricorrenze, cerimonie) con esportazione iCal.
  ✅ *Fatti*: prossimi impegni, vista mensile, appuntamenti e scadenze inseriti a mano,
  riquadro nel cruscotto, esportazione iCal (file e collegamento personale).
- ✅ Scambio dell'anagrafica con le rubriche (vCard): esportazione e importazione con anteprima.
- Eventi e cerimonie con adesioni.
- Cariche sociali con storico e scadenza dei mandati.
- Area personale del socio: tessera digitale con QR verificabile, dati e quote.
- Tessera stampabile (formato card) con QR di verifica.
- ✅ Promemoria automatici di rinnovo ai soci non in regola.
- GDPR: esportazione dati di una persona, anonimizzazione, termini di conservazione automatici.
- Backup automatici cifrati con verifica del ripristino.
- Ricerca globale (persone, protocolli, verbali, beni) con ricerca testuale PostgreSQL.
- API REST con token con scadenza e permessi limitati (per integrazioni esterne).
- Pagamenti delle quote tracciati (contanti, bonifico, POS) con ricevuta numerata.
