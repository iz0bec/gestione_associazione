<!--
******************************************************
* Progetto:    Gestione Associazione
* Autore:      Bartolomeo Santoro aka IZ0BEC
* Email:       info@iz0bec.info
* Descrizione: Manuale operativo del modulo Organi sociali
* Licenza:     CC0 1.0 Universal (pubblico dominio)
* SPDX-License-Identifier: CC0-1.0
******************************************************
-->

# Organi sociali

Il modulo gestisce gli **organi** dell'associazione (assemblea dei soci, consiglio direttivo, organo di
controllo), le **cariche** con il loro storico, le **riunioni** dalla convocazione al **verbale**, le
**delibere** e i **libri dei verbali**.

## Organi e regole

![Gli organi dell'associazione e delle sezioni](immagini/organi.jpg)

**Organi sociali** mostra gli organi, le prossime riunioni e quelle in preparazione. Alla prima
installazione ci sono *Assemblea dei soci*, *Consiglio direttivo* e *Collegio dei revisori*.

Le **regole** di ogni organo (pulsante *Regole*, solo amministratore) vanno allineate allo **statuto**:

| Regola | Significato | Predefinito |
|---|---|---|
| Quorum in prima convocazione | la seduta è valida se i presenti (più i rappresentati per delega) superano questa percentuale degli aventi diritto al voto | 50% = più della metà |
| Quorum in seconda convocazione | come sopra; 0 = valida con qualunque numero di presenti | assemblea 0%, consiglio 50% |
| Deleghe per persona | deleghe che un presente può ricevere; 0 = non ammesse | assemblea 3 (art. 24 CTS), altri 0 |
| Votano solo i soci in regola | per l'assemblea: votano i soci con la quota dell'anno pagata | sì |

## Cariche

![La pagina di un organo: componenti in carica con le azioni Modifica e Fine carica](immagini/organo.jpg)

**Organi dell'associazione e delle sezioni.** Ogni organo è dell'associazione (o federazione) oppure
di una **sezione** (campo *Sezione*): l'elenco li raggruppa così. L'assemblea di una sezione è formata
dai soci di quella sezione. Lo stesso socio può avere cariche in organi diversi, ad esempio
presidente della propria sezione e consigliere dell'associazione. **Nuovo organo** (Amministratore di
sistema) ne crea uno; per una sezione si fa prima con *Crea gli organi* in **Sistema → Sezioni**, che
ne prepara consiglio e assemblea.

Nella pagina di un organo (non dell'assemblea, che è formata da tutti i soci): **Nomina** con persona,
ruolo (presidente, vicepresidente, segretario, tesoriere, consigliere, componente, supplente), data di
inizio e atto di nomina. **Fine carica** registra la data di cessazione e il motivo: **da quel giorno** la persona non è più
in carica (con la data di oggi esce subito dai componenti e passa allo storico). Lo storico resta
consultabile: chi ha avuto quale carica e quando. I **supplenti** non contano tra gli aventi diritto al voto.

**Modifica** (accanto a ogni componente e a ogni riga dello storico) corregge le **date** di inizio e
di cessazione, l'atto di nomina e le note di una carica registrata male. Svuotando la data di
cessazione la persona torna in carica. Il programma impedisce una cessazione prima dell'inizio e due
cariche della stessa persona che si sovrappongono nello stesso organo (una carica può iniziare il
giorno stesso in cui finisce la precedente). Ogni modifica è annotata nel registro attività con i
valori prima e dopo; le presenze delle riunioni già aperte non cambiano.

**Firme sulle stampe.** Le cariche registrate qui firmano le stampe: in calce compaiono la qualifica,
lo spazio per la firma e il **nome di chi era in carica alla data del documento** (un verbale del
2025 porta il presidente del 2025, anche se oggi è un altro). Se la carica era vacante resta lo
spazio per la firma senza nome: il programma non inventa mai un firmatario.

| Stampa | Firme |
|---|---|
| Ricevuta della quota | tesoriere; se non c'è, presidente (alla data del pagamento) |
| Rendiconto | tesoriere (solo se c'è) e presidente |
| Libro soci, inventario, ricevuta di protocollo, dati personali (GDPR) | presidente |
| Convocazione | presidente dell'associazione o della sezione dell'organo |
| Verbale | presidente e segretario della riunione (scritti nel verbale) |
| Lettere e attestati (*Documenti*) | firmatario del modello o presidente in carica |

Contano le cariche degli organi dell'associazione (per le convocazioni di un organo di sezione,
quelle della sezione) e, fra più organi, prima l'organo di amministrazione.

**Organigramma PDF** (pulsante in alto nella pagina dell'organo): i componenti in carica alla data
di oggi, su carta intestata e in orizzontale. In alto il presidente; sotto vicepresidente, segretario
e tesoriere; poi i consiglieri, i componenti e i supplenti. Ogni scheda riporta la foto dell'anagrafica
(o le iniziali), il ruolo, il nome e la data di inizio della carica.

## Riunioni

1. **Nuova riunione**: organo, ordinaria o straordinaria, data, ora e luogo della **prima** e (facoltativa)
   della **seconda convocazione**, modalità (in presenza, mista, videoconferenza con le istruzioni di
   collegamento), **ordine del giorno** (un punto per riga) ed eventuale testo introduttivo della lettera.
2. **Convocazione**: il PDF della lettera è sempre disponibile per controllo. **Convoca** assegna il numero
   della riunione (es. *Consiglio direttivo n. 3/2026*) e, se scelto, **protocolla** la convocazione in
   uscita con la lettera e gli aventi diritto come destinatari. L'invio per email arriverà con il modulo
   Comunicazioni.
3. Fino alla chiusura del verbale si possono modificare data, luogo e ordine del giorno, o **annullare** la
   riunione con il motivo.

## Presenze

**Foglio presenze** → *Prepara l'elenco degli aventi diritto*: per l'assemblea i soci attivi alla data della
riunione (con l'indicazione di chi vota), per gli altri organi i componenti in carica. L'elenco si può
aggiornare (aggiunge solo chi manca).

Per ognuno si sceglie: presente, in collegamento, rappresentato per delega, assente giustificato, assente.
Per una **delega** si sceglie il delegato tra i presenti: il programma controlla il numero massimo di deleghe
e, se il delegato viene poi segnato assente, le sue deleghe decadono. In alto è sempre aggiornato il
**numero legale** per la prima e la seconda convocazione.

## Verbale

Dalla riunione, **Inizia il verbale**:

- **Seduta**: convocazione in cui si è svolta, apertura e chiusura, luogo, presidente e segretario (proposti
  dalle cariche in corso), constatazioni iniziali, altri intervenuti;
- **Discussione** di ogni punto all'ordine del giorno e varie ed eventuali;
- **Delibere**: punto, oggetto, dispositivo, votazione (palese, segreta, per acclamazione), unanimità o voti
  favorevoli/contrari/astenuti, esito. Il programma segnala un'approvazione con più contrari che favorevoli.

**Anteprima PDF** mostra il verbale come sarà stampato (con la scritta BOZZA), comprensivo del foglio presenze.

**Chiudi il verbale**:
- assegna il numero nel **libro dei verbali** dell'organo e numera le **delibere** (es. *CD 4/2026*);
- conserva il PDF definitivo con la sua **impronta SHA-256** e, se scelto, lo **protocolla** (protocollo interno);
- da quel momento il verbale **non si modifica più**.

Un verbale **senza numero legale** si può chiudere (seduta deserta) ma non può contenere delibere.

## Libri e registri

- **Libro dei verbali**: nella pagina di ogni organo, l'elenco dei verbali chiusi con il PDF.
- **Registro delle delibere** (*Organi sociali → Registro delibere*): tutte le delibere dei verbali chiusi,
  con ricerca nel testo e filtro per organo.
