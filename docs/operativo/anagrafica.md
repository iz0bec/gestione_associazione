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

![L'elenco dell'anagrafica con la ricerca istantanea e i filtri](immagini/anagrafica.jpg)

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

## Codice fiscale assistito

- **Calcola** (sotto il campo, per le persone): calcola il codice da cognome, nome, sesso, data e
  luogo di nascita. Se il campo è vuoto lo compila; se c'è già un codice e non corrisponde ai dati,
  mostra quello calcolato, dice cosa non torna (cognome, nome, sesso, data o luogo) e offre **Usa
  questo**. Il pulsante c'è anche nella registrazione delle domande di iscrizione, dove si sceglie il
  sesso accanto al pulsante.
- **Luogo di nascita**: si scrive il comune italiano (anche in maiuscolo, con apostrofi o nella forma
  bilingue: «SANT'ANTONIO», «Bolzano/Bozen») o lo **stato estero** (es. *Germania*). Per i comuni con
  lo **stesso nome** in province diverse compaiono i pulsanti per scegliere (es. *Castro (BG)*,
  *Castro (LE)*); si può anche scrivere la provincia tra parentesi. Vale il comune com'era alla
  **data di nascita**, anche se poi è stato soppresso, fuso o rinominato.
- Il codice calcolato è quello «teorico». In rari casi l'Agenzia delle Entrate ne ha attribuito uno
  diverso (omocodia o errori storici): **fa fede la tessera sanitaria**. Per questo il programma non
  blocca mai il salvataggio per il nome: segnala soltanto.
- Nella **scheda** di una persona, sotto il codice fiscale, compare un avviso se il codice non è valido
  o non corrisponde ai dati (e, per i soci, se manca), con il codice ricavato dai dati.
- **Codici fiscali** (pulsante nell'elenco dell'anagrafica): le persone con il codice **non valido**,
  **non corrispondente** ai dati o **mancante** (solo per i soci, perché per un contatto della rubrica
  è normale), con il codice calcolato. **Applica** lo sostituisce, dopo conferma; se i dati non
  bastano per il calcolo, **Completa i dati** apre la scheda. Ogni correzione è nel registro attività
  con il valore precedente. Il programma rifiuta un codice già usato da un'altra persona.

## La scheda

![La scheda di una persona](immagini/scheda-anagrafica.jpg)

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

## Privacy: diritti dell'interessato (GDPR)

![Il riquadro Privacy (GDPR) nella scheda della persona](immagini/scheda-gdpr.jpg)

Nella scheda di una persona, riquadro **Privacy (GDPR)**:

- **Esporta tutti i dati** (Amministratore di sistema, Segretario) - per la **richiesta di accesso**
  o di **portabilità** dell'interessato: un archivio ZIP con un **riepilogo in PDF**, lo stesso
  contenuto in **JSON** (formato elaborabile) e l'eventuale foto. Comprende scheda, categorie,
  consensi, utente, iscrizione al libro soci, tessere e quote, domande di iscrizione, cariche,
  presenze alle riunioni, protocolli, comunicazioni ricevute, liste, movimenti di tesoreria, beni
  donati o avuti in prestito.
- **Anonimizza** (solo Amministratore di sistema) - per la **richiesta di cancellazione** o al
  termine del periodo di conservazione. È **irreversibile**: si cancellano nome, recapiti, codice
  fiscale, date, luogo di nascita, foto, note, categorie e liste, i dati personali delle domande di
  iscrizione e il modulo firmato, i nomi e le email nelle copie degli invii. **Restano** i documenti
  ufficiali che vanno conservati per legge (protocolli, verbali, prima nota, ricevute e libro soci
  con il numero) e il registro attività. Si chiede il **motivo** e di scrivere **ANONIMIZZA**.

Non si anonimizza un socio attivo o sospeso (prima si registra la cessazione), una persona collegata
a un utente del programma o un ente. Una scheda anonimizzata non si modifica più.

**Termini di conservazione** (*Sistema → Conservazione dei dati*, Amministratore di sistema): si
indica per quanti **anni** conservare i dati dopo la **cessazione da socio** o, per chi non è socio,
dopo l'**archiviazione** della scheda (predefinito 10; 0 = nessun termine). La pagina elenca le
persone oltre il termine: si selezionano e si anonimizzano in blocco scrivendo **ANONIMIZZA**. Con
**Anonimizzazione automatica** (spenta per impostazione predefinita) lo fa il programma ogni notte.
Sono sempre escluse le **persone decedute** (il GDPR non si applica ai defunti e l'associazione ne
conserva la memoria), chi è collegato a un utente e chi è già anonimizzato.

![I termini di conservazione e le persone oltre il termine](immagini/conservazione.jpg)

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
