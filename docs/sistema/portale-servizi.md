<!--
******************************************************
* Progetto:    Gestione Associazione
* Autore:      Bartolomeo Santoro aka IZ0BEC
* Email:       info@iz0bec.info
* Descrizione: Portale dei servizi: pagina comune che elenca le installazioni del gestionale
* Licenza:     CC0 1.0 Universal (pubblico dominio)
* SPDX-License-Identifier: CC0-1.0
******************************************************
-->

# Portale dei servizi

Quando un'associazione usa più installazioni (federazione, sezioni), una **pagina comune** può
elencarle tutte con i servizi attivi e i recapiti: *Gestionale*, *Area soci*, *Iscrizione online*,
*Sito web*. La genera `scripts/portale/genera_portale.py`, uno script che usa solo la libreria standard
di Python e **legge i dati da ciascun gestionale**. Non serve aggiornarla a mano quando una sezione
attiva l'iscrizione online, l'area soci o cambia sede.

## Da dove vengono i dati

Ogni installazione pubblica la propria scheda in `/.well-known/gestione-associazione`, la stessa delle
[API](api.md). La scheda contiene sempre i **servizi** attivi, con il loro indirizzo; contiene i
**recapiti** (sede, telefono, email, PEC, sito) solo se l'ente lo consente: *Sistema → Organizzazione →
Pagina pubblica*, **Recapiti nella scheda pubblica dell'istanza** (spenta per default).

La lettura avviene in HTTPS sull'indirizzo pubblico: i dati sono destinati a una pagina pubblica, quindi
non serve il canale firmato delle API, che resta per i dati riservati. Se un gestionale non risponde si
usano i dati dell'ultima lettura riuscita (`cache.json` accanto alla configurazione).

## Configurazione

Un file TOML (vedi [`scripts/portale/esempio.toml`](../../scripts/portale/esempio.toml)) indica:

- testi della testata (ente, motto, intestazione, sottotitolo), piede, stemma, favicon e foto di sfondo
  (nella stessa cartella del file);
- **colori** come la veste delle email: testata, accento, sfondo;
- i **livelli** (es. sede nazionale, federazione, sezioni), divisi in **gruppi** (es. per provincia),
  con le **voci**. Per ogni voce: `nome`, `sottotitolo`, l'indirizzo `gestionale` da cui leggere i
  dati, `etichetta` del pulsante, `escludi` per i recapiti da non mostrare (`sede`, `telefono`,
  `email`, `pec`, `sito`), `recapiti` per correggerne uno, `collegamenti` aggiuntivi e `ampia` per la
  scheda a tutta larghezza. Una voce senza `gestionale` mostra solo testi e collegamenti.

## Installazione

Su un server con nginx (o un altro server web per file statici) e il codice del gestionale:

```bash
mkdir -p /etc/portale-servizi /var/www/portale-servizi
cp scripts/portale/esempio.toml /etc/portale-servizi/portale.toml   # e le immagini
python3 scripts/portale/genera_portale.py /etc/portale-servizi/portale.toml --uscita /var/www/portale-servizi
cp scripts/portale/portale-servizi.{service,timer} /etc/systemd/system/   # adattare i percorsi
systemctl daemon-reload && systemctl enable --now portale-servizi.timer
```

Il timer rigenera la pagina ogni ora e all'avvio; `systemctl start portale-servizi` la rigenera subito.
La pagina mostra in fondo la data dell'ultimo aggiornamento.
