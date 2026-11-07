<!--
******************************************************
* Progetto:    Gestione Associazione
* Autore:      Bartolomeo Santoro aka IZ0BEC
* Email:       info@iz0bec.info
* Descrizione: Manuale operativo del modulo Patrimonio
* Licenza:     CC0 1.0 Universal (pubblico dominio)
* SPDX-License-Identifier: CC0-1.0
******************************************************
-->

# Patrimonio

L'inventario dei beni dell'associazione: bandiere e labari, cimeli, medaglie, documenti, arredi,
attrezzature. Ogni bene ha un **numero di inventario** progressivo (es. `INV 00012`) che non si riusa mai.

## Inserire un bene

**Patrimonio → Nuovo bene**:

- nome, **categoria**, descrizione, **quantità** (per oggetti uguali, es. 12 medaglie), **ubicazione**,
  stato di conservazione;
- **provenienza**: modalità (acquisto, donazione, lascito, comodato, rinvenimento), data, donatore o
  fornitore, documento (fattura, atto di donazione, verbale), valore di acquisizione;
- **numero di inventario precedente**, se il bene era già in un registro cartaceo;
- **foto**: viene ridimensionata e privata dei dati nascosti (posizione GPS, modello del telefono).

Le categorie si adattano da *Altro → Categorie*.

## Valore e valutazioni

Il valore iniziale è quello di acquisizione. **Valutazione** registra una nuova stima (stima interna,
perizia, valore assicurato, valore di mercato) con data e note: il valore attuale diventa quello della
valutazione più recente. Lo storico resta nella scheda del bene. Per i beni in più pezzi il valore è per
pezzo; nell'inventario compare il totale.

## Prestiti e uscite

**Prestito o uscita**:

- **prestito** a una persona o a un ente (es. una bandiera per una mostra del Comune): motivo, condizioni,
  restituzione prevista. Il bene risulta *in prestito*; i prestiti scaduti sono segnalati in cima
  all'inventario. Al rientro, **Restituzione** con la data e le condizioni (integro o danneggiato).
- **uscite definitive**: donazione ad altri, vendita (con l'importo, da registrare anche in tesoreria),
  restituzione al proprietario di un bene in comodato, dismissione o distruzione, smarrimento o furto.

I beni usciti **non si cancellano**: restano nell'inventario come «usciti», con la loro storia (filtro
*Stato*).

## Scheda pubblica e QR

Per i cimeli esposti in sede o durante le mostre: nella modifica del bene attivare **scheda pubblica** e
scrivere il **testo pubblico** (storia, provenienza, significato). Facoltativamente si mostra la foto.

Chi inquadra il QR vede **solo** nome, categoria, numero di inventario, testo pubblico ed eventuale foto,
con il nome dell'associazione: **mai valore, ubicazione, donatore o note**. L'indirizzo contiene un codice
casuale che non si può indovinare; disattivando la scheda pubblica il QR smette di funzionare.

**Altro → Etichette con QR**: foglio A4 di etichette (con il QR per i beni con scheda pubblica, solo il
numero per gli altri) da stampare e applicare.

## Stampe

- **Stampa l'inventario**: PDF per categoria con quantità, ubicazione, conservazione, acquisizione, stato
  e valore, con il totale. Rispetta i filtri dell'elenco.
- **Esporta CSV** per elaborazioni con un foglio di calcolo.

## Passaggio di consegne

Quando cambia il responsabile del patrimonio (es. nuovo presidente o consiglio):
**Altro → Passaggi di consegne → Nuovo passaggio**:

1. controllare l'elenco dei beni che vengono consegnati (quelli in dotazione e in prestito);
2. indicare data, chi consegna e chi riceve con il loro ruolo, eventuali **osservazioni** (beni mancanti o
   danneggiati riscontrati);
3. **Registra e genera il verbale**: viene creato il PDF con l'elenco completo e lo spazio per le firme, con
   la sua impronta; se scelto, viene protocollato (protocollo interno).

Il passaggio conserva l'elenco **com'era quel giorno**: le modifiche successive all'inventario non lo
cambiano. Non si modifica né si cancella.
