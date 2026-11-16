<!--
******************************************************
* Progetto:    Gestione Associazione
* Autore:      Bartolomeo Santoro aka IZ0BEC
* Email:       info@iz0bec.info
* Descrizione: Manuale operativo del modulo Comunicazioni e anniversari
* Licenza:     CC0 1.0 Universal (pubblico dominio)
* SPDX-License-Identifier: CC0-1.0
******************************************************
-->

# Comunicazioni e anniversari

Il modulo invia email a soci, autorità e altre associazioni, tiene il **registro** di ogni invio e
ricorda gli **anniversari**: compleanni, onomastici, anniversari di iscrizione, ricorrenze
dell'associazione e anniversari di scomparsa. Gli auguri possono partire da soli.

## Privacy: chi riceve cosa

Ogni comunicazione ha una **finalità**, che decide chi la può ricevere:

| Finalità | Esempi | Chi la riceve |
|---|---|---|
| **Istituzionale** | convocazioni, ricevute, esito della domanda | tutti i destinatari con email |
| **Comunicazioni associative** | avvisi, programmi, iniziative | solo chi ha il consenso *Comunicazioni associative* |
| **Auguri e ricorrenze** | compleanni, onomastici, anniversari | solo chi ha il consenso *Auguri e ricorrenze* |

Conta l'**ultimo consenso** registrato in anagrafica: se è stato revocato, la persona è esclusa.
Sono sempre esclusi i **deceduti**, le schede **archiviate** e chi non ha email. Nell'anteprima ogni
escluso compare con il motivo.

Ogni destinatario riceve un **messaggio separato**: nessuno vede gli indirizzi degli altri. Le risposte
arrivano all'email dell'associazione (*Sistema → Organizzazione*).

## Scrivere una comunicazione

![Il registro delle comunicazioni](immagini/comunicazioni.jpg)

**Comunicazioni → Nuova comunicazione**.

1. Facoltativo: **Parti da un modello** per avere oggetto e testo già pronti.
2. **Oggetto** e **testo**: si possono usare i **segnaposto**, sostituiti per ogni destinatario.
   Esempio: `{{ saluto }} {{ nome }},` diventa «Caro Mario,» o «Cara Anna,».
3. **Documenti** da allegare (es. un programma in PDF).
4. **Destinatari**: una o più **liste**, persone ed enti cercati in anagrafica, altri indirizzi scritti a
   mano (uno per riga: `Mario Rossi <mario@example.org>`).
5. **Finalità**, eventuale data di **invio programmato**, **protocolla in uscita** al termine.
6. **Prepara e controlla**: nulla parte ancora. La pagina mostra l'**anteprima** del messaggio come lo
   riceverà il primo destinatario e l'elenco dei destinatari con gli **esclusi** e il motivo.
7. **Conferma e invia**. I primi messaggi partono subito, gli altri a gruppi nei minuti successivi.

Lo stato di ogni destinatario (in attesa, inviato, errore, escluso) resta nel registro. Se il server di
posta non risponde, il programma ritenta tre volte; poi si può usare **Ritenta gli errori**.

### Chi non ha l'email: lettere e buste

Nella pagina dell'invio, il riquadro **Su carta** elenca i destinatari esclusi solo perché senza email
e offre:

- **Lettere (PDF)**: una lettera per persona con l'intestazione dell'ente, l'indirizzo nella
  posizione della finestra della busta, la data, l'oggetto e il testo con gli stessi segnaposto
  dell'email (es. *Gentile Mario*);
- **Buste DL (Word)** già compilate, oppure il documento per la **stampa unione** con l'**elenco
  (CSV)**: sono le stesse buste del protocollo in uscita.

L'indirizzo è quello **attuale** dell'anagrafica; se manca o è incompleto la pagina lo segnala. Se
l'invio è protocollato, lettere e buste riportano il numero di protocollo. Vale la stessa regola
dei consensi delle email: per le comunicazioni non istituzionali chi non ha dato il consenso non
riceve nemmeno la lettera (la pagina dice quanti sono). Ogni scaricamento resta nel registro attività.

### Segnaposto disponibili

| Segnaposto | Valore |
|---|---|
| `{{ nome }}`, `{{ cognome }}`, `{{ nome_completo }}`, `{{ titolo }}` | dati della persona |
| `{{ saluto }}` | «Caro», «Cara» o «Gentile» secondo il sesso in anagrafica |
| `{{ anni }}` | età, anni di iscrizione o della ricorrenza (negli auguri) |
| `{{ numero_socio }}`, `{{ anni_socio }}` | dati del socio |
| `{{ organizzazione }}`, `{{ data }}` | denominazione dell'associazione, data di oggi |
| `{{ riunione }}`, `{{ data_riunione }}`, `{{ luogo_riunione }}`, `{{ ordine_del_giorno }}` | nelle convocazioni |
| `{{ anno_quota }}`, `{{ importo }}`, `{{ ricevuta }}`, `{{ tessera }}` | nelle ricevute |
| `{{ esito }}` | nell'esito della domanda di iscrizione |
| `{{ ricorrenza }}` | nome della ricorrenza |

Un segnaposto scritto male viene segnalato e la comunicazione non parte.

## Modelli e liste

- **Modelli**: testi pronti per uso (convocazione, ricevuta, conferma di ricezione ed esito della domanda, compleanno, onomastico,
  anniversario di iscrizione, ricorrenza, generico). Sono già presenti modelli di base da adattare.
- **Liste**: unione di persone scelte, **categorie** dell'anagrafica (es. Autorità), **tutti i soci** o
  **solo quelli in regola** con la quota, **componenti di un organo**. Le liste si aggiornano da sole.
  Con più sezioni (federazione), **Solo i soci delle sezioni** limita i soci a quelle scelte (nessuna
  = tutte); chi è abilitato solo ad alcune sezioni vede e deve scegliere solo le proprie. Le
  persone scelte, le categorie e l'organo non dipendono dalle sezioni.
  Si usano anche nel **protocollo in uscita** (liste di distribuzione), con le buste per chi non ha
  l'email.

### Modificare una lista fuori linea (Excel)

1. Dalla pagina della lista, **Esporta in Excel**. Il file ha quattro fogli:
   - **Lista**: nome, descrizione, soci (tutti o solo in regola: «sì»/«no»), sezioni dei soci
     (nomi o codici; vuoto = tutte), organo, categorie
     (separate da punto e virgola) e il *codice lista*, che non va modificato;
   - **Persone**: le persone e gli enti scelti uno per uno (codice, tipo, cognome o denominazione,
     nome, codice fiscale, email e indirizzo postale: indirizzo, CAP, comune, provincia, nazione);
   - **Destinatari**: chi riceve oggi le comunicazioni della lista, **compresi i soci, le categorie
     e l'organo**, con email, indirizzo postale e il motivo per cui è nella lista (scelto, socio,
     categoria, organo). È solo da consultare: all'importazione viene ignorato;
   - **Istruzioni**.
2. Si lavora sul file anche senza collegamento: per togliere qualcuno si cancella la riga, per
   aggiungere qualcuno già in anagrafica basta il codice fiscale o l'email.
3. **Liste → Importa da Excel**: si carica il file e si vede l'**anteprima** (impostazioni, persone
   abbinate, aggiunte e tolte, righe non riconosciute). Nulla cambia finché non si conferma.

Il *codice lista* indica quale lista aggiornare; se manca, si aggiorna la lista con lo stesso nome o se
ne crea una nuova. Le persone sono riconosciute per **codice**, poi **codice fiscale**, poi **email**
(solo se una sola scheda ha quell'email: altrimenti la riga è segnalata come ambigua). Chi non è in
anagrafica è solo segnalato, a meno di spuntare **Crea in anagrafica le persone non trovate** (serve il
permesso di inserire schede): la scheda nasce con i soli dati del file e senza consensi, quindi riceve
solo le comunicazioni istituzionali finché non si registra il consenso. Organi e categorie sconosciuti
sono segnalati e ignorati. Esportazione e importazione restano nel registro attività.

Il foglio *Persone* contiene solo chi è stato scelto uno per uno: in una lista fatta di soci è
vuoto, e i soci (con i loro indirizzi) sono nel foglio *Destinatari*.

Gli **indirizzi postali** servono per le buste di chi non ha l'email. Delle schede già presenti si
**completano solo i campi vuoti**: un valore diverso da quello in anagrafica è segnalato
nell'anteprima e resta com'è (si corregge nella scheda). Un CAP o una provincia non validi sono
segnalati e ignorati; un CAP a cui Excel ha tolto lo zero iniziale viene ricomposto.

## Dagli altri moduli

- **Riunione convocata** → *Invia per email*: la lettera di convocazione in PDF a tutti gli aventi diritto.
- **Tessera pagata** (scheda del socio) → icona ✉: la **ricevuta** in PDF al socio.
- **Domanda di iscrizione valutata** → *Comunica l'esito*: anche a chi non è ancora in anagrafica.

In tutti i casi si apre l'anteprima: si controlla e si conferma.

La scheda anagrafica mostra le **comunicazioni** ricevute dalla persona.

## Anniversari

**Anniversari** mostra, giorno per giorno, i prossimi:

- **compleanni**, con gli anni compiuti; per chi è nato il 29 febbraio si festeggia il 1° marzo;
- **onomastici**, dal calendario (*Auguri automatici e ricorrenze → Calendario degli onomastici*). Per i
  nomi composti si cerca prima il nome intero («Maria Teresa»), poi il primo nome;
- **anniversari di iscrizione** dei soci attivi, con gli anni di appartenenza;
- **ricorrenze** dell'associazione e nazionali, con gli anni trascorsi (es. 4 Novembre, 108 anni);
- **anniversari di scomparsa** di soci e persone, solo come promemoria.

Gli anniversari «tondi» sono evidenziati. Accanto a ognuno, **Auguri** o **Scrivi** apre una
comunicazione con il modello adatto. I prossimi 14 giorni sono anche sul cruscotto.

## Auguri automatici

**Anniversari → Auguri automatici e ricorrenze**. Per compleanni, onomastici e anniversari di iscrizione:

- **attiva**, **modello** da usare, **destinatari** (solo soci attivi o tutta l'anagrafica), **ora** dalla
  quale partono;
- per l'iscrizione, gli **anni da festeggiare** (es. `1,5,10,25,50`).

Sono **spenti** dopo l'installazione: vanno attivati quando modelli e consensi sono pronti. Ogni giorno il
programma prepara gli auguri, li invia e li registra tra le comunicazioni; una persona non riceve mai due
volte gli stessi auguri nello stesso giorno.

**Ricorrenze**: sono già inserite le principali date nazionali (Giorno della Memoria, Giorno del Ricordo,
25 Aprile, 24 Maggio, 2 Giugno, 2 e 4 Novembre, 12 Novembre). Si aggiungono quelle della sezione (es.
fondazione, inaugurazione del monumento) con l'anno di inizio. Con *invio automatico*, il giorno della
ricorrenza parte un messaggio alla lista indicata.

I **promemoria di rinnovo della quota** ai soci non in regola funzionano allo stesso modo: si
impostano da *Tesseramento → Promemoria di rinnovo* (vedi [Soci](soci.md#promemoria-di-rinnovo)).

Per il funzionamento automatico serve il **pianificatore** attivo sul server (manuale di sistema).
