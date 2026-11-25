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
    "soci.view_sezione",
    "soci.view_listinotessere",
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
    "soci.gestisci_ciclo_tessere",
]
SOCI_TESORERIA = [
    *SOCI_LETTURA,
    "soci.add_tessera",
    "soci.incassa_quota",
    "soci.annulla_tessera",
    "soci.gestisci_tessere_fisiche",
    "soci.add_listinotessere",
    "soci.change_listinotessere",
    "soci.gestisci_ciclo_tessere",
]

PROTOCOLLO_LETTURA = [
    "protocollo.view_protocollo",
    "protocollo.view_classificazione",
    "protocollo.view_modelloprotocollo",
]
PROTOCOLLO_OPERATIVO = [
    *PROTOCOLLO_LETTURA,
    "protocollo.add_protocollo",
    "protocollo.change_protocollo",
    "protocollo.esporta_protocollo",
    "protocollo.view_registrogiornaliero",
    "protocollo.view_messaggioricevuto",
    "protocollo.gestisci_posta",
    "protocollo.spedisci_protocollo",
]
PROTOCOLLO_RESPONSABILE = [
    *PROTOCOLLO_OPERATIVO,
    "protocollo.annulla_protocollo",
    "protocollo.vedi_riservati",
    "protocollo.add_classificazione",
    "protocollo.change_classificazione",
    "protocollo.add_modelloprotocollo",
    "protocollo.change_modelloprotocollo",
    "protocollo.gestisci_manuale",
    "protocollo.view_casellaposta",
    "protocollo.change_casellaposta",  # solo l'uso nel protocollo: si configura in Sistema
    "protocollo.ripulisci_posta",
]

ORGANI_LETTURA = [
    "organi.view_organo",
    "organi.view_carica",
    "organi.view_rappresentantelegale",
    "organi.view_modelloconvocazione",
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
    "organi.add_modelloconvocazione",
    "organi.change_modelloconvocazione",
]

ELEZIONI_LETTURA = [
    "elezioni.view_rinnovo",
    "elezioni.view_lista",
    "elezioni.view_profiloelettorale",
]
ELEZIONI_GESTIONE = [
    *ELEZIONI_LETTURA,
    "elezioni.gestisci_rinnovi",
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
    "comunicazioni.view_promemoriarinnovo",
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
    "comunicazioni.change_promemoriarinnovo",
]

TESORERIA_LETTURA = [
    "tesoreria.view_movimento",
    "tesoreria.view_esercizio",
    "tesoreria.view_previsione",
    "tesoreria.view_conto",
    "tesoreria.view_voce",
    "tesoreria.view_incasso",
    "tesoreria.view_storno",
]
TESORERIA_GESTIONE = [
    *TESORERIA_LETTURA,
    "tesoreria.add_movimento",
    "tesoreria.change_movimento",
    "tesoreria.annulla_movimento",
    "tesoreria.add_esercizio",
    "tesoreria.change_saldoconto",
    "tesoreria.chiudi_esercizio",
    "tesoreria.change_previsione",
    "tesoreria.add_conto",
    "tesoreria.change_conto",
    "tesoreria.add_voce",
    "tesoreria.change_voce",
    "tesoreria.registra_incasso",
    "tesoreria.storna",
]

PATRIMONIO_LETTURA = [
    "patrimonio.view_bene",
    "patrimonio.view_categoriabene",
    "patrimonio.view_passaggioconsegne",
]
PATRIMONIO_GESTIONE = [
    *PATRIMONIO_LETTURA,
    "patrimonio.add_bene",
    "patrimonio.change_bene",
    "patrimonio.movimenta_bene",
    "patrimonio.valuta_bene",
    "patrimonio.add_categoriabene",
    "patrimonio.change_categoriabene",
    "patrimonio.add_passaggioconsegne",
]

DOCUMENTI_STAMPA = ["documenti.view_modellostampa", "documenti.stampa_documento"]
DOCUMENTI_GESTIONE = [
    *DOCUMENTI_STAMPA,
    "documenti.add_modellostampa",
    "documenti.change_modellostampa",
]

CALENDARIO_LETTURA = ["calendario.view_appuntamento", "eventi.view_evento"]
CALENDARIO_GESTIONE = [
    *CALENDARIO_LETTURA,
    "calendario.add_appuntamento",
    "calendario.change_appuntamento",
    "eventi.add_evento",
    "eventi.change_evento",
]

PROGETTI_LETTURA = [  # tutti gli organi consultano, propongono idee e le valutano
    "progetti.view_idea",
    "progetti.add_idea",
    "progetti.valuta_idea",
    "progetti.view_progetto",
    "progetti.view_finalitastatutaria",
    "progetti.view_criteriovalutazione",
]
PROGETTI_GESTIONE = [
    *PROGETTI_LETTURA,
    "progetti.change_idea",
    "progetti.gestisci_idee",
    "progetti.add_progetto",
    "progetti.change_progetto",
    "progetti.gestisci_progetti",
    "progetti.add_finalitastatutaria",
    "progetti.change_finalitastatutaria",
    "progetti.add_criteriovalutazione",
    "progetti.change_criteriovalutazione",
]

RUOLI = {
    "Amministratore di sistema": [
        "organi.gestisci_firme",
        "organi.gestisci_timbri",  # timbri degli enti: solo da Sistema → Organizzazione
        *CALENDARIO_GESTIONE,
        *ANAGRAFICA_SCRITTURA,
        "anagrafica.esporta_soggetti",
        "anagrafica.importa_soggetti",
        "anagrafica.esporta_dati_personali",
        "anagrafica.anonimizza_soggetto",
        "anagrafica.add_categoria",
        "anagrafica.change_categoria",
        "core.gestisci_organizzazione",
        "core.gestisci_backup",
        "core.gestisci_servizi_posta",
        "core.ripristina_backup",
        "core.view_eventoaudit",
        "api.view_clienteapi",
        "api.gestisci_controparti",
        "accounts.view_utente",
        "accounts.add_utente",
        "accounts.change_utente",
        *SOCI_SEGRETERIA,
        *SOCI_TESORERIA,
        "soci.valuta_domanda",
        "soci.add_sezione",
        "soci.change_sezione",
        "soci.importa_soci",
        "soci.trasferisci_socio",
        *PROTOCOLLO_RESPONSABILE,
        *ORGANI_SEGRETERIA,
        "organi.add_organo",
        "organi.change_organo",
        *ELEZIONI_GESTIONE,
        "elezioni.add_profiloelettorale",
        "elezioni.change_profiloelettorale",
        *COMUNICAZIONI_GESTIONE,
        *TESORERIA_GESTIONE,
        *PATRIMONIO_GESTIONE,
        *DOCUMENTI_GESTIONE,
        *PROGETTI_GESTIONE,
    ],
    "Presidente": [
        "organi.gestisci_firme",
        *CALENDARIO_GESTIONE,
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
        *ELEZIONI_GESTIONE,
        *COMUNICAZIONI_INVIO,
        *TESORERIA_LETTURA,
        *PATRIMONIO_LETTURA,
        "patrimonio.add_passaggioconsegne",
        *DOCUMENTI_STAMPA,
        *PROGETTI_GESTIONE,
    ],
    "Segretario": [
        "organi.gestisci_firme",
        *CALENDARIO_GESTIONE,
        *ANAGRAFICA_SCRITTURA,
        "anagrafica.esporta_soggetti",
        "anagrafica.importa_soggetti",
        "anagrafica.esporta_dati_personali",
        "anagrafica.add_categoria",
        "anagrafica.change_categoria",
        "core.gestisci_organizzazione",
        *SOCI_SEGRETERIA,
        "soci.valuta_domanda",
        "soci.importa_soci",
        "soci.trasferisci_socio",
        *PROTOCOLLO_RESPONSABILE,
        *ORGANI_SEGRETERIA,
        *ELEZIONI_GESTIONE,
        "elezioni.add_profiloelettorale",
        "elezioni.change_profiloelettorale",
        *COMUNICAZIONI_GESTIONE,
        "tesoreria.view_esercizio",
        *PATRIMONIO_GESTIONE,
        *DOCUMENTI_GESTIONE,
        *PROGETTI_GESTIONE,
    ],
    "Tesoriere": [
        "comunicazioni.change_promemoriarinnovo",
        *CALENDARIO_GESTIONE,
        *ANAGRAFICA_LETTURA,
        *SOCI_TESORERIA,
        *PROTOCOLLO_LETTURA,
        *ORGANI_LETTURA,
        *ELEZIONI_LETTURA,
        *COMUNICAZIONI_INVIO,
        *TESORERIA_GESTIONE,
        *PATRIMONIO_GESTIONE,
        *DOCUMENTI_STAMPA,
        *PROGETTI_LETTURA,
    ],
    # responsabile di una sezione: le assegnazioni in «sezioni» dell'utente limitano soci,
    # tessere e domande alla sua sezione; nessun accesso ai moduli della federazione
    "Presidente di sezione": [
        "organi.gestisci_firme",  # solo le firme della propria sezione (i timbri: amministratore)
        *ANAGRAFICA_SCRITTURA,
        *SOCI_LETTURA,
        "soci.add_socio",
        "soci.change_socio",
        "soci.cessa_socio",
        "soci.add_tessera",
        "soci.add_domandaiscrizione",
        "soci.valuta_domanda",
        "soci.esporta_libro_soci",
        "soci.gestisci_tessere_fisiche",
        *ELEZIONI_GESTIONE,  # il rinnovo della propria sezione (filtrato per sezione)
        *CALENDARIO_LETTURA,
        *DOCUMENTI_STAMPA,
        *PROGETTI_LETTURA,
    ],
    "Addetto protocollo": [
        *CALENDARIO_LETTURA,
        *ANAGRAFICA_SCRITTURA,
        *PROTOCOLLO_OPERATIVO,
        *ORGANI_LETTURA,
        *ELEZIONI_LETTURA,
        *COMUNICAZIONI_LETTURA,
        *DOCUMENTI_STAMPA,
        *PROGETTI_LETTURA,
    ],
    "Consigliere": [
        *CALENDARIO_LETTURA,
        *ANAGRAFICA_LETTURA,
        *SOCI_LETTURA,
        *PROTOCOLLO_LETTURA,
        *ORGANI_LETTURA,
        *ELEZIONI_LETTURA,
        "comunicazioni.view_ricorrenza",
        "tesoreria.view_esercizio",
        *PATRIMONIO_LETTURA,
        *PROGETTI_LETTURA,
    ],
    "Revisore": [
        *CALENDARIO_LETTURA,
        *ANAGRAFICA_LETTURA,
        *SOCI_LETTURA,
        "core.view_eventoaudit",
        *PROTOCOLLO_LETTURA,
        "protocollo.esporta_protocollo",
        "protocollo.view_registrogiornaliero",
        *ORGANI_LETTURA,
        *ELEZIONI_LETTURA,
        *COMUNICAZIONI_LETTURA,
        *TESORERIA_LETTURA,
        *PATRIMONIO_LETTURA,
        *PROGETTI_LETTURA,
    ],
    "Progettista": [  # da abbinare ad altri ruoli: chi segue i progetti
        *PROGETTI_GESTIONE,
        *CALENDARIO_LETTURA,
        *ANAGRAFICA_LETTURA,
        *PROTOCOLLO_LETTURA,
        *ORGANI_LETTURA,
    ],
}

# il manuale di gestione adottato è consultabile da tutti gli utenti, la chat interna è per tutti
for _permessi in RUOLI.values():
    _permessi.append("protocollo.view_manualegestione")
    _permessi.append("chat.usa_chat")


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
