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

La tabella cresce con i nuovi moduli (soci, protocollo, tesoreria, ...): per esempio il
tesoriere avrà la piena gestione della tesoreria, il revisore la sola consultazione.

Chi tenta di aprire una pagina non consentita vede il messaggio *Accesso non consentito*.
