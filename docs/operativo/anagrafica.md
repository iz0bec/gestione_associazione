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

## Foto

Nel modulo di inserimento e modifica, alla voce **Foto**, si carica la foto della persona o il logo
dell'ente (JPEG, PNG o WebP, fino a 15 MB). La foto:

- viene **ridotta** (600 pixel di lato) e **ripulita dai dati nascosti** (posizione GPS,
  modello del telefono, data dello scatto);
- prende un nome casuale e si vede **solo da chi accede** all'anagrafica o al libro soci. Non è
  mai raggiungibile da un indirizzo pubblico;
- compare negli elenchi (al posto delle iniziali) e nelle schede di anagrafica e soci.

Per toglierla basta spuntare **Togli la foto attuale**. Prima di pubblicare o usare la foto di una
persona fuori dall'archivio serve il suo consenso (finalità *Pubblicazione di foto e video*).

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

## Rubrica del telefono e del computer (vCard)

**Esporta in rubrica** scarica le schede dell'elenco **con i filtri applicati** in un file
`.vcf`, il formato delle rubriche: aprendolo sul telefono, o importandolo in Google Contatti,
iCloud, Outlook o Thunderbird, i contatti vengono aggiunti con nome (e titolo), email, PEC,
cellulare, telefono, indirizzo, data di nascita, qualifica e categorie; per i soci attivi è
indicato il numero di socio. Le persone decedute sono escluse; note e codice fiscale **non** sono
esportati. Dalla scheda, il pulsante **vCard** scarica il solo contatto. Come per il CSV, ogni
esportazione è annotata nel registro attività.

**Importa da rubrica** (Amministratore di sistema, Segretario) fa il percorso inverso: si carica
il file `.vcf` esportato dalla rubrica (vCard 2.1, 3.0 o 4.0, anche con molti contatti) e si
sceglie, se serve, una categoria da assegnare a tutti (es. «Autorità»). Prima viene mostrata
un'**anteprima**, senza salvare nulla:

- **nuova**: il contatto non c'è e viene creato (persona, o ente se ha solo il nome
  dell'organizzazione);
- **da completare**: il contatto è già in anagrafica (stessa email, stesso telefono o stesso nome
  e cognome) e se ne riempiono **solo i campi vuoti**: nulla viene sovrascritto;
- **invariata**: già presente con gli stessi dati;
- **ambigua**: più schede corrispondono (es. due omonimi), il contatto viene saltato e va
  sistemato a mano;
- **scartata**: manca il nome.

Telefoni ed email in più rispetto ai campi della scheda finiscono nelle note; dati malformati
(CAP non di 5 cifre, email non valide, province non in sigla) sono ignorati. Le categorie del
contatto vengono assegnate se esistono già con lo stesso nome. Con **Conferma l'importazione**
le schede sono salvate e l'operazione è annotata nel registro attività. Reimportare lo stesso
file non crea doppioni.
