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

| Ruolo | Anagrafica | Esporta anagrafica (CSV, rubrica) | Importa da rubrica | Dati organizzazione, aspetto, configurazione guidata | Registro attività | Utenti e ruoli |
|---|---|---|---|---|---|---|
| Amministratore di sistema | consulta, inserisce, modifica, archivia | sì | sì | modifica | consulta | **gestisce** |
| Presidente | consulta, inserisce, modifica, archivia | sì | - | - | consulta | - |
| Segretario | consulta, inserisce, modifica, archivia | sì | sì | modifica | - | - |
| Addetto protocollo | consulta, inserisce, modifica, archivia | - | - | - | - | - |
| Tesoriere | consulta | - | - | - | - | - |
| Consigliere | consulta | - | - | - | - | - |
| Revisore | consulta | - | - | - | consulta | - |

### Soci e tesseramento

| Ruolo | Libro soci | Tesseramento e attribuzione | Carico tessere dalla sede centrale | Incassi e annullamenti | Listino (costi e quote) | Domande | Stampe ed elenco tesserati | Tipologie | Importazione dal registro nazionale | Sezioni |
|---|---|---|---|---|---|---|---|---|---|---|
| Amministratore di sistema | consulta, iscrive, modifica, cessa | sì | sì | sì | modifica | registra, accoglie/respinge | sì | modifica | sì | modifica |
| Presidente | consulta | consulta | consulta | - | consulta | accoglie/respinge | sì | consulta | - | consulta |
| Segretario | consulta, iscrive, modifica, cessa | sì | sì | - | consulta | registra, accoglie/respinge | sì | modifica | sì | consulta |
| Tesoriere | consulta | sì | sì | **sì** | **modifica** | consulta | - | consulta | - | consulta |
| Consigliere, Revisore | consulta | consulta | consulta | - | consulta | consulta | - | consulta | - | consulta |
| Addetto protocollo | - | - | - | - | - | - | - | - | - | - |

**Sezioni.** In una federazione a un utente si possono assegnare una o più sezioni: con qualunque
ruolo, vedrà e gestirà solo soci, tessere, carichi e domande di quelle sezioni. Gli utenti senza
sezioni assegnate, e l'amministratore tecnico, vedono tutto.

Incassi e segreteria sono separati di proposito: chi iscrive i soci non registra i pagamenti.
In un'associazione piccola la stessa persona può avere entrambi i ruoli.

### Protocollo

| Ruolo | Registro | Registra, aggiunge documenti, posta | Annulla | Riservati | Esporta e registri | Titolario e caselle |
|---|---|---|---|---|---|---|
| Amministratore di sistema | consulta | sì | sì | sì | sì | modifica |
| Presidente | consulta | - (vede la posta) | - | sì | sì | consulta il titolario |
| Segretario | consulta | sì | sì | sì | sì | modifica |
| Addetto protocollo | consulta | sì | - | - | sì | consulta il titolario |
| Tesoriere, Consigliere | consulta | - | - | - | - | consulta il titolario |
| Revisore | consulta | - | - | - | sì | consulta il titolario |

L'addetto protocolla ma non annulla: l'annullamento lo decide un responsabile (segretario).

### Organi sociali

| Ruolo | Consulta organi, riunioni, verbali, delibere | Prepara e convoca riunioni | Presenze e verbali | Cariche | Regole degli organi |
|---|---|---|---|---|---|
| Amministratore di sistema | sì | sì | sì | sì | sì |
| Presidente | sì | sì | sì | - | - |
| Segretario | sì | sì | sì | sì | - |
| Tesoriere, Addetto protocollo, Consigliere, Revisore | sì | - | - | - | - |

### Comunicazioni e anniversari

| Ruolo | Anniversari | Registro comunicazioni | Scrive e invia | Modelli, liste, ricorrenze, auguri automatici |
|---|---|---|---|---|
| Amministratore di sistema, Segretario | sì | sì | sì | sì |
| Presidente, Tesoriere | sì | sì | sì | consulta |
| Addetto protocollo, Revisore | sì | sì | - | consulta |
| Consigliere | sì | - | - | - |

### Tesoreria

| Ruolo | Rendiconti | Prima nota, saldi, preventivo | Registra e annulla movimenti, chiude gli esercizi, conti e piano dei conti |
|---|---|---|---|
| Amministratore di sistema, Tesoriere | sì | sì | sì |
| Presidente, Revisore | sì | consulta | - |
| Segretario, Consigliere | sì | - | - |
| Addetto protocollo | - | - | - |

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
