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
| Web | **Modulo pubblico di iscrizione** (disattivato di default): campo trappola, tempo minimo di compilazione (4 s) con token firmato valido 2 ore, massimo 3 domande/ora per IP e 30/ora in totale, `noindex`; nessun CAPTCHA esterno | `apps/soci/forms.py` |
| Dati | **PDF** generati solo con risorse locali: il generatore rifiuta URL esterni, `file:` e percorsi fuori da static/media (niente SSRF né lettura di file) | `apps/core/pdf.py` |
| Dati | Libro soci, tessere e ricevute: numeri mai riutilizzati, annullamenti motivati, nessuna cancellazione dall'interfaccia | `apps/soci/servizi.py` |
| Dati | **Protocollo**: numero, data, oggetto e corrispondenti immodificabili; annullamento motivato; documenti solo aggiunti, con impronta SHA-256; registro giornaliero PDF con impronta | `apps/protocollo/servizi.py` |
| Dati | Documenti salvati con nome = impronta (mai il nome scelto da chi carica), estensioni ammesse e dimensione massima configurabili, tipo dedotto dal server; download come allegato con `CSP: sandbox` | `apps/protocollo` |
| Dati | **Protocolli riservati** visibili solo con permesso specifico (404 per gli altri), consultazioni registrate | `ProtocolloQuerySet.visibili_a` |
| Dati | Posta: caselle IMAP in **sola lettura**, TLS con verifica del certificato, messaggi mostrati **solo come testo** (l'HTML non viene mai reso), limite di 50 MB per messaggio | `apps/protocollo/posta.py` |
| Dati | Password delle caselle **cifrate** (Fernet, chiave `CHIAVE_CIFRATURA` fuori dal database, rotazione possibile); mai mostrate nell'interfaccia | `apps/core/cifratura.py` |
| Privacy | **Comunicazioni**: finalità per ogni invio; per comunicazioni associative e auguri vale l'ultimo consenso registrato; deceduti e archiviati sempre esclusi; un messaggio per destinatario (nessun indirizzo esposto); registro per destinatario | `apps/comunicazioni/servizi.py` |
| Web | Segnaposto dei testi con sostituzione semplice (nessun linguaggio di template eseguito sui testi scritti dagli utenti); email HTML con testo sempre escapato | `servizi.componi` |
| Dati | **Tesoreria**: prima nota numerata, movimenti annullati e non cancellati, esercizi chiusi immutabili (riapertura motivata e registrata), giustificativi con impronta, quote collegate una sola volta alla prima nota | `apps/tesoreria/servizi.py` |
| Dati | **Patrimonio**: inventario numerato, beni usciti mai cancellati, passaggi di consegne immutabili con PDF e impronta | `apps/patrimonio/servizi.py` |
| Privacy | **Foto dei beni** ridimensionate e senza metadati EXIF (posizione GPS, dispositivo); servite solo con permesso | `servizi.foto_ripulita` |
| Web | **Schede pubbliche dei beni**: indirizzo con codice casuale (96 bit), solo dati scelti per la pubblicazione, disattivabili; QR generato in SVG senza servizi esterni | `apps/patrimonio` |
| Privacy | **Foto di persone ed enti** e **logo**: verificati e ricodificati con Pillow (JPEG 600 px / PNG 512 px), senza metadati, con nome casuale; le foto si vedono solo con il permesso di anagrafica o del libro soci, il logo è pubblico. SVG mai accettati (potrebbero contenere script) | `apps/core/immagini.py` |
| Web | **Aspetto personalizzato** servito come foglio di stile (`/aspetto.css`) generato dai soli valori validati (colore `#RRGGBB`, scelte fisse): la CSP resta senza stili inline | `apps/core/aspetto.py` |
| Permessi | **Sezioni**: un utente con sezioni assegnate vede e modifica solo soci, tessere, carichi e domande di quelle sezioni (le altre rispondono 404); i filtri sono applicati in tutte le viste e nelle esportazioni | `apps/soci/sezioni.py` |
| Dati | **Importazione dal registro nazionale**: file al massimo 10 MB e 20.000 righe, Excel letto con `defusedxml` (niente attacchi XML), nessuna formula valutata; anteprima eseguita in una transazione annullata; file tenuto tra anteprima e conferma con nome casuale fuori dalle cartelle servite ed eliminato dopo l'uso (o dopo 24 ore); i dati locali non vengono mai sovrascritti; importazione registrata | `apps/soci/importazione.py` |
| Privacy | Gli estratti del registro soci vanno tenuti fuori dal repository: la cartella `tmp/` è esclusa dal versionamento | `.gitignore` |
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
10. Se si attiva il **modulo pubblico di iscrizione**, configurare `PROXY_COUNT` correttamente
    dietro reverse proxy: il limite per IP usa l'indirizzo del client ricavato dalle intestazioni del proxy.

## Segnalare una vulnerabilità

Scrivere a <info@iz0bec.info> descrivendo il problema; non pubblicare dettagli prima della correzione.
