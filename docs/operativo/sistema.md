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
eventuale iscrizione al RUNTS, sede, recapiti, PEC e testo dell'**informativa privacy**.
Sono usati nelle intestazioni dei documenti, nelle comunicazioni e nei moduli; la denominazione
breve compare in alto nel menu. Ogni modifica è registrata.

Questi dati si inseriscono la prima volta con la [configurazione guidata](configurazione-iniziale.md).

## Aspetto

**Sistema → Aspetto** (amministratore e segretario):

- **logo**: PNG o JPEG, meglio quadrato e con sfondo trasparente. Viene ridotto a 512 pixel e
  ricodificato. Compare nel menu, nella pagina di accesso, nelle pagine pubbliche, come icona del
  browser e nell'intestazione dei PDF;
- **colore principale**: pulsanti, collegamenti, voci attive, intestazioni dei PDF. Il testo sopra
  il colore diventa bianco o scuro da solo, per restare leggibile;
- **menu laterale**: scuro, chiaro o nel colore principale.

Ogni utente può comunque passare dal tema chiaro a quello scuro con il pulsante in alto.

## Sezioni

**Sistema → Sezioni**: codice (come nel registro nazionale), nome, comune, provincia, email. Con
una sola sezione l'applicazione si comporta come per un'associazione singola. Con più sezioni
compaiono il filtro e la scelta della sezione in soci, tessere e domande di iscrizione. Una
sezione con soci attivi non si può disattivare.

Le sezioni visibili a un utente si assegnano nella sua scheda (**Amministrazione tecnica →
Utenti → Sezioni**). Senza sezioni assegnate l'utente vede tutto.

La casella **Domande di iscrizione online** pubblica il modulo di iscrizione all'indirizzo
`/iscrizione/` (vedi [Soci e tesseramento](soci.md#domande-di-iscrizione)).

## Registro attività

**Sistema → Registro attività** (amministratore, presidente, revisore). Elenca, dal più recente:

- accessi, uscite e **tentativi di accesso falliti** (con indirizzo IP);
- inserimenti, modifiche (con i campi cambiati), archiviazioni;
- **esportazioni** di dati.

Si filtra per tipo di azione e per utente. Gli eventi **non si possono modificare né cancellare**,
nemmeno dall'amministratore: il registro serve proprio a ricostruire chi ha fatto cosa.

Cosa controllare periodicamente: molti *accessi falliti* (qualcuno prova a indovinare una password),
esportazioni inattese, modifiche fatte in orari insoliti.
