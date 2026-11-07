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
| **0.0.1 RC** | tutti i moduli di base utilizzabili, import dai tre gestionali attuali, installazione Docker e su host | GitLab personale |
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
   collegamento degli incassi alla prima nota (con Tesoreria), foto del socio.
2. **Protocollo** - registro in entrata/uscita/interno (numerazione annuale), allegati privati,
   annullamento motivato, registro giornaliero PDF, ricezione email/PEC da protocollare.
3. **Organi sociali** - organi, riunioni con 1ª/2ª convocazione e ordine del giorno, presenze dai
   soci, verbali con delibere e votazioni, PDF, protocollazione automatica, libri dei verbali.
4. **Comunicazioni** - modelli con segnaposto, invii a persone/categorie/liste, coda di invio in
   background, registro invii, auguri di compleanno automatici (rispettando consensi e decessi).
5. **Tesoreria** - esercizi, conti cassa/banca, prima nota, previsionale, rendiconto (Modello D),
   chiusura e riapertura con riporto saldi, collegamento con le quote.
6. **Patrimonio** - inventario numerato, valutazioni, prestiti/cessioni/donazioni e restituzioni,
   passaggio di consegne con fotografia immutabile, schede QR pubbliche (dati minimi).
7. **Documenti PDF** - modelli di stampa HTML con intestazione dell'ente (WeasyPrint).
8. **Import** - comandi di importazione da Protocollo ANCR (PostgreSQL), Gestione Soci e Gestione
   Assemblee (SQLite), con deduplica dell'anagrafica per codice fiscale/email e rapporto finale.
9. **Installazione su host** - script per Debian/Ubuntu/RHEL con systemd (come per il Protocollo).
10. **Gestione utenti dall'interfaccia** - creazione, ruoli, reimpostazione, MFA obbligatoria per ruolo.

## Fase 2 - Dopo la RC (proposte)

- Scadenzario e calendario (assemblee, rinnovi, ricorrenze, cerimonie) con esportazione iCal.
- Eventi e cerimonie con adesioni.
- Cariche sociali con storico e scadenza dei mandati.
- Area personale del socio: tessera digitale con QR verificabile, dati e quote.
- Tessera stampabile (formato card) con QR di verifica.
- Promemoria automatici di rinnovo ai soci non in regola.
- GDPR: esportazione dati di una persona, anonimizzazione, termini di conservazione automatici.
- Backup automatici cifrati con verifica del ripristino.
- Ricerca globale (persone, protocolli, verbali, beni) con ricerca testuale PostgreSQL.
- API REST con token con scadenza e permessi limitati (per integrazioni esterne).
- Pagamenti delle quote tracciati (contanti, bonifico, POS) con ricevuta numerata.
