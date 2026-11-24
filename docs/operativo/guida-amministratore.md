<!--
******************************************************
* Progetto:    Gestione Associazione
* Autore:      Bartolomeo Santoro aka IZ0BEC
* Email:       info@iz0bec.info
* Descrizione: Guida rapida dell'amministratore di sistema
* Licenza:     CC0 1.0 Universal (pubblico dominio)
* SPDX-License-Identifier: CC0-1.0
******************************************************
-->

# Guida rapida dell'amministratore di sistema

L'amministratore **configura** il gestionale e gestisce **utenti**, **servizi di posta**, **backup** e
**collegamenti** con le altre installazioni; può fare tutto ciò che fanno gli altri ruoli.

## All'avvio

1. **Configurazione guidata**: dati dell'ente, logo, sezioni, listino. Vedi
   [Configurazione iniziale](configurazione-iniziale.md).
2. **Sistema → Servizi di posta**: server di invio (SMTP) e caselle da leggere (IMAP/PEC).
3. **Sistema → Utenti e ruoli**: un utente per persona, con i ruoli e (in federazione) le sezioni.

## Utenti

![Gli utenti](immagini/utenti.jpg)

1. **Nuovo utente** (o **Utenti dalle cariche**): la password temporanea si mostra **una volta sola**.
2. Ruoli e, se serve, **sezioni**; il **secondo fattore** si rende obbligatorio per ruolo, con
   l'eventuale **esenzione** motivata per singolo utente.
3. Chi lascia l'incarico si **disattiva**, non si cancella.

Vedi [Utenti e ruoli](utenti.md).

## Collegamenti con federazione e sezioni

![I collegamenti API](immagini/collegamenti.jpg)

1. **Sistema → Collegamenti**: invito (o codice ricevuto), poi confronto dell'**impronta** per una
   seconda via e **attivazione**.
2. Indicare il **ruolo** (federazione o sezione) e concedere gli ambiti (es. *Soci e tessere: lettura*).
3. **Verifica soci** la prima volta; poi l'**allineamento automatico** tiene i soci allineati ogni 15
   minuti, con le email delle novità e delle incongruenze.

Vedi [Collegamenti API](collegamenti-api.md).

## Ogni tanto

- **Backup**: controllare che quello automatico ci sia (*Sistema → Backup*) e scaricarne una copia.
- **Registro attività** per verificare operazioni insolite.
- Aggiornamenti del programma: vedi la guida di sistema dell'installazione.

Vedi [Organizzazione, aspetto, sezioni e registro attività](sistema.md).
