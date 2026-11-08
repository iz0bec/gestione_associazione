<!--
******************************************************
* Progetto:    Gestione Associazione
* Autore:      Bartolomeo Santoro aka IZ0BEC
* Email:       info@iz0bec.info
* Descrizione: Manuale dei modelli di stampa (lettere, attestati, documenti)
* Licenza:     CC0 1.0 Universal (pubblico dominio)
* SPDX-License-Identifier: CC0-1.0
******************************************************
-->

# Documenti e modelli di stampa

**Documenti** nel menu: lettere, attestati e documenti su carta intestata (logo e dati da
*Sistema → Organizzazione*), preparati da modelli che si scrivono una volta e si stampano per una
persona, per una lista o per una categoria.

## Modelli

![I modelli di stampa](immagini/documenti.jpg)

Un modello ha un **nome**, un **tipo** e un **testo**:

| Tipo | Impaginazione |
|---|---|
| Lettera | luogo e data, destinatario a destra (adatto alle buste a finestra), «Oggetto:», testo, firma |
| Attestato | titolo grande centrato, testo centrato, luogo e data, firma |
| Documento libero | titolo e testo |
| Attestato solenne / benemerenza | pagina A4 orizzontale con cornice dorata e angoli ornati, stemmi, titolo in capitali, alloro, coccarda tricolore, due firme (vedi sotto) |

Nel testo:

- una **riga vuota** separa i paragrafi;
- `**parola**` scrive in **grassetto**, `*parola*` in *corsivo*;
- le righe che iniziano con `- ` formano un elenco;
- i **segnaposto** fra doppie graffe vengono sostituiti con i dati del destinatario: per esempio
  `{{ nome_completo }}` (Rossi Mario), `{{ intestazione }}` (Cav. Mario Rossi), `{{ saluto }}` («Caro», «Cara» o «Gentile»), `{{ numero_socio }}`,
  `{{ anni_socio }}`, `{{ organizzazione }}`, `{{ luogo }}`, `{{ data_estesa }}`. L'elenco
  completo è a destra nella pagina del modello. Un segnaposto scritto male viene segnalato al
  salvataggio.

**Firma**: qualifica (predefinita «Il Presidente») e nome. Se il nome è vuoto si usa il presidente
in carica registrato negli [Organi sociali](organi.md).

Il nome del firmatario è stampato nella forma «Mario Rossi», con il titolo se presente.

**Anteprima** mostra il modello compilato con i dati della propria scheda in anagrafica.

Sono già presenti quattro modelli, da adattare: *Attestato di iscrizione*, *Attestato di
benemerenza*, *Lettera di auguri*, *Lettera*.

## Attestato solenne (benemerenza)

Per benemerenze, riconoscimenti, ringraziamenti e attestati di partecipazione a cerimonie. Ogni
pagina, in A4 orizzontale, ha:

- **cornice** a doppio filetto dorato con perline, angoli ornati e fregio in basso;
- in testa gli **stemmi**: a sinistra il logo dell'ente (*Sistema → Organizzazione*), a destra lo
  **stemma del modello** (es. della presidenza nazionale o del Comune) che si carica nella pagina del
  modello; senza, si usa il logo del modulo di adesione. Con un solo stemma, è centrato sopra la
  denominazione. Il logo dell'ente compare anche in **filigrana** al centro;
- il **titolo** in capitali (es. *Attestato di Benemerenza*) e un ramo d'**alloro**;
- il **testo**: la riga in grassetto (es. `**{{ intestazione }}**`) diventa il nome del
  destinatario in grande corsivo; conviene un testo di due o tre frasi, perché tutto deve stare in
  una pagina;
- luogo e data, la **coccarda tricolore** al centro e le **firme**: a destra il firmatario del modello,
  a sinistra la **seconda firma** facoltativa (Vicepresidente, Segretario o Tesoriere), con il nome
  di chi è in carica negli Organi sociali.

Si stampa come gli altri modelli (anche per una lista o una categoria, una pagina per persona);
rende al meglio su cartoncino avorio o pergamena.

## Stampare

- Da una **scheda dell'anagrafica**: pulsante **Stampa documento**, poi si sceglie il modello.
- Da **Documenti → Stampa un documento**: si sceglie il modello e i destinatari: una persona o un
  ente, una **lista di distribuzione** (vedi [Comunicazioni](comunicazioni.md)), una **categoria**,
  oppure nessuno (documento unico).

Con una lista o una categoria si ottiene **un unico PDF con una pagina per destinatario**, pronto
per la stampa e l'imbustamento. Le schede archiviate e le persone decedute sono escluse.

**Registra a protocollo in uscita** (solo per chi può protocollare): il documento riceve un numero
di protocollo, stampato in alto su ogni pagina; la registrazione elenca i destinatari, ha il PDF
come documento principale e indica il mezzo di spedizione (posta ordinaria, raccomandata, a mano).
Un documento senza destinatari viene registrato come protocollo interno.

Ogni stampa è annotata nel [registro attività](sistema.md#registro-attività).
