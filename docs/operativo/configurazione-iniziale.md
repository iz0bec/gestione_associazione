<!--
******************************************************
* Progetto:    Gestione Associazione
* Autore:      Bartolomeo Santoro aka IZ0BEC
* Email:       info@iz0bec.info
* Descrizione: Configurazione iniziale guidata e riepilogo delle informazioni da preparare
* Licenza:     CC0 1.0 Universal (pubblico dominio)
* SPDX-License-Identifier: CC0-1.0
******************************************************
-->

# Configurazione iniziale

Al primo accesso l'amministratore viene accompagnato dalla **configurazione guidata**. Sono sei
passi; ognuno salva subito i dati, quindi si può interrompere e riprendere. Ogni passo si può
anche **saltare** e completare dopo. La configurazione si può rifare quando serve da
**Sistema → Configurazione guidata**: i dati già inseriti compaiono già compilati.

Prima di iniziare conviene raccogliere le informazioni elencate qui sotto. Bastano 15 minuti
se si ha tutto a portata di mano.

## Cosa preparare

### 1. Dati dell'ente

| Dato | Obbligatorio | Dove si trova | Dove si usa |
|---|---|---|---|
| Denominazione completa | sì | statuto, atto costitutivo | intestazione di documenti, ricevute, email |
| Denominazione breve | no | es. «ANCR Avigliano» | menu, titolo delle pagine |
| Codice fiscale | consigliato | certificato di attribuzione dell'Agenzia delle Entrate | ricevute delle quote, rendiconto |
| Partita IVA | solo se ne ha una | | intestazioni |
| Iscrizione al RUNTS | se iscritta | numero di repertorio | intestazioni, rendiconto |
| Indirizzo della sede, CAP, comune, provincia | consigliato | | intestazioni, lettere |
| Telefono, email, PEC | consigliati | | intestazioni, pagine pubbliche, risposte alle email |
| Sito web | no | | pagine pubbliche |

### 2. Logo e colori

| Dato | Note |
|---|---|
| Logo | file PNG o JPEG, meglio **quadrato** e con **sfondo trasparente**, almeno 512×512 pixel. Viene ridotto e ripulito dai dati nascosti. Non si accettano SVG. |
| Colore principale | codice del colore istituzionale (es. `#1d4e89`). Si sceglie anche dalla tavolozza. Il colore del testo sui pulsanti, bianco o scuro, viene scelto in automatico per restare leggibile. |
| Menu laterale | scuro, chiaro o nel colore principale |

Logo e colore compaiono nel menu e nella pagina di accesso, nelle pagine pubbliche (domanda di
iscrizione, schede dei cimeli), come icona del browser e nell'intestazione di tutti i PDF.

### 3. Sezioni

Si sceglie com'è organizzata l'associazione:

- **Un'unica associazione** (o una sola sezione). Servono il **codice** della sezione nel registro
  nazionale (es. `085`) e il suo **nome**. Con una sola sezione la scelta della sezione non compare
  mai nei moduli.
- **Una federazione con più sezioni**. Serve l'elenco delle sezioni, una per riga, nella forma
  `codice; nome; comune; provincia`. Comune e provincia sono facoltativi. Esempio:

  ```
  085; Sezione di Avigliano; Avigliano; PZ
  086; Sezione di Potenza; Potenza; PZ
  ```

  Le sezioni si possono aggiungere anche dopo (**Sistema → Sezioni**). Si possono anche creare in
  automatico con l'[importazione dei soci](soci.md#importare-dal-registro-nazionale).

In una federazione soci e tessere fisiche appartengono a una sezione. A ogni utente si possono
assegnare una o più sezioni: vedrà e gestirà solo quelle. Protocollo, organi, tesoreria e
patrimonio restano unici dell'ente che usa l'applicazione.

### 4. Tesseramento

| Dato | Esempio | Note |
|---|---|---|
| Anno del tesseramento | 2026 | di solito l'anno in corso |
| Costo d'acquisto per tessera | 3,50 € | quanto si paga alla **sede centrale** per ogni tessera fisica |
| Quota annuale per ogni tipologia di socio | Ordinario 25 €, Sostenitore 50 €, Onorario 0 € | prezzo di distribuzione: quanto paga il **socio**; 0 = esente |

Le tipologie predefinite si possono rinominare o integrare da **Tesseramento → Tipologie**. Costi
e quote si rivedono ogni anno: all'apertura di un nuovo esercizio il listino viene copiato
dall'anno precedente e va confermato (vedi [Listino del tesseramento](soci.md#listino-del-tesseramento)).

### 5. Tesoreria

| Dato | Note |
|---|---|
| Primo esercizio da gestire | l'anno da cui si inizia a registrare la prima nota |
| Saldo della **cassa contanti** a inizio esercizio | contare il contante al 1° gennaio (o alla data di partenza) |
| Saldo del **conto bancario** a inizio esercizio | dall'estratto conto al 31 dicembre precedente |
| IBAN del conto | facoltativo, compare nei documenti |

Altri conti (postale, carta prepagata) si aggiungono in **Tesoreria → Conti**. Dal secondo esercizio
i saldi iniziali si riportano da soli alla chiusura.

### 6. Riepilogo

Mostra tutto ciò che è stato inserito e segnala cosa manca. Con **Concludi la configurazione** si
arriva al cruscotto. Il riepilogo ricorda anche le attività successive.

## Dopo la configurazione

1. **Operatori**: creare gli account di segretario, tesoriere, ecc. e assegnare i
   [ruoli](ruoli.md) e, in una federazione, le sezioni.
2. **Soci**: [importarli dal registro nazionale](soci.md#importare-dal-registro-nazionale), oppure
   iscriverli uno per uno.
3. **Tessere**: [caricare i lotti](soci.md#tessere-dalla-sede-centrale) ricevuti dalla sede
   centrale e attribuirle.
4. **Posta**: collegare le caselle email e PEC da cui protocollare (**Protocollo → Caselle**).
5. Con l'amministratore di sistema verificare i parametri del file `.env`: invio delle email
   (`EMAIL_*`) e indirizzo pubblico (`URL_PUBBLICO`) per i QR dei cimeli (vedi
   [Configurazione](../sistema/configurazione.md)).
