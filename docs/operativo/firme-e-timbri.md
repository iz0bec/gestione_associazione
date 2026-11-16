<!--
******************************************************
* Progetto:    Gestione Associazione
* Autore:      Bartolomeo Santoro aka IZ0BEC
* Email:       info@iz0bec.info
* Descrizione: Manuale operativo: firme e timbri nelle stampe, come acquisirli e caricarli
* Licenza:     CC0 1.0 Universal (pubblico dominio)
* SPDX-License-Identifier: CC0-1.0
******************************************************
-->

# Firme e timbri

Le stampe del programma (ricevute delle quote, convocazioni, ricevute di protocollo, rendiconto,
libro soci, inventario, lettere e attestati dei *Modelli di stampa*) hanno in calce la qualifica e
il nome di chi firma. Qui si aggiungono l'**immagine della firma** di ogni persona e il **timbro**
dell'associazione e di ogni sezione. Si gestiscono in *Organi sociali → Firme e timbri*; possono
farlo l'amministratore di sistema, il presidente e il segretario per tutta la struttura, e il
**presidente di sezione** solo per la propria sezione (il timbro della sezione e le firme di chi vi
ricopre una carica; per lui la voce *Firme e timbri* è direttamente nel menu).

## Prima di cominciare

- La firma stampata è una **riproduzione grafica**, non una firma digitale né una firma autografa:
  non dà al documento un valore legale che senza non avrebbe. Per gli atti che richiedono la firma
  autografa si stampa e si firma a penna; per quelli da inviare con valore legale si usa la firma
  digitale (CAdES/PAdES) fuori dal programma.
- Si carica **solo con l'autorizzazione della persona**: chiedetela per iscritto (meglio se
  protocollata) e annotatela nel campo *Autorizzazione*. Chi lascia la carica può chiedere di
  toglierla: basta **Togli**.
- Le immagini restano sul server: non hanno un indirizzo pubblico, compaiono solo nei PDF e
  nell'anteprima di questa pagina. Ogni caricamento, sostituzione o rimozione va nel registro attività.

## Il foglio prestampato

In *Firme e timbri* ci sono due fogli A4 da stampare:

- **Foglio per la firma** (in alto, vuoto; oppure accanto a ogni persona, già intestato): sei
  riquadri da **60 × 20 mm**, le proporzioni dello spazio della firma nelle stampe (circa 56 × 17 mm),
  così la firma viene alla grandezza giusta senza essere rimpicciolita o deformata. In fondo c'è la
  **dichiarazione di autorizzazione** all'uso della riproduzione grafica, da firmare e protocollare:
  vale come autorizzazione scritta.
- **Foglio per il timbro** (accanto all'associazione o alla sezione): sei riquadri da **45 × 45 mm**.

I bordi dei riquadri sono **azzurro chiarissimo**: il programma li toglie insieme al bianco della carta.
Per avere le misure giuste il foglio va stampato **al 100%** («dimensione effettiva», non «adatta alla
pagina»): il segmento in alto deve misurare 5 cm, controllatelo con un righello.

## Come acquisire la firma

1. Stampate il foglio per la firma (o usate un foglio bianco liscio, senza righe né quadretti).
2. Firmate **dentro** alcuni riquadri, alla grandezza abituale e senza toccare i bordi, con penna a
   **inchiostro nero o blu scuro** e tratto pieno: meglio un pennarello fine o una roller che una biro
   chiara; niente matita. Fate più prove: si sceglie la migliore.
3. Acquisite il foglio con lo scanner (vedi sotto) o con il telefono.
4. Ritagliate il riquadro venuto meglio **stando appena dentro il bordo azzurro** (basta l'app Foto
   o l'anteprima del computer). Non serve precisione: il programma taglia da solo i margini vuoti;
   evitate però che restino altri segni (testo stampato, bordi del foglio, dita).

## Come acquisire il timbro

1. Stampate il foglio per il timbro e imprimete il timbro **al centro** di alcuni riquadri, con il
   tampone ben inchiostrato, premendo in modo uniforme senza muoverlo, finché l'impronta è completa e
   nitida.
2. Acquisite e ritagliate come per la firma. Se avete il **file grafico originale** del timbro (dal
   timbrificio o dal grafico) usate quello: è il risultato migliore, meglio ancora se è un **PNG con
   sfondo trasparente**.

## Impostazioni dello scanner

| Impostazione | Valore | Perché |
|---|---|---|
| Risoluzione | **300 dpi** (600 dpi per un tratto molto sottile) | una firma di 5 cm a 300 dpi è larga circa 600 pixel: stampata resta nitida. Sotto i 150 dpi si vede sgranata |
| Colore | **a colori** o **scala di grigi** | il «bianco e nero» (1 bit) rende i bordi del tratto seghettati |
| Formato | **PNG**, oppure JPEG alla qualità più alta | il JPEG molto compresso sporca il bianco intorno al tratto |
| Scala | **100%** | per mantenere le proporzioni |
| Da spegnere | OCR, «ottimizzazione testo», «documento in bianco e nero», nitidezza o contrasto automatici forti | alterano il tratto |
| Area | il foglio intero o il solo riquadro | il ritaglio si può fare dopo |

Con il **telefono** usate un'app di scansione dei documenti (ad esempio quella integrata in *Note* su
iPhone o in *Google Drive* su Android), che raddrizza il foglio e schiarisce lo sfondo; oppure una foto
dall'alto, con il foglio in piano, luce diffusa, senza ombre né flash. Inquadrate il foglio intero e poi
ritagliate: avvicinarsi troppo deforma l'immagine.

Il programma rifiuta un'immagine troppo piccola (meno di 300 pixel sul lato lungo dopo il ritaglio)
perché stampata sarebbe sgranata: in quel caso rifate la scansione a 300 dpi.

## Caricare l'immagine

1. *Organi sociali → Firme e timbri*. Nella parte **Firme** compaiono le persone in carica che firmano
   (presidente, vicepresidente, segretario, tesoriere, presidente dell'organo di controllo, dell'associazione
   e delle sezioni) e i rappresentanti legali; nella parte **Timbri** l'associazione e ogni sezione attiva.
2. Accanto alla persona o all'ente: **Carica**, scegliete il file (PNG o JPEG, al massimo 15 MB).
3. Lasciate attivo **Togli lo sfondo bianco**: il bianco del foglio diventa trasparente, così la firma
   si appoggia alla riga senza un rettangolo bianco intorno. Toglietelo solo se l'immagine è già un PNG
   con sfondo trasparente e colori chiari che non vanno persi.
4. Per una firma scrivete come la persona ha dato l'**autorizzazione** (es. «scritta del 12/11/2026,
   prot. 2026-00045»).
5. Controllate l'anteprima (la scacchiera indica le parti trasparenti) e aprite la **Stampa di prova**,
   un PDF con le firme e il timbro di oggi, come compariranno sui documenti. Per una sezione c'è il
   collegamento *Stampa di prova della sezione*.

Il programma ripulisce ogni immagine: toglie i metadati (fotocamera, posizione, data), gira le foto secondo
l'orientamento del telefono, ritaglia i margini, la ridimensiona e la salva in PNG. Se dice che «non si vede né una firma né
un timbro», l'immagine è troppo chiara: rifate la scansione con un inchiostro più scuro.

**Sostituisci** carica un'immagine nuova al posto di quella vecchia (che viene cancellata). **Non usare**
la tiene ma non la stampa più (es. durante una sostituzione); **Usa nelle stampe** la riattiva.
**Togli** la cancella.

## Firma e timbro generici

Se per qualcuno l'immagine manca, il programma usa firma e timbro **generici**. Sono **accesi in
partenza**; nel riquadro **Se manca l'immagine** (solo per chi gestisce tutta la struttura) si possono
spegnere:

- **Firma generica**: sopra la riga compare il nome di chi firma in corsivo. Se è spenta, resta lo
  spazio vuoto per firmare a penna.
- **Timbro generico**: un timbro tondo con la denominazione dell'ente lungo il bordo e, al centro, il
  comune della sede (per l'associazione) o il nome della sezione. Se è spento, senza timbro caricato
  non si stampa nessun timbro.

Le cariche vacanti restano sempre senza nome e senza firma: il programma non inventa un firmatario.
Una sezione senza timbro proprio non usa quello dell'associazione, che riporta un altro ente (vale il
timbro generico, se attivo).

## Dove compaiono

Nelle stampe con le firme in calce (vedi la tabella in [Organi sociali](organi.md)): il timbro a
sinistra delle firme, la firma di ogni persona sopra il suo nome. Si usa la firma della persona che
**era in carica alla data del documento**: ristampando un documento vecchio compare la firma di chi
firmava allora, se è ancora caricata. Nelle lettere e negli attestati dei *Modelli di stampa* la firma
è quella del presidente in carica o del rappresentante legale; un nome scritto a mano nel modello non è
collegato a una persona e riceve al più la firma generica. L'attestato solenne ha già il proprio sigillo
fra le firme e non riporta il timbro.
