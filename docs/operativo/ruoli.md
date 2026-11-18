<!--
******************************************************
* Progetto:    Gestione Associazione
* Autore:      Bartolomeo Santoro aka IZ0BEC
* Email:       info@iz0bec.info
* Descrizione: Ruoli e permessi
* Licenza:     CC0 1.0 Universal (pubblico dominio)
* SPDX-License-Identifier: CC0-1.0
******************************************************
-->

# Ruoli e permessi

Ogni utente ha uno o più **ruoli**; il ruolo decide cosa si vede e cosa si può fare.
I ruoli li assegna l'amministratore da **Sistema → Utenti e ruoli** (vedi [Utenti e ruoli](utenti.md)),
dove si sceglie anche per quali ruoli il secondo fattore è obbligatorio.

| Ruolo | Anagrafica | Esporta anagrafica (CSV, rubrica) | Importa da rubrica | Dati organizzazione, aspetto, configurazione guidata | Registro attività | Utenti e ruoli, servizi di posta |
|---|---|---|---|---|---|---|
| Amministratore di sistema | consulta, inserisce, modifica, archivia | sì | sì | modifica | consulta | **gestisce** |
| Presidente | consulta, inserisce, modifica, archivia | sì | - | - | consulta | - |
| Segretario | consulta, inserisce, modifica, archivia | sì | sì | modifica | - | - |
| Addetto protocollo | consulta, inserisce, modifica, archivia | - | - | - | - | - |
| Tesoriere | consulta | - | - | - | - | - |
| Consigliere | consulta | - | - | - | - | - |
| Revisore | consulta | - | - | - | consulta | - |

### Presidente di sezione

Per chi guida una **sezione** in un'associazione con più sezioni (es. una federazione provinciale).
Va sempre assegnato insieme alla sua sezione (*Sistema → Utenti e ruoli → Sezioni*):

- **anagrafica**: consulta, inserisce, modifica, archivia;
- **soci, tesseramento e domande di iscrizione della sola propria sezione**: ammissioni, modifiche,
  cessazioni, tesseramenti, tessere fisiche, valutazione delle domande, libro soci;
- **calendario** e **stampa dei documenti** dai modelli;
- **non** accede a protocollo, organi sociali, comunicazioni, tesoreria, patrimonio, né alle
  configurazioni (tipologie, listino, sezioni, utenti). Non registra incassi (vanno in prima nota).

Chi guida l'intera associazione o federazione ha il ruolo **Presidente**.

**Privacy (GDPR)**: l'esportazione di tutti i dati di una persona spetta ad Amministratore di sistema
e Segretario, l'anonimizzazione al solo Amministratore di sistema (vedi [Anagrafica](anagrafica.md)).

### Soci e tesseramento

| Ruolo | Libro soci | Tesseramento e attribuzione | Carico tessere dalla sede centrale | Incassi e annullamenti | Listino (costi e quote) | Domande | Stampe ed elenco tesserati | Tipologie | Importazione dal registro nazionale | Sezioni |
|---|---|---|---|---|---|---|---|---|---|---|
| Amministratore di sistema | consulta, iscrive, modifica, cessa | sì | sì | sì | modifica | registra, accoglie/respinge | sì | modifica | sì | modifica |
| Presidente | consulta | consulta | consulta | - | consulta | accoglie/respinge | sì | consulta | - | consulta |
| Segretario | consulta, iscrive, modifica, cessa | sì | sì | - | consulta | registra, accoglie/respinge | sì | modifica | sì | consulta |
| Tesoriere | consulta | sì | sì | **sì** | **modifica** | consulta | - | consulta | - | consulta |
| Consigliere, Revisore | consulta | consulta | consulta | - | consulta | consulta | - | consulta | - | consulta |
| Addetto protocollo | - | - | - | - | - | - | - | - | - | - |

La **campagna delle tessere con le sezioni** (richieste, ordine al nazionale, magazzino, consegne,
avvisi, importazione della consegna) è di Amministratore di sistema, Segretario e Tesoriere. I
versamenti delle sezioni sono incassi, quindi li registra chi registra gli incassi.

**Sezioni.** In una federazione a un utente si possono assegnare una o più sezioni: con qualunque
ruolo, vedrà e gestirà solo soci, tessere, carichi e domande di quelle sezioni. Gli utenti senza
sezioni assegnate, e l'amministratore tecnico, vedono tutto.

Il **trasferimento di sezione** è riservato ad Amministratore di sistema e Segretario.

Incassi e segreteria sono separati di proposito: chi iscrive i soci non registra i pagamenti.
In un'associazione piccola la stessa persona può avere entrambi i ruoli.

### Protocollo

| Ruolo | Registro | Registra, aggiunge documenti, posta, spedisce per email/PEC | Annulla | Riservati | Esporta e registri | Titolario, modelli di registrazione e caselle usate | Manuale di gestione |
|---|---|---|---|---|---|---|---|
| Amministratore di sistema | consulta | sì | sì | sì | sì | modifica (anche i modelli) | prepara e adotta |
| Presidente | consulta | - (vede la posta) | - | sì | sì | consulta titolario e modelli | consulta |
| Segretario | consulta | sì | sì | sì | sì | modifica (anche i modelli) | prepara e adotta |
| Addetto protocollo | consulta | sì | - | - | sì | consulta titolario e modelli | consulta |
| Tesoriere, Consigliere | consulta | - | - | - | - | consulta titolario e modelli | consulta |

Le versioni adottate del **manuale di gestione** sono consultabili da tutti i ruoli, compresi presidente di
sezione e revisore; la bozza solo da chi accede al protocollo.
| Revisore | consulta | - | - | - | sì | consulta il titolario |

L'addetto protocolla ma non annulla: l'annullamento lo decide un responsabile (segretario).
Chi modifica titolario e modelli sceglie anche quali **caselle** usa il protocollo; la configurazione delle
caselle e dei servizi di invio (server, password) spetta solo all'Amministratore di sistema
(*Sistema → Servizi di posta*). L'eliminazione definitiva della posta scartata spetta a segretario e
amministratore di sistema, non all'addetto. Chi gestisce la posta (addetto, segretario, amministratore)
può scegliere per sé gli **avvisi** dei messaggi nuovi su Telegram, SMS o WhatsApp.

### Organi sociali

| Ruolo | Consulta organi, riunioni, verbali, delibere | Prepara e convoca riunioni | Presenze e verbali | Cariche, rappresentante legale, modelli di convocazione | Regole degli organi | Firme e timbri |
|---|---|---|---|---|---|---|
| Amministratore di sistema | sì | sì | sì | sì | sì | sì |
| Presidente | sì | sì | sì | - | - | firme |
| Segretario | sì | sì | sì | sì | - | firme |
| Tesoriere, Addetto protocollo, Consigliere, Revisore | sì | - | - | - | - | - |
| Presidente di sezione | - | - | - | - | - | firme della propria sezione |

I **timbri** degli enti (associazione e sezioni) li gestisce solo l'**amministratore di sistema**, da
*Sistema → Organizzazione* (permesso `organi.gestisci_timbri`).

### Comunicazioni e anniversari

| Ruolo | Anniversari | Registro comunicazioni | Scrive e invia | Modelli, liste, ricorrenze, auguri automatici |
|---|---|---|---|---|
| Amministratore di sistema, Segretario | sì | sì | sì | sì |
| Presidente, Tesoriere | sì | sì | sì | consulta |
| Addetto protocollo, Revisore | sì | sì | - | consulta |
| Consigliere | sì | - | - | - |

**Promemoria di rinnovo della quota**: li imposta chi gestisce le comunicazioni (Amministratore,
Segretario) e il Tesoriere; li consultano Presidente e chi può inviare. *Prepara ora* richiede di
poter scrivere comunicazioni.

### Tesoreria

| Ruolo | Rendiconti | Prima nota, saldi, preventivo, incassi e registro incassi | Registra e annulla movimenti, incassi e storni, chiude gli esercizi, conti e piano dei conti |
|---|---|---|---|
| Amministratore di sistema, Tesoriere | sì | sì | sì |
| Presidente, Revisore | sì | consulta | - |
| Segretario, Consigliere | sì | - | - |
| Addetto protocollo | - | - | - |

### Eventi

| Ruolo | Consulta eventi e adesioni | Crea eventi, gestisce le adesioni |
|---|---|---|
| Amministratore di sistema, Presidente, Segretario, Tesoriere | sì | sì |
| Presidente di sezione, Addetto protocollo, Consigliere, Revisore | sì | - |

### Patrimonio

| Ruolo | Consulta inventario e passaggi | Inserisce, modifica, valuta, presta e registra uscite | Passaggio di consegne |
|---|---|---|---|
| Amministratore di sistema, Segretario, Tesoriere | sì | sì | sì |
| Presidente | sì | - | sì |
| Consigliere, Revisore | sì | - | - |
| Addetto protocollo | - | - | - |

### Documenti

| Ruolo | Consulta i modelli e stampa | Crea e modifica i modelli |
|---|---|---|
| Amministratore di sistema, Segretario | sì | sì |
| Presidente, Tesoriere, Addetto protocollo | sì | - |
| Consigliere, Revisore | - | - |

### Calendario

Il **Calendario** è aperto a tutti gli utenti, ma ognuno vede (e riceve sul telefono) solo gli
impegni dei moduli che può consultare: riunioni degli organi, ricorrenze, restituzioni dei beni
in prestito e, per chi consulta i soci, i compleanni dei soci attivi.

| Ruolo | Consulta appuntamenti e scadenze | Inserisce, modifica, segna fatte, annulla |
|---|---|---|
| Amministratore di sistema, Presidente, Segretario, Tesoriere | sì | sì |
| Addetto protocollo, Consigliere, Revisore | sì | - |

### Collegamenti API

| Ruolo | Consulta controparti | Inviti, abbinamento, attivazione, sospensione, revoca, rotazione delle chiavi |
|---|---|---|
| Amministratore di sistema | sì | sì |
| Tutti gli altri | - | - |

### Chat interna

La **Chat** è aperta a tutti gli utenti con almeno un ruolo (non ai soci dell'area personale). Ognuno
legge solo le conversazioni a cui partecipa: **nemmeno l'amministratore di sistema** vede quelle degli
altri.

## Funzioni che coinvolgono più moduli

Un'operazione che scrive in un altro modulo richiede anche il permesso di quel modulo:

- **protocollare** (convocazioni e verbali degli Organi, passaggi di consegne, email inviate,
  documenti stampati) richiede il permesso di registrare protocolli: chi non lo ha non vede
  l'opzione, e il protocollo rifiuta comunque la registrazione;
- **inviare per email** ricevute, esiti delle domande e convocazioni richiede anche di poter
  consultare la tessera, la domanda o la riunione, e solo per le proprie sezioni;
- **incassare le quote** è dato solo a chi può anche registrare in prima nota.

La coerenza fra ruoli, menu e permessi è verificata dai test automatici a ogni modifica.

Chi tenta di aprire una pagina non consentita vede il messaggio *Accesso non consentito*.
