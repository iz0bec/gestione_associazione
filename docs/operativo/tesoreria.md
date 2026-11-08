<!--
******************************************************
* Progetto:    Gestione Associazione
* Autore:      Bartolomeo Santoro aka IZ0BEC
* Email:       info@iz0bec.info
* Descrizione: Manuale operativo del modulo Tesoreria
* Licenza:     CC0 1.0 Universal (pubblico dominio)
* SPDX-License-Identifier: CC0-1.0
******************************************************
-->

# Tesoreria

La tesoreria segue il **principio di cassa**: si registrano le entrate e le uscite quando il denaro
entra o esce davvero. A fine anno produce il **rendiconto per cassa** degli Enti del Terzo Settore
(Modello D, D.M. 5 marzo 2020), previsto per gli enti con entrate inferiori a 220.000 euro.

## Prima volta

1. **Tesoreria → Impostazioni → Conti**: sono già presenti *Cassa* (usata per le quote in contanti) e
   *Banca* (per bonifici e POS). Rinominarli, aggiungere l'IBAN o altri conti (es. conto postale).
2. **Apri l'esercizio** dell'anno.
3. Inserire i **saldi iniziali** al 1° gennaio di ogni conto (solo nel primo esercizio: poi sono riportati
   automaticamente alla chiusura).
4. Facoltativo: **Preventivo** e **sottovoci** del piano dei conti.

## Il cruscotto

![Il cruscotto della tesoreria](immagini/tesoreria.jpg)

Per l'esercizio scelto mostra entrate, uscite, avanzo o disavanzo, i **saldi** di ogni conto, gli ultimi
movimenti e il confronto con il preventivo. Un avviso segnala le quote incassate non ancora in prima nota.

## Prima nota

**+ Entrata**, **− Uscita** o **Movimento**:

- **tipo**: entrata, uscita o **giroconto** (spostamento tra conti, ad esempio il versamento dei contanti
  in banca: non è né entrata né uscita);
- **data**, **importo**, **conto** (e, per i giroconti, il conto di destinazione);
- **voce del rendiconto** (o una sua sottovoce), **descrizione**, **controparte**, **documento**
  (es. «fattura n. 12/2026»);
- **giustificativo**: la fattura o la ricevuta in PDF o immagine, conservata con la sua impronta.

Ogni movimento riceve un numero progressivo nell'esercizio (es. `2026/0042`). Finché l'esercizio è
aperto un movimento si può correggere (ogni modifica è registrata) o **annullare** con il motivo: resta
visibile come annullato ma non conta nei saldi né nel rendiconto. I movimenti non si cancellano.

La prima nota si filtra per testo, tipo, conto, voce e periodo, con i totali dei movimenti filtrati, e si
esporta in **CSV**.

## Quote sociali

Quando si registra l'incasso di una quota (*Soci → scheda del socio* o *Tesseramento*), l'entrata va in
prima nota **automaticamente**: voce *A 1) Entrate da quote associative*, conto *Cassa* per i contanti o
*Banca* per bonifico e POS, controparte il socio, documento il numero della ricevuta. Se l'esercizio non
è aperto (o è chiuso) l'incasso resta valido e la quota compare nell'avviso del cruscotto: **Registra le
quote** la porta in prima nota.

## Piano dei conti

Le voci sono quelle ufficiali del Modello D, divise in sezioni: **A** attività di interesse generale,
**B** attività diverse, **C** raccolta fondi, **D** attività finanziarie e patrimoniali, **E** supporto
generale, più **investimenti e disinvestimenti** e **imposte**. Non si modificano.

Per il dettaglio si aggiungono **sottovoci** (*Impostazioni → Piano dei conti*). Sono già proposte, ad
esempio: *Corone, onoranze e cerimonie* (A 2 Servizi), *Tessere e bollini della sede centrale*,
*Offerte e donazioni* (A 4 Erogazioni liberali), *Spese e commissioni bancarie*. Nel rendiconto le
sottovoci confluiscono nella loro voce.

| Esempio | Voce |
|---|---|
| Quote dei soci | Entrate A 1 |
| Offerte raccolte durante una cerimonia | Entrate A 4 (o C 2 se è una raccolta fondi occasionale) |
| Contributo del Comune per il 4 Novembre | Entrate A 8 |
| 5 per mille | Entrate A 5 |
| Corona al monumento | Uscite A 2 |
| Tessere acquistate dalla sede centrale | Uscite A 1 |
| Cancelleria, spese postali | Uscite E 1, E 2 |
| Commissioni bancarie | Uscite D 1 |
| Acquisto di una bandiera, di un computer | Investimenti, uscite 1 |

## Preventivo

**Preventivo e confronto**: per ogni voce l'importo previsto, con accanto il consuntivo dell'anno
precedente, l'effettivo dell'anno e la differenza. Si modifica finché l'esercizio è aperto.

## Rendiconto

**Rendiconto per cassa (Modello D)**: le sezioni con uscite ed entrate dell'anno e dell'anno precedente,
l'avanzo o disavanzo di ogni sezione e complessivo, le imposte, gli investimenti, la cassa e i depositi
al 31 dicembre. Si stampa in **PDF** (con lo spazio per le firme di tesoriere e presidente) o si esporta
in **CSV**. Finché l'esercizio è aperto è indicato come *provvisorio*.

## Chiusura dell'esercizio

Dopo la fine dell'anno, verificati i saldi con l'estratto conto e la cassa contata, **Chiudi l'esercizio**
(con gli estremi dell'approvazione, se già avvenuta):

- i saldi finali sono fissati e **riportati** come iniziali dell'anno successivo (che viene aperto, se
  non esiste);
- i movimenti dell'anno non si possono più modificare.

Se serve una correzione, **Riapri** (solo il tesoriere o l'amministratore, con il motivo); alla nuova
chiusura i saldi riportati si aggiornano.
