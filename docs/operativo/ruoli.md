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

| Ruolo | Libro soci | Tessere | Incassi e annullamenti | Domande | Stampa libro soci | Tipologie |
|---|---|---|---|---|---|---|
| Amministratore di sistema | consulta, iscrive, modifica, cessa | rilascia, rinnovo | sì | registra, accoglie/respinge | sì | modifica |
| Presidente | consulta | consulta | - | accoglie/respinge | sì | consulta |
| Segretario | consulta, iscrive, modifica, cessa | rilascia, rinnovo | - | registra, accoglie/respinge | sì | modifica |
| Tesoriere | consulta | rilascia, rinnovo | **sì** | consulta | - | consulta |
| Consigliere, Revisore | consulta | consulta | - | consulta | - | consulta |
| Addetto protocollo | - | - | - | - | - | - |

Incassi e segreteria sono separati di proposito: chi iscrive i soci non registra i pagamenti.
In un'associazione piccola la stessa persona può avere entrambi i ruoli.

La tabella cresce con i nuovi moduli (protocollo, tesoreria, ...).

Chi tenta di aprire una pagina non consentita vede il messaggio *Accesso non consentito*.
