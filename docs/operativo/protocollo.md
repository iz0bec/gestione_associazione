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

- Numero, data, direzione, **oggetto, testo e corrispondenti non si modificano** dopo la registrazione.
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
   **Testo** (facoltativo): il corpo di un'email, di una PEC o di un messaggio (WhatsApp, SMS...)
   incollato così com'è, oppure la trascrizione di una comunicazione a voce o di un biglietto.
   Serve quando il contenuto non è in un file da allegare; si cerca come l'oggetto.
4. **Mittenti** (entrata) o **destinatari** (uscita): cercare nell'anagrafica scrivendo nome, ente o
   email e cliccare il risultato; compare un'etichetta (togliendo la spunta lo si esclude). Chi non è
   in anagrafica si scrive nel riquadro sotto, uno per riga: `Prefettura di Potenza <prefettura@pec.it>`
   oppure solo il nome; per la posta anche `Prefettura di Potenza; Piazza Pagano 1, 85100 Potenza (PZ)`
   (nome e indirizzo separati da `;`). Per una PEC viene proposto l'indirizzo PEC del soggetto, per
   posta, raccomandata o consegna a mano l'indirizzo postale. Con **Liste di distribuzione** (in
   uscita) si aggiungono tutti i componenti delle liste scelte, una volta sola ciascuno e senza le
   persone decedute; le liste si creano in *Comunicazioni → Liste*.
5. **Documento**: data del documento, numero di protocollo del mittente, data di ricezione (se diversa),
   **in risposta a** (numero come `2026-00012`), i **file** (il primo è il documento principale).
6. **Registra**: compaiono numero, data e ora.

**Parti da un modello** (in alto nella nuova registrazione) compila direzione, mezzo, classificazione,
oggetto, testo e liste di distribuzione da un modello di registrazione: si completano i puntini (`...`),
i corrispondenti e i documenti, poi si registra. I modelli si gestiscono in *Altro → Modelli di
registrazione* (responsabile del protocollo e segretario); ce ne sono alcuni di base da adattare
(convocazione dell'assemblea, invito a una cerimonia, richiesta di patrocinio, composizione degli organi,
trasmissione del rendiconto, richiesta di contributo, domanda di iscrizione ricevuta). Nell'oggetto e nel
testo `{{ anno }}`, `{{ anno_precedente }}`, `{{ data }}` e `{{ organizzazione }}` diventano i valori del
giorno.

Dalla scheda di un protocollo in entrata, **Rispondi** apre una registrazione in uscita già collegata,
con oggetto e destinatari precompilati. Dalla scheda anagrafica di un ente o di una persona si vedono i
suoi protocolli e si può registrare direttamente un'entrata o un'uscita.

**Ricevuta**: PDF con numero, data, oggetto e corrispondenti, da consegnare a chi porta un documento
a mano o da apporre sul documento cartaceo.

## Buste e spedizioni su carta

Nella scheda di un protocollo in uscita compare il pulsante **Buste** quando qualcuno lo riceve su
carta: con posta, raccomandata o consegna a mano tutti i destinatari; con email o PEC solo quelli
**senza indirizzo email** (il pulsante ne riporta il numero, es. «Buste (3 senza email)»). Si scarica:

- **Buste DL compilate (Word)**: una busta 220 × 110 mm per destinatario, già pronta da stampare, con
  il mittente in alto a sinistra, il numero di protocollo, la dicitura «RACCOMANDATA» quando serve e il
  destinatario nella finestra a destra;
- **Busta DL per la stampa unione (Word)** ed **Elenco dei destinatari (CSV)**: per chi preferisce la
  stampa unione. In Word: *Lettere → Inizia stampa unione → Lettere*, poi *Seleziona destinatari → Usa
  elenco esistente* e scegliere il CSV (separatore punto e virgola, codifica UTF-8); *Anteprima
  risultati* per controllare e *Finalizza e unisci → Modifica singoli documenti* o *Stampa documenti*.
  In LibreOffice: *Strumenti → Stampa in serie guidata*, scegliendo il CSV come origine dati.

Il CSV ha le colonne `Nominativo`, `Qualifica`, `Indirizzo`, `CAP`, `Comune`, `Provincia` e
`Riga1`…`Riga4` (le righe della busta, senza righe vuote nel mezzo), utili anche per etichette o
modulistica di Poste. Gli indirizzi sono quelli **registrati nel protocollo**. Se un indirizzo
postale manca o è incompleto la scheda lo segnala e la colonna `Avviso` lo indica: si completa la
scheda anagrafica per le spedizioni successive, oppure a mano sulla busta. Ogni scaricamento è
registrato nel registro delle attività.

## Spedire per email o PEC

Un protocollo **in uscita** si spedisce dalla sua scheda con **Spedisci** (serve il permesso di
spedire, che hanno l'addetto al protocollo e i ruoli superiori). Nel modulo:

- **Spedisci da**: uno dei **servizi di invio** configurati in *Sistema → Servizi di posta* (per la
  **PEC** quello della PEC dell'ente, per l'email ordinaria il server generale). Se il protocollo è
  registrato con mezzo PEC viene proposto il servizio PEC;
- **Destinatari**: quelli del protocollo, ciascuno con l'indirizzo proposto dall'anagrafica (la PEC
  quando si spedisce da un servizio PEC, altrimenti l'email) e modificabile; si tolgono quelli da non
  raggiungere (per esempio chi riceve per posta). Parte **un messaggio per destinatario**, così
  nessuno vede gli indirizzi degli altri e ogni PEC ha le proprie ricevute;
- **Testo**: è proposto quello del protocollo, o una lettera di trasmissione standard;
- **Documenti allegati**: quelli del protocollo, tutti spuntati (al massimo 20 MB in tutto).

L'**oggetto** del messaggio è quello del protocollo con numero e data: «Prot. n. 2026-00042 del
16/11/2026 - ...». Si possono fare più spedizioni dello stesso protocollo (per esempio a un
destinatario aggiunto dopo); oggetto e corrispondenti del protocollo non cambiano.

Nella scheda, il riquadro **Spedizioni** riporta per ogni destinatario l'esito:

| Esito | Significato |
|---|---|
| In coda | in attesa di partire (anche con l'invio delle email spento in *Sistema → Servizi di posta*) |
| Inviato | consegnato al server di invio; per l'email ordinaria non ci sono altre conferme |
| Accettato dal gestore | PEC: ricevuta di accettazione del proprio gestore |
| Consegnato | PEC: ricevuta di avvenuta consegna nella casella del destinatario |
| Non accettato / Non consegnato | PEC: il gestore ha rifiutato il messaggio o non è riuscito a consegnarlo |
| Errore di invio | il server non ha accettato il messaggio dopo tre tentativi: **Riprova** lo rimette in coda |

Le **ricevute PEC** arrivano nella casella PEC e, quando la casella viene letta, si **agganciano da
sole** alla spedizione: aggiornano l'esito e diventano documenti del protocollo (`ricevuta
avvenuta-consegna - indirizzo.eml`, con la firma del gestore). Non compaiono fra la posta da
protocollare. Per questo la PEC che spedisce deve essere configurata anche come **casella da
leggere** (*Protocollo → Caselle*), con la lettura attiva.

## Cercare

Il registro si filtra mentre si scrive: numero (`42` o `2026-42`), parole dell'oggetto o del testo, mittente,
destinatario, email; poi direzione, classificazione, stato (validi/annullati), anno e periodo.
**Esporta CSV** scarica le registrazioni filtrate (operazione registrata).

## Posta da protocollare

![La posta da protocollare, con la selezione per lo scarto in blocco](immagini/posta.jpg)

Se sono configurate le caselle email o PEC, i messaggi arrivano in **Posta da protocollare**
(automaticamente ogni 15 minuti, oppure con **Scarica ora**). Sul server non viene cancellato né
segnato come letto nulla: i messaggi scaricati vengono **spostati nella cartella `PROCESSATA`** della
casella (creata al primo scaricamento, visibile anche dalla webmail; con Aruba si chiama
`INBOX.PROCESSATA`, cioè una sottocartella della posta in arrivo), così nella posta in arrivo restano
solo quelli non ancora acquisiti. La cartella si cambia nella scheda della casella; lasciandola vuota i
messaggi restano dove sono.

Per ogni messaggio:
- si legge il testo (sempre in solo testo, per sicurezza; l'originale completo è scaricabile come `.eml`)
  e si aprono gli allegati;
- **Protocolla**: si conferma o si migliora l'oggetto, si sceglie la classificazione; il mittente viene
  riconosciuto se la sua email o PEC è in anagrafica. Il messaggio originale e gli allegati diventano i
  documenti del protocollo e il testo del messaggio diventa il **testo** della registrazione;
- **Domanda di iscrizione**: per le richieste di iscrizione (etichetta *iscrizione?* nell'elenco),
  registra la domanda con i dati recuperati dal messaggio e protocolla in un colpo solo (vedi il
  manuale *Soci*, *Domande arrivate per email*);
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

## Manuale di gestione

*Altro → Manuale di gestione* prepara il **manuale di gestione documentale**, il documento che descrive
come l'ente riceve, registra, classifica, spedisce e conserva i documenti. È obbligatorio per le pubbliche
amministrazioni (Linee guida AgID sulla formazione, gestione e conservazione dei documenti informatici) e
consigliato a ogni associazione che tiene un protocollo: dà valore al registro e aiuta chi subentra.

Il programma lo compone con la **configurazione reale**: sezioni, ruoli e capacità (con il secondo fattore
obbligatorio), utenti abilitati, caselle di posta e PEC collegate, mezzi, regole della registrazione, dei
riservati e dell'annullamento, registro giornaliero, backup, titolario, modelli di registrazione. Un capitolo
dice con chiarezza cosa il sistema **non** fa rispetto alle regole tecniche delle pubbliche amministrazioni
(segnatura XML e interoperabilità tra protocolli, invio automatico del registro alla conservazione,
conservazione digitale, firma digitale).

Si indicano i dati organizzativi: **responsabile della gestione documentale** e vicario, responsabile della
conservazione e come si conservano i documenti nel lungo periodo, atto di adozione e **disposizioni
aggiuntive** proprie dell'ente (un capitolo libero, con grassetto ed elenchi). Le parti ancora da indicare
compaiono in rosso nella **bozza aggiornata** (PDF).

Dopo l'approvazione dell'organo competente, **Adotta e protocolla** registra la nuova versione come
protocollo interno, con il PDF allegato e l'atto di adozione nel testo. Quando cambiano organizzazione,
titolario, caselle o ruoli la bozza si aggiorna da sola: si adotta una nuova versione. Preparano e adottano il
manuale amministratore di sistema e segretario.

**Consultazione.** Le versioni adottate restano tutte consultabili, con data, atto e protocollo di adozione,
nella tabella **Versioni adottate**; quella in vigore è segnata. Le vedono **tutti gli utenti**, qualunque sia
il ruolo: anche dalla pagina di aiuto (pulsante **?**, riquadro *Documenti dell'ente*). La bozza e i dati
organizzativi restano a chi lavora sul protocollo.

**Pubblicazione.** Il manuale in vigore si può mettere nella **pagina dei documenti pubblici**, accanto a
statuto e regolamento, consultabile da chiunque (le pubbliche amministrazioni lo pubblicano sul sito
istituzionale): subito, spuntando *Pubblica subito* quando si adotta, oppure **in qualsiasi momento dopo**,
con il pulsante *Pubblica la versione … fra i documenti pubblici* sotto lo storico. Si pubblica la versione
**così com'era all'adozione**: insieme al manuale il programma conserva nel protocollo una variante senza
l'elenco nominativo degli utenti e senza gli account delle caselle di posta, ed è quella che va in rete.
Quando si adotta una nuova versione, quella pubblicata viene sostituita da sola. *Ritira dalla pubblicazione*
la toglie dalla pagina pubblica; le versioni restano agli atti.

## Titolario e caselle

- **Titolario** (*Protocollo → Altro → Titolario*): voci di classificazione con codice. Ne è proposto uno di base
  (organizzazione, soci, organi sociali, contabilità, patrimonio, eventi, rapporti con enti...), da
  adattare. Le voci non più usate si disattivano.
- **Caselle** (da *Posta da protocollare → Caselle*): server IMAP, porta (993), utente, password,
  cartella da leggere e cartella dei messaggi scaricati (`PROCESSATA`). La password è salvata **cifrata**; serve che l'amministratore di sistema abbia configurato la
  chiave di cifratura. Per la PEC segnare *è una PEC* (per Aruba `imaps.pec.aruba.it`, porta 993).
  Le caselle servono **solo a leggere**: i server per **spedire** (email e PEC) si configurano in
  *Sistema → Servizi di posta* (vedi la guida del [Sistema](sistema.md#servizi-di-posta)).
