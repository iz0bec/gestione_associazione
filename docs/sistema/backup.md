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

L'applicazione fa da sé backup **completi**: un unico file `.tar` con il database (`pg_dump`), i
file caricati (`MEDIA_ROOT`) e un manifesto (data, versione, migrazioni, numero di soci e
protocolli, impronte SHA-256). Il file `.env` va custodito **a parte**: contiene i segreti
(`SECRET_KEY`, `CHIAVE_CIFRATURA`, password del database) e non è nel backup.

## Dall'interfaccia

**Sistema → Backup** (amministratore di sistema):

- **Crea backup ora**;
- **scarica** un backup, per conservarlo fuori dal server;
- **carica** un backup creato altrove, ad esempio per trasferire i dati su un nuovo server.
  Viene verificato prima di essere aggiunto all'elenco;
- **ripristina**: chiede di scrivere `RIPRISTINA` e la propria password. Poi:
  1. verifica il file: impronte e compatibilità. Un backup di una versione **più recente** del
     programma va ripristinato dopo aver aggiornato il programma;
  2. salva lo stato attuale in un backup «prima del ripristino»;
  3. sostituisce database e file e applica le migrazioni mancanti (backup di versioni precedenti);
  4. mostra l'avanzamento in una pagina che si aggiorna da sola. Alla fine si accede di nuovo,
     perché anche utenti e sessioni sono quelli del backup;
- **elimina** un backup.

Ogni operazione resta nel registro attività.

## Backup automatici

Il pianificatore crea ogni notte un backup **automatico** e conserva solo gli ultimi. I backup
manuali e quelli «prima del ripristino» restano finché non si eliminano.

| Variabile `.env` | Predefinito | |
|---|---|---|
| `BACKUP_ROOT` | `var/backup` | cartella dei backup (permessi 700, file 600) |
| `BACKUP_AUTOMATICO` | `true` | backup notturno |
| `BACKUP_ORA` | `2` | ora del backup notturno |
| `BACKUP_CONSERVA` | `14` | quanti backup automatici tenere |

## Da terminale

```bash
manage.py backup                      # crea un backup
manage.py backup --elenco             # elenca i backup
manage.py ripristina NOME_O_PERCORSO  # chiede di scrivere il nome del database
manage.py ripristina FILE --conferma NOME_DATABASE   # senza domande (script)
```

Servono i programmi `pg_dump` e `pg_restore` della **stessa versione principale** del server
PostgreSQL (o più recente). Lo script di installazione li installa.

## Raccomandazioni

- Copiare i backup **fuori dal server** (altro disco, NAS, cloud cifrato), ad esempio con un
  `rsync` notturno della cartella `BACKUP_ROOT`.
- Cifrare i backup che lasciano il server (contengono dati personali), ad esempio con
  `gpg --symmetric`.
- Conservare insieme ai backup una copia del file `.env`, o almeno di `CHIAVE_CIFRATURA`: senza
  quella chiave le password delle caselle di posta salvate non sono leggibili.
- Provare il ripristino su un'installazione di prova almeno due volte l'anno.

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

