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

## Backup

**Sistema → Backup** (amministratore di sistema): backup completi di dati e file, creati ogni notte
e su richiesta, da scaricare e conservare fuori dal server; ripristino con conferma. Vedi il
[manuale di sistema](../sistema/backup.md).

## Servizi di posta

![Servizi di posta: interruttori, stato del server di invio e verifica delle caselle](immagini/servizi-posta.jpg)

**Sistema → Servizi di posta**, solo per l'Amministratore di sistema. Due interruttori generali:

- **Invio delle email**: spento, **nessuna email parte**. Le comunicazioni si possono ancora scrivere
  e confermare: restano *in coda* e partono quando l'invio viene riattivato. Gli **auguri** e i
  **promemoria di rinnovo** automatici non vengono nemmeno preparati, così alla riattivazione non
  partono messaggi ormai fuori tempo; anche le email dell'accesso (recupero della password) non
  vengono spedite.
- **Lettura delle caselle di posta (IMAP)**: spento, la posta da protocollare non viene scaricata,
  né dal pianificatore né con il pulsante *Scarica ora*.

Quando un servizio è spento, le pagine interessate (Comunicazioni, Promemoria di rinnovo, Posta da
protocollare) lo segnalano con un avviso. La pagina mostra anche lo **stato**: server SMTP
configurato (la password non è mai mostrata), mittente, messaggi in coda e caselle IMAP con
l'ultimo controllo ed eventuali errori. Ogni modifica è annotata nel registro attività.

**Verifica** (accanto a ogni casella e al server di invio) fa una **prova di accesso**, anche con i
servizi spenti: per una casella riporta quanti messaggi contiene, quanti rientrano nel periodo da
scaricare e quanti sono già nel programma, **senza scaricare nulla** (la cartella è aperta in sola
lettura); per il server di invio si collega e si disconnette **senza spedire email**. In caso di
errore mostra il motivo (password errata, server o cartella sbagliati, server non raggiungibile).

Utile durante il collaudo, quando il server di posta non è ancora configurato, o per fermare
tutto in caso di problemi. Il server SMTP si configura nel file `.env` (manuale di sistema), le
caselle IMAP in *Protocollo → Posta da protocollare*.

## Sezioni

![Le sezioni, con organigramma e creazione degli organi](immagini/sezioni.jpg)

**Sistema → Sezioni**: codice (come nel registro nazionale), nome, comune, provincia, email. Ogni
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
