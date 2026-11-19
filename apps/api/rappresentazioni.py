# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Risorse dell'API come JSON del contratto (schemi Evento e Sezione) e
# *              visibilità per controparte: alle integrazioni solo gli eventi con modulo pubblico.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from datetime import UTC

from apps.eventi.models import Evento
from apps.soci.models import Sezione

from .models import ClienteApi


def data_ora(valore):
    return valore.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ") if valore else None


def evento(e: Evento) -> dict:
    return {
        "uuid": str(e.uuid),
        "versione": e.versione,
        "modificato_il": data_ora(e.modificato_il),
        "titolo": e.titolo,
        "tipo": e.tipo,
        "inizio": data_ora(e.inizio),
        "fine": data_ora(e.fine),
        "luogo": e.luogo,
        "descrizione": e.descrizione,
        "quota": e.quota,
        "posti": e.posti,
        "posti_liberi": e.posti_liberi,
        "accompagnatori_max": e.accompagnatori,
        "adesioni_aperte": e.adesioni_aperte,
        "chiusura_adesioni": data_ora(e.chiusura_adesioni),
        "pubblico": e.pubblico,
        "annullato": e.annullato,
    }


def sezione(s: Sezione) -> dict:
    return {
        "uuid": str(s.uuid),
        "versione": s.versione,
        "modificato_il": data_ora(s.modificato_il),
        "codice": s.codice,
        "nome": s.nome,
        "comune": s.comune,
        "provincia": s.provincia,
        "email": s.email,
        "attiva": s.attiva,
    }


def eventi_visibili(cliente: ClienteApi):
    eventi = Evento.objects.all()
    if cliente.tipo == ClienteApi.Tipo.INTEGRAZIONE:
        eventi = eventi.filter(pubblico=True)
    return eventi


def sezioni_visibili(cliente: ClienteApi):
    return Sezione.objects.all()


# flusso → (ambito, risorse visibili alla controparte)
FLUSSI = {
    "eventi": ("eventi:lettura", eventi_visibili),
    "sezioni": ("sezioni:lettura", sezioni_visibili),
}


def adesione(a) -> dict:
    return {
        "uuid": str(a.uuid),
        "versione": a.versione,
        "modificato_il": data_ora(a.modificata_il),
        "evento": str(a.evento.uuid),
        "cognome": a.cognome,
        "nome": a.nome,
        "email": a.email,
        "telefono": a.telefono,
        "accompagnatori": a.accompagnatori,
        "note": a.note,
        "riferimento_esterno": a.riferimento_esterno,
        "annullata": a.annullata,
        "origine": a.origine,
    }


def documento(request, d) -> dict:
    from django.urls import reverse

    return {
        "id": d.pk,
        "titolo": d.titolo,
        "descrizione": d.descrizione,
        "nome_file": d.nome_file,
        "dimensione": d.dimensione,
        "modificato_il": data_ora(d.modificato_il),
        "file": reverse("api_v1:documento_file", args=[d.pk]),
        "pagina_pubblica": request.build_absolute_uri(d.get_absolute_url()),
    }


def organigramma() -> list:
    """Cariche in corso degli organi attivi (assemblee escluse): ruolo e nome, nient'altro."""
    from apps.organi.models import Organo
    from apps.organi.servizi import organigramma as livelli

    risultato = []
    organi = (
        Organo.objects.filter(attivo=True)
        .exclude(tipo=Organo.Tipo.ASSEMBLEA)
        .select_related("sezione")
        .order_by("sezione__ordine", "ordine", "nome")
    )
    for organo in organi:
        componenti = [
            {"ruolo": c.ruolo, "ruolo_descrizione": c.get_ruolo_display(),
             "nome": c.soggetto.nome_completo, "dal": c.dal.isoformat() if c.dal else None}
            for riga in livelli(organo) for c in riga
        ]  # fmt: skip
        if componenti:
            risultato.append({
                "organo": organo.nome, "tipo": organo.tipo,
                "sezione": organo.sezione.codice if organo.sezione_id else None,
                "componenti": componenti,
            })  # fmt: skip
    return risultato


def ente() -> dict:
    """Dati di contatto istituzionali dell'organizzazione (mai dati di persone)."""
    from apps.core.models import Organizzazione

    org = Organizzazione.corrente()
    campi = ("denominazione", "codice_fiscale", "partita_iva", "indirizzo", "cap", "comune",
             "provincia", "telefono", "email", "pec", "sito_web")  # fmt: skip
    return {c: getattr(org, c) or "" for c in campi}
