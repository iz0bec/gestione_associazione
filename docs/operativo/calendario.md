<!--
******************************************************
* Progetto:    Gestione Associazione
* Autore:      Bartolomeo Santoro aka IZ0BEC
* Email:       info@iz0bec.info
* Descrizione: Manuale del calendario e dell'esportazione iCal
* Licenza:     CC0 1.0 Universal (pubblico dominio)
* SPDX-License-Identifier: CC0-1.0
******************************************************
-->

# Calendario

**Calendario** nel menu raccoglie gli impegni registrati negli altri moduli e li porta sul
calendario del telefono o del computer (formato **iCal**, compatibile con iPhone, Android/Google
Calendar, Outlook e Thunderbird).

## Cosa contiene

| Impegno | Da dove viene | Chi lo vede |
|---|---|---|
| Riunioni (1ª e 2ª convocazione, luogo, ordine del giorno, collegamento) | [Organi sociali](organi.md): riunioni convocate o già verbalizzate | chi consulta le riunioni |
| Ricorrenze (ogni anno) | [Anniversari](comunicazioni.md): ricorrenze attive | chi consulta le ricorrenze |
| Restituzioni previste dei beni in prestito | [Patrimonio](patrimonio.md): prestiti non ancora rientrati | chi consulta l'inventario |
| Compleanni dei soci attivi (ogni anno, a scelta) | [Soci](soci.md) e anagrafica, solo delle proprie sezioni | chi consulta i soci |
| Appuntamenti e scadenze inseriti a mano | questa pagina (vedi sotto) | tutti; li inseriscono Amministratore, Presidente, Segretario, Tesoriere |

Le riunioni in preparazione o annullate non compaiono. La pagina mostra i **prossimi 60 giorni**;
ogni voce porta alla scheda corrispondente. **Mese** apre la vista mensile (frecce per i mesi
precedenti e successivi, *Oggi* per tornare al mese corrente); su un telefono il mese è un elenco
dei soli giorni con impegni. Il **cruscotto** mostra i prossimi 14 giorni e le scadenze superate.

## Appuntamenti e scadenze

**Nuovo** (anche con il **+** che compare su un giorno della vista mensile) inserisce:

- **Evento**, **Cerimonia o commemorazione**, **Promemoria**: con giorno, ora (vuota = tutto il
  giorno), eventuale fine (anche su più giorni), luogo e descrizione;
- **Scadenza**: qualcosa da fare entro una data (invio del rendiconto, rinnovo
  dell'assicurazione, adempimenti RUNTS). Si segna **fatta** dalla scheda o con il ✓ nel riquadro
  *Scadenze da fare*; finché non lo è, superata la data compare in rosso nel calendario e nel
  cruscotto. *Riapri* toglie il segno.

**Ogni anno** ripete l'impegno nello stesso giorno. Per una scadenza annuale «fatta» vale per
l'anno in corso: l'anno dopo torna da fare.

Gli appuntamenti non si cancellano: **Annulla** li toglie dal calendario (resta traccia nel registro
attività). Riunioni, ricorrenze e prestiti non vanno inseriti qui: compaiono da soli.

## Sul telefono e sul computer

**Collegamento personale (consigliato).** *Crea il collegamento* genera un indirizzo segreto
che il calendario del telefono o del computer legge da solo ogni poche ore: le riunioni convocate
dopo compaiono senza fare nulla. Il collegamento viene mostrato **una sola volta**: copiarlo
subito (un clic sul campo lo copia) o premere *Apri nell'app Calendario*.

- **iPhone/iPad**: *Apri nell'app Calendario*, oppure Impostazioni → Calendario → Account →
  Aggiungi account → Altro → Aggiungi calendario sottoscritto, e incollare l'indirizzo.
- **Android / Google Calendar**: da un computer, calendar.google.com → *Altri calendari* → **+** →
  *Da URL*; il calendario compare poi anche sul telefono.
- **Outlook**: *Aggiungi calendario* → *Sottoscrivi dal Web*.

Il collegamento vale **come una password**: chi lo conosce legge gli impegni che vede il titolare
(con i suoi stessi permessi). Se viene diffuso per errore, **Nuovo collegamento** ne crea uno
diverso (il vecchio smette subito di funzionare) e **Revoca** lo disattiva. Il programma ne
conserva solo un'impronta, non il collegamento; mostra quando è stato letto l'ultima volta.
Se l'utente viene disattivato, il collegamento smette di funzionare.

**Scarica .ics.** Salva una copia degli impegni da tre mesi fa a un anno avanti, da importare una
volta nel calendario: non si aggiorna da sola.

Gli orari sono esportati in tempo universale: ogni calendario li mostra nell'ora locale. Le
riunioni durano convenzionalmente due ore.
