<!--
******************************************************
* Progetto:    Gestione Associazione
* Autore:      Bartolomeo Santoro aka IZ0BEC
* Email:       info@iz0bec.info
* Descrizione: Manuale operativo in PDF
* Licenza:     CC0 1.0 Universal (pubblico dominio)
* SPDX-License-Identifier: CC0-1.0
******************************************************
-->

# Manuale operativo in PDF

[manuale-operativo.pdf](manuale-operativo.pdf): il [manuale operativo](../operativo/README.md) in un
unico PDF, con copertina, indice e le schermate dell'applicazione. Le immagini mostrano **dati di
esempio** (un'associazione di fantasia), mai dati reali.

Si rigenera a ogni versione, con i dati dimostrativi (vedi [Sviluppo](../sistema/sviluppo.md#immagini-del-manuale)):

```bash
DATABASE_URL=.../gestione_demo uv run python manage.py manuale_pdf --uscita docs/manuale/manuale-operativo.pdf
```

Dall'applicazione lo stesso manuale si scarica con *Manuale → Manuale in PDF*: in quel caso la
copertina riporta la denominazione della propria associazione.
