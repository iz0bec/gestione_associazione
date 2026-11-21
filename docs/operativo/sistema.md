<!--
******************************************************
* Progetto:    Gestione Associazione
* Autore:      Bartolomeo Santoro aka IZ0BEC
* Email:       info@iz0bec.info
* Descrizione: Dati dell'organizzazione e registro attività
* Licenza:     CC0 1.0 Universal (pubblico dominio)
* SPDX-License-Identifier: CC0-1.0
******************************************************
-->

# Organizzazione e registro attività

## Dati dell'organizzazione

**Sistema → Organizzazione** (amministratore e segretario). Denominazione, codice fiscale,
eventuale iscrizione al RUNTS, sede, recapiti, PEC e testo dell'**informativa privacy**.
Sono usati nelle intestazioni dei documenti, nelle comunicazioni e nei moduli; la denominazione
breve compare in alto nel menu. Ogni modifica è registrata.

Questi dati si inseriscono la prima volta con la [configurazione guidata](configurazione-iniziale.md).

### Timbri

In fondo alla pagina, solo per l'**amministratore di sistema**, il riquadro **Timbri**: il timbro
dell'associazione e di ogni sezione (carica, sostituisci, non usare, togli), il foglio per acquisirlo,
la stampa di prova e l'interruttore del **timbro generico**. Come acquisirli: [Firme e timbri](firme-e-timbri.md).

### Modulo di richiesta di adesione (Allegato A)

Nella stessa pagina si impostano i testi del modulo di adesione e consenso, usati sia per il modulo
online sia per il PDF da stampare e far firmare:

| Campo | Esempio ANCR |
|---|---|
| Federazione | Potenza Matera |
| Intestazione (una riga per voce; la prima è il nome dell'associazione) | ASSOCIAZIONE NAZIONALE COMBATTENTI E REDUCI / (Eretta in ente morale con decreto 24 giugno 1923 n.1371) / PRESIDENZA NAZIONALE |
| Articoli dello statuto richiamati | all'art. 2 ed agli articoli 5, 6, 7, 8, 9 e 58 |
| Dichiarazione SI/NO | iscritto all'Associazione Decorati di Medaglia d'Oro al valor Militare e/o Valor Civile |
| Piè di pagina | sede legale nazionale, partita IVA, codice fiscale, recapiti |
| Logo del modulo | il logo della presidenza nazionale (senza, si usa il logo dell'ente) |
| Informativa privacy | il testo dell'informativa ex art. 13 GDPR; i titoletti («Diritti dell'interessato.») vengono stampati in grassetto |

Il PDF ha tre pagine, come l'originale: richiesta di adesione, consenso al trattamento dei dati,
informativa. Nel testo dei consensi il riferimento normativo è al D.Lgs. n. 196/03 (Codice della
privacy).

## Aspetto

**Sistema → Aspetto** (amministratore e segretario):

- **logo**: PNG o JPEG, meglio quadrato e con sfondo trasparente. Viene ridotto a 512 pixel e
  ricodificato. Compare nel menu, nella pagina di accesso, nelle pagine pubbliche, come icona del
  browser e nell'intestazione dei PDF;
- **colore principale**: pulsanti, collegamenti, voci attive, intestazioni dei PDF. Il testo sopra
  il colore diventa bianco o scuro da solo, per restare leggibile;
- **menu laterale**: scuro, chiaro o nel colore principale.

Ogni utente può comunque passare dal tema chiaro a quello scuro con il pulsante in alto.

### Veste delle email

Nella stessa pagina, **Veste delle email** sceglie l'aspetto di tutti i messaggi che partono dal
gestionale (comunicazioni, auguri, accesso all'area personale, recupero della password, promemoria):

- **titolo** e **sottotitolo** della testata (vuoto: la denominazione), es. «Associazione Nazionale
  Combattenti e Reduci» e «Federazione Provinciale di Potenza e Matera»;
- **logo nella testata**: viaggia dentro il messaggio, quindi si vede anche senza scaricare immagini;
- **colori** della testata, d'accento (filetti, collegamenti, firma) e dello sfondo. Testata e accento
  lasciati uguali al colore principale lo seguono quando cambia; un accento troppo chiaro viene
  scurito nei collegamenti per restare leggibile;
- **fascia in alto**: nessuna, tricolore o nel colore d'accento;
- **carattere dei titoli**: con grazie (come una lettera) o senza;
- **firma**: le righe sotto il nome; vuota, si usano indirizzo, telefono, email e sito
  dell'organizzazione;
- **informativa in calce**: poche righe in piccolo sotto il messaggio (titolare, come chiedere la
  cancellazione, collegamento all'informativa completa). Gli indirizzi diventano collegamenti.

A destra c'è l'**anteprima** di un messaggio di esempio; **Invia una prova a me** lo manda alla propria
email per vederlo nel proprio programma di posta. Le **spedizioni del protocollo** hanno una veste
sobria: senza fascia né informativa, con gli a capo del testo conservati.

## Backup

**Sistema → Backup** (amministratore di sistema): backup di dati e file, creati ogni notte e su
richiesta; ripristino con conferma. I documenti si salvano **una volta sola** e ogni backup li richiama,
così un backup nuovo occupa poco; quello **scaricato** è sempre completo, da conservare fuori dal server.
Con la chiave dei backup (`CHIAVE_BACKUP`) i backup sono **cifrati**: se manca, la pagina lo segnala
e mostra i comandi per crearla. Il pulsante con la provetta (**prova di ripristino**) controlla che un backup sia ripristinabile (lo fa
da sé anche una volta alla settimana). I vecchi backup
si eliminano da soli a rotazione (ultimi giorni, settimane e mesi): accanto a ognuno si legge perché è
conservato. Con la **puntina** un backup si esclude dalla rotazione (es. quello di fine anno) e resta
finché non lo si rimette in rotazione. Vedi il [manuale di sistema](../sistema/backup.md).

## Servizi di posta

![Servizi di posta: interruttori, stato del server di invio e verifica delle caselle](immagini/servizi-posta.jpg)

**Sistema → Servizi di posta**, solo per l'Amministratore di sistema. È l'unico punto in cui si
configura la posta: le **caselle** da leggere (email e PEC in arrivo) e i **servizi di invio** per
spedire. Il protocollo sceglie soltanto quali caselle usare (*Protocollo → Caselle*). Due interruttori
generali:

- **Invio dei messaggi**: spento, **non parte nulla**: né email e PEC né Telegram, SMS e WhatsApp. Le comunicazioni si possono ancora scrivere
  e confermare: restano *in coda* e partono quando l'invio viene riattivato. Gli **auguri** e i
  **promemoria di rinnovo** automatici non vengono nemmeno preparati, così alla riattivazione non
  partono messaggi ormai fuori tempo; anche le email dell'accesso (recupero della password) non
  vengono spedite.
- **Lettura delle caselle di posta (IMAP)**: spento, la posta da protocollare non viene scaricata,
  né dal pianificatore né con il pulsante *Scarica ora*.

Quando un servizio è spento, le pagine interessate (Comunicazioni, Promemoria di rinnovo, Posta da
protocollare) lo segnalano con un avviso.

### Caselle di posta (IMAP)

Ogni **casella** è un indirizzo email o PEC da leggere: nome, *è una PEC*, server IMAP, porta, SSL,
utente e password (conservata **cifrata**, serve la chiave `CHIAVE_CIFRATURA`), cartella da leggere,
cartella in cui spostare i messaggi scaricati (`PROCESSATA`) e giorni da scaricare. Per **Aruba**:
email `imaps.aruba.it`, PEC `imaps.pec.aruba.it`, porta 993 con SSL. Una casella nuova resta spenta
finché non la si abilita in *Protocollo → Caselle* (interruttore **Usata dal protocollo**).

**Rispondi con** indica il servizio di invio con cui si risponde ai messaggi arrivati nella casella. Si
compila da solo con il servizio che ha lo stesso indirizzo e lo stesso tipo (PEC o email), anche quando
il servizio viene creato dopo la casella; si cambia a mano se le risposte devono partire da un altro
indirizzo. Nell'elenco ogni casella mostra «risponde con: …», oppure un avviso se non c'è un servizio
adatto (le risposte partirebbero dal server generale).

**Eliminare una casella**: il cestino nell'elenco oppure **Elimina** in fondo alla pagina *Modifica*. Si
elimina solo una casella che non ha mai scaricato messaggi; se ne ha, i messaggi restano nella posta del
protocollo e la casella si toglie dalla lettura in *Protocollo → Caselle* (*non usata*).

### Servizi di invio (SMTP)

Ogni **servizio di invio** è un server SMTP con cui il programma spedisce: nome, tipo (**Email** o
**PEC**), indirizzo e nome del mittente (vuoto: la denominazione dell'organizzazione), server, porta,
SSL, nome utente (vuoto: l'indirizzo) e password, conservata **cifrata** e mai mostrata.

- Il servizio segnato come **server generale** (uno solo, di tipo email) spedisce le
  **comunicazioni**, le **email dell'accesso** (recupero della password) e i protocolli per email.
  Finché nessun servizio è generale vale il server indicato nel file `.env` (riga «riserva»).
- Gli altri servizi, come la **PEC**, si scelgono in *Spedisci* dalla scheda di un protocollo in uscita.
- L'**interruttore** accanto a ogni servizio lo attiva o lo disattiva: un servizio disattivato non si
  può scegliere per spedire. Il server generale non si disattiva (prima se ne indica un altro).
- Per **Aruba**: email `smtps.aruba.it`, PEC `smtps.pec.aruba.it`, porta 465 con SSL; utente e
  password sono quelli della casella.
- **Eliminare un servizio**: il cestino nell'elenco oppure **Elimina** in fondo alla pagina *Modifica*.
  Un servizio già usato per spedire comunicazioni o protocolli non si elimina (le spedizioni ne
  conservano il riferimento): si disattiva con l'interruttore.

### Telegram

Il riquadro **Telegram** collega il **bot** dell'associazione, da cui partono le comunicazioni scelte
«anche su Telegram». Per crearlo: in Telegram scrivere a **@BotFather**, comando `/newbot`, scegliere
nome e username del bot e incollare nel riquadro il **token** che restituisce (è conservato cifrato e non
si mostra più). Il programma lo verifica con Telegram e mostra il nome del bot; poi si **attiva**
l'interruttore. Il riquadro indica quante persone sono collegate e l'ultimo controllo. Il bot legge i
collegamenti (`/start`) e le disiscrizioni (`/stop`) ogni minuto; i messaggi partono solo con l'invio
attivo. Il server deve poter raggiungere `api.telegram.org` (HTTPS in uscita); non serve aprire porte.

**Rimuovi il bot** (in fondo al riquadro) cancella il token e spegne Telegram, per esempio per passare
a un altro bot: dopo averne collegato uno nuovo, le persone devono ricollegarsi con il proprio link.

### SMS e WhatsApp

Il riquadro **SMS e WhatsApp** elenca i **fornitori** (interruttore, **Verifica**, Modifica, cestino per
eliminarli, anche dalla pagina *Modifica*);
**Nuovo** ne aggiunge uno. Si usa il primo attivo per ciascun canale. Password e token sono cifrati.

| Fornitore | Account | Password o token | Mittente e altro |
|---|---|---|---|
| Skebby, Aruba SMS | nome utente | password | mittente alfanumerico (max 11, registrato presso il fornitore); qualità (es. `GP`) |
| Twilio | Account SID | Auth Token | numero `+...` o Messaging Service `MG...` |
| WhatsApp Business (API Cloud di Meta) | ID del numero di telefono | token permanente di un utente di sistema | nome e lingua del **modello approvato** con un parametro `{{1}}` |

**Verifica** prova l'accesso senza mandare messaggi (per gli SMS mostra anche il credito). L'indirizzo
dell'API ha un valore predefinito per ogni fornitore e si cambia solo se il fornitore lo indica. Le
integrazioni seguono la documentazione dei fornitori ma non sono ancora state provate con un account
reale: alla prima configurazione usare *Verifica* e una comunicazione di prova a sé stessi.

La pagina mostra anche i **messaggi in coda** e, per ogni casella, se è usata dal protocollo,
l'ultimo controllo ed eventuali errori. Ogni modifica è annotata nel registro attività (mai la password).

**Verifica** (accanto a ogni casella e a ogni servizio di invio) fa una **prova di accesso**, anche con i
servizi spenti: per una casella riporta quanti messaggi contiene, quanti rientrano nel periodo da
scaricare e quanti sono già nel programma, **senza scaricare nulla** (la cartella è aperta in sola
lettura); per il server di invio si collega e si disconnette **senza spedire email**. In caso di
errore mostra il motivo (password errata, server o cartella sbagliati, server non raggiungibile).

Utile durante il collaudo, quando il server di posta non è ancora configurato, o per fermare
tutto in caso di problemi.

## Sezioni

![Le sezioni, con organigramma e creazione degli organi](immagini/sezioni.jpg)

**Sistema → Sezioni**: codice (come nel registro nazionale), nome, comune, provincia ed **email
istituzionale**, obbligatoria. È l'indirizzo a cui vanno gli avvisi del tesseramento. Nei documenti
la sezione si scrive «Sezione di …» (es. «Sezione di Ruoti»), a meno che il nome non lo dica già. Ogni
comune ha **una sola sezione attiva**: il comune serve anche a riconoscere la sezione nell'importazione
dal registro nazionale, quindi va scritto come nel registro (es. «Rionero in Vulture»). Con
una sola sezione l'applicazione si comporta come per un'associazione singola. Con più sezioni
compaiono il filtro e la scelta della sezione in soci, tessere e domande di iscrizione. Una
sezione con soci attivi non si può disattivare.

Le sezioni visibili a un utente si assegnano nella sua scheda (**Sistema → Utenti e ruoli**,
vedi [Utenti e ruoli](utenti.md)). Senza sezioni assegnate l'utente vede tutto.

La casella **Domande di iscrizione online** pubblica il modulo di iscrizione all'indirizzo
`/iscrizione/` (vedi [Soci e tesseramento](soci.md#domande-di-iscrizione)).

**Organi della sezione.** Nella colonna *Organi*, **Crea gli organi** prepara il *Consiglio
direttivo* e l'*Assemblea dei soci* della sezione, con le stesse regole (quorum, deleghe) degli
organi dell'associazione; poi se ne nominano i componenti in *Organi sociali*. Quando la sezione ha
organi con componenti, **Organigramma** apre il PDF con una pagina per ogni organo. Lo stesso socio
può avere cariche nella propria sezione e nell'associazione (vedi [Organi sociali](organi.md)).

## Pagina pubblica

![La pagina pubblica di presentazione, per chi non ha fatto l'accesso](immagini/presentazione.jpg)

In **Sistema → Organizzazione**, riquadro *Pagina pubblica*: con **Pagina pubblica di presentazione**
spuntata, chi apre l'indirizzo principale dell'applicazione **senza aver fatto l'accesso** vede una
pagina con il logo e la denominazione, le **finalità dell'associazione** (testo libero; una riga vuota
separa i paragrafi), i **documenti pubblici**, i **contatti** (sede, telefono, email, PEC, codice
fiscale), il riquadro **Verifica una tessera** (numero e cognome; vedi
[Soci](soci.md#tessera-digitale-e-verifica)), il pulsante **Accedi** e, se attive, **Chiedi l'iscrizione**. Chi ha fatto l'accesso vede
sempre il cruscotto. Senza la spunta l'indirizzo principale porta subito alla pagina di accesso.
Il collegamento *Anteprima* mostra la pagina anche prima di attivarla.

**Recapiti nella scheda pubblica dell'istanza**: pubblica sede, telefono, email, PEC e sito anche nella
scheda leggibile dai programmi (`/.well-known/gestione-associazione`), da cui li prende il **portale dei
servizi** che elenca federazione e sezioni (vedi la documentazione di sistema, *Portale dei servizi*).
Spenta, il portale mostra solo i servizi attivi (gestionale, area soci, iscrizione online).

## Documenti pubblici

![La gestione dei documenti pubblici](immagini/documenti-pubblici.jpg)

**Sistema → Documenti pubblici** (Amministratore di sistema, Segretario): si caricano i PDF da
rendere consultabili **da chiunque, senza accesso**, ad esempio **statuto** e **regolamento**:
titolo, descrizione (es. *in vigore dal 21/06/2021*), ordine nell'elenco e *Pubblicato*. Sono
accettati solo file PDF fino a 30 MB.

La pagina pubblica è `/documenti-pubblici/`, collegata dalla pagina di accesso, dal modulo di
iscrizione online e dalle altre pagine pubbliche: ogni documento si legge nel browser o si scarica.
Per una nuova versione si apre il documento e si carica il nuovo file (il precedente è sostituito);
togliendo *Pubblicato* il documento non è più consultabile. Ogni caricamento è nel registro attività.

![La pagina pubblica di statuto e regolamento, consultabile senza accesso](immagini/documenti-pubblici-pagina.jpg)

## Registro attività

**Sistema → Registro attività** (amministratore, presidente, revisore). Elenca, dal più recente:

- accessi, uscite e **tentativi di accesso falliti** (con indirizzo IP);
- inserimenti, modifiche (con i campi cambiati), archiviazioni;
- **esportazioni** di dati.

Si filtra per tipo di azione e per utente. Gli eventi **non si possono modificare né cancellare**,
nemmeno dall'amministratore: il registro serve proprio a ricostruire chi ha fatto cosa.

Cosa controllare periodicamente: molti *accessi falliti* (qualcuno prova a indovinare una password),
esportazioni inattese, modifiche fatte in orari insoliti.
