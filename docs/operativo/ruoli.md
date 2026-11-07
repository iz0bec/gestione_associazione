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
I ruoli li assegna l'amministratore.

| Ruolo | Anagrafica | Esporta anagrafica | Dati organizzazione | Registro attività |
|---|---|---|---|---|
| Amministratore di sistema | consulta, inserisce, modifica, archivia | sì | modifica | consulta |
| Presidente | consulta, inserisce, modifica, archivia | sì | - | consulta |
| Segretario | consulta, inserisce, modifica, archivia | sì | modifica | - |
| Addetto protocollo | consulta, inserisce, modifica, archivia | - | - | - |
| Tesoriere | consulta | - | - | - |
| Consigliere | consulta | - | - | - |
| Revisore | consulta | - | - | consulta |

### Soci e tesseramento

| Ruolo | Libro soci | Tesseramento e attribuzione | Carico tessere dalla sede centrale | Incassi e annullamenti | Domande | Stampe ed elenco tesserati | Tipologie |
|---|---|---|---|---|---|---|---|
| Amministratore di sistema | consulta, iscrive, modifica, cessa | sì | sì | sì | registra, accoglie/respinge | sì | modifica |
| Presidente | consulta | consulta | consulta | - | accoglie/respinge | sì | consulta |
| Segretario | consulta, iscrive, modifica, cessa | sì | sì | - | registra, accoglie/respinge | sì | modifica |
| Tesoriere | consulta | sì | sì | **sì** | consulta | - | consulta |
| Consigliere, Revisore | consulta | consulta | consulta | - | consulta | - | consulta |
| Addetto protocollo | - | - | - | - | - | - |

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

La tabella cresce con i nuovi moduli (comunicazioni, tesoreria, ...).

Chi tenta di aprire una pagina non consentita vede il messaggio *Accesso non consentito*.
