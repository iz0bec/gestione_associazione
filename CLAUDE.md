<!--
******************************************************
* Progetto:    Gestione Associazione
* Autore:      Bartolomeo Santoro aka IZ0BEC
* Email:       info@iz0bec.info
* Descrizione: Istruzioni per Claude Code su questo repository
* Licenza:     CC0 1.0 Universal (pubblico dominio)
* SPDX-License-Identifier: CC0-1.0
******************************************************
-->

# CLAUDE.md — Gestione Associazione

Gestionale unico per associazioni (nato per una sezione ANCR) che unifica tre progetti esistenti:
`~/sviluppo/Protocollo_ANCR` (Node), `~/sviluppo/Gestione_Soci_v0` (Flask), `~/sviluppo/ANCR - Assemblee`
(Flask, repo `ANCR.git`). Analisi in `docs/analisi/analisi-e-finalita.md`, decisioni in
`docs/architettura/decisioni.md`, piano in `docs/roadmap.md`.

## Stack e comandi

Python 3.13 · Django 6.1 · PostgreSQL · HTMX · Tabler · uv.

```bash
uv sync
uv run python manage.py runserver
uv run pytest                                   # richiede PostgreSQL (DATABASE_URL in .env)
uv run ruff check . && uv run ruff format .
uv run python scripts/verifica_intestazioni.py
uv run python manage.py makemigrations --check --dry-run
```

DB di sviluppo: `compose.dev.yaml` (Docker, 127.0.0.1:55432) oppure cluster locale in `var/pgdata`
(PostgreSQL 17 Homebrew): `$(brew --prefix postgresql@17)/bin/pg_ctl -D var/pgdata -o "-p 55432 -k /tmp" -l var/postgres.log start`.

## Regole del progetto

- **Intestazione su ogni file sorgente** (py, sh, css, js, yaml, toml, md e template base):
  Progetto, Autore «Bartolomeo Santoro aka IZ0BEC», Email «info@iz0bec.info», Descrizione,
  Licenza «CC0 1.0 Universal (pubblico dominio)», `SPDX-License-Identifier: CC0-1.0`.
  Nei template che usano `{% extends %}` l'intestazione va DOPO `extends` (deve essere il primo tag).
- **Licenza CC0 1.0**: non introdurre codice copiato con licenze incompatibili; le librerie in
  `static/vendor` vanno elencate in `static/vendor/README.md` e `docs/sistema/licenze-terze-parti.md`.
- Testi, nomi di dominio, documentazione e commit in **italiano** (`Feat:`, `Fix:`, `Docs:`).
- Logica nei **servizi** (`apps/<modulo>/servizi.py`), viste sottili; operazioni rilevanti → `apps.core.audit.registra`.
- Ogni vista protetta con `apps.core.views.PermessoMixin` + `permission_required`; i permessi nuovi vanno
  assegnati ai ruoli in `apps/accounts/ruoli.py` (allineati a ogni `migrate`; un permesso inesistente fa fallire).
- Numeri progressivi **solo** con `apps.core.numerazione.prossimo_numero` dentro `transaction.atomic()`
  insieme al salvataggio del documento.
- Anagrafica unica: i moduli si collegano a `anagrafica.Soggetto`; i documenti ufficiali conservano anche
  il testo del mittente/destinatario al momento della registrazione.
- **CSP rigorosa**: niente `<script>` inline, `onclick`, `style=` nei template; comportamenti in
  `static/js/app.js` con attributi `data-*`; niente CDN. htmx con `allowEval=false`.
- Allegati in `MEDIA_ROOT` (mai serviti direttamente): download solo da viste con controllo permessi.
- Moduli: `{{ form }}` / `{{ campo.as_field_group }}` usano `templates/moduli/` e il filtro `con_stile`.
- Liste con ricerca HTMX: partial nel template (`{% partialdef nome inline %}`, vista che restituisce
  `"pagina.html#nome"` se `request.htmx`).
- Email: Django 6.1 usa `MAILERS` (le impostazioni `EMAIL_*` sono deprecate) — vedi `config/settings.py`.
- PDF: `apps.core.pdf.risposta_pdf(template, contesto, nome)`; i modelli estendono `pdf/base.html`
  e referenziano risorse solo come `risorsa:static/...` / `risorsa:media/...` (il fetcher rifiuta il resto).
- Soci: sequenze `libro_soci` (unica) e `ricevuta_quota` (annuale). Le **tessere sono fisiche, numerate dalla
  sede centrale**: lotti `LottoTessere` → `CartaTessera` (stato) → attribuite a `Tessera` (tesseramento annuale)
  con `servizi.attribuisci_carta`; mai generare numeri di tessera;
  operazioni solo da `apps/soci/servizi.py` (sollevano `OperazioneNonValida` con messaggio per l'utente).
- Modulo pubblico `/iscrizione/`: anti-spam in `DomandaPubblicaForm` (orologio in `_adesso()`, patchabile nei test).
- Protocollo: sequenza `protocollo` (annuale); registrazione solo con `servizi.registra_protocollo`;
  campi immutabili dopo la registrazione (si annulla); documenti solo aggiunti con `aggiungi_allegato`
  (nome su disco = impronta). Riservati: filtrare sempre con `Protocollo.objects.visibili_a(user)`.
- Download di file: `FileResponse` come allegato con `Content-Security-Policy: default-src 'none'; sandbox`.
- Segreti nel DB: `apps.core.cifratura.cifra/decifra` (chiave `CHIAVE_CIFRATURA`, mai nel DB).
- Lavori periodici: `manage.py pianificatore` (servizio) o i comandi singoli; devono essere rieseguibili.
- Organi: sequenze `riunione_<id organo>` (annuale), `verbale_<id>` (libro), `delibera_<id>` (annuale);
  verbale chiuso = immutabile (`servizi._controlla_aperto`); aventi diritto da `servizi.aventi_diritto`.
- Email: solo tramite `apps.comunicazioni.servizi.crea_invio` (bozza → `conferma` → coda `elabora_coda`);
  testi utente con segnaposto `{{ chiave }}` (`servizi.componi`, chiavi in `SEGNAPOSTO`), mai con il motore
  dei template. Finalità ≠ istituzionale ⇒ serve l'ultimo consenso prestato.
- Tesoreria: movimenti solo con `servizi.registra_movimento` (sequenza `prima_nota` annuale), esercizio
  chiuso = immutabile; le quote entrano con `servizi.registra_quota` (chiamata da `soci.servizi`).
- Traduzioni mancanti in Django: `locale/it/LC_MESSAGES/django.po` (ricompilare il `.mo` con `msgfmt`).
- Ogni modulo nuovo: test, pagina in `docs/operativo/`, aggiornamento di `docs/sistema/` se servono
  configurazioni, voce in `CHANGELOG.md`, tabella ruoli in `docs/operativo/ruoli.md`.

## Pubblicazione

- Nessun remote finché non c'è la **0.0.1 RC**: allora GitLab personale (`mygitlab.iz0bec.info/sbart64/`).
- Release stabile (1.0) su **GitHub**.

## Stato

Fase 0 completata (fondamenta + anagrafica). Fase 1: **Soci e tesseramento** completato
(`apps/soci`), **Protocollo** (`apps/protocollo`), **Organi sociali** (`apps/organi`), **Comunicazioni e
anniversari** (`apps/comunicazioni`), **Tesoreria** (`apps/tesoreria`).
Prossimo: Patrimonio.
