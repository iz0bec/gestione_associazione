# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Amministrazione tecnica delle comunicazioni (registro in sola lettura)
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.contrib import admin

from apps.core.admin import SolaLettura

from .models import Destinatario, Invio, Modello, Onomastico, Ricorrenza


@admin.register(Invio)
class InvioAdmin(SolaLettura):
    list_display = ["oggetto", "stato", "finalita", "creato_il"]
    list_filter = ["stato", "finalita"]


@admin.register(Destinatario)
class DestinatarioAdmin(SolaLettura):
    list_display = ["nome", "email", "stato", "inviato_il"]
    list_filter = ["stato"]


admin.site.register([Modello, Onomastico, Ricorrenza])
