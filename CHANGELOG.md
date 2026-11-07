# Changelog

Tutte le modifiche rilevanti del progetto. Formato: [Keep a Changelog](https://keepachangelog.com/it/1.1.0/);
versioni: [Semantic Versioning](https://semver.org/lang/it/).

## [Non rilasciato] - 0.0.1.dev0

### Aggiunto - Soci e tesseramento
- Libro soci con numero di iscrizione progressivo mai riutilizzato, tipologie con quota annua,
  ammissione dalla scheda anagrafica (categoria «Socio» automatica), sospensione, cessazione con causa
  (il decesso aggiorna l'anagrafica), riammissione con lo stesso numero.
- Tessere annuali numerate per anno, quota della tipologia modificabile, incasso con metodo e
  riferimento, ricevute numerate per anno in PDF, annullamento motivato senza riuso dei numeri.
- Rinnovo annuale massivo, pagina Tesseramento con riepilogo incassi, filtro soci in regola/morosi.
- Domande di iscrizione da segreteria e dal **modulo pubblico** `/iscrizione/` (attivabile), con
  campo trappola, tempo minimo, limite per IP; accoglimento con deduplica per codice fiscale e
  registrazione dei consensi, rigetto motivato.
- Stampa del libro soci in PDF ed esportazione CSV; generazione PDF con sole risorse locali.
- Riquadro socio nella scheda anagrafica, indicatori soci e domande sul cruscotto.
- Manuale operativo «Soci e tesseramento», tabella ruoli, ADR-013 e ADR-014.

### Aggiunto - Fondamenta
- Analisi dei progetti di origine (Protocollo ANCR, Gestione Soci, Gestione Assemblee), finalità e perimetro.
- Registro delle decisioni di architettura (Django 6.1, PostgreSQL, HTMX, Tabler, CC0).
- Accesso con django-allauth: login con username o email, recupero password, verifica in due
  passaggi (TOTP, passkey, codici di recupero); registrazione libera disattivata.
- Blocco dei tentativi di accesso ripetuti (django-axes), password Argon2 di almeno 12 caratteri.
- Sette ruoli predefiniti con permessi per funzione, allineati automaticamente dopo ogni migrazione.
- Dati dell'organizzazione, registro attività non modificabile, numerazioni atomiche condivise.
- Anagrafica unica di persone ed enti: categorie, codice fiscale con compilazione automatica e
  controllo di coerenza, partita IVA, data di decesso, consensi privacy, archiviazione,
  storia delle modifiche, ricerca istantanea, esportazione CSV protetta e registrata.
- Interfaccia Tabler con menu per ruolo, tema chiaro/scuro, uso da smartphone, CSP senza script inline.
- Manuale operativo, manuale di sistema, roadmap.
- Test automatici, lint, verifica intestazioni, pipeline GitLab CI.
- Dockerfile e compose di produzione (build ancora da verificare).
