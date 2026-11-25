# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Verifica dei requisiti dei bandi sui dati del gestionale (organizzazione, soci,
# *              tesoreria). Solo dati reali: ciò che non si può accertare resta «da verificare».
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

from django.utils import timezone

from .models import Requisito

SI, NO, VERIFICARE = Requisito.Esito.SI, Requisito.Esito.NO, Requisito.Esito.VERIFICARE


@dataclass(frozen=True)
class Verifica:
    nome: str
    parametro: str  # etichetta del parametro richiesto ("" = nessuno)
    funzione: Callable
    numerico: bool = False


def _org():
    from apps.core.models import Organizzazione

    return Organizzazione.corrente()


def _runts(bando, _):
    n = _org().iscrizione_runts.strip()
    return (SI, f"Iscritta al RUNTS: {n}.") if n else (NO, "Iscrizione al RUNTS non indicata.")


def _codice_fiscale(bando, _):
    cf = _org().codice_fiscale.strip()
    return (SI, f"Codice fiscale {cf}.") if cf else (NO, "Codice fiscale dell'ente non indicato.")


def _pec(bando, _):
    pec = _org().pec.strip()
    return (SI, f"PEC {pec}.") if pec else (NO, "Nessuna PEC nei dati dell'organizzazione.")


def _elenco(parametro):
    return [v.strip().lower() for v in parametro.replace(";", ",").split(",") if v.strip()]


def _sede_provincia(bando, parametro):
    provincia = _org().provincia.strip()
    if not provincia:
        return VERIFICARE, "Provincia della sede non indicata."
    if provincia.lower() in _elenco(parametro):
        return SI, f"Sede in provincia di {provincia.upper()}."
    return NO, f"La sede è in provincia di {provincia.upper()}."


def _sede_comune(bando, parametro):
    comune = _org().comune.strip()
    if not comune:
        return VERIFICARE, "Comune della sede non indicato."
    if comune.lower() in _elenco(parametro):
        return SI, f"Sede a {comune}."
    return NO, f"La sede è a {comune}."


def _soci_attivi(bando, parametro):
    from apps.soci.models import Socio

    n = Socio.objects.attivi().count()
    esito = SI if n >= int(parametro) else NO
    return esito, f"{n} soci attivi (richiesti almeno {parametro})."


def _soci_in_regola(bando, parametro):
    from apps.soci.models import Socio

    anno = timezone.localdate().year
    n = Socio.objects.attivi().in_regola(anno).count()
    esito = SI if n >= int(parametro) else NO
    return esito, f"{n} soci in regola con la quota {anno} (richiesti almeno {parametro})."


def _rendiconto(bando, _):
    from apps.tesoreria.models import Esercizio

    anno = timezone.localdate().year - 1
    e = Esercizio.objects.filter(anno=anno).first()
    if e is None:
        return VERIFICARE, f"Nessun esercizio {anno} nella tesoreria del gestionale."
    if e.stato != Esercizio.Stato.CHIUSO:
        return NO, f"L'esercizio {anno} non è chiuso."
    if not e.approvazione.strip():
        return VERIFICARE, f"Esercizio {anno} chiuso, approvazione del rendiconto non indicata."
    return SI, f"Rendiconto {anno} approvato: {e.approvazione}."


def _finalita(bando, _):
    comuni = list(bando.finalita.filter(attiva=True))
    if comuni:
        nomi = ", ".join(f.codice or f.titolo for f in comuni)
        return SI, f"Il bando risponde alle finalità statutarie: {nomi}."
    return VERIFICARE, "Indicare nel bando a quali finalità statutarie risponde."


VERIFICHE = {
    "finalita": Verifica("Coerenza con le finalità statutarie", "", _finalita),
    "runts": Verifica("Iscrizione al RUNTS", "", _runts),
    "codice_fiscale": Verifica("Codice fiscale dell'ente", "", _codice_fiscale),
    "pec": Verifica("Casella PEC", "", _pec),
    "sede_provincia": Verifica("Sede in una provincia", "sigle, es. PZ, MT", _sede_provincia),
    "sede_comune": Verifica("Sede in un comune", "comuni, separati da virgole", _sede_comune),
    "soci_attivi": Verifica("Numero minimo di soci attivi", "numero", _soci_attivi, True),
    "soci_in_regola": Verifica(
        "Numero minimo di soci in regola con la quota", "numero", _soci_in_regola, True
    ),
    "rendiconto": Verifica("Rendiconto dell'anno precedente approvato", "", _rendiconto),
}

SCELTE = [("", "Da controllare a mano")] + [(k, v.nome) for k, v in VERIFICHE.items()]


def controlla_parametro(verifica, parametro):
    """Messaggio d'errore per un parametro non valido ("" se va bene)."""
    v = VERIFICHE.get(verifica)
    if v is None:
        return ""
    parametro = (parametro or "").strip()
    if v.parametro and not parametro:
        return f"Indicare il parametro ({v.parametro})."
    if v.numerico and not parametro.isdigit():
        return "Il parametro deve essere un numero intero."
    return ""


@dataclass
class Esito:
    requisito: Requisito
    esito: str
    spiegazione: str
    automatico: bool

    @property
    def etichetta(self):
        return Requisito.Esito(self.esito).label


def esito(requisito):
    """Esito di un requisito: quello indicato a mano prevale sulla verifica automatica."""
    if requisito.esito_manuale:
        return Esito(
            requisito, requisito.esito_manuale, requisito.nota or "Indicato a mano.", False
        )
    v = VERIFICHE.get(requisito.verifica)
    if v is None:
        return Esito(requisito, VERIFICARE, requisito.nota or "Da controllare a mano.", False)
    try:
        risultato, spiegazione = v.funzione(requisito.bando, requisito.parametro.strip())
    except (ValueError, TypeError):
        risultato, spiegazione = VERIFICARE, "Parametro non valido."
    return Esito(requisito, risultato, spiegazione, True)


def riepilogo(bando):
    esiti = [esito(r) for r in bando.requisiti.all()]
    conteggi = Counter(e.esito for e in esiti)
    return {
        "esiti": esiti,
        "soddisfatti": conteggi[SI],
        "mancanti": conteggi[NO],
        "da_verificare": conteggi[VERIFICARE],
        "tutti": bool(esiti) and conteggi[SI] == len(esiti),
    }
