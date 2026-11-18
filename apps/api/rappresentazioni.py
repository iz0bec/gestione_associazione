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
