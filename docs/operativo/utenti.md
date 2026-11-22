<!--
******************************************************
* Progetto:    Gestione Associazione
* Autore:      Bartolomeo Santoro aka IZ0BEC
* Email:       info@iz0bec.info
* Descrizione: Manuale della gestione utenti e ruoli
* Licenza:     CC0 1.0 Universal (pubblico dominio)
* SPDX-License-Identifier: CC0-1.0
******************************************************
-->

# Utenti e ruoli

**Sistema → Utenti e ruoli**, per l'amministratore di sistema. Un utente è un account di accesso
(nome utente o email, più la password); i suoi permessi dipendono dai [ruoli](ruoli.md).

## Elenco

![L'elenco degli utenti](immagini/utenti.jpg)

Ricerca per nome, cognome, nome utente o email; filtri per ruolo e stato (attivi, disattivati,
tutti). Per ogni utente si vedono i ruoli, le sezioni assegnate, il secondo fattore e l'ultimo
accesso. Il cartellino **password temporanea** indica chi non ha ancora scelto la propria password;
**richiesto, da configurare** indica chi ha un ruolo con il secondo fattore obbligatorio ma non lo
ha ancora attivato.

### Utenti connessi

In cima all'elenco, **Connessi ora** mostra chi ha usato il programma negli ultimi 5 minuti (clic sul
nome per la scheda); il filtro *Connessi ora* restringe l'elenco a loro. Nella colonna dell'ultimo
accesso compare *connesso ora* oppure l'ora dell'ultima attività. Chi esce con **Esci** non risulta più
connesso; chi chiude solo il browser scompare dopo 5 minuti. L'attività si annota al massimo una volta
al minuto per utente.

## Nuovo utente

**Nuovo utente**: nome utente, nome, cognome, email (unica, serve anche per accedere), telefono,
ruoli e, in una federazione, sezioni.

Ogni utente **deve avere una scheda in anagrafica**: si sceglie la persona (solo persone non già
collegate a un altro utente) oppure si spunta *Crea la scheda in anagrafica*, che la crea con nome,
cognome, email e telefono dell'utente. Se la persona è un socio, l'elenco degli utenti mostra il
numero di socio. Gli utenti creati prima di questa regola (es. l'amministratore iniziale) sono
segnalati con *senza scheda in anagrafica*: si collegano dalla loro scheda.

Alla creazione il programma genera una **password temporanea** e la mostra **una sola volta**:
comunicarla all'interessato di persona o per telefono. Al primo accesso l'utente deve sceglierne
una nuova prima di poter fare qualunque altra cosa. La password temporanea non è conservata in
chiaro e non compare nel registro attività.

## Utenti dalle cariche

**Utenti e ruoli → Utenti dalle cariche** crea in una volta gli utenti «standard» per chi ha una
**carica in corso** negli organi sociali (consiglio, organo di controllo, altri organi; non le
assemblee) e non ha ancora un utente. La pagina elenca le persone con le cariche, il nome utente
proposto (`nome.cognome`) e i ruoli che riceveranno:

| Carica | Ruoli nel gestionale | Attivo (predefinito) |
|---|---|---|
| Presidente, Vicepresidente | Presidente | sì |
| Segretario | Segretario e Tesoriere | sì |
| Tesoriere | Tesoriere | no |
| Consigliere, Supplente | Consigliere | no |
| Organo di controllo (presidente, componenti) | Revisore | no |
| Altri organi (es. garanti) | Consigliere | no |

Per ogni tipo di carica si sceglie la **password**: vuota la genera il programma, una sola per tutte
le persone con quella carica. Scrivendo la stessa password in più gestionali (es. federazione e
sezioni), chi ha la stessa carica la usa ovunque. Si sceglie anche quali cariche hanno l'utente
**attivo** (gli altri si attivano in seguito dalla scheda), se **obbligare il cambio** della password
al primo accesso e se preparare una **comunicazione in bozza** con le credenziali e i passaggi per
cambiare la password per ogni utente attivo con un'email (le bozze si controllano e si inviano da
*Comunicazioni*; il testo contiene la password: va cambiata al primo accesso).

Chi non ha un'email in anagrafica riceve un indirizzo segnaposto `…@senza-email.invalid` (il recupero
della password non funziona finché non si inserisce quella vera). In un'installazione con più
sezioni, chi ha cariche solo negli organi di una sezione vede solo quella sezione. Le password si
vedono **una sola volta**, nella pagina che conclude l'operazione.

## Scheda dell'utente

Nei dati dell'utente due caselle regolano la password:

- **Può cambiare la propria password** (spuntata per i nuovi utenti): togliendola, la password la
  imposta solo l'amministratore. L'utente non vede *Cambia password* nel menu, non può aprire le
  pagine per cambiarla e il recupero della password via email non gli viene spedito;
- **Deve cambiare la password**: al prossimo accesso l'utente deve sceglierne una nuova prima di
  fare altro (non si può spuntare per chi non può cambiarla).

Modifica dei dati, dei ruoli e delle sezioni; nel riquadro **Accesso**:

- **Imposta password** - l'amministratore sceglie la password (scritta due volte, con gli stessi
  controlli di robustezza delle altre) e decide se l'utente **deve cambiarla al primo accesso**; la
  password non viene mostrata né conservata nel registro attività: va comunicata di persona;
- **Nuova password temporanea** - per chi ha dimenticato la password: la precedente smette di
  funzionare, la nuova va cambiata al primo accesso;
- **Azzera il secondo fattore** - per chi ha perso il telefono o la passkey: elimina app di
  autenticazione, passkey e codici di recupero; se il ruolo lo richiede, l'utente dovrà
  configurarlo di nuovo al prossimo accesso;
- **Disattiva / Riattiva** - un utente disattivato non può accedere; i suoi dati e le sue operazioni
  nel registro attività restano. Gli utenti non si eliminano.

Regole di sicurezza:

- non si può disattivare il proprio account né togliersi i ruoli che permettono di gestire gli
  utenti (evita di restare senza amministratori);
- password e secondo fattore del proprio account si gestiscono dal menu del profilo;
- solo un superutente (l'amministratore creato dall'installazione) può modificare un superutente;
  dall'interfaccia non si creano superutenti.

Ogni operazione è registrata nel [registro attività](sistema.md#registro-attività).

## Ruoli e secondo fattore obbligatorio

**Utenti e ruoli → Ruoli** elenca i ruoli con il numero di utenti attivi e di permessi. La colonna
**Secondo fattore obbligatorio** si spunta per i ruoli che trattano dati delicati (es.
Amministratore di sistema, Presidente, Segretario, Tesoriere): chi ha uno di quei ruoli, al
prossimo accesso, deve configurare un'app di autenticazione (TOTP) o una passkey prima di usare il
programma (vedi [Primi passi](primi-passi.md)). I codici di recupero da soli non bastano.

L'obbligo è **bloccante**: finché non configura il secondo fattore, l'utente vede solo la pagina per
farlo (e può uscire). Chi non ha uno smartphone può usare una **chiave di sicurezza o la passkey** del
computer, oppure un'app di autenticazione per computer (es. KeePassXC); altrimenti si toglie l'obbligo
al ruolo.

I permessi dei ruoli predefiniti sono fissati dal programma e riallineati a ogni aggiornamento
(tabella in [Ruoli e permessi](ruoli.md)).
