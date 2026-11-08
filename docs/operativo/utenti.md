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

Ricerca per nome, cognome, nome utente o email; filtri per ruolo e stato (attivi, disattivati,
tutti). Per ogni utente si vedono i ruoli, le sezioni assegnate, il secondo fattore e l'ultimo
accesso. Il cartellino **password temporanea** indica chi non ha ancora scelto la propria password;
**richiesto, da configurare** indica chi ha un ruolo con il secondo fattore obbligatorio ma non lo
ha ancora attivato.

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

## Scheda dell'utente

Modifica dei dati, dei ruoli e delle sezioni; nel riquadro **Accesso**:

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

I permessi dei ruoli predefiniti sono fissati dal programma e riallineati a ogni aggiornamento
(tabella in [Ruoli e permessi](ruoli.md)).
