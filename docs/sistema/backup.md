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
