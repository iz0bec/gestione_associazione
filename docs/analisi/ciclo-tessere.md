<!--
******************************************************
* Progetto:    Gestione Associazione
* Autore:      Bartolomeo Santoro aka IZ0BEC
* Email:       info@iz0bec.info
* Descrizione: Analisi del ciclo delle tessere fra ente sovraordinato, federazione e sezioni
* Licenza:     CC0 1.0 Universal (pubblico dominio)
* SPDX-License-Identifier: CC0-1.0
******************************************************
-->

# Ciclo delle tessere fra i livelli dell'associazione

*Analisi del 18/11/2026, base della fase F4 dell'API (ADR-030). Da completare con i punti aperti
in fondo.*

## Il processo reale

Le tessere sono **fisiche e numerate dalla sede nazionale**, l'ente sovraordinato. La
**federazione** fa da intermediario: raccoglie i fabbisogni delle sezioni, ordina e paga il
nazionale, riceve le tessere nel proprio **magazzino** e le **suddivide fra le sezioni** decidendo
quali numeri vanno a ciascuna. Le **sezioni** pagano la federazione e attribuiscono le tessere ai
soci.

Per un'associazione generica la figura della federazione può essere l'ente sovraordinato stesso.
Il ciclo è lo stesso con un livello in meno.

```
 Sede nazionale        emette le tessere numerate, incassa, rilascia le ricevute
     ▲ ordine, pagamento        │ lotti, ricevuta
     │                          ▼
 Federazione           raccoglie i fabbisogni, paga, tiene il magazzino, suddivide i numeri,
     ▲ richiesta, pagamento     │ consegna (lotto), ricevuta
     │                          ▼
 Sezione               attribuisce le tessere ai soci, rendiconta
```

Fatti stabiliti:

| Aspetto | Regola |
|---|---|
| Importo | la sezione paga per ogni tessera il **costo nazionale più una quota federale** |
| Quando | **misto**: in genere un acconto e un saldo, ma le regole possono cambiare da sezione a sezione |
| Tessere non usate | **restano alla sezione**: pagate comunque, a fine campagna si annullano o restano in carico come scadute; non si rendono |
| Numerazione | il nazionale consegna blocchi alla federazione, che **li suddivide** fra le sezioni |
| Soldi | i movimenti di cassa si registrano **a mano** nella prima nota di ciascuno |
| Documenti | le **ricevute si scambiano e si protocollano** regolarmente, da entrambe le parti |

## Il ciclo nel gestionale

**Principio: l'intero processo funziona anche senza interoperabilità.** Ogni passaggio si fa in ogni
installazione con le funzioni normali del gestionale:

- si stampa o si esporta il documento in PDF;
- si spedisce per email o PEC dal protocollo;
- chi riceve lo protocolla in entrata e registra a mano, oppure importa il file della consegna
  (elenco dei numeri) con anteprima.

L'API (fase F4) **non aggiunge passaggi**: consegna gli stessi documenti senza intervento e li
propone già compilati a chi li riceve. Se il collegamento manca, è sospeso o una delle due parti
non ha un'installazione propria, il ciclo continua con email, PEC e file. Si può anche passare da
una modalità all'altra a metà campagna, perché i documenti e i numeri sono gli stessi.

Il gestionale **non muove mai soldi da solo**. Fa quattro cose:

- scambia i documenti fra le installazioni e li protocolla dalle due parti;
- li collega ai movimenti di cassa;
- propone la registrazione già compilata, che il tesoriere conferma;
- tiene la quadratura per sezione e per anno.

Nella tabella, «via API» vuol dire «oppure per email/PEC dal protocollo e importazione del file».

| # | Passaggio | Da → a | Documento | Federazione | Sezione |
|---|---|---|---|---|---|
| 1 | Fabbisogno | sezione → federazione | richiesta di tessere (anno, quantità) | protocollo in entrata; entra nel fabbisogno dell'anno | protocollo in uscita |
| 2 | Ordine | federazione → nazionale | ordine aggregato, con il dettaglio per sezione | protocollo in uscita (fuori dal sistema, se il nazionale non lo usa) | - |
| 3 | Pagamento della sezione (acconto o saldo) | sezione → federazione | **ricevuta numerata della federazione** | registra l'incasso a mano ed emette la ricevuta, che parte via API | riceve la ricevuta, la protocolla in entrata e la lega al proprio movimento in uscita come giustificativo |
| 4 | Pagamento al nazionale | federazione → nazionale | ricevuta del nazionale | movimento a mano; ricevuta protocollata in entrata e usata come giustificativo | - |
| 5 | Arrivo delle tessere | nazionale → federazione | blocchi numerati | **carico nel magazzino** della federazione, ancora senza sezione | - |
| 6 | Distribuzione | federazione → sezione | **documento di consegna** con anno, serie e numeri | assegna un intervallo del magazzino alla sezione; documento protocollato in uscita | il lotto entra con fornitore «federazione» e riferimento al protocollo; la sezione **conferma la presa in carico** e protocolla in entrata |
| 7 | Uso | sezione | - | - | attribuzione ai soci (come oggi) |
| 8 | Rendiconto | sezione → federazione | numeri del tesseramento: attribuite, fuori uso, in carico | quadratura per sezione | - |
| 9 | Fine campagna | sezione | - | - | le tessere non usate si annullano o restano in carico come scadute |

### Quadratura per sezione e per anno (federazione)

| Voce | Origine |
|---|---|
| tessere consegnate | documenti di consegna (6), con presa in carico confermata |
| tessere attribuite, fuori uso, in carico | rendiconto della sezione (8), dal flusso `lotti` |
| **dovuto** | consegnate × (costo nazionale + quota federale) |
| **pagato** | ricevute emesse alla sezione (3) |
| **saldo** | dovuto − pagato |

E per la federazione verso il nazionale: tessere ricevute (5), pagato (4), saldo.

## Cosa cambia nel gestionale

- **Magazzino della federazione**:
  - un lotto può non avere ancora una sezione, quindi `LottoTessere.sezione` diventa facoltativa
    per i lotti di magazzino;
  - la distribuzione crea, per un intervallo di numeri, il lotto della sezione e segna le carte
    come consegnate;
  - ogni numero appartiene sempre a un solo lotto.
- **Listino**:
  - il `ListinoTessere` dell'anno distingue *costo nazionale* e *quota federale*;
  - nella sezione il costo per tessera ricevuto dalla federazione è la somma delle due.
- **Ricevute fra livelli**:
  - un tipo di incasso «tessere da sezione», con la ricevuta numerata della federazione (sequenza
    esistente degli incassi);
  - acconti e saldi sono incassi distinti, legati alla stessa sezione e allo stesso anno.
- **Documenti scambiabili senza API**: richiesta, documento di consegna e ricevuta hanno il PDF da
  stampare o spedire dal protocollo. La consegna ha anche un **file con i numeri** (CSV), che la
  sezione importa con anteprima per caricare il lotto senza ribatterlo.
- **Documenti scambiati via API** (fase F4, facoltativa):
  - richiesta di tessere, documento di consegna e ricevuta, ognuno con il PDF;
  - chi riceve lo trova nella posta da protocollare, già compilato, e lo protocolla con un clic;
  - il PDF della ricevuta si lega al movimento di cassa scelto o proposto.
- **Registrazioni proposte, mai automatiche**: alla ricevuta arrivata, la sezione vede «registra il
  pagamento in prima nota» con importo, voce e giustificativo già compilati.
- **Tessere non usate**: azione di fine campagna sulla sezione («annulla le non attribuite
  dell'anno» oppure «lascia in carico come scadute»), con il motivo, senza movimenti verso la
  federazione.

## Comunicazioni del ciclo (email e PEC)

Modelli di messaggio predefiniti, modificabili come gli altri in *Comunicazioni → Modelli*. Usano i
segnaposto `{{ chiave }}` e si spediscono per email o PEC dal protocollo, con la protocollazione in
uscita. Destinatari: le **direzioni delle associazioni dipendenti** (sezioni), cioè l'indirizzo
della sezione o il suo presidente.

| Modello | Quando | Contenuto | Segnaposto proposti |
|---|---|---|---|
| **Avviso di nuovo tesseramento e richiesta del fabbisogno** | apertura della campagna | annuncia il tesseramento dell'anno; comunica la **quota decisa con delibera del consiglio direttivo** (costo nazionale + quota federale), le modalità e le scadenze di pagamento (acconto/saldo); chiede il **quantitativo di tessere** entro una data | `anno`, `sezione`, `quota_tessera`, `costo_nazionale`, `quota_federale`, `delibera` (numero e data), `scadenza_richiesta`, `modalita_pagamento`, `iban` |
| **Sollecito della richiesta del fabbisogno** | dopo la scadenza, alle sezioni che non hanno ancora chiesto | richiama l'avviso (con il suo protocollo) e la nuova scadenza | come sopra + `protocollo_avviso`, `nuova_scadenza` |
| **Avviso di attribuzione delle tessere e modalità di distribuzione** | dopo la suddivisione dal magazzino | numeri attribuiti alla sezione (anno, serie, dal/al, quantità), importo dovuto e già versato, **modalità di distribuzione** (ritiro presso la sede, consegna a mano, spedizione) con luogo e date | `anno`, `sezione`, `serie`, `numero_da`, `numero_a`, `quantita`, `importo_dovuto`, `importo_versato`, `saldo`, `modalita_distribuzione`, `luogo_ritiro`, `date_ritiro`, `protocollo_consegna` |

Regole:

- La **quota** non si scrive nel messaggio a mano: viene dal listino dell'anno, che tiene il
  riferimento alla **delibera del consiglio direttivo** che l'ha decisa (organi: numero e data).
  Senza delibera collegata l'avviso segnala «[delibera da indicare]», come fa il manuale di
  gestione con i dati mancanti.
- Gli invii sono **per sezione**: un messaggio per destinatario con i dati della sua sezione, in
  coda come gli altri invii, protocollati in uscita (uno per sezione o un protocollo cumulativo, a
  scelta).
- Il **sollecito** si propone solo per le sezioni senza richiesta registrata dopo la scadenza.
- Senza interoperabilità questi messaggi *sono* il canale. Con l'API la richiesta del fabbisogno e
  la consegna arrivano anche come documenti strutturati, ma il messaggio parte comunque: resta la
  traccia formale protocollata.

## Punti aperti

1. **Pagamento misto**: l'acconto è una percentuale fissa, un importo libero o le tessere
   richieste? Quando si chiede il saldo: alla consegna, a una data o a fine campagna?
2. **Regole per sezione**: servono condizioni diverse per alcune sezioni (es. tutto anticipato)?
   Basta un'impostazione per sezione e per anno?
3. **Quota federale**: è uguale per tutte le tipologie di socio, o cambia, ad esempio per gli
   onorari?
4. **Ordine al nazionale**: serve un documento d'ordine stampabile, con il dettaglio per sezione, o
   basta il protocollo con un allegato libero?
5. ~~Sezioni senza installazione propria~~ **Deciso**: il ciclo funziona sempre anche senza
   interoperabilità. Vedi il principio all'inizio di «Il ciclo nel gestionale».
6. **Ricevute del nazionale**: arrivano per PEC o su carta? Con la PEC il protocollo le aggancia già
   alla posta in arrivo.
7. **Destinatari degli avvisi**: indirizzo della sezione (email/PEC in *Sezioni*) o il presidente in
   carica? Uno solo o entrambi?
8. **Modalità di distribuzione**: elenco fisso (ritiro in sede, consegna a mano, spedizione) o testo
   libero per ogni campagna?
