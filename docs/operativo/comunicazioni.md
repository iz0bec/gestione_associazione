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

- **Modelli**: testi pronti per uso (convocazione, ricevuta, esito della domanda, compleanno, onomastico,
  anniversario di iscrizione, ricorrenza, generico). Sono già presenti modelli di base da adattare.
- **Liste**: unione di persone scelte, **categorie** dell'anagrafica (es. Autorità), **tutti i soci** o
  **solo quelli in regola** con la quota, **componenti di un organo**. Le liste si aggiornano da sole.

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
