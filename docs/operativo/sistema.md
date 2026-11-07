<!--
******************************************************
* Progetto:    Gestione Associazione
* Autore:      Bartolomeo Santoro aka IZ0BEC
* Email:       info@iz0bec.info
* Descrizione: Dati dell'organizzazione e registro attività
* Licenza:     CC0 1.0 Universal (pubblico dominio)
* SPDX-License-Identifier: CC0-1.0
******************************************************
-->

# Organizzazione e registro attività

## Dati dell'organizzazione

**Sistema → Organizzazione** (amministratore e segretario). Denominazione, codice fiscale,
eventuale iscrizione al RUNTS, sede, recapiti, PEC, logo e testo dell'**informativa privacy**.
Sono usati nelle intestazioni dei documenti, nelle comunicazioni e nei moduli; la denominazione
breve compare in alto nel menu. Ogni modifica è registrata.

## Registro attività

**Sistema → Registro attività** (amministratore, presidente, revisore). Elenca, dal più recente:

- accessi, uscite e **tentativi di accesso falliti** (con indirizzo IP);
- inserimenti, modifiche (con i campi cambiati), archiviazioni;
- **esportazioni** di dati.

Si filtra per tipo di azione e per utente. Gli eventi **non si possono modificare né cancellare**,
nemmeno dall'amministratore: il registro serve proprio a ricostruire chi ha fatto cosa.

Cosa controllare periodicamente: molti *accessi falliti* (qualcuno prova a indovinare una password),
esportazioni inattese, modifiche fatte in orari insoliti.
