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

## Chi può fare cosa

Tutti gli organi consultano idee, progetti e bandi, propongono idee, le valutano e commentano.
Presidente, Segretario e Amministratore decidono priorità e stati, avviano e gestiscono i progetti e
i bandi (requisiti, stato, candidature). Il ruolo
**Progettista** dà le stesse possibilità e si **abbina** al ruolo di chi segue i progetti (per esempio
un consigliere incaricato). Dettagli in [Ruoli](ruoli.md).
