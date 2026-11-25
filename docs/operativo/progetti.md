<!--
******************************************************
* Progetto:    Gestione Associazione
* Autore:      Bartolomeo Santoro aka IZ0BEC
* Email:       info@iz0bec.info
* Descrizione: Manuale del modulo Progetti: idee e necessità, valutazione, progetti
* Licenza:     CC0 1.0 Universal (pubblico dominio)
* SPDX-License-Identifier: CC0-1.0
******************************************************
-->

# Idee, necessità e progetti

Il modulo accompagna le iniziative con cui l'associazione persegue i propri **scopi statutari**: dalla
raccolta delle idee e delle necessità (anche segnalate da fuori: scuole, comuni, altre associazioni)
alla valutazione, alla decisione del consiglio e alla gestione del progetto fino alla chiusura.

## Finalità statutarie e criteri

In *Idee e necessità → Finalità* si inseriscono le **finalità statutarie** (codice, titolo, testo);
idee e progetti vi si collegano, così si vede a quale scopo risponde ogni iniziativa. L'amministratore
può caricarle in una volta da un file di testo, una per riga nella forma «a) testo»:

```bash
uv run python manage.py importa_finalita articolo2.txt
```

In *Criteri* si definiscono i **criteri di valutazione** con il loro **peso** (1–10). All'installazione
ce ne sono quattro, modificabili: coerenza con le finalità, fattibilità, urgenza, risorse e persone.

## Idee e necessità

**Nuova idea**: titolo, descrizione, bisogno a cui risponde, destinatari, finalità, costo stimato e
**fonte**: *interna* (proposta da un utente o da un organo) o *esterna* (da chi arriva: un soggetto
dell'anagrafica o un testo libero).

Una sollecitazione esterna si registra direttamente:

- dalla **scheda di un protocollo in entrata**, con **Proponi come idea**: oggetto, testo e mittente
  sono proposti e il protocollo resta collegato;
- dalla **posta da protocollare**, con **Idea di progetto**: il messaggio resta collegato (va comunque
  protocollato o scartato).

Le idee sono numerate per anno (`I-2026-001`).

### Valutazione

Ogni utente con il permesso dà un punteggio **da 1 a 5** per ciascun criterio, con un commento: la
media è **pesata** con i pesi dei criteri. Ognuno ha una sola valutazione per idea e la può
modificare. La scheda mostra la media per criterio e quella complessiva; l'elenco permette di
filtrare per stato, finalità, fonte e priorità.

### Decisione

Chi gestisce le idee fissa la **priorità** (alta, media, bassa), facoltativamente con la **delibera**
del consiglio, e lo **stato**: nuova, in valutazione, accantonata (con il motivo). Con **Trasforma in
progetto** l'idea diventa *approvata* e nasce il progetto.

## Progetti

Un progetto nasce da un'idea (titolo, sintesi e finalità proposti; i documenti dell'idea restano
visibili) o da zero, con il **responsabile**, il periodo previsto e, se c'è, la **delibera di avvio**.
È numerato per anno (`P-2026-001`).

### Stati

| Da | A |
|---|---|
| In progettazione | Candidato a un bando, In corso, Accantonato |
| Candidato | Finanziato, Non finanziato |
| Non finanziato | In progettazione (si ripresenta), Accantonato |
| Finanziato | In corso |
| In corso | In rendicontazione, Chiuso |
| In rendicontazione | Chiuso |

Ogni passaggio resta nello **storico** con data, utente, motivo e delibera; *Accantonato* e *Non
finanziato* chiedono il motivo. Un progetto chiuso o accantonato non si modifica più.

### Gruppo, scadenze, documenti

- **Gruppo di lavoro**: utenti del gestionale o persone dell'anagrafica, con il ruolo nel progetto e
  l'indicazione di **volontario**.
- **Scadenze**: compaiono nel **Calendario** finché il progetto è aperto; si segnano come fatte.
- **Documenti**: si allegano file (fino a 20 MB), scaricabili solo da chi ha il permesso.
- **Discussione**: commenti di chi consulta il progetto.

## Progettazione

La scheda del progetto ha cinque schede: **Scheda**, **Quadro**, **Cronoprogramma**, **Partner**,
**Piano economico**. Quadro, partner e piano si modificano finché il progetto è **in progettazione**:
dopo la candidatura restano quelli presentati (le varianti si registreranno con la loro delibera nella
fase di esecuzione). Il cronoprogramma si aggiorna finché il progetto è aperto.

### Quadro

**Obiettivo generale**, **destinatari** e **territorio**; gli **obiettivi specifici** con i **risultati
attesi**; per ciascuno gli **indicatori** misurabili: descrizione, unità di misura, valore iniziale,
**valore atteso** e fonte di verifica (il valore raggiunto si aggiornerà durante l'esecuzione).

### Cronoprogramma

Le **attività** con obiettivo, responsabile, inizio e fine e, se dipende da un'altra, **«dopo
l'attività»** (deve iniziare dopo la sua fine). Il **diagramma a barre** mostra il periodo di ciascuna,
i mesi e le dipendenze tratteggiate; le attività compaiono anche nel **Calendario**.

### Partner

Enti, sezioni e persone dall'**anagrafica**, con il ruolo (capofila, partner, sostenitore, rete), il
contributo al progetto, l'eventuale **cofinanziamento** e se la **lettera di partenariato** è arrivata.

### Piano economico

- **Costi**: voci per categoria (personale, beni, servizi, viaggi, comunicazione, volontariato
  valorizzato, altre spese) come quantità × costo unitario; **spese generali** forfettarie in
  percentuale sui costi diretti.
- **Coperture**: contributo richiesto al bando, cofinanziamento proprio in denaro, altri finanziatori;
  il **cofinanziamento dei partner** viene dalle loro schede e quello **in natura** dal volontariato
  valorizzato.
- **Controlli**: costi e coperture devono equivalersi; con un bando collegato si controllano anche il
  **contributo massimo**, il **cofinanziamento minimo**, le **spese generali** ammesse, i **limiti per
  categoria** e la quota massima **in natura**. I limiti si inseriscono nella scheda del bando
  (spese generali e in natura nel modulo, limiti per categoria nell'elenco dei dati).

### Proposta (scrittura guidata)

La scheda **Proposta** raccoglie i testi da presentare, sezione per sezione. Le sezioni sono quelle del
**formulario del bando**, se nella scheda del bando sono state inserite (titolo, domande o istruzioni,
massimo di caratteri), altrimenti uno **schema predefinito**: contesto e bisogni, coerenza con le
finalità statutarie, obiettivi e risultati, destinatari e territorio, attività e metodologia,
partenariato, esperienza dell'associazione, monitoraggio e valutazione, comunicazione, impatto e
sostenibilità.

Il gestionale **non scrive al posto vostro** (niente IA): per ogni sezione mostra le **domande guida**;
**Proponi dal progetto** compone un testo di partenza dai dati già inseriti (finalità statutarie citate,
obiettivi e risultati, destinatari, attività del cronoprogramma, partner, indicatori), da rivedere; i
**testi della stessa sezione** scritti per altri progetti si possono riusare. Il contatore segnala quando
si supera il **limite di caratteri** del bando. La proposta si modifica finché il progetto è in
progettazione.

### Candidatura

La scheda **Candidatura** riunisce:

- la **verifica prima dell'invio**: sezioni da scrivere o troppo lunghe, quadro incompleto, attività
  oltre la fine prevista, lettere di partenariato mancanti, errori del piano economico, requisiti del
  bando mancanti o da verificare, termine scaduto;
- i **documenti**: la **proposta in PDF** (testi, obiettivi e indicatori, cronoprogramma, partner, piano
  economico) e il **piano economico in Excel**;
- **lettere e dichiarazioni** dai **modelli di stampa** (*Documenti*), indirizzate a un partner o senza
  destinatario, con in più i segnaposto `{{ progetto }}`, `{{ codice_progetto }}`, `{{ bando }}`,
  `{{ finanziatore }}` e `{{ ruolo_partner }}` (per esempio la lettera di partenariato o la dichiarazione
  del legale rappresentante);
- lo **stato**: bando, delibera di approvazione (quella indicata candidando il progetto) e protocollo.

Il percorso: con la verifica a posto si **candida** il progetto dalla sua scheda, con la **delibera**
(il progetto passa a «Candidato» e la proposta si blocca); poi **Protocolla la candidatura** registra un
**protocollo in uscita** verso il finanziatore del bando (scelto dall'anagrafica, con la sua PEC) con la
proposta, il piano e i documenti scelti, e apre la **spedizione** del protocollo per PEC o email, con le
ricevute agganciate come per ogni altro protocollo. Serve anche il permesso di protocollare.

## Esecuzione

Quando il progetto è **finanziato**, **in corso** o **in rendicontazione**, la scheda **Esecuzione**
segue la realizzazione. In alto: attività completate, media degli indicatori raggiunti, costi sostenuti
sui previsti, contributo incassato e da incassare.

- **Centro di costo**: i movimenti di **prima nota** (entrate e uscite) si **imputano** al progetto,
  per intero o in parte; le uscite a una **voce del piano**, le entrate come **contributo del
  finanziatore** (anticipi e saldo) o altra entrata. Il movimento in tesoreria non cambia: l'imputazione
  lo collega soltanto (serve il permesso di consultare la prima nota). Un movimento va a un solo
  progetto.
- **Preventivo e consuntivo** per voce, con la percentuale spesa e lo **scostamento**; i costi senza voce
  a parte.
- **Volontariato**: il registro delle **ore** per persona (dall'anagrafica), data e attività; la
  **tariffa oraria** si indica nel progetto (o vale quella del bando) e valorizza le ore come
  **cofinanziamento in natura**, confrontato con il preventivo.
- **Avanzamento**: attività **completate**, **valore raggiunto** degli indicatori, **eventi** collegati
  (dal modulo Eventi).
- **Varianti**: in esecuzione il piano economico non si modifica liberamente: si **apre una variante**
  (cosa cambia e perché, con la **delibera**), si modifica il piano, si **chiude** la variante. Restano
  il piano prima e dopo.

## Bandi e finanziamenti

In *Bandi* si registrano i bandi e gli avvisi di finanziamento: titolo, **finanziatore** (dall'anagrafica
o scritto a mano), indirizzo del testo, descrizione, **finalità statutarie** a cui risponde, contributo
massimo, **cofinanziamento** richiesto (la quota a carico dell'associazione), apertura, **scadenza della
domanda** ed esito previsto. Gli stati sono: *da valutare*, *interessante*, *partecipato*, *scartato*
(con il motivo). L'elenco mostra di norma i bandi aperti, con i giorni che mancano alla scadenza.

### Requisiti

Nella scheda del bando si elencano i **requisiti di partecipazione**. Ognuno può avere una **verifica
automatica** sui dati del gestionale:

| Verifica | Cosa controlla |
|---|---|
| Coerenza con le finalità statutarie | che il bando sia collegato ad almeno una finalità |
| Iscrizione al RUNTS | il numero di iscrizione nei dati dell'organizzazione |
| Codice fiscale dell'ente, Casella PEC | i dati dell'organizzazione |
| Sede in una provincia / in un comune | la sede dell'organizzazione (parametro: sigle o comuni, separati da virgole) |
| Numero minimo di soci attivi / in regola con la quota | i soci del gestionale (parametro: il numero) |
| Rendiconto dell'anno precedente approvato | l'esercizio chiuso in tesoreria con l'approvazione indicata |

Senza verifica, il requisito si **controlla a mano**. L'esito è *soddisfatto*, *mancante* o *da
verificare*: se un dato non c'è, il gestionale non lo presume e il requisito resta da verificare. Chi
gestisce i bandi può sempre **indicare l'esito a mano** con una nota (per esempio il documento che lo
prova): prevale sulla verifica automatica, e togliendolo si torna a quella.

### Candidatura

Un progetto **in progettazione** si candida dalla sua scheda (*Candida a un bando*) o da quella del
bando (*Candida il progetto*), con l'eventuale delibera: il progetto passa a **Candidato** con il bando
nello storico, e il bando a **Partecipato**. Un bando scaduto o scartato non accetta candidature.

### Scadenze e promemoria

La scadenza della domanda compare nel **Calendario** e, nei 14 giorni precedenti, nel **cruscotto**. Per
i bandi *da valutare* o *interessanti* il gestionale manda un promemoria **7 e 2 giorni prima** (una
volta per soglia; cambiando la scadenza i promemoria ripartono) a chi gestisce i bandi, sul canale
scelto nella pagina **Avvisi** (tipo *Scadenze dei bandi*). Il controllo è nel lavoro giornaliero del
pianificatore; a mano: `manage.py promemoria_bandi`.

## Raccolta automatica dei bandi

Il gestionale può cercare da solo i bandi nuovi e proporli a chi gestisce i bandi, che li **vaglia**:
non entra nulla nel registro senza una persona che lo accolga.

### Fonti

In *Bandi → Fonti* si indicano le fonti sorvegliate:

- **feed RSS o Atom** dei siti che li pubblicano (molti siti WordPress hanno il feed in `/feed/`, e
  per una categoria in `/category/nome/feed/`);
- **pagine web**: si propongono i collegamenti nuovi della pagina (per esempio l'elenco dei bandi di un
  comune o di una fondazione).

Sono ammessi solo indirizzi **https** pubblici. Fra i **portali noti** (verificati) si aggiungono con un
clic: *Regione Basilicata – Avvisi e bandi*, *CSV Basilicata – Bandi* (proponi tutto: pubblica solo
opportunità per il Terzo settore), *Fondazione con il Sud*. Di ogni fonte si vede l'ultimo controllo e
l'esito; **Controlla ora** la legge subito.

### Parole chiave

Una novità è proposta se contiene almeno una **parola chiave** e nessuna **parola esclusa**, senza
distinguere maiuscole, accenti e punteggiatura. Le parole valgono per tutte le fonti; ogni fonte può
aggiungerne di proprie. **Proponi tutto** (per le fonti di soli bandi) ignora le parole chiave ma rispetta
le escluse. *Aggiungi le parole suggerite* inserisce un elenco di partenza (Terzo settore, volontariato,
memoria, storia, cultura, giovani, scuole, legalità, pace…; escluse: concessioni demaniali, forniture,
affidamenti, personale della Regione, imprese, libri di testo, concorsi, master), da adattare.

### Da vagliare

*Bandi → Da vagliare* elenca le novità con fonte, data e parole trovate. **Accogli** registra il bando
(*da valutare*, con il link e la fonte come finanziatore) e apre il modulo per completarlo; le altre si
**scartano** in blocco. Una novità già vista (stesso link) non si ripropone.

La raccolta gira ogni notte con il pianificatore (`manage.py raccogli_bandi`) e avvisa chi gestisce i
bandi, con il tipo di avviso *Scadenze dei bandi*, quando ci sono novità.

## Assistente (connettore MCP)

Il gestionale **non contiene IA**. Il **connettore MCP** (Model Context Protocol) permette a un assistente
scelto dall'associazione di **leggere** idee, bandi, progetti, finalità e criteri e di aiutare a
confrontare e motivare le valutazioni: le **decisioni restano alle persone**. Si consiglia un **modello
locale con Ollama**: i dati restano nella rete dell'associazione.

- È **spento di norma**: lo attiva l'amministratore di sistema in *Progetti → Assistente (MCP)*.
- Ognuno crea i propri **token personali** (mostrati una volta sola, si possono revocare e far scadere):
  il token vale con i **permessi del suo utente**, nel database resta solo l'impronta.
- **Sola lettura**: dati dell'associazione (numeri aggregati: soci attivi e in regola, RUNTS, PEC,
  rendiconto), finalità e criteri, elenco e scheda di idee, bandi (con i requisiti verificati) e
  progetti (quadro, attività, partner, piano con i controlli, proposta, verifica della candidatura),
  bandi da vagliare.
- **Nessun dato personale dei soci**: le persone fisiche compaiono come «persona (riservato)», i nomi
  scritti a mano nelle fonti delle idee non si espongono, i responsabili delle attività nemmeno.
- **Commenti firmati «[Assistente]»** nella discussione di idee e progetti solo se l'amministratore li
  ammette **e** il token li consente; non cambiano nient'altro.
- Ogni chiamata è nel **registro attività** (strumento e argomenti).

Collegamento (indirizzo `…/progetti/mcp/`, trasporto *MCP Streamable HTTP*, autenticazione *Bearer*):

- **Ollama con Open WebUI** (0.6.31 o successiva): *Impostazioni di amministrazione → External Tools →
  aggiungi*, tipo **MCP (Streamable HTTP)**, URL del connettore, autenticazione **Bearer** con il token;
  serve un modello con supporto agli strumenti.
- **Ollama con ollama-mcp-bridge**: nel file di configurazione un server con `url` e
  `headers: {"Authorization": "Bearer …"}`.
- **Claude Code**: `claude mcp add --transport http gestionale <indirizzo> --header "Authorization: Bearer <token>"`.
- **Claude Desktop**: con `npx mcp-remote <indirizzo> --header "Authorization: Bearer <token>"`.

La pagina mostra gli stessi esempi con l'indirizzo dell'installazione. Il client deve raggiungere il
gestionale in HTTPS con un certificato che riconosce.

## Chi può fare cosa

Tutti gli organi consultano idee, progetti e bandi, propongono idee, le valutano e commentano.
Presidente, Segretario e Amministratore decidono priorità e stati, avviano e gestiscono i progetti e
i bandi (requisiti, stato, candidature). Il ruolo
**Progettista** dà le stesse possibilità e si **abbina** al ruolo di chi segue i progetti (per esempio
un consigliere incaricato). Dettagli in [Ruoli](ruoli.md).
