# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Ruoli predefiniti e relativi permessi. Applicati dopo ogni migrate (idempotente).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

# Ogni ruolo è un gruppo Django. I permessi sono "app_label.codename".
# Aggiungere qui i permessi dei nuovi moduli: al successivo migrate i gruppi vengono allineati.
# Un utente può avere più ruoli; il superutente ha sempre tutti i permessi.

ANAGRAFICA_LETTURA = ["anagrafica.view_soggetto", "anagrafica.view_categoria"]
ANAGRAFICA_SCRITTURA = [
    *ANAGRAFICA_LETTURA,
    "anagrafica.add_soggetto",
    "anagrafica.change_soggetto",
    "anagrafica.archivia_soggetto",
    "anagrafica.add_consenso",
    "anagrafica.change_consenso",
    "anagrafica.view_consenso",
]

SOCI_LETTURA = [
    "soci.view_socio",
    "soci.view_tessera",
    "soci.view_tipologiasocio",
    "soci.view_domandaiscrizione",
    "soci.view_lottotessere",
    "soci.view_cartatessera",
]
SOCI_SEGRETERIA = [
    *SOCI_LETTURA,
    "soci.add_socio",
    "soci.change_socio",
    "soci.cessa_socio",
    "soci.add_tessera",
    "soci.add_domandaiscrizione",
    "soci.esporta_libro_soci",
    "soci.add_tipologiasocio",
    "soci.change_tipologiasocio",
    "soci.gestisci_tessere_fisiche",
]
SOCI_TESORERIA = [
    *SOCI_LETTURA,
    "soci.add_tessera",
    "soci.incassa_quota",
    "soci.annulla_tessera",
    "soci.gestisci_tessere_fisiche",
]

PROTOCOLLO_LETTURA = ["protocollo.view_protocollo", "protocollo.view_classificazione"]
PROTOCOLLO_OPERATIVO = [
    *PROTOCOLLO_LETTURA,
    "protocollo.add_protocollo",
    "protocollo.change_protocollo",
    "protocollo.esporta_protocollo",
    "protocollo.view_registrogiornaliero",
    "protocollo.view_messaggioricevuto",
    "protocollo.gestisci_posta",
]
PROTOCOLLO_RESPONSABILE = [
    *PROTOCOLLO_OPERATIVO,
    "protocollo.annulla_protocollo",
    "protocollo.vedi_riservati",
    "protocollo.add_classificazione",
    "protocollo.change_classificazione",
    "protocollo.view_casellaposta",
    "protocollo.add_casellaposta",
    "protocollo.change_casellaposta",
]

ORGANI_LETTURA = [
    "organi.view_organo",
    "organi.view_carica",
    "organi.view_riunione",
    "organi.view_verbale",
    "organi.view_delibera",
]
ORGANI_SEGRETERIA = [
    *ORGANI_LETTURA,
    "organi.add_riunione",
    "organi.change_riunione",
    "organi.convoca_riunione",
    "organi.verbalizza",
    "organi.gestisci_cariche",
]

COMUNICAZIONI_LETTURA = [
    "comunicazioni.view_invio",
    "comunicazioni.view_ricorrenza",
    "comunicazioni.view_modello",
    "comunicazioni.view_lista",
    "comunicazioni.view_onomastico",
]
COMUNICAZIONI_INVIO = [
    *COMUNICAZIONI_LETTURA,
    "comunicazioni.add_invio",
    "comunicazioni.conferma_invio",
]
COMUNICAZIONI_GESTIONE = [
    *COMUNICAZIONI_INVIO,
    "comunicazioni.add_modello",
    "comunicazioni.change_modello",
    "comunicazioni.add_lista",
    "comunicazioni.change_lista",
    "comunicazioni.add_ricorrenza",
    "comunicazioni.change_ricorrenza",
    "comunicazioni.add_onomastico",
    "comunicazioni.change_onomastico",
    "comunicazioni.view_automazione",
    "comunicazioni.change_automazione",
]

RUOLI = {
    "Amministratore di sistema": [
        *ANAGRAFICA_SCRITTURA,
        "anagrafica.esporta_soggetti",
        "anagrafica.add_categoria",
        "anagrafica.change_categoria",
        "core.gestisci_organizzazione",
        "core.view_eventoaudit",
        "accounts.view_utente",
        "accounts.add_utente",
        "accounts.change_utente",
        *SOCI_SEGRETERIA,
        *SOCI_TESORERIA,
        "soci.valuta_domanda",
        *PROTOCOLLO_RESPONSABILE,
        *ORGANI_SEGRETERIA,
        "organi.change_organo",
        *COMUNICAZIONI_GESTIONE,
    ],
    "Presidente": [
        *ANAGRAFICA_SCRITTURA,
        "anagrafica.esporta_soggetti",
        "core.view_eventoaudit",
        *SOCI_LETTURA,
        "soci.esporta_libro_soci",
        "soci.valuta_domanda",
        *PROTOCOLLO_LETTURA,
        "protocollo.vedi_riservati",
        "protocollo.esporta_protocollo",
        "protocollo.view_registrogiornaliero",
        "protocollo.view_messaggioricevuto",
        *ORGANI_LETTURA,
        "organi.add_riunione",
        "organi.change_riunione",
        "organi.convoca_riunione",
        "organi.verbalizza",
        *COMUNICAZIONI_INVIO,
    ],
    "Segretario": [
        *ANAGRAFICA_SCRITTURA,
        "anagrafica.esporta_soggetti",
        "anagrafica.add_categoria",
        "anagrafica.change_categoria",
        "core.gestisci_organizzazione",
        *SOCI_SEGRETERIA,
        "soci.valuta_domanda",
        *PROTOCOLLO_RESPONSABILE,
        *ORGANI_SEGRETERIA,
        *COMUNICAZIONI_GESTIONE,
    ],
    "Tesoriere": [
        *ANAGRAFICA_LETTURA,
        *SOCI_TESORERIA,
        *PROTOCOLLO_LETTURA,
        *ORGANI_LETTURA,
        *COMUNICAZIONI_INVIO,
    ],
    "Addetto protocollo": [
        *ANAGRAFICA_SCRITTURA,
        *PROTOCOLLO_OPERATIVO,
        *ORGANI_LETTURA,
        *COMUNICAZIONI_LETTURA,
    ],
    "Consigliere": [
        *ANAGRAFICA_LETTURA,
        *SOCI_LETTURA,
        *PROTOCOLLO_LETTURA,
        *ORGANI_LETTURA,
        "comunicazioni.view_ricorrenza",
    ],
    "Revisore": [
        *ANAGRAFICA_LETTURA,
        *SOCI_LETTURA,
        "core.view_eventoaudit",
        *PROTOCOLLO_LETTURA,
        "protocollo.esporta_protocollo",
        "protocollo.view_registrogiornaliero",
        *ORGANI_LETTURA,
        *COMUNICAZIONI_LETTURA,
    ],
}


def configura_ruoli(verbose=False):
    from django.contrib.auth.models import Group, Permission

    for nome, permessi in RUOLI.items():
        gruppo, _ = Group.objects.get_or_create(name=nome)
        trovati = []
        for p in permessi:
            app_label, codename = p.split(".", 1)
            perm = Permission.objects.filter(
                content_type__app_label=app_label, codename=codename
            ).first()
            if perm is None:
                raise LookupError(f"Permesso inesistente nel ruolo '{nome}': {p}")
            trovati.append(perm)
        gruppo.permissions.set(trovati)
        if verbose:
            print(f"{nome}: {len(trovati)} permessi")
