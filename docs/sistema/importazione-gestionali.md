<!--
******************************************************
* Progetto:    Gestione Associazione
* Autore:      Bartolomeo Santoro aka IZ0BEC
* Email:       info@iz0bec.info
* Descrizione: Importazione dai tre gestionali precedenti
* Licenza:     CC0 1.0 Universal (pubblico dominio)
* SPDX-License-Identifier: CC0-1.0
******************************************************
-->

# Importazione dai gestionali precedenti

Il comando `importa_gestionale` porta nel nuovo gestionale i dati di **Gestione Soci**, **Gestione
Assemblee** e **Protocollo ANCR**. Regole comuni:

- **Anteprima predefinita**: senza `--esegui` tutto avviene in una transazione poi annullata.
  Il rapporto mostra esattamente cosa accadrà, senza modificare nulla. Con `--dettagli` compare
  ogni record.
- **Rieseguibile**: ogni record importato viene annotato (tabella `migrazione_origine`); una
  seconda esecuzione salta i record già importati, senza doppioni.
- **Prevalgono i dati già presenti** (es. quelli del registro nazionale). Delle schede esistenti
  si completano solo i campi vuoti; le differenze compaiono nel rapporto come «dati locali diversi,
  non sovrascritti».
- Le fonti si leggono **in sola lettura**. Fare sempre un [backup](backup.md) prima di `--esegui`.
- `--utente NOME` indica l'autore delle operazioni nel registro attività.

Ordine consigliato: Gestione Soci, poi Gestione Assemblee, poi Protocollo ANCR.

## Gestione Soci

```bash
manage.py importa_gestionale gestione-soci /percorso/gestione_soci.db [--esegui]
```

| Dato | Diventa |
|---|---|
| soci | schede in anagrafica e iscrizioni al libro soci, con la stessa logica dell'[importazione dal registro nazionale](../operativo/soci.md); sezione riconosciuta dall'ultimo livello del campo sezione («BASILICATA / POTENZA MATERA / RUOTI» → comune Ruoti) |
| tessere | tesseramenti con la tessera fisica (aggiunta al lotto «Registro soci nazionale» se manca) e la **quota versata**, segnata come incassata fuori dall'applicazione (niente ricevuta né prima nota) |
| anni contabili e movimenti | esercizi con i movimenti in prima nota (conto dei contanti, voci del rendiconto dalla categoria); gli **anni passati vengono chiusi** e i saldi finali riportati nell'anno successivo |
| beni e valutazioni | inventario con un nuovo numero; il numero precedente resta in «numero di inventario precedente» |
| foto dei soci | foto della scheda in anagrafica, ripulita dai metadati, **solo se la scheda non ne ha già una**; una foto non trovata si annota nel rapporto e si può aggiungere ripetendo l'importazione con la cartella giusta |
| passaggi di consegne | passaggi di consegne del patrimonio con l'elenco dei beni di allora, il PDF originale se si trova o uno rigenerato dai dati, con la sua impronta |
| cessioni dei beni | uscite dal patrimonio: prestito (con la restituzione, se avvenuta, e le condizioni al rientro), donazione, alienazione (dismissione); documento e protocollo della cessione restano nelle condizioni |

Abbinamento dei soci: per codice fiscale; se il codice non trova nessuno, per **tessera dello stesso
anno e data di nascita**. Così si riconosce la stessa persona anche quando uno dei due archivi ha
un codice fiscale o un nome errati. Quando succede, il rapporto lo annota.

Opzioni: `--tipologia` (tipologia dei soci nuovi, predefinita «Ordinario»), `--sezione CODICE`
(per i soci senza sezione), `--abbina comune|nome|codice`, `--crea-sezioni`, `--conto NOME`,
`--senza-tesoreria`, `--senza-beni`, `--file CARTELLA` (la cartella `static/uploads` del vecchio
gestionale, con le sottocartelle `soci/` e dei documenti; predefinita: quella accanto al database,
cioè `../static/uploads` rispetto a `instance/`).

## Gestione Assemblee

```bash
manage.py importa_gestionale assemblee /percorso/instance/ancr_gestione.db [--esegui]
```

- **Contatti** in anagrafica: abbinati per codice fiscale, email, nome e data di nascita, o cognome
  e data di nascita se il risultato è unico. Si completano solo i campi vuoti; fissi e cellulari
  vengono separati.
- **Modelli email**: importati **disattivati**, con i segnaposto convertiti (`{nome}` →
  `{{ nome }}`). Quelli senza equivalente restano tra parentesi quadre (es. `[mittente_nome]`) e
  vanno corretti prima dell'uso.
- **Assemblee e riunioni del direttivo** negli Organi sociali: «generale» va all'assemblea dei soci,
  «direttivo» all'organo di amministrazione dell'associazione; data e luogo di prima e seconda
  convocazione, ordine del giorno (un punto per riga), stato (le annullate restano annullate), numero
  di protocollo della convocazione nella premessa.
- **Verbali**: importati **aperti**, con presidente, segretario, partecipanti, discussione, decisioni
  e provvedimenti, da **rivedere e chiudere** qui: la chiusura assegna il numero nel libro dei verbali
  e fissa il PDF con la sua impronta.
- Le comunicazioni sono solo contate.

## Protocollo ANCR

Da eseguire sul server del Protocollo ANCR, che legge le credenziali dal suo `.env`:

```bash
manage.py importa_gestionale protocollo --env /opt/ancr-protocollo/.env \
    --allegati /opt/ancr-protocollo/public/uploads [--esegui]
```

In alternativa `--dsn postgresql://utente:password@host/database`.

- **Rubrica** in anagrafica (persone ed enti, abbinati per email o nome) e **liste di
  distribuzione** come liste delle Comunicazioni.
- **Registrazioni con il numero originale** (`AAAA-NNNNN`), data e ora, direzione, mezzo,
  mittente e destinatari (testo conservato; scheda anagrafica collegata quando l'email corrisponde),
  annullamenti con il motivo. L'operatore originale è annotato nelle note e, se ha la stessa email
  di un utente, diventa l'autore.
- **Documenti** dalla cartella `--allegati`, con il nome originale (nome su disco = impronta, come
  gli altri allegati). I file mancanti vengono contati nel rapporto; i percorsi fuori dalla
  cartella vengono ignorati.
- La numerazione dell'anno **riprende dopo l'ultimo numero importato**.
- Un anno **non si importa** se nel nuovo gestionale ci sono già registrazioni di quell'anno, per
  non sovrapporre i numeri. Va quindi importato prima di iniziare a protocollare qui, oppure
  dall'anno successivo.
- Registri giornalieri e posta ricevuta non vengono importati: i registri si rigenerano qui.
