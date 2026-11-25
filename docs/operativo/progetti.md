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

## Chi può fare cosa

Tutti gli organi consultano idee e progetti, propongono idee, le valutano e commentano. Presidente,
Segretario e Amministratore decidono priorità e stati, avviano e gestiscono i progetti. Il ruolo
**Progettista** dà le stesse possibilità e si **abbina** al ruolo di chi segue i progetti (per esempio
un consigliere incaricato). Dettagli in [Ruoli](ruoli.md).
