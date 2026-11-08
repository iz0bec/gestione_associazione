<!--
******************************************************
* Progetto:    Gestione Associazione
* Autore:      Bartolomeo Santoro aka IZ0BEC
* Email:       info@iz0bec.info
* Descrizione: Manuale operativo del modulo Protocollo
* Licenza:     CC0 1.0 Universal (pubblico dominio)
* SPDX-License-Identifier: CC0-1.0
******************************************************
-->

# Protocollo

Il registro di protocollo attesta **che cosa** l'associazione ha ricevuto o spedito, **quando**
e **da chi / a chi**. Ogni registrazione riceve un numero progressivo annuale (es. `2026-00042`)
e la data e l'ora di registrazione, assegnati automaticamente.

## Regole da conoscere

- Numero, data, direzione, **oggetto e corrispondenti non si modificano** dopo la registrazione.
  Se c'è un errore si **annulla** la registrazione (con il motivo) e se ne fa una nuova: il numero
  annullato resta nel registro e non viene riutilizzato.
- Si possono sempre aggiornare i dati accessori: classificazione, collegamento a un altro protocollo,
  riservatezza, note. Si possono **aggiungere** documenti, non toglierli.
- Ogni documento caricato è conservato con la sua **impronta SHA-256**: permette di dimostrare
  che il file non è stato cambiato.
- I protocolli **riservati** (es. dati sanitari o disciplinari) li vedono solo presidente, segretario
  e amministratore; ogni consultazione è registrata.

## Registrare un documento

![Il registro di protocollo](immagini/protocollo.jpg)

**Protocollo → Entrata / Uscita / ⇄ (interno)**.

1. **Direzione**: entrata (ricevuto), uscita (spedito), interno (es. comunicazione tra organi).
2. **Mezzo**: email, PEC, posta, raccomandata, a mano...
3. **Oggetto**: chiaro e completo, perché non si potrà correggere.
4. **Mittenti** (entrata) o **destinatari** (uscita): cercare nell'anagrafica scrivendo nome, ente o
   email e cliccare il risultato; compare un'etichetta (togliendo la spunta lo si esclude). Chi non è
   in anagrafica si scrive nel riquadro sotto, uno per riga: `Prefettura di Potenza <prefettura@pec.it>`
   oppure solo il nome. Per una PEC viene proposto l'indirizzo PEC del soggetto.
5. **Documento**: data del documento, numero di protocollo del mittente, data di ricezione (se diversa),
   **in risposta a** (numero come `2026-00012`), i **file** (il primo è il documento principale).
6. **Registra**: compaiono numero, data e ora.

Dalla scheda di un protocollo in entrata, **Rispondi** apre una registrazione in uscita già collegata,
con oggetto e destinatari precompilati. Dalla scheda anagrafica di un ente o di una persona si vedono i
suoi protocolli e si può registrare direttamente un'entrata o un'uscita.

**Ricevuta**: PDF con numero, data, oggetto e corrispondenti, da consegnare a chi porta un documento
a mano o da apporre sul documento cartaceo.

## Cercare

Il registro si filtra mentre si scrive: numero (`42` o `2026-42`), parole dell'oggetto, mittente,
destinatario, email; poi direzione, classificazione, stato (validi/annullati), anno e periodo.
**Esporta CSV** scarica le registrazioni filtrate (operazione registrata).

## Posta da protocollare

![La posta da protocollare, con la selezione per lo scarto in blocco](immagini/posta.jpg)

Se sono configurate le caselle email o PEC, i messaggi arrivano in **Posta da protocollare**
(automaticamente ogni 15 minuti, oppure con **Scarica ora**). Le caselle sono lette in **sola lettura**:
sul server non viene cancellato né segnato nulla.

Per ogni messaggio:
- si legge il testo (sempre in solo testo, per sicurezza; l'originale completo è scaricabile come `.eml`)
  e si aprono gli allegati;
- **Protocolla**: si conferma o si migliora l'oggetto, si sceglie la classificazione; il mittente viene
  riconosciuto se la sua email o PEC è in anagrafica. Il messaggio originale e gli allegati diventano i
  documenti del protocollo;
- **Scarta** con un motivo (pubblicità, doppione...): il messaggio resta nell'elenco *Scartati*;
  dalla sua scheda, **Riporta tra quelli da esaminare** annulla uno scarto sbagliato.

**Azioni in blocco** (per chi gestisce la posta): nell'elenco *Da esaminare* si spuntano i messaggi
(la casella in testa seleziona tutti quelli della pagina), si scrive o si sceglie il **motivo** (es.
*Ricevuta PEC di sistema*, *Pubblicità o newsletter*, *Già protocollato*) e si preme **Scarta**:
tutti ricevono lo stesso motivo. Nell'elenco *Scartati*, **Riporta tra quelli da esaminare** fa il
contrario. I messaggi già gestiti nel frattempo da un altro utente sono saltati e indicati nel
messaggio di esito; ogni scarto e ripristino è annotato nel registro attività. La protocollazione
resta una per messaggio, perché ognuno ha il proprio oggetto e la propria classificazione.

Per le **PEC** vengono mostrati mittente, oggetto e allegati del messaggio originale (quello dentro la
busta di posta certificata); la busta con le ricevute resta nel file `.eml`.

## Registri giornalieri

**Protocollo → Altro → Registri giornalieri**. Ogni notte l'applicazione genera il PDF del registro del giorno precedente con
tutte le registrazioni (per i riservati l'oggetto è omesso) e ne conserva l'impronta. I registri non si
rigenerano: sono la fotografia di quel giorno. **Genera i mancanti** recupera eventuali giorni saltati.

## Titolario e caselle

- **Titolario** (*Protocollo → Altro → Titolario*): voci di classificazione con codice. Ne è proposto uno di base
  (organizzazione, soci, organi sociali, contabilità, patrimonio, eventi, rapporti con enti...), da
  adattare. Le voci non più usate si disattivano.
- **Caselle** (da *Posta da protocollare → Caselle*): server IMAP, porta (993), utente, password,
  cartella. La password è salvata **cifrata**; serve che l'amministratore di sistema abbia configurato la
  chiave di cifratura. Per la PEC segnare *è una PEC*.
