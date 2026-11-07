<!--
******************************************************
* Progetto:    Gestione Associazione
* Autore:      Bartolomeo Santoro aka IZ0BEC
* Email:       info@iz0bec.info
* Descrizione: Misure di sicurezza e raccomandazioni di esercizio
* Licenza:     CC0 1.0 Universal (pubblico dominio)
* SPDX-License-Identifier: CC0-1.0
******************************************************
-->

# Sicurezza

L'applicazione tratta dati personali di soci e terzi (anche dati di persone anziane e,
in prospettiva, dati contabili): la sicurezza è un requisito, non un'aggiunta.

## Misure nell'applicazione

| Area | Misura | Dove |
|---|---|---|
| Accesso | Password con hash **Argon2**, minimo 12 caratteri, non comuni né simili ai dati dell'utente | `config/settings.py` |
| Accesso | **Secondo fattore**: app di autenticazione (TOTP), passkey/chiavi di sicurezza, codici di recupero | django-allauth `mfa` |
| Accesso | **Blocco** dopo 5 tentativi falliti per 15 minuti (utente + IP), più il limite di frequenza di allauth | django-axes |
| Accesso | Nessuna registrazione libera: gli account li crea l'amministratore | `apps/accounts/adapter.py` |
| Accesso | Sessione di 8 ore, chiusa alla chiusura del browser; cookie `HttpOnly`, `SameSite=Lax`, `Secure` con HTTPS | settings |
| Permessi | **Ruoli per funzione** con permessi minimi; ogni vista verifica il permesso (403 altrimenti) | `apps/accounts/ruoli.py` |
| Web | Protezione **CSRF** su tutti i moduli e sulle richieste HTMX | Django |
| Web | **Content Security Policy**: solo risorse locali, nessuno script inline né `eval`, niente iframe esterni | settings `SECURE_CSP` |
| Web | `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy: same-origin`, COOP; HSTS con HTTPS | settings |
| Web | Template con escaping automatico; nessun contenuto esterno inserito in script | template |
| Web | Librerie front-end incluse nel progetto: nessun CDN, nessun tracciamento | `static/vendor` |
| Dati | **Registro attività** non modificabile: accessi (anche falliti), creazioni, modifiche con valori prima/dopo, esportazioni | `apps/core/audit.py` |
| Dati | Numerazioni atomiche nel database (niente duplicati) | `apps/core/numerazione.py` |
| Dati | Allegati fuori dalla cartella pubblica, scaricabili solo con permesso | `MEDIA_ROOT` |
| Dati | Esportazione CSV protetta dall'iniezione di formule e sempre registrata | `apps/anagrafica/servizi.py` |
| Privacy | Consensi per finalità con data e modalità; persone decedute escluse da auguri e comunicazioni | anagrafica |
| Codice | Test automatici sui controlli di sicurezza (permessi, blocco, CSP, CSV); lint con regole di sicurezza (`ruff` S) | `apps/*/tests` |

## Raccomandazioni di esercizio

1. **HTTPS sempre** in produzione (`HTTPS=true`), anche in rete locale se possibile.
2. **Secondo fattore obbligatorio** almeno per amministratore, presidente, segretario e tesoriere.
3. Un account **personale** per ogni persona; mai account condivisi. Disattivare subito gli account
   di chi lascia un incarico (il passaggio di consegne lo prevede).
4. Usare il superutente solo per l'amministrazione tecnica.
5. **Backup** giornalieri del database e degli allegati, conservati fuori dal server e cifrati;
   provare il ripristino almeno due volte l'anno ([Backup](backup.md)).
6. Aggiornare l'applicazione e il sistema operativo regolarmente; controllare `uv lock --upgrade`
   e le note di sicurezza di Django.
7. Database raggiungibile solo dal server dell'app (porta non esposta in rete).
8. Controllare periodicamente il **registro attività**, in particolare gli accessi falliti e le esportazioni.
9. Nominare per iscritto le persone autorizzate al trattamento (GDPR art. 29) e mantenere il registro
   dei trattamenti (art. 30) se richiesto.

## Segnalare una vulnerabilità

Scrivere a <info@iz0bec.info> descrivendo il problema; non pubblicare dettagli prima della correzione.
