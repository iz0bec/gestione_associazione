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
    ],
    "Presidente": [*ANAGRAFICA_SCRITTURA, "anagrafica.esporta_soggetti", "core.view_eventoaudit"],
    "Segretario": [
        *ANAGRAFICA_SCRITTURA,
        "anagrafica.esporta_soggetti",
        "anagrafica.add_categoria",
        "anagrafica.change_categoria",
        "core.gestisci_organizzazione",
    ],
    "Tesoriere": [*ANAGRAFICA_LETTURA],
    "Addetto protocollo": [*ANAGRAFICA_SCRITTURA],
    "Consigliere": [*ANAGRAFICA_LETTURA],
    "Revisore": [*ANAGRAFICA_LETTURA, "core.view_eventoaudit"],
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
