<!--
******************************************************
* Progetto:    Gestione Associazione
* Autore:      Bartolomeo Santoro aka IZ0BEC
* Email:       info@iz0bec.info
* Descrizione: Backup e ripristino
* Licenza:     CC0 1.0 Universal (pubblico dominio)
* SPDX-License-Identifier: CC0-1.0
******************************************************
-->

# Backup e ripristino

L'applicazione fa da sé i backup. Ognuno è un file `.tar` con il database (`pg_dump`), l'elenco dei
file caricati (`MEDIA_ROOT`) con le impronte SHA-256 e un manifesto (data, versione, migrazioni,
numero di soci e protocolli). I file caricati non sono copiati in ogni backup: stanno **una volta
sola** nell'archivio comune della cartella dei backup (vedi *Backup incrementali*). Un backup è
quindi completo **insieme all'archivio**; quello scaricato dall'interfaccia contiene già tutto.
Il file `.env` va custodito **a parte**: contiene i segreti (`SECRET_KEY`, `CHIAVE_CIFRATURA`,
`CHIAVE_BACKUP`, password del database) e non è nel backup.

## Dall'interfaccia

**Sistema → Backup** (amministratore di sistema):

- **Crea backup ora**;
- **scarica** un backup, per conservarlo fuori dal server: il file scaricato è sempre completo,
  con dentro anche i documenti dell'archivio;
- **carica** un backup creato altrove, ad esempio per trasferire i dati su un nuovo server.
  Viene verificato prima di essere aggiunto all'elenco;
- **ripristina**: chiede di scrivere `RIPRISTINA` e la propria password. Poi:
  1. verifica il file: impronte e compatibilità. Un backup di una versione **più recente** del
     programma va ripristinato dopo aver aggiornato il programma;
  2. salva lo stato attuale in un backup «prima del ripristino»;
  3. sostituisce database e file e applica le migrazioni mancanti (backup di versioni precedenti);
  4. **se qualcosa non riesce** (database, aggiornamento dello schema, file) rimette da sé lo stato
     salvato al punto 2 e lo dice: nulla risulta cambiato. Solo se fallisse anche questo ritorno, il
     messaggio indica il backup «prima del ripristino» da ripristinare a mano;
  5. mostra l'avanzamento in una pagina che si aggiorna da sola. Alla fine si accede di nuovo,
     perché anche utenti e sessioni sono quelli del backup;
- **elimina** un backup.

Ogni operazione resta nel registro attività.

### Backup di versioni diverse

| Backup creato con… | Ripristino |
|---|---|
| la stessa versione | normale |
| una versione **precedente** | il database torna com'era, poi si applicano le migrazioni mancanti: le tabelle arrivano alla versione attuale e ruoli e permessi si riallineano |
| una versione **più recente** | rifiutato prima di toccare qualsiasi cosa: aggiornare prima il programma |

Il confronto si fa sulle migrazioni elencate nel manifesto, non sul numero di versione.

## Backup incrementali, cifratura e prova di ripristino (dalla 1.0.30)

- **Incrementali**: i file caricati si salvano una volta sola nell'archivio `BACKUP_ROOT/oggetti/`
  (per impronta SHA-256); ogni backup contiene database ed elenco dei file. I file che nessun backup usa
  più si tolgono con la rotazione. Il backup **scaricato** dall'interfaccia è sempre completo (con i
  file dentro, cartella `oggetti/` del `.tar`). I backup fino alla 1.0.29 restano ripristinabili.
- **Cifratura**: con `CHIAVE_BACKUP` nel `.env` (`manage.py genera_chiave_backup`) database e file sono
  cifrati con AES-256-GCM. **Conservare la chiave fuori dal server**: senza non si ripristina nulla.
  La pagina *Sistema → Backup* mostra il comando pronto da copiare e l'impronta della chiave in uso.
- **Prova di ripristino**: pulsante nella pagina o `manage.py backup --prova [NOME]`; controlla le
  impronte (decifrando) e il dump e, se l'utente PostgreSQL ha il permesso `CREATEDB`, ripristina in un
  database temporaneo confrontando i conteggi. Il pianificatore ne fa una alla settimana sull'ultimo.
- **Ripristino a mano**: `manage.py backup --estrai NOME CARTELLA` scrive `database.dump` (per
  `pg_restore`) e la cartella `media` decifrati.

## Backup automatici

Il pianificatore crea ogni notte un backup **automatico**, poi applica la conservazione.

## Conservazione a rotazione

Senza regole la cartella dei backup crescerebbe senza fine. Dopo ogni backup (notturno, manuale o
da terminale) si eliminano quelli che non servono più, poi si tolgono dall'archivio i documenti
che nessun backup rimasto usa:

- **automatici**: l'ultimo di ciascuno degli ultimi `BACKUP_GIORNALIERI` giorni, `BACKUP_SETTIMANALI`
  settimane e `BACKUP_MENSILI` mesi. Con i valori predefiniti si tengono al massimo 7 + 4 + 12 file
  (di fatto qualcuno meno, perché lo stesso file può valere per il giorno, la settimana e il mese);
- **altri** (manuali, caricati, «prima del ripristino», «prima dell'aggiornamento», «prima
  dell'inizializzazione»): gli ultimi `BACKUP_ALTRI`;
- **tetto di spazio**: con `BACKUP_SPAZIO_MASSIMO`, se i file di backup tenuti lo superano si
  eliminano i più vecchi, prima gli automatici poi gli altri. Il tetto conta i file di backup, non
  l'archivio dei documenti, che la pagina mostra a parte;
- **mai eliminati da soli**: l'ultimo backup automatico e l'ultimo degli altri, i backup
  **esclusi dalla rotazione** e i file illeggibili (vanno controllati a mano). Durante un ripristino
  la pulizia non tocca nulla.

Un backup **non parte** se sul disco resterebbero meno di `BACKUP_SPAZIO_LIBERO_MINIMO` byte liberi
(si stima il doppio dell'ultimo backup: file temporanei più file finale); il messaggio d'errore
compare nella pagina o nel registro del pianificatore. Anche un ripristino si ferma prima di
cominciare se non c'è spazio per il backup «prima del ripristino».

Nella pagina **Sistema → Backup** accanto a ogni backup si legge perché è conservato (giornaliero,
settimanale, mensile, recente) oppure «sarà eliminato al prossimo backup», e lo spazio occupato e
libero.

### Escludere un backup dalla rotazione

Il pulsante con la puntina, **Escludi dalla rotazione**, conserva un backup finché non lo si rimette in
rotazione o lo si elimina, ad esempio quello di fine anno sociale o quello prima di una migrazione
di dati. Lo spazio che occupa conta comunque nel tetto `BACKUP_SPAZIO_MASSIMO`. L'elenco sta nel file
`.conservati.json` della cartella dei backup.

| Variabile `.env` | Predefinito | |
|---|---|---|
| `BACKUP_ROOT` | `var/backup` | cartella dei backup (permessi 700, file 600) |
| `BACKUP_AUTOMATICO` | `true` | backup notturno |
| `BACKUP_ORA` | `2` | ora del backup notturno |
| `BACKUP_GIORNALIERI` | `7` | giorni coperti dagli automatici (vecchio nome: `BACKUP_CONSERVA`) |
| `BACKUP_SETTIMANALI` | `4` | settimane coperte |
| `BACKUP_MENSILI` | `12` | mesi coperti |
| `BACKUP_ALTRI` | `10` | backup non automatici da tenere (`0` = tutti) |
| `BACKUP_SPAZIO_MASSIMO` | vuoto | spazio massimo dei backup, es. `20G` (vuoto = nessun tetto) |
| `BACKUP_SPAZIO_LIBERO_MINIMO` | `1G` | spazio da lasciare libero sul disco |

### Perché il file è `.tar` e non `.tar.gz`

Il database è già compresso (formato *custom* di `pg_dump`) e gran parte dei documenti (PDF, foto)
lo è per natura; con la cifratura, poi, i dati non si comprimono più. Comprimere il contenitore
costerebbe tempo senza ridurre lo spazio.

Dentro il `.tar` ci sono `manifest.json`, `database.dump` (`database.dump.cif` se cifrato),
`file.json` (l'elenco dei file con le impronte) e, solo nei backup scaricati, la cartella
`oggetti/` con i documenti. I backup fino alla 1.0.29 avevano invece i file in `file.tar.gz`: si
ripristinano ancora.

## Da terminale

```bash
manage.py backup                      # crea un backup
manage.py backup --elenco             # elenca i backup, perché sono conservati, spazio
manage.py backup --pulisci            # applica solo la conservazione
manage.py backup --conserva NOME --nota "fine anno 2026"   # esclude dalla rotazione
manage.py backup --rilascia NOME      # rimette in rotazione
manage.py ripristina NOME_O_PERCORSO  # chiede di scrivere il nome del database
manage.py ripristina FILE --conferma NOME_DATABASE   # senza domande (script)
```

Servono i programmi `pg_dump` e `pg_restore` della **stessa versione principale** del server
PostgreSQL (o più recente). Lo script di installazione li installa.

## Raccomandazioni

- Copiare i backup **fuori dal server** (altro disco, NAS, cloud), ad esempio con un `rsync`
  notturno della cartella `BACKUP_ROOT` **compresa la sottocartella `oggetti/`**: senza
  l'archivio i backup non contengono i documenti. In alternativa si conserva il backup scaricato,
  che è completo.
- Impostare `CHIAVE_BACKUP`: i backup contengono dati personali e così lasciano il server già
  cifrati, senza bisogno di altri programmi.
- Conservare **fuori dal server**, in un posto diverso dai backup, una copia di `CHIAVE_BACKUP`
  (senza, i backup cifrati non si ripristinano) e di `CHIAVE_CIFRATURA` (senza, le password delle
  caselle di posta salvate non sono leggibili).
- La prova di ripristino settimanale controlla impronte e database; almeno due volte l'anno conviene
  comunque ripristinare davvero un backup su un'installazione di prova.

## Inizializzazione (azzerare tutto)

Per ripartire da zero, ad esempio dopo le prove o prima di caricare i dati definitivi, il comando
`inizializza` riporta l'applicazione allo stato di una nuova installazione:

1. mostra cosa verrà cancellato: database, numero di soci, protocolli e movimenti, cartella dei file;
2. chiede di **scrivere il nome del database** come conferma (oppure `--conferma NOME` negli script);
3. salva un **backup completo** «prima dell'inizializzazione» in `BACKUP_ROOT`. **Se il backup non
   riesce, non cancella nulla**;
4. elimina tutte le tabelle e le ricrea con le migrazioni, con i dati iniziali (ruoli, tipologie,
   piano dei conti, organi, ricorrenze, sezione predefinita);
5. cancella i file caricati (allegati, foto, loghi, moduli firmati);
6. crea l'amministratore (`--admin`, `--email`; password chiesta due volte, oppure dalla variabile
   `INIZIALIZZA_PASSWORD`).

Al primo accesso riparte la [configurazione guidata](../operativo/configurazione-iniziale.md).

```bash
# fermare prima l'applicazione e il pianificatore
sudo systemctl stop gestione-associazione gestione-associazione-pianificatore
sudo -u gestione /opt/gestione-associazione/.venv/bin/python manage.py inizializza
sudo systemctl start gestione-associazione gestione-associazione-pianificatore

# con Docker
docker compose stop app pianificatore
docker compose run --rm app python manage.py inizializza
docker compose start app pianificatore
```

Per tornare indietro si ripristina il backup appena creato, da *Sistema → Backup* oppure con
`manage.py ripristina`.

L'inizializzazione **non esiste nell'interfaccia web**, di proposito: un'operazione che cancella tutto
deve richiedere l'accesso al server.

