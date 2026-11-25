<!--
******************************************************
* Progetto:    Gestione Associazione
* Autore:      Bartolomeo Santoro aka IZ0BEC
* Email:       info@iz0bec.info
* Descrizione: Analisi e roadmap del modulo Progetti: dall'idea al rendiconto, progetti
*              finalizzati agli scopi statutari, bandi, piano economico, volontariato
* Licenza:     CC0 1.0 Universal (pubblico dominio)
* SPDX-License-Identifier: CC0-1.0
******************************************************
-->

# Modulo Progetti: analisi e roadmap

## Perché

Un'associazione realizza i propri **scopi statutari** soprattutto attraverso progetti: una mostra
sui Caduti con le scuole, il restauro di un monumento, un viaggio della memoria, un servizio di
assistenza ai soci anziani. Quasi sempre servono **risorse esterne** (bandi di Regione, Comuni,
fondazioni, ministeri, sponsor), che chiedono una **progettazione** coerente, un **piano economico**,
molti **documenti** e, alla fine, un **rendiconto** con i giustificativi.

Oggi tutto questo vive in cartelle e fogli di calcolo. Il modulo segue il progetto **dall'idea al
rendiconto**, riusando ciò che il gestionale già fa: delibere (Organi sociali), protocollo e PEC,
prima nota (Tesoreria), modelli di stampa (Documenti), calendario, anagrafica.

## Decisioni (25/11/2026)

| Tema | Scelta |
|---|---|
| Chi propone le idee | **utenti e organi**, che raccolgono anche **sollecitazioni esterne** (un ente, un cittadino, una lettera protocollata): la fonte resta annotata |
| Tesoreria | **centro di costo completo**: budget per voce, ogni movimento di prima nota imputabile al progetto, preventivo/consuntivo, rendiconto per il finanziatore |
| Rete | **ogni installazione per sé**: partner (altre sezioni, enti) in anagrafica |
| Bandi | **registro manuale**, **raccolta automatica** (feed RSS/Atom, pagine web sorvegliate, portali noti preimpostati), **verifica dei requisiti**, **scrittura guidata** |
| Scrittura | **guidata, senza IA**: schemi, domande guida, testi riusabili, finalità statutarie; nessun servizio esterno |
| Volontariato | **ore registrate e valorizzate** a tariffa, conteggiate come cofinanziamento «in natura» |

## Ciclo di vita

```
idea ─► in valutazione ─► in progettazione ─► candidato ─► finanziato ─► in corso ─► in rendicontazione ─► chiuso
                 │                                  │
                 └─► accantonata                    └─► non finanziato (riproponibile)
```

Ogni passaggio di stato si registra con data, utente e motivo; quelli decisivi (avvio della
progettazione, candidatura, accettazione del contributo, chiusura) si collegano a una **delibera**
del consiglio.

## Roadmap

### P1 - Idee, necessità e progetti (fondamenta)

- **Finalità statutarie** dell'organizzazione come elenco (precompilato, modificabile): ogni idea e
  progetto indica a quali finalità risponde.
- **Idee e necessità**: titolo, descrizione, bisogno a cui risponde, destinatari, finalità, **fonte**
  (interna; esterna con l'ente o la persona in anagrafica; una lettera o email: *Protocollo → Proponi
  come idea* e *Posta da protocollare → Idea di progetto*), proponente, allegati.
- **Valutazione**: commenti, criteri semplici (coerenza con le finalità, fattibilità, costo stimato,
  urgenza, persone disponibili) con un punteggio, **priorità** decisa dal consiglio (delibera
  collegata).
- **Progetto**: nasce da un'idea; responsabile, gruppo di lavoro (utenti e volontari), stato e
  storico, scadenze nel **calendario**, documenti, registro attività.
- Permessi e ruoli (consultazione per tutti gli organi, gestione a presidenza, segreteria e
  progettisti), pagina del manuale e guida rapida.

### P2 - Bandi e finanziatori

- **Registro dei bandi**: ente finanziatore (anagrafica), titolo, collegamento, importi minimo e
  massimo, percentuale di cofinanziamento richiesta, spese ammissibili, scadenze (domanda,
  chiarimenti, avvio, conclusione, rendiconto), documenti del bando, stato (aperto, chiuso,
  candidato, esito).
- **Scadenze e avvisi**: nel calendario e per email/Telegram a chi segue il bando, giorni prima della
  scadenza.
- **Requisiti** come lista di controllo per bando, con la **verifica automatica** sui dati
  dell'organizzazione dove possibile (forma giuridica, iscrizione al RUNTS, anni di attività, sede,
  bilanci approvati, numero di soci, regolarità contributiva dichiarata) e a mano per il resto.
- **Abbinamento** bando ↔ idea o progetto, con la verifica dei requisiti e dei limiti economici.
- Dati dell'organizzazione mancanti (data di costituzione, numero e data RUNTS, ecc.) aggiunti alla
  configurazione.

### P3 - Raccolta automatica dei bandi

- **Fonti** configurabili dall'amministratore: **feed RSS/Atom**; **pagine web** da sorvegliare
  (elenco dei collegamenti nuovi in una pagina, con un'area indicata); **portali noti preimpostati**,
  da verificare insieme prima di attivarli (es. Regione Basilicata, CSV Basilicata, fondazioni,
  portali nazionali).
- **Parole chiave** e territori per filtrare; lavoro periodico (pianificatore), rieseguibile, senza
  doppioni (impronta dell'indirizzo e del titolo).
- **Proposte da vagliare**: *accetta* (diventa un bando del registro, da completare) o *scarta*;
  avviso a chi segue i bandi.

### P4 - Progettazione e candidatura

- **Quadro del progetto**: obiettivo generale e specifici, risultati attesi e **indicatori**,
  destinatari, territorio, durata.
- **Attività e cronoprogramma**: attività con responsabile, inizio e fine, dipendenze semplici;
  vista a barre (Gantt) e scadenze nel calendario.
- **Partner**: enti e sezioni dall'anagrafica, ruolo, contributo, lettere di partenariato.
- **Piano economico**: voci di costo per categoria (personale, beni, servizi, viaggi, comunicazione,
  volontariato valorizzato, spese generali in percentuale), fonti (contributo richiesto,
  cofinanziamento proprio in denaro, **in natura**, altri finanziatori), **controlli dei limiti del
  bando** (percentuali massime, cofinanziamento minimo).
- **Scrittura guidata**: per ogni sezione domande guida e schema, testi riusabili da progetti
  precedenti, finalità statutarie citate, controllo dei campi mancanti e della lunghezza richiesta
  dal bando.
- **Documenti di candidatura**: proposta e piano economico in PDF/Excel, modelli (dichiarazioni del
  legale rappresentante, lettere di partenariato) con i segnaposto del progetto, **delibera** di
  approvazione, **protocollo in uscita** e invio per PEC, ricevute agganciate.

### P5 - Esecuzione

- **Centro di costo**: ogni movimento di prima nota imputabile a un progetto e a una voce del budget;
  incassi del contributo (anticipi, saldo); **preventivo/consuntivo** per voce con gli scostamenti.
- **Volontariato**: registro delle **ore** per persona e attività, tariffa oraria di valorizzazione
  (dal bando o fissata dal consiglio), totale come cofinanziamento in natura.
- **Avanzamento**: attività completate, indicatori aggiornati, eventi collegati (Eventi), varianti
  al piano economico con la loro delibera.

### P6 - Rendicontazione e chiusura

- **Rendiconto per il finanziatore**: per voce, con i movimenti, i **giustificativi** già allegati in
  prima nota e le ore valorizzate; esportazione PDF ed Excel e **archivio ZIP** dei giustificativi.
- **Relazione finale guidata**: attività svolte, risultati e indicatori, criticità, foto e materiali.
- **Chiusura** con delibera, archivio del progetto, testi e piani riusabili per i progetti futuri.

### Trasversale (a ogni fase)

Test, pagina in `docs/operativo/progetti.md` con la voce dell'aiuto in linea, guida rapida dei ruoli
coinvolti, tabella dei permessi in `docs/operativo/ruoli.md`, CHANGELOG, manuale.

## Da chiarire più avanti

- **Tariffa del volontariato**: unica, per ruolo o per bando (molti bandi la fissano).
- **Fonti preimpostate**: quali portali usate davvero, da verificare uno per uno (formato, stabilità).
- **Requisiti verificabili**: quali dati dell'organizzazione mancano oggi per la verifica automatica.
- **Più bandi per un progetto** (cofinanziamenti incrociati): ammesso fin dall'inizio nel modello.
