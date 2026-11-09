<!--
******************************************************
* Progetto:    Gestione Associazione
* Autore:      Bartolomeo Santoro aka IZ0BEC
* Email:       info@iz0bec.info
* Descrizione: Manuale operativo del modulo Soci e tesseramento
* Licenza:     CC0 1.0 Universal (pubblico dominio)
* SPDX-License-Identifier: CC0-1.0
******************************************************
-->

# Soci e tesseramento

Il modulo tiene il **libro soci** (art. 15 D.Lgs. 117/2017), il **tesseramento annuale** con le
**tessere fisiche** ricevute dalla sede centrale, le quote e le **ricevute**, e raccoglie le
**domande di iscrizione**, anche dal sito.

Un socio è sempre una **persona dell'anagrafica**: i dati personali (indirizzo, recapiti,
codice fiscale) si modificano dalla scheda anagrafica e valgono ovunque.

## Concetti

![Il libro soci](immagini/soci.jpg)

| | |
|---|---|
| **Numero di iscrizione** | Progressivo unico del libro soci, assegnato automaticamente all'ammissione. Non si modifica e non si riusa, nemmeno dopo la cessazione. |
| **Sezione** | Sezione territoriale del socio. Un'associazione singola ne ha una sola, e la scelta non compare nei moduli. In una federazione soci e tessere fisiche sono divisi per sezione, e ogni utente può essere limitato alle proprie sezioni. |
| **Matricola nazionale** | Numero del socio nel registro nazionale, se assegnato. È diversa dal numero di iscrizione locale. |
| **Tipologia** | Ordinario, sostenitore, onorario... La quota di ogni anno è fissata nel **listino** (0 = esente). |
| **Listino** | Per ogni anno contiene il **costo d'acquisto** di una tessera dalla sede centrale e il **prezzo di distribuzione**, cioè la quota chiesta al socio, per ogni tipologia. Si fissa all'inizio dell'anno contabile. |
| **Stato** | *Attivo*, *sospeso* (non riceve la tessera, resta nel libro) o *cessato* (con data e causa). |
| **Tessera fisica** | Tessera prestampata e numerata dalla **sede centrale**, ricevuta a lotti. È *disponibile*, *attribuita* a un socio, *annullata* (deteriorata, errata), *smarrita* o *restituita*. |
| **Tesseramento** | Uno per socio e per anno, con la quota e la tessera fisica attribuita (il suo numero è quello stampato). La quota può essere *da pagare*, *pagata*, *esente*; il tesseramento può essere *annullato*. |
| **Ricevuta** | Numerata per anno di incasso (es. `2026/0007`), assegnata quando si registra il pagamento. |
| **In regola / moroso** | In regola = ha la tessera dell'anno pagata. Moroso = socio attivo senza tessera pagata (gli esenti non sono morosi). |

## Iscrivere un nuovo socio

1. **Soci → Nuovo socio**, cercare la persona per cognome, nome o codice fiscale.
2. Se non c'è, crearla prima in **Anagrafica** (dalla scheda si usa poi **Iscrivi**).
3. Nella pagina di ammissione indicare la **sezione** (solo con più sezioni), la **tipologia**, la
   **matricola nazionale** se già assegnata, la **data** e, se c'è, la **delibera**
   (es. «Consiglio direttivo del 12/01/2026, verbale n. 3»). Con la casella *Rilascia subito la
   tessera* viene creata anche la tessera dell'anno, da pagare.

All'iscrizione la persona riceve la categoria **Socio** in anagrafica. Non si possono iscrivere
enti, persone archiviate o decedute, né chi è già nel libro soci.

## Scheda del socio

![La scheda del socio con cariche, tessere e quote](immagini/scheda-socio.jpg)

Mostra i dati di iscrizione, le tessere di tutti gli anni, la situazione della quota corrente e
la storia delle operazioni. Le **cariche sociali** in corso (es. *Presidente · CD*) compaiono accanto
al nome; il riquadro *Cariche sociali* elenca anche quelle concluse, con date e atto di nomina
(le cariche si registrano negli [Organi sociali](organi.md#cariche) e compaiono anche nella scheda
dell'anagrafica). Dai pulsanti in alto:

- **Modifica**: sezione, matricola, tipologia, data e delibera di ammissione, note, **foto** (ogni
  cambio è registrato);
- **Sospendi / Riattiva**;
- **Cessazione**: data, causa (dimissioni, decesso, esclusione, morosità, altro) e note.
  Il socio resta nel libro con il suo numero; perde la categoria *Socio*. Per il **decesso** la data
  viene riportata anche nella scheda anagrafica, così la persona esce da auguri e comunicazioni.
- **Riammetti** (socio cessato): torna attivo con **lo stesso numero**.

## Tessere dalla sede centrale

**Tesseramento → Tessere dalla sede centrale**.

1. Quando arrivano le tessere, **Carico tessere**: anno, primo e ultimo numero stampati, eventuale
   **serie** (lettere prima del numero) e numero di **cifre** (per gli zeri iniziali, es. 6 → `000123`),
   data, fornitore, riferimento (ordine, documento di trasporto, protocollo) e **costo per tessera**
   dovuto alla sede centrale. Se i numeri non sono consecutivi si registra un carico per ogni blocco.
   Un numero già caricato per lo stesso anno viene rifiutato.
2. La pagina mostra la **giacenza**: tessere ricevute, disponibili, attribuite, fuori uso e restituite,
   con il costo complessivo (le restituite non si contano), e l'elenco tessera per tessera con il socio.
3. Una tessera non attribuita si può segnare **annullata** (deteriorata, stampata male), **smarrita**
   o **restituita** alla sede centrale, sempre con il motivo; per errore si rimette *disponibile*.
4. **Elenco tesserati (CSV)**: numero di tessera e dati dei soci tesserati nell'anno, da inviare
   alla sede centrale.

## Attribuire le tessere

- **Al rinnovo annuale**: con la casella *Attribuisci subito le tessere disponibili* ogni socio
  rinnovato riceve la prima tessera libera, in ordine di numero socio. Se le tessere non bastano,
  i rimanenti restano *senza tessera*.
- **Dopo** (es. arriva un nuovo lotto): in *Tesseramento* compare l'avviso con i soci senza tessera e
  il pulsante **Attribuisci** (in ordine di numero socio o di cognome); il filtro *Senza tessera* li elenca.
- **Singolarmente**: pulsante **Attribuisci** sulla riga del tesseramento, indicando il **numero
  stampato** sulla tessera consegnata (con o senza serie e zeri iniziali) o lasciando vuoto per la prima
  disponibile.
- Annullando un tesseramento la tessera fisica diventa *annullata*; se non era stata consegnata si
  spunta *rimettila tra le disponibili* e potrà essere data a un altro socio.

## Quote e ricevute

![Il tesseramento dell'anno](immagini/tesseramento.jpg)

- **Tesseramento singolo**: dalla scheda del socio, pulsante **Tessera**: anno, quota (proposta
  quella della tipologia, modificabile), tessera fisica (*prima disponibile*, *numero indicato* o
  *da attribuire in seguito*). Chi ha il permesso di incasso può segnare subito *Quota incassata ora*.
- **Incasso**: pulsante **Incassa** (scheda del socio o pagina Tesseramento). Si indicano data,
  importo, metodo (contanti, bonifico, POS) e un riferimento (es. CRO). Viene assegnato il numero di
  ricevuta.
- **Incasso di più quote insieme** (Tesoriere e Amministratore): *Tesseramento → Incasso quote*
  elenca le quote da pagare dell'anno; si spuntano (o *seleziona tutte*) e si indicano una sola volta
  data, metodo e riferimento (es. «assemblea del 15/03»). Ogni quota mantiene il suo importo, riceve
  la sua ricevuta numerata ed entra in prima nota; una quota già pagata nel frattempo viene
  segnalata senza bloccare le altre.
- **Ricevuta**: pulsante **Ricevuta** su ogni tessera pagata, in PDF con l'intestazione dell'ente,
  da stampare, firmare o inviare.
- **Annullamento**: pulsante ✕ con il motivo obbligatorio. Il tesseramento resta visibile come
  annullato e la ricevuta non viene riutilizzata; poi si può rifare il tesseramento.

## Tessera digitale e verifica

![La tessera digitale (fronte); sul retro c'è il QR di verifica](immagini/tessera-digitale.jpg)

La tessera vera resta quella **prestampata dalla sede centrale** e consegnata a mano. In più, per
ogni tessera attribuita, nella scheda del socio:

- **Tessera** apre la **tessera digitale** in PDF, in formato carta (fronte con ente, anno, titolare,
  numero di socio, sezione e numero di tessera; retro con un **QR di verifica**);
- **✈ (invia)** prepara un'email **in bozza** al socio con la tessera digitale allegata, da
  controllare e confermare in Comunicazioni (modello *Tessera digitale*). I soci non accedono al
  programma: la tessera la ricevono così.

**Verifica.** Chi inquadra il QR, o inserisce **numero della tessera e cognome** nella pagina
`/verifica-tessera/` (c'è un riquadro anche nella pagina pubblica), vede solo se la tessera è
**valida** - dell'anno in corso, non annullata, quota versata (o esente), titolare socio attivo - con
nome, anno e sezione del titolare: nessun altro dato. Le ricerche per numero e cognome sono
limitate a 20 l'ora per indirizzo; il codice nel QR è casuale e non si ricava dal numero.

![La verifica pubblica di una tessera](immagini/verifica-tessera.jpg)

## Rinnovo annuale

![L'incasso delle quote in blocco](immagini/incasso-quote.jpg)

**Tesseramento → Rinnovo annuale**: scelto l'anno, mostra i soci attivi non ancora rinnovati e
le tessere fisiche disponibili; alla conferma crea il tesseramento per tutti (quota da pagare della
loro tipologia) e, se richiesto, attribuisce le tessere. Gli incassi si registrano poi man mano.

La pagina **Tesseramento** riassume per l'anno scelto: tessere rilasciate e pagate, totale
incassato e da incassare, soci non in regola e soci ancora senza tessera.

## Morosi

**Soci**, filtro *Quota: non in regola* (con l'anno accanto): elenco dei soci attivi senza la
tessera pagata. Si può esportare in CSV dal menu *Stampa ed esporta*. Lo stesso dato è sul cruscotto.

### Promemoria di rinnovo

**Tesseramento → Promemoria di rinnovo** (Amministratore di sistema, Segretario e Tesoriere li
impostano; il Presidente li consulta). Nelle **date dell'anno** indicate (es. `15/01, 01/03, 15/04,
01/06`), dopo l'**ora** scelta, il programma scrive per email ai soci non in regola con la quota
dell'anno, con l'**importo dovuto** (quello della tessera già rilasciata e non pagata, altrimenti
la quota del listino per la tipologia) e il numero di tessera se c'è. Sono **spenti** dopo
l'installazione: si attivano con la spunta *Attivo*.

- Esclusi gli esenti (quota 0), i cessati, i deceduti e chi non ha l'email: la pagina indica
  quanti soci non in regola sono **senza email**, da contattare in altro modo.
- Nessuno riceve il promemoria due volte nello stesso giorno.
- **Prepara ora il promemoria** crea subito un invio **in bozza** con tutti i destinatari: lo si
  controlla e lo si conferma in *Comunicazioni*, come ogni altro invio.
- Il testo è il modello *Promemoria di rinnovo della quota* (Comunicazioni → Modelli), con i
  segnaposto `{{ anno_quota }}`, `{{ importo }}` e `{{ tessera }}`.

Il promemoria è una comunicazione istituzionale (non serve un consenso specifico). Per l'invio
automatico serve il pianificatore attivo sul server.

## Domande di iscrizione

La domanda ha **gli stessi campi e le stesse dichiarazioni del modulo di richiesta di adesione e
consenso (Allegato A)**, nello stesso ordine:

1. dati personali e recapiti: nato/a a, il, residenza, telefono, cellulare, email, codice fiscale;
2. presa visione dello Statuto e del Regolamento, con gli articoli richiamati;
3. **chiede** di essere iscritto/a alla sezione indicata;
4. informazioni particolari, con risposta SI/NO (es. iscrizione all'Associazione Decorati di Medaglia
   d'Oro);
5. consensi: trattamento dei dati personali (**obbligatorio**), trattamento dei dati «particolari»,
   uso dell'immagine. L'informativa si apre sotto i consensi.

I testi del modulo si impostano in *Sistema → Organizzazione → Modulo di richiesta di adesione*:
intestazione, articoli dello statuto, dichiarazione SI/NO, piè di pagina e informativa.

- **Su carta**: *Domande di iscrizione → Modulo in bianco* stampa l'Allegato A da compilare a mano.
  Con **Registra domanda** si copiano poi i dati del modulo firmato. Qui l'email è facoltativa, e c'è
  la tipologia (uso interno).
- **Dal sito**: se attivato in *Sistema → Organizzazione* (casella *Domande di iscrizione online*),
  il modulo è pubblico all'indirizzo **`/iscrizione/`** dell'applicazione e si può collegare dal sito
  dell'associazione. Qui l'email è obbligatoria, per poter rispondere.
- Dalla domanda, **Modulo da firmare (PDF)** stampa l'Allegato A già compilato con i dati inseriti,
  da far firmare al richiedente.

Le domande in attesa compaiono sul cruscotto. Nella domanda:

- **Accogli**: si scelgono tipologia, data e delibera. Se in anagrafica esiste già una persona con lo
  stesso codice fiscale viene usata quella scheda (l'avviso lo segnala), altrimenti viene creata.
  La persona viene iscritta, riceve il numero e, se richiesto, la tessera. In anagrafica vengono
  registrati i consensi della domanda: trattamento, dati particolari, immagine e comunicazioni
  associative, che rientrano nelle finalità dell'informativa. La risposta SI/NO passa sulla scheda
  del socio.
- **Respingi**: con la motivazione obbligatoria.

L'esito resta sulla domanda (data, utente, motivazione). Comunicare l'esito al richiedente è per ora
compito della segreteria; l'invio automatico arriverà con il modulo *Comunicazioni*.

Il modulo pubblico è protetto dagli invii automatici (vedi il manuale di sistema, *Sicurezza*):
se qualcuno segnala di non riuscire a inviarlo, deve ricaricare la pagina e riprovare dopo qualche minuto.

## Richiesta di adesione firmata

Nella scheda del socio, il riquadro **Richiesta di adesione firmata** mostra il modulo firmato
direttamente nella pagina. Si può sfogliare, ingrandire, stampare, oppure aprire in un'altra
scheda con **Apri**.

- **Carica**: un PDF (ad esempio la scansione), oppure le **foto delle pagine** fatte con il telefono
  (JPEG o PNG, anche più di una), che vengono unite in un unico PDF. Massimo 20 MB.
- **Sostituisci**: sostituisce il file. Il caricamento e la sostituzione restano nella storia, con
  l'impronta del file.
- **Modulo da firmare**: stampa l'Allegato A già compilato con i dati del socio, utile per chi non ha
  ancora il modulo firmato in archivio, ad esempio i soci importati dal registro nazionale.

Il modulo firmato si vede solo con l'accesso al libro soci (e, in una federazione, solo per le
proprie sezioni). Ogni consultazione è registrata.

## Stampe ed esportazioni

| Stampa | Dove | Chi |
|---|---|---|
| **Libro soci** (PDF, A4 orizzontale, tutti gli iscritti compresi i cessati) | Soci → Stampa ed esporta | presidente, segretario, amministratore |
| **Elenco filtrato** (CSV per Excel, con sezione e matricola) | Soci → Stampa ed esporta | come sopra |
| **Per un'altra installazione** (Excel di scambio, vedi sotto) | Soci → Stampa ed esporta | come sopra |
| **Ricevuta** (PDF) | tessera pagata | tutti i ruoli che vedono le tessere |

Ogni stampa ed esportazione è registrata nel registro attività.

### Scambio dei soci fra installazioni (federazione e sezioni)

Quando la federazione e le sezioni usano ciascuna la propria installazione, l'elenco dei soci si
tiene allineato **nei due sensi** con un file Excel:

1. nell'installazione di partenza, *Soci*, filtro sulla **sezione** (e l'anno nel filtro *Quota*,
   se non è l'anno in corso), poi **Stampa ed esporta → Per un'altra installazione (Excel)**;
2. nell'installazione di arrivo, *Sistema → Importa soci*, si carica il file così com'è: le colonne
   sono le stesse dell'importazione dal registro nazionale, più **Data pagamento**. Conviene
   spuntare **Tieni conto della colonna «Valido»**.

Il file contiene, per ogni socio - **cessati compresi**, qualunque sia il filtro sullo stato -:
anagrafica, sezione (nome e codice), matricola, tipologia, date di ammissione e cessazione con la
**causa**, numero di tessera dell'anno e dell'anno precedente, **Valido** (SI = quota versata o
esente, NO = da versare) e **data del pagamento**. All'importazione:

- i soci nuovi vengono iscritti, le **tessere** attribuite con il loro numero, le **quote** segnate
  come incassate alla data del pagamento (incassi avvenuti altrove: niente ricevuta né prima nota);
- le **cessazioni** vengono registrate con data e causa (per un decesso anche la data di decesso
  nella scheda); un socio cessato in questa installazione ma attivo nel file **non viene
  riattivato**: è segnalato nel rapporto;
- dei soci già presenti si **completano i dati anagrafici vuoti**; quelli diversi **non vengono
  sovrascritti** e sono segnalati nel rapporto, da sistemare a mano dove è giusto;
- la sospensione di un socio non passa da un'installazione all'altra.

## Tipologie

**Tesseramento → Tipologie**. Alla prima installazione ci sono *Ordinario*, *Sostenitore* e
*Onorario*. La **quota di riferimento** di ogni tipologia serve solo come proposta per i nuovi
listini. La quota effettiva di un anno è quella del listino. Una tipologia non più usata si
disattiva (non si cancella).

## Listino del tesseramento

**Tesseramento → Listino {anno}** (tesoriere, amministratore). Per ogni anno si fissano:

- il **costo d'acquisto** di una tessera dalla sede centrale. Viene proposto quando si registra un
  carico di tessere: si può lasciare vuoto e il carico prende quello del listino;
- il **prezzo di distribuzione** (la quota annuale) per ogni tipologia. Viene proposto al rilascio
  delle tessere e nel rinnovo annuale.

Il listino si crea da solo all'**apertura dell'esercizio** in tesoreria, copiando l'anno precedente,
e va confermato o corretto. Finché non è fissato, la pagina del tesseramento lo segnala. Cambiare il
listino non modifica le tessere già rilasciate né i carichi già registrati.

## Importare dal registro nazionale

**Sistema → Importa soci** (amministratore, segretario). Carica l'estratto del registro soci
nazionale in Excel (`.xlsx`) o CSV. Il formato `.xls` di Excel 97-2003 va prima salvato come
`.xlsx`.

1. Caricare il file e scegliere:
   - la **sezione** per le righe senza colonna sezione (con una sola sezione è già scelta);
   - la **tipologia predefinita** per le righe senza tipologia o con una tipologia sconosciuta;
   - se **creare le sezioni** del file non ancora registrate;
   - se **spostare** nella sezione del registro i soci già presenti in un'altra sezione;
   - l'**anno** per cui attribuire i numeri di tessera del file (facoltativo; vale solo per le
     tessere fisiche già caricate).
2. Premere **Anteprima**. Si vede, riga per riga, cosa succederà: *nuovo*, *aggiornato*,
   *invariato* o *errore*, con le note. **Nulla viene modificato.**
3. Premere **Esegui l'importazione**. Le righe con errori vengono saltate e le altre importate.

Anteprima ed esecuzione girano in sottofondo: una finestra mostra l'avanzamento («riga 258 di 588 ·
44%») e si chiude da sola alla fine, mostrando il rapporto. Con file grandi possono servire alcuni
minuti; l'importazione prosegue anche se la pagina viene chiusa, e riaprendo lo stesso indirizzo si
ritrova l'avanzamento.

Il file **«Gestione Registro Soci»** esportato dal registro nazionale (di una sezione o di tutta la
federazione) si carica così com'è. Ecco cosa si ricava:

| Colonna del registro | Cosa diventa |
|---|---|
| Sezione | sezione del socio, riconosciuta **per comune** (vedi sotto); se manca si crea, con l'opzione |
| Cognome, Nome, Luogo e Data di nascita, CodiceFiscale, Indirizzo, CAP, Città, PR, Email | scheda anagrafica (nomi e luoghi scritti in maiuscolo diventano «Rionero in Vulture») |
| Telefono | separato in telefono fisso e cellulare |
| Data di ammissione a socio | data di ammissione nel libro soci |
| Numero tessera, Anno sociale, Data tessera | tesseramento dell'anno con la tessera attribuita e la data di rilascio |
| Numero tessera anno 2025 | tesseramento dell'anno precedente |
| Data di annullamento iscrizione | cessazione del socio con quella data (con l'opzione, attiva in partenza) |
| Codice incarico socio ordinario | annotato nelle note del socio (es. «Presidente») |
| Regione, Federazione, Scheda completa, Valido | ignorate |

Le tessere indicate dal registro e non ancora caricate vengono aggiunte al carico **«Registro soci
nazionale»** dell'anno e della sezione, con il costo d'acquisto del listino.

Per le **quote** dei tesseramenti importati si sceglie al momento dell'importazione:

- **da incassare**: compaiono tra i morosi finché non si registra l'incasso, con ricevuta e prima nota;
- **già incassate**: risultano pagate alla data della tessera, *incassate fuori dall'applicazione*.
  Non hanno ricevuta e non vanno in prima nota, perché gli incassi sono avvenuti prima.

**Colonna «Valido».** Nel registro nazionale indica il socio **validato**, cioè attivo e in regola.
Spuntando *Tieni conto della colonna «Valido»* la scelta sulle quote vale riga per riga per l'anno
sociale del file:

- **validato** (sì, X, 1, vero): la quota risulta già incassata, anche se la tessera era già stata
  importata in precedenza;
- **non validato** (no, 0, falso): la quota resta da incassare, con l'annotazione *non validato nel
  registro* nel rapporto;
- **cella vuota**: vale la scelta generale (da incassare o già incassate).

Senza la spunta la colonna è ignorata. Non riguarda la tessera dell'anno precedente.

I codici fiscali non validi non vengono usati per riconoscere la
persona, ma restano nelle note della scheda per poterli correggere.

**Come si riconosce la sezione.** Il valore della colonna «Sezione» del file (es. «RIONERO IN
VULTURE») si confronta, a scelta, con:

- il **comune** delle sezioni (predefinito): poiché ogni comune ha una sola sezione è il confronto più
  sicuro, e non dipende da come è stato scritto il nome («Sezione Rionero», «ANCR Rionero»...).
  Maiuscole, accenti e una provincia scritta dopo («Rionero in Vulture, PZ») non contano;
- il **nome** della sezione, anche se scritto diversamente («AVIGLIANO» e «ANCR Sezione di Avigliano»);
- il **codice** della sezione (o la colonna «Codice sezione», se il file ce l'ha).

Si considerano solo le sezioni **attive**. L'anteprima elenca per ogni valore del file la sezione
scelta, o il motivo per cui non è stata abbinata (nessuna sezione con quel comune, oppure più di una).

Per altri formati le colonne sono riconosciute dalle intestazioni, anche se il file ha righe di
titolo sopra:
cognome e nome (o nominativo), codice fiscale, matricola, sesso, data e luogo di nascita, indirizzo,
CAP, comune, provincia, email, telefono, cellulare, sezione (nome o codice), tipologia, data di
iscrizione, numero di tessera. Le colonne non riconosciute sono elencate e ignorate.

Regole:

- la persona si riconosce per **codice fiscale**, poi per **matricola**, poi per **cognome, nome e
  data di nascita**. Chi non c'è viene inserito in anagrafica e iscritto al libro soci;
- delle schede già presenti si **completano solo i dati mancanti**. Ciò che è già registrato qui
  non viene sovrascritto, e le differenze (email, comune, indirizzo, sezione, matricola) sono
  segnalate nelle note;
- un codice fiscale non valido viene ignorato, con una nota;
- si può **ripetere** l'importazione a ogni aggiornamento del registro, senza creare doppioni;
- l'esito elenca anche i **soci attivi assenti dal file**. Non vengono toccati: verificare se sono
  cessati;
- un utente limitato ad alcune sezioni importa solo i soci di quelle sezioni.

Per file molto grandi l'amministratore di sistema può usare il comando
`importa_registro_soci` (vedi [Configurazione](../sistema/configurazione.md#comandi)).
