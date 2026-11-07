# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Amministrazione tecnica del protocollo (sola consultazione: registrazioni,
# *              annullamenti e allegati passano dall'interfaccia, che numera e registra).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.contrib import admin

from apps.core.admin import SolaLettura

from .models import (
    CasellaPosta,
    Classificazione,
    MessaggioRicevuto,
    Protocollo,
    RegistroGiornaliero,
)


@admin.register(Classificazione)
class ClassificazioneAdmin(admin.ModelAdmin):
    list_display = ["codice", "descrizione", "attiva"]


@admin.register(Protocollo)
class ProtocolloAdmin(SolaLettura):
    list_display = ["segnatura", "registrato_il", "direzione", "oggetto", "annullato"]
    list_filter = ["anno", "direzione", "annullato"]
    search_fields = ["oggetto"]


@admin.register(RegistroGiornaliero)
class RegistroGiornalieroAdmin(SolaLettura):
    list_display = ["data", "registrazioni", "impronta"]


@admin.register(CasellaPosta)
class CasellaPostaAdmin(SolaLettura):
    list_display = ["nome", "server", "utente", "attiva", "ultimo_controllo", "ultimo_errore"]


@admin.register(MessaggioRicevuto)
class MessaggioRicevutoAdmin(SolaLettura):
    list_display = ["oggetto", "mittente", "data", "stato"]
    list_filter = ["stato", "casella"]
