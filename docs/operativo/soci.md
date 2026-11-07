<!--
******************************************************
* Progetto:    Gestione Associazione
* Autore:      Bartolomeo Santoro aka IZ0BEC
* Email:       info@iz0bec.info
* Descrizione: Manuale operativo del modulo Soci e tesseramento
* Licenza:     CC0 1.0 Universal (pubblico dominio)
* SPDX-License-Identifier: CC0-1.0
******************************************************
-->

# Soci e tesseramento

Il modulo tiene il **libro soci** (art. 15 D.Lgs. 117/2017), le **tessere annuali** con le
quote e le **ricevute**, e raccoglie le **domande di iscrizione**, anche dal sito.

Un socio è sempre una **persona dell'anagrafica**: i dati personali (indirizzo, recapiti,
codice fiscale) si modificano dalla scheda anagrafica e valgono ovunque.

## Concetti

| | |
|---|---|
| **Numero di iscrizione** | Progressivo unico del libro soci, assegnato automaticamente all'ammissione. Non si modifica e non si riusa, nemmeno dopo la cessazione. |
| **Tipologia** | Ordinario, sostenitore, onorario... Ognuna ha una **quota annua** proposta al rilascio della tessera (0 = esente). |
| **Stato** | *Attivo*, *sospeso* (non riceve la tessera, resta nel libro) o *cessato* (con data e causa). |
| **Tessera** | Una per socio e per anno, numerata per anno (es. `2026/0012`), con la quota. Può essere *da pagare*, *pagata*, *esente* o *annullata*. |
| **Ricevuta** | Numerata per anno di incasso (es. `2026/0007`), assegnata quando si registra il pagamento. |
| **In regola / moroso** | In regola = ha la tessera dell'anno pagata. Moroso = socio attivo senza tessera pagata (gli esenti non sono morosi). |

## Iscrivere un nuovo socio

1. **Soci → Nuovo socio**, cercare la persona per cognome, nome o codice fiscale.
2. Se non c'è, crearla prima in **Anagrafica** (dalla scheda si usa poi **Iscrivi**).
3. Nella pagina di ammissione indicare **tipologia**, **data** e, se c'è, la **delibera**
   (es. «Consiglio direttivo del 12/01/2026, verbale n. 3»). Con la casella *Rilascia subito la
   tessera* viene creata anche la tessera dell'anno, da pagare.

All'iscrizione la persona riceve la categoria **Socio** in anagrafica. Non si possono iscrivere
enti, persone archiviate o decedute, né chi è già nel libro soci.

## Scheda del socio

Mostra i dati di iscrizione, le tessere di tutti gli anni, la situazione della quota corrente e
la storia delle operazioni. Dai pulsanti in alto:

- **Modifica**: tipologia, data e delibera di ammissione, note (ogni cambio è registrato);
- **Sospendi / Riattiva**;
- **Cessazione**: data, causa (dimissioni, decesso, esclusione, morosità, altro) e note.
  Il socio resta nel libro con il suo numero; perde la categoria *Socio*. Per il **decesso** la data
  viene riportata anche nella scheda anagrafica, così la persona esce da auguri e comunicazioni.
- **Riammetti** (socio cessato): torna attivo con **lo stesso numero**.

## Tessere e quote

- **Rilascio singolo**: dalla scheda del socio, pulsante **Tessera**. La quota proposta è quella
  della tipologia; si può cambiare (es. quota ridotta). Chi ha il permesso di incasso può segnare
  subito *Quota incassata ora*.
- **Incasso**: pulsante **Incassa** (scheda del socio o pagina Tesseramento). Si indicano data,
  importo, metodo (contanti, bonifico, POS) e un riferimento (es. CRO). Viene assegnato il numero di
  ricevuta.
- **Ricevuta**: pulsante **Ricevuta** su ogni tessera pagata, in PDF con l'intestazione dell'ente,
  da stampare, firmare o inviare.
- **Annullamento**: pulsante ✕ con il motivo obbligatorio. La tessera resta visibile come annullata
  e i numeri (tessera e ricevuta) **non vengono riutilizzati**; poi si può rilasciare una nuova tessera.

## Rinnovo annuale

**Tesseramento → Rinnovo annuale**: scelto l'anno, mostra i soci attivi che non hanno ancora la
tessera e, alla conferma, la rilascia a tutti (da pagare, con la quota della loro tipologia).
Gli incassi si registrano poi man mano.

La pagina **Tesseramento** riassume per l'anno scelto: tessere rilasciate e pagate, totale
incassato e da incassare, soci non in regola e soci ancora senza tessera.

## Morosi

**Soci**, filtro *Quota: non in regola* (con l'anno accanto): elenco dei soci attivi senza la
tessera pagata. Si può esportare in CSV dal menu *Stampa ed esporta*. Lo stesso dato è sul cruscotto.

## Domande di iscrizione

- **Su carta**: *Domande di iscrizione → Registra domanda*, copiando i dati del modulo firmato.
- **Dal sito**: se attivato in *Sistema → Organizzazione* (casella *Domande di iscrizione online*),
  il modulo è pubblico all'indirizzo **`/iscrizione/`** dell'applicazione: si può collegare dal sito
  dell'associazione. Il richiedente dichiara di accettare lo statuto, di aver letto l'informativa
  privacy (testo preso dai dati dell'organizzazione) ed esprime i consensi facoltativi.

Le domande in attesa compaiono sul cruscotto. Nella domanda:

- **Accogli**: si scelgono tipologia, data e delibera. Se in anagrafica esiste già una persona con lo
  stesso codice fiscale viene usata quella scheda (l'avviso lo segnala), altrimenti viene creata.
  La persona viene iscritta, riceve il numero e, se richiesto, la tessera; i consensi della domanda
  sono registrati in anagrafica.
- **Respingi**: con la motivazione obbligatoria.

L'esito resta sulla domanda (data, utente, motivazione). Comunicare l'esito al richiedente è per ora
compito della segreteria; l'invio automatico arriverà con il modulo *Comunicazioni*.

Il modulo pubblico è protetto dagli invii automatici (vedi il manuale di sistema, *Sicurezza*):
se qualcuno segnala di non riuscire a inviarlo, deve ricaricare la pagina e riprovare dopo qualche minuto.

## Stampe ed esportazioni

| Stampa | Dove | Chi |
|---|---|---|
| **Libro soci** (PDF, A4 orizzontale, tutti gli iscritti compresi i cessati) | Soci → Stampa ed esporta | presidente, segretario, amministratore |
| **Elenco filtrato** (CSV per Excel) | Soci → Stampa ed esporta | come sopra |
| **Ricevuta** (PDF) | tessera pagata | tutti i ruoli che vedono le tessere |

Ogni stampa ed esportazione è registrata nel registro attività.

## Tipologie e quote

**Tesseramento → Tipologie e quote**. Alla prima installazione ci sono *Ordinario*, *Sostenitore*
e *Onorario* con quota 0: **impostare le quote** prima del primo rinnovo. Cambiare la quota non
modifica le tessere già rilasciate. Una tipologia non più usata si disattiva (non si cancella).
