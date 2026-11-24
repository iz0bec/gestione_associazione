<!--
******************************************************
* Progetto:    Gestione Associazione
* Autore:      Bartolomeo Santoro aka IZ0BEC
* Email:       info@iz0bec.info
* Descrizione: Manuale degli eventi e delle cerimonie con le adesioni
* Licenza:     CC0 1.0 Universal (pubblico dominio)
* SPDX-License-Identifier: CC0-1.0
******************************************************
-->

# Eventi e cerimonie

**Eventi** nel menu raccoglie cerimonie e commemorazioni, incontri, gite, pranzi e cene, con le
**adesioni** dei partecipanti. Gli eventi compaiono anche nel **Calendario** (e nell'esportazione iCal).

## Creare un evento

**Nuovo evento**: titolo, tipo, inizio ed eventuale fine, luogo, descrizione (programma, appuntamento),
**quota** di partecipazione (solo indicativa: gli incassi si registrano in *Tesoreria → Incassi*),
**posti disponibili** (vuoto = senza limite), **accompagnatori** che ciascuno può indicare, apertura e
**chiusura delle adesioni** (vuota = fino all'inizio), **modulo pubblico di adesione**,
**pubblica sui siti collegati** e **annullato**.

## Adesioni

Nella scheda dell'evento:

- **Aggiungi un'adesione** (segreteria): cognome, nome, email, telefono, accompagnatori, note. Se
  l'email, oppure nome e cognome, corrispondono a una sola persona dell'anagrafica, l'adesione viene
  collegata alla sua scheda. La segreteria può aggiungere adesioni anche dopo la chiusura, mai oltre i
  posti.
- La stessa persona (stessa scheda o stessa email) non può aderire due volte.
- Ogni adesione si può **annullare** (resta nell'elenco, barrata): i posti tornano liberi.
- **Foglio presenze** in PDF (con le righe per le firme) e **Aderenti** in Excel.

## Modulo pubblico

Con **Modulo pubblico di adesione** l'evento ha un **collegamento segreto** (mostrato nella scheda, da
copiare) che si può diffondere sul sito, sui social o per email: chiunque lo abbia, anche chi non è
socio, aderisce indicando nome, cognome, email ed eventuali accompagnatori. Il modulo ha le stesse
protezioni dell'iscrizione online (campo trappola, tempo minimo, limite di invii per indirizzo) e si
chiude da solo alla scadenza o quando i posti finiscono. Togliendo la spunta il collegamento smette di
funzionare.

### Pubblica sui siti collegati

Con **Pubblica sui siti collegati** (insieme al modulo pubblico) i siti collegati al gestionale,
come un WordPress con il [connettore](../sistema/connettore-wordpress.md), ne fanno un **articolo**:
in bozza per default, da rivedere (foto, testo) e pubblicare. L'articolo mostra sempre data, luogo,
posti liberi e modulo di adesione aggiornati; se l'evento viene annullato il titolo diventa
«ANNULLATO – …». Le adesioni dal sito arrivano qui con origine «integrazione».

