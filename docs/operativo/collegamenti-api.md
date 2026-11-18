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
