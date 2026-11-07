# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Validazione di codice fiscale e partita IVA italiani.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from codicefiscale import codicefiscale
from django.core.exceptions import ValidationError


def valida_codice_fiscale(valore):
    """Codice fiscale di persona fisica (16 caratteri, con omocodie) o numerico di 11 cifre."""
    if not valore:
        return
    cf = valore.strip().upper()
    if len(cf) == 11 and cf.isdigit():
        valida_partita_iva(cf)
        return
    if not codicefiscale.is_valid(cf):
        raise ValidationError("Codice fiscale non valido.", code="cf_non_valido")


def valida_partita_iva(valore):
    """Partita IVA italiana: 11 cifre con cifra di controllo."""
    if not valore:
        return
    piva = valore.strip()
    if len(piva) != 11 or not piva.isdigit():
        raise ValidationError("La partita IVA è di 11 cifre.", code="piva_formato")
    somma = 0
    for i, c in enumerate(piva[:10]):
        n = int(c)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        somma += n
    if (10 - somma % 10) % 10 != int(piva[10]):
        raise ValidationError("Partita IVA non valida (cifra di controllo).", code="piva_controllo")


def dati_da_codice_fiscale(valore):
    """Sesso, data e luogo di nascita ricavati dal codice fiscale (None se non valido)."""
    if not valore or not codicefiscale.is_valid(valore.strip().upper()):
        return None
    d = codicefiscale.decode(valore.strip().upper())
    luogo = d.get("birthplace") or {}
    nome_luogo = luogo.get("name", "")
    if luogo.get("province") and luogo.get("province") != "EE":
        nome_luogo = f"{nome_luogo} ({luogo['province']})"
    return {
        "sesso": d["gender"],
        "data_nascita": d["birthdate"].date(),
        "luogo_nascita": nome_luogo,
    }
