<!--
******************************************************
* Progetto:    Gestione Associazione
* Autore:      Bartolomeo Santoro aka IZ0BEC
* Email:       info@iz0bec.info
* Descrizione: Anagrafica: persone, enti, categorie, consensi
* Licenza:     CC0 1.0 Universal (pubblico dominio)
* SPDX-License-Identifier: CC0-1.0
******************************************************
-->

# Anagrafica

L'anagrafica raccoglie **tutte le persone e gli enti** con cui l'associazione ha rapporti:
soci, autorità, amici della sezione, altre associazioni, sezioni consorelle, enti pubblici,
fornitori. Ogni persona è inserita **una volta sola** e viene riutilizzata da tutti i moduli
(soci, protocollo, assemblee, comunicazioni).

## Cercare

**Anagrafica** nel menu. La casella di ricerca filtra mentre si scrive: nome, cognome,
denominazione, email, comune, qualifica o codice fiscale completo. Più parole restringono
la ricerca (es. `rossi avigliano`). Accanto si filtra per tipo, categoria e stato
(attivi, archiviati, tutti).

## Inserire una persona o un ente

1. **Nuovo** in alto a destra.
2. Scegliere **Persona fisica** o **Ente / organizzazione**: il modulo mostra i campi adatti.
3. Per una persona basta il **cognome**; per un ente la **denominazione**. Il resto è facoltativo.
4. **Codice fiscale**: se inserito, *sesso, data e luogo di nascita si compilano da soli* quando
   lasciati vuoti; se invece sono già compilati e non corrispondono, l'applicazione lo segnala.
   Lo stesso codice fiscale non può appartenere a due schede.
5. **Qualifica**: la carica o il ruolo pubblico (es. «Sindaco di Avigliano»): compare negli elenchi
   e nelle intestazioni delle lettere.
6. **Categorie**: una o più (es. *Socio* e *Amico della sezione*).
7. **Data di decesso**: se indicata, la persona resta nello storico ma non riceve più auguri né comunicazioni.
8. **Salva**.

## La scheda

Mostra dati, recapiti, categorie, note, chi l'ha inserita e modificata. Chi ha accesso al
registro attività vede anche la **storia delle modifiche** (passando il mouse sul nome di un campo
compaiono il valore precedente e quello nuovo).

## Consensi privacy

Nel riquadro **Consensi privacy** della scheda si registra, per ogni finalità (comunicazioni
associative, auguri, pubblicazione di foto, comunicazione a enti collegati), se il consenso è
stato **prestato** oppure **negato/revocato**, la data e la modalità (es. «modulo cartaceo»).
Una revoca si registra aggiungendo un nuovo consenso con la casella *Prestato* non spuntata:
lo storico resta visibile.

## Archiviare

Chi non è più in rapporto con l'associazione si **archivia** (pulsante *Archivia* nella scheda):
non compare più negli elenchi, ma resta nei documenti già registrati. Si può ripristinare
in qualsiasi momento (stato *Archiviati* nel filtro → scheda → *Ripristina*).
Le schede non si cancellano: i documenti ufficiali devono poter fare riferimento ai soggetti.

## Esportare

**Esporta CSV** scarica l'elenco **con i filtri applicati** (file apribile con Excel o LibreOffice,
separatore `;`). Ogni esportazione viene registrata nel registro attività: i dati esportati
sono dati personali, da conservare con cura e cancellare quando non servono più.
