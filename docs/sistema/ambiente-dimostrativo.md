<!--
******************************************************
* Progetto:    Gestione Associazione
* Autore:      Bartolomeo Santoro aka IZ0BEC
* Email:       info@iz0bec.info
* Descrizione: Ambiente dimostrativo: installazione pubblica di prova con dati di fantasia
* Licenza:     CC0 1.0 Universal (pubblico dominio)
* SPDX-License-Identifier: CC0-1.0
******************************************************
-->

# Ambiente dimostrativo

Un'installazione **di prova**, raggiungibile da chiunque, per far conoscere il gestionale: dati di
fantasia (quelli delle schermate del manuale), logo generato, un utente per ogni ruolo con una
password pubblica e un amministratore con una password privata. Il 1° di ogni mese torna come nuova.

> **Attenzione**: l'azzeramento **cancella tutto il database e tutti i file**. `DEMO=true` va messo
> solo in un'installazione dedicata, mai in una con dati veri.

## Come si attiva

In un'installazione nuova e dedicata (es. un container a parte), nel `.env`:

```ini
DEMO=true
DEMO_PASSWORD=Demo-2026            # pubblica: compare nella pagina di accesso
DEMO_ADMIN_PASSWORD=...            # privata: solo per chi gestisce la demo
```

poi, riavviati i servizi, il primo caricamento:

```bash
cd /opt/gestione-associazione && sudo -u gestione .venv/bin/python manage.py demo --conferma
```

Il comando rifiuta di partire senza `DEMO=true` e senza `--conferma`.

## Cosa si vede

- In **ogni pagina** una fascia «Ambiente dimostrativo».
- Nella **pagina di accesso** la tabella degli utenti dei ruoli con la password comune:
  `presidente`, `segretario`, `tesoriere`, `protocollo`, `sezione` (presidente di sezione, vede solo
  la sezione di Valleverde), `consigliere`, `revisore`. L'amministratore (`admin`) non compare.
- Gli utenti dei ruoli **non possono cambiare la password** (nessun visitatore chiude fuori gli altri);
  il blocco dopo i tentativi falliti vale per la coppia utente + indirizzo IP, quindi colpisce solo chi
  sbaglia.
- **Nessun messaggio parte**: l'invio di email, PEC, Telegram, SMS e WhatsApp e la lettura delle caselle
  sono spenti; l'iscrizione online è attiva per mostrarla.

## Azzeramento

Il **pianificatore** esegue `manage.py demo --se-dovuto` con i lavori giornalieri: il 1° del mese,
una volta sola, cancella database e file e ricarica i dati. A mano: `manage.py demo --conferma`.
