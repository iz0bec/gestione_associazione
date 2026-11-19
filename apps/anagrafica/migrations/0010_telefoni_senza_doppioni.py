# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Pulizia di telefono e cellulare: toglie i numeri ripetuti (anche fra i due campi)
# *              e i pezzi troncati lasciati dagli scambi fra installazioni («X, X, X…»). Le
# *              schede già pulite non cambiano; la logica è copiata qui (non importa l'app).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import re

from django.db import migrations


def _cifre(numero):
    cifre = re.sub(r"\D", "", numero)
    if numero.strip().startswith("+39"):
        return cifre[2:]
    return cifre[4:] if cifre.startswith("0039") else cifre


def _numeri(testo, visti):
    """Numeri del campo non ancora visti (aggiorna `visti`), senza pezzi troncati."""
    elenco = []
    for numero in re.split(r"[,;/]| e ", testo or ""):
        numero = " ".join(numero.split())
        cifre = _cifre(numero)
        if len(cifre) < 6 or cifre in visti:
            continue
        visti.add(cifre)
        elenco.append((numero, cifre))
    return elenco


def ripulisci(apps, schema_editor):
    Soggetto = apps.get_model("anagrafica", "Soggetto")
    qs = Soggetto.objects.exclude(telefono="", cellulare="").only("pk", "telefono", "cellulare")
    for p in qs.iterator():
        visti = set()
        cellulari = _numeri(p.cellulare, visti)  # prima il cellulare: un mobile resta lì
        fissi = _numeri(p.telefono, visti)
        tutte = [c for _, c in cellulari + fissi]

        def _tieni(elenco):
            return ", ".join(n for n, c in elenco if not (
                len(c) < 9 and any(a != c and a.startswith(c) for a in tutte)))

        grezzi = [n for t in (p.telefono, p.cellulare) for n in re.split(r"[,;/]| e ", t or "")
                  if len(_cifre(n)) >= 6]  # fmt: skip
        tenuti = [c for _, c in cellulari + fissi if not (
            len(c) < 9 and any(a != c and a.startswith(c) for a in tutte))]  # fmt: skip
        if len(tenuti) == len(grezzi):
            continue  # nulla di ripetuto o troncato: la scheda resta com'è
        telefono, cellulare = _tieni(fissi)[:30], _tieni(cellulari)[:30]
        if (telefono, cellulare) != (p.telefono, p.cellulare):
            Soggetto.objects.filter(pk=p.pk).update(telefono=telefono, cellulare=cellulare)


class Migration(migrations.Migration):
    dependencies = [("anagrafica", "0009_sms_whatsapp")]

    operations = [migrations.RunPython(ripulisci, migrations.RunPython.noop)]
