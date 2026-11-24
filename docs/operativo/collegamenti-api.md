<!--
******************************************************
* Progetto:    Gestione Associazione
* Autore:      Bartolomeo Santoro aka IZ0BEC
* Email:       info@iz0bec.info
* Descrizione: Manuale dei collegamenti API fra installazioni e con integrazioni esterne
* Licenza:     CC0 1.0 Universal (pubblico dominio)
* SPDX-License-Identifier: CC0-1.0
******************************************************
-->

# Collegamenti con altre installazioni e integrazioni (API)

**Sistema → Collegamenti API** collega questa installazione ad altre installazioni di Gestione
Associazione (es. la federazione e le sue sezioni) e a **integrazioni esterne** (un sito WordPress,
un'app) scritte da altri sul contratto pubblico dell'API. La pagina è riservata all'**Amministratore
di sistema**.

Ogni messaggio fra le due parti è **firmato**: chi lo riceve sa con certezza chi lo ha mandato e che
nessuno lo ha modificato, anche se passa da un proxy o dalla rete interna. Le controparti si
riconoscono dalle loro chiavi, non dall'indirizzo.

> Cosa può fare oggi una controparte, se ne ha l'ambito:
>
> - **leggere**: eventi e sezioni (con il feed dei cambiamenti), documenti pubblici, organigramma,
>   verifica di una tessera;
> - **inviare**: adesioni agli eventi, domande di iscrizione, messaggi del modulo contatti.
>
> Lo scambio di soci e tessere fra federazione e sezioni arriva con la fase successiva.

## Questa istanza

Il riquadro a destra mostra l'**identità** dell'installazione (un codice UUID che non cambia), le
sue **chiavi pubbliche** e l'**indirizzo** da comunicare alle controparti. Se compare l'avviso sulla
chiave di cifratura, va prima configurata `CHIAVE_CIFRATURA` (vedi [Sistema](sistema.md)): le chiavi
private si conservano cifrate.

Se c'è l'impronta **SPKI** del certificato, l'installazione serve HTTPS da sola e le altre
installazioni della rete interna possono verificarla anche con un certificato autofirmato.

## Collegare una controparte: l'invito

1. **Nuovo invito**: nome (come la riconoscerete), tipo (*installazione* o *integrazione esterna*)
   e **ambiti**, cioè cosa potrà fare. Concedete solo il necessario: si cambia in ogni momento.
2. Compare il **codice d'invito**, insieme all'indirizzo dell'installazione. Si vede **una sola
   volta**, vale **24 ore** e **una volta sola**: copiatelo e comunicatelo all'amministratore
   della controparte per un canale riservato.
3. La controparte lo usa: un'altra installazione da *Usa un invito ricevuto*, un'integrazione con la
   chiamata descritta nel contratto. La controparte compare **in prova**.
4. **Confrontate l'impronta**: nella scheda della controparte c'è un codice di 32 cifre (es.
   `4862 7F83 33D0 EF87 …`), lo stesso sulle due installazioni. Leggetelo all'altro
   amministratore **per telefono** o di persona, oppure scambiatelo con un atto protocollato.
   Se coincide, nessuno si è messo in mezzo.
5. Spuntate *Ho confrontato l'impronta* e premete **Attiva**.

Finché resta *in prova*, la controparte può solo verificare il collegamento.

## Collegarsi a un'altra installazione: usare un invito ricevuto

Dall'amministratore dell'altra installazione ricevete un codice e un indirizzo. Andate su **Usa un
invito ricevuto**:

- **Indirizzo pubblico**: quello su Internet, solo `https://`.
- **Indirizzo interno**: se l'altra installazione è nella vostra rete (anche sullo stesso Proxmox)
  indicatelo e spuntate **rete interna**. Si prova per primo; quello pubblico resta di riserva.
- **Verifica del certificato** (sull'indirizzo interno; non si può disattivare):
  - *CA del sistema*: certificati pubblici, come quelli di Let's Encrypt;
  - *CA interna*: incollate il certificato radice della vostra CA, ad esempio step-ca;
  - *impronta*: va bene anche un certificato autofirmato; l'impronta la stampa l'installatore
    dell'altra installazione alla fine («Impronta SPKI del certificato»).
- **http in chiaro**: un'eccezione solo per indirizzi privati. Firma e controlli restano, ma il
  traffico si può leggere in rete. Meglio HTTPS anche in rete interna: vedi la guida *HTTPS anche
  in rete interna* del manuale di sistema.
- **Ambiti**: cosa potrà fare l'altra installazione presso di voi.

Con **Abbina**, le due installazioni si scambiano le chiavi e controllano di calcolare la stessa
impronta. Poi confrontatela anche voi e attivate, come sopra. Ognuna delle due parti attiva l'altra.

## La scheda della controparte

- **Prova il collegamento**: manda una richiesta firmata e mostra l'esito: firma, scarto
  dell'orologio, stato presso la controparte, indirizzo usato. Se l'indirizzo interno non risponde,
  l'esito lo segnala e la prova passa a quello pubblico.
- **Modifica**:
  - ambiti, indirizzi e modalità di verifica;
  - **indirizzi IP ammessi**: un controllo in più, perché l'identità è data dalla firma;
  - **scadenza**: dopo quella data la controparte viene sospesa da sola.
- **Notifiche** (in *Modifica*): flussi di cui avvisare la controparte e indirizzo a cui inviare
  l'avviso. Nella scheda si vedono quante notifiche sono in coda e quali non sono state consegnate
  dopo i tentativi; queste ultime si rimettono in coda con **Riprova**.
- **Aggiorna chiavi e impronte** (solo installazioni): rilegge le chiavi e l'impronta del
  certificato dell'altra installazione, ad esempio dopo una sua rotazione delle chiavi o il rinnovo
  del certificato. Lo fa da sola anche ogni notte.
- **Sospendi** / **Riattiva**: blocca temporaneamente le chiamate.
- **Revoca**: chiude il collegamento in modo definitivo. Per ricollegarsi serve un nuovo invito.
- **Ultime chiamate ricevute**: data, richiesta, esito e IP; gli errori hanno un codice, ad esempio
  `firma-scaduta` se l'orologio di una delle due macchine è fuori di oltre 5 minuti.

## Federazione e sezioni: il ruolo del collegamento

Nella scheda della controparte (*Modifica*) si indica il **ruolo**:

- sull'installazione della **federazione**, per ogni sezione collegata: «È una nostra sezione», con
  **quale sezione** del proprio elenco è (una sola per collegamento);
- sull'installazione di una **sezione**: «È la nostra federazione».

Il ruolo dice che cosa è **l'altra** installazione per noi, quindi le due schede hanno ruoli
opposti. Un'installazione con più sezioni è la federazione e non accetta «È la nostra federazione».
Se i ruoli risultano invertiti, la *Verifica soci* si ferma con «Ruoli incoerenti» e indica la
scheda da correggere; nessun dato viene letto.

**Voce di rubrica.** Quando il collegamento è attivo e ha il ruolo di federazione o di sezione
(all'attivazione o quando si imposta il ruolo), il programma legge dalla controparte i suoi contatti
istituzionali (denominazione, codice fiscale, indirizzo postale, telefono, email e PEC, come li ha in
*Sistema → Organizzazione*) e crea o aggiorna l'**ente** corrispondente in *Anagrafica*. Un ente già
presente è riconosciuto per codice fiscale, PEC o denominazione e non viene duplicato; i valori non
validi sono scartati e un codice fiscale già presente non si sostituisce. Sulla federazione si
completano anche email, comune e provincia della sezione, se mancano. La scheda della controparte
mostra la voce (**In rubrica**) e il pulsante **Aggiorna la voce di rubrica** per rileggerla. Se la
controparte non risponde o ha una versione precedente, il collegamento funziona lo stesso: la voce si
può inserire a mano in anagrafica.

A entrambe le parti va concesso l'ambito **«Ciclo delle tessere»**. Da quel momento, ogni 15 minuti
(o con *Sincronizza ora* nella campagna):

- richieste di tessere, consegne con i numeri, ricevute dei versamenti e prese in carico passano
  da sole fra le due installazioni;
- ogni documento arriva nella *Campagna delle tessere*, riquadro **Documenti in arrivo**, e si
  conferma da lì (vedi il manuale dei soci). Le prese in carico si registrano da sole;
- ognuno vede solo i documenti della propria sezione.

## Verifica dei soci fra federazione e sezione

Con il ruolo indicato e l'ambito **«Soci e tessere: lettura»** concesso **da entrambe le parti**, la
scheda della controparte mostra il riquadro **Soci** con il pulsante **Verifica soci** (serve il
permesso di importare i soci). Lo stesso pulsante è nel menu **Importa e verifica** dell'elenco dei soci
e nella pagina *Sistema → Importa soci*. Il gestionale legge i soci che la controparte ha per quella sezione e
li confronta con i propri; **nulla cambia finché non si conferma**:

- i soci che **mancano** qui sono proposti **da creare** (popolamento): arrivano con anagrafica,
  tipologia, ammissione, stato e tessere recenti, come nell'importazione da file;
- per i soci **presenti** si mostrano le **modifiche campo per campo** (valore qui → valore della
  controparte) e si sceglie a chi applicarle. Se il dato qui è stato modificato **dopo** quello
  della controparte, la voce resta non spuntata e porta l'avviso «il dato qui è più recente»;
- i soci si riconoscono dal codice fiscale (o matricola, o nome con data di nascita); se mancano,
  nella stessa sezione dal numero di tessera o dal nome e cognome se unico. Gli **omonimi** non
  distinguibili si escludono con il motivo: vanno sistemati a mano, per non creare doppi;
- i soci **allineati** non compaiono; gli **esclusi** (es. socio di un'altra sezione) riportano il
  motivo; i soci **presenti solo qui** sono elencati per informazione.

Chi aggiorna cosa:

- dalla **federazione** alla sezione arrivano le **anagrafiche** (residenza, contatti, dati di
  nascita, matricola); stato, cessazioni e rinnovi restano della sezione;
- dalla **sezione** alla federazione arrivano anche **stato, cessazioni e rinnovi** (tessera
  dell'anno e quota versata, registrata come incassata altrove, senza ricevuta né prima nota): la
  federazione li riceve e li verifica prima di applicarli;
- nome, cognome e codice fiscale non cambiano mai; un socio cessato non si riattiva; un campo
  vuoto della controparte non cancella il dato qui; una tessera con numero diverso si segnala e
  si corregge a mano.

La pagina della verifica resta consultabile con gli esiti. I dati ricevuti si cancellano appena la
verifica è applicata (o dopo 30 giorni se non lo è).

### Allineamento automatico

Dopo una **prima Verifica soci applicata**, nel riquadro **Soci** della controparte si può
premere **Attiva l'allineamento automatico**. Da quel momento, ogni 15 minuti, il gestionale fa da
solo la verifica e applica le modifiche, con le stesse regole di *chi aggiorna cosa* e in **ordine
di tempo** rispetto all'ultimo allineamento:

- un socio cambiato **solo presso la controparte** si aggiorna qui; un socio **nuovo** si crea;
- un socio cambiato **solo qui** non si tocca: sarà la controparte a prendere la modifica;
- un socio cambiato **da entrambe le parti** è un'**incongruenza**: vale la modifica più recente
  e chi gestisce i soci riceve un'email «Incongruenze nell'allineamento» da controllare (la
  riceve anche l'altra installazione, dalla propria parte);
- le voci che non si sistemano da sole (omonimi, socio di un'altra sezione, tessera con numero
  diverso) restano **da verificare a mano** con una *Verifica soci* manuale, e si segnalano una
  volta sola.

Ogni giro che porta novità lascia una voce **«allineamento automatico»** fra le verifiche recenti,
con il dettaglio, e un'**email** a chi gestisce i soci di quella sezione: così la **federazione
supervisiona** ogni rinnovo, nuovo socio o cessazione arrivati dalla sezione, e la sezione vede ciò
che arriva dalla federazione. **Allinea ora** esegue subito un giro; **Disattiva** torna alla sola
verifica manuale. Se la controparte non risponde, l'errore resta nel riquadro e si riprova al giro
dopo. Lo scambio con file Excel resta sempre possibile.

### Sezione che la federazione non raggiunge (a spinta)

Se la federazione non può chiamare la sezione (sezione dietro NAT o senza indirizzo pubblico), in
*Modifica* della controparte si spunta **«Soci a spinta»** da tutte e due le parti:

- sulla **sezione** (controparte = federazione): è la sezione a **inviare** l'elenco dei suoi soci
  alla federazione, ogni 15 minuti **solo se è cambiato** (pulsante **Invia ora i soci** per farlo
  subito); la federazione deve concederle l'ambito **«Consegna dei cambiamenti»**;
- sulla **federazione** (controparte = sezione): non la si legge più; ogni invio della sezione si
  applica da sé se l'allineamento automatico è acceso, altrimenti diventa una **Verifica soci da
  decidere** (un invio nuovo sostituisce quello non ancora deciso) e chi gestisce i soci riceve
  un'email.

## Cosa arriva dalle integrazioni

- **Adesioni**: compaiono nell'evento come le altre, con origine «Integrazione (API)». Valgono le
  stesse regole del modulo pubblico: adesioni aperte, posti, accompagnatori. Un'integrazione può
  aderire solo agli eventi con modulo pubblico e annullare solo le adesioni che ha inviato lei.
- **Domande di iscrizione**: arrivano in *Soci → Domande* «in attesa», con origine «Integrazione
  (API)». Si valutano come quelle del modulo online: niente viene accolto da solo.
- **Messaggi del modulo contatti**: arrivano tra la **posta da protocollare**, casella «Modulo
  contatti (API)», e si protocollano o si scartano come le email.

La scheda della controparte riporta quante adesioni e domande ha inviato.

## Dati personali

L'ambito **Soci e tessere** porta fuori dati personali. A un'**integrazione esterna** si concede solo
con la conferma esplicita del trattamento: chi la gestisce tratta i dati per conto dell'associazione
e serve un accordo ai sensi dell'art. 28 del GDPR.

## Rotazione delle chiavi

**Ruota le chiavi** crea chiavi nuove. Le precedenti restano valide **7 giorni**: in quel periodo le
risposte sono firmate con entrambe, e le altre installazioni accettano da sole le chiavi nuove. Serve se si teme che il server sia stato
compromesso. Tutte le operazioni finiscono nel **registro attività**.
