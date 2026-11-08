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

Da salvare: **database** e **allegati** (`MEDIA_ROOT`). Il file `.env` va custodito a parte
(contiene i segreti): senza `SECRET_KEY` i dati restano leggibili ma le sessioni e i token si invalidano.

## Docker

```bash
# database
docker compose exec -T db pg_dump -U gestione -d gestione_associazione | gzip > backup_$(date +%F).sql.gz
# allegati
docker run --rm -v gestione_associazione_media:/m -v "$PWD":/b alpine tar czf /b/media_$(date +%F).tgz -C /m .
```

Ripristino (applicazione ferma):

```bash
docker compose stop app
gunzip -c backup_AAAA-MM-GG.sql.gz | docker compose exec -T db psql -U gestione -d gestione_associazione
docker compose start app
```

## Senza Docker

```bash
runuser -u postgres -- pg_dump gestione_associazione | gzip > /root/backups/gestione_$(date +%F).sql.gz
tar czf /root/backups/media_$(date +%F).tgz -C /var/lib/gestione-associazione media
```

## Cosa contiene `media`

Logo dell'ente, **documenti protocollati**, messaggi di posta scaricati e **registri giornalieri**
del protocollo (PDF con impronta SHA-256 nel database). È importante quanto il database: i due backup
vanno fatti insieme. Conservare a parte anche il file `.env` (in particolare `CHIAVE_CIFRATURA`).

## Raccomandazioni

- Automatizzare con un timer systemd o cron, una copia al giorno, con rotazione (es. 30 giorni).
- Copiare i backup **fuori dal server** (altro disco, NAS, cloud cifrato).
- Cifrare i backup che lasciano il server (contengono dati personali), es. `gpg --symmetric`.
- Provare il ripristino su un'installazione di prova almeno due volte l'anno.

Backup automatici con verifica sono previsti nella [roadmap](../roadmap.md).

## Inizializzazione (azzerare tutto)

Per ripartire da zero, ad esempio dopo le prove o prima di caricare i dati definitivi, il comando
`inizializza` riporta l'applicazione allo stato di una nuova installazione:

1. mostra cosa verrà cancellato: database, numero di soci, protocolli e movimenti, cartella dei file;
2. chiede di **scrivere il nome del database** come conferma (oppure `--conferma NOME` negli script);
3. salva un **backup completo** in `var/backup/` (o in `--cartella-backup`): il database con
   `pg_dump` (formato custom) e l'archivio dei file caricati. **Se il backup non riesce, non
   cancella nulla**;
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

Per tornare indietro si ripristina il backup appena creato:

```bash
pg_restore --clean --no-owner -d NOME_DATABASE var/backup/prima_inizializzazione_AAAAMMGG_HHMMSS.dump
tar -xzf var/backup/prima_inizializzazione_AAAAMMGG_HHMMSS_file.tar.gz -C /percorso/di/MEDIA_ROOT --strip-components=1
```

L'inizializzazione **non esiste nell'interfaccia web**, di proposito: un'operazione che cancella tutto
deve richiedere l'accesso al server.

