# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Ciclo delle tessere via API (ADR-030, F4 blocco A), lato di chi risponde:
# *              flusso «tessere» risolto per la controparte (la federazione vede la sezione
# *              legata, la sezione la propria), documenti JSON e PDF di consegne, ricevute,
# *              richieste e prese in carico. Niente dati personali.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import base64
from datetime import UTC

from apps.core.models import Organizzazione
from apps.soci.models import ConsegnaTessere, LottoTessere, RichiestaTessere, Sezione

from .models import ClienteApi

AMBITO = "tessere:scambio"


def sezione_per(cliente: ClienteApi):
    """La sezione del ciclo che la controparte può vedere, o None."""
    if cliente.ruolo == ClienteApi.Ruolo.SEZIONE and cliente.sezione_id:
        return cliente.sezione  # siamo la federazione: la sua sezione nel nostro elenco
    if (
        cliente.ruolo == ClienteApi.Ruolo.FEDERAZIONE
        and not Sezione.objects.filter(attiva=True)[1:2].exists()
    ):
        return Sezione.predefinita()  # siamo la sezione: la nostra
    # con più sezioni siamo la federazione: una controparte indicata come «nostra federazione»
    # è un errore di configurazione e non deve vedere i dati della sezione principale
    return None


def flusso_per(cliente):
    sezione = sezione_per(cliente)
    return f"tessere:{sezione.codice}" if sezione else None


def _data_ora(valore):
    return valore.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ") if valore else None


def _pdf(template, contesto):
    from apps.core.pdf import genera_pdf

    contesto = {"organizzazione": Organizzazione.corrente(), **contesto}
    return base64.b64encode(genera_pdf(template, contesto)).decode()


def _mittente():
    org = Organizzazione.corrente()
    return org.denominazione


def consegna(c: ConsegnaTessere, con_pdf=True):
    from apps.soci import ciclo

    dati = {
        "uuid": str(c.uuid), "versione": c.versione, "modificato_il": _data_ora(c.modificato_il),
        "anno": c.anno, "numero": c.numero, "data": c.data.isoformat(),
        "serie": c.blocco.serie, "numero_da": c.numero_da, "numero_a": c.numero_a,
        "cifre": c.blocco.cifre, "quantita": c.quantita,
        "prezzo_unitario": f"{c.prezzo_unitario:.2f}", "importo": f"{c.importo:.2f}",
        "modalita": c.modalita, "modalita_descrizione": c.get_modalita_display(),
        "note_distribuzione": c.note_distribuzione, "mittente": _mittente(),
    }  # fmt: skip
    if con_pdf:
        riga = next((r for r in ciclo.quadratura(c.anno) if r.sezione.pk == c.sezione_id), None)
        dati["pdf"] = _pdf("soci/pdf/consegna_tessere.html", {"consegna": c, "riga": riga})
    return dati


def ricevuta(i, con_pdf=True):
    dati = {
        "uuid": str(i.uuid), "versione": i.versione, "modificato_il": _data_ora(i.modificato_il),
        "anno": i.anno_tessere, "data": i.data.isoformat(), "ricevuta": i.codice_ricevuta,
        "importo": f"{i.importo:.2f}", "metodo": i.get_metodo_display(),
        "riferimento": i.riferimento, "causale": i.causale, "mittente": _mittente(),
        "stornata": i.storni.exists(),
    }  # fmt: skip
    if con_pdf:
        dati["pdf"] = _pdf("tesoreria/pdf/ricevuta_incasso.html", {"incasso": i})
    return dati


def richiesta(r: RichiestaTessere, con_pdf=True):
    from apps.soci import ciclo

    dati = {
        "uuid": str(r.uuid), "versione": r.versione, "modificato_il": _data_ora(r.modificato_il),
        "anno": r.anno, "quantita": r.quantita, "data": r.data.isoformat(), "note": r.note,
        "mittente": _mittente(),
    }  # fmt: skip
    if con_pdf:
        dati["pdf"] = base64.b64encode(ciclo.pdf_richiesta(r)).decode()
    return dati


def presa(lotto: LottoTessere, con_pdf=True):
    return {
        "uuid": str(lotto.uuid), "versione": lotto.versione,
        "modificato_il": _data_ora(lotto.modificato_il), "consegna": str(lotto.consegna_uuid),
        "data": lotto.data_acquisizione.isoformat(), "quantita": lotto.quantita,
        "mittente": _mittente(),
    }  # fmt: skip


def documento(cliente, risorsa, uuid_risorsa):
    """(dati) del documento `risorsa` della sezione visibile alla controparte, o None."""
    from apps.tesoreria.models import Incasso

    sezione = sezione_per(cliente)
    if sezione is None:
        return None
    if risorsa == "consegna":
        c = (
            ConsegnaTessere.objects.filter(uuid=uuid_risorsa, sezione=sezione)
            .select_related("blocco", "sezione")
            .first()
        )
        return consegna(c) if c else None
    if risorsa == "ricevuta":
        i = Incasso.objects.filter(uuid=uuid_risorsa, sezione=sezione, tipo="tessere").first()
        return ricevuta(i) if i else None
    if risorsa == "richiesta":
        r = RichiestaTessere.objects.filter(uuid=uuid_risorsa, sezione=sezione,
                                            uuid_origine__isnull=True,
                                            inviata_il__isnull=False).first()  # fmt: skip
        return richiesta(r) if r else None
    if risorsa == "presa":
        lotto = LottoTessere.objects.filter(uuid=uuid_risorsa, sezione=sezione,
                                            consegna_uuid__isnull=False).first()  # fmt: skip
        return presa(lotto) if lotto else None
    return None
