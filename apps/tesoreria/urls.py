# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Indirizzi del modulo Tesoreria
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.urls import path

from . import views

app_name = "tesoreria"

urlpatterns = [
    path("", views.CruscottoView.as_view(), name="cruscotto"),
    path("esercizi/nuovo/", views.EsercizioNuovoView.as_view(), name="esercizio_nuovo"),
    path("esercizi/<int:anno>/saldi/", views.SaldiInizialiView.as_view(), name="saldi"),
    path("esercizi/<int:anno>/chiusura/", views.ChiudiEsercizioView.as_view(), name="chiusura"),
    path("esercizi/<int:anno>/preventivo/", views.PreventivoView.as_view(), name="preventivo"),
    path("esercizi/<int:anno>/rendiconto/", views.RendicontoView.as_view(), name="rendiconto"),
    path("rendiconti/", views.RendicontiView.as_view(), name="rendiconti"),
    path("prima-nota/", views.PrimaNotaView.as_view(), name="prima_nota"),
    path("prima-nota.csv", views.EsportaPrimaNotaView.as_view(), name="esporta"),
    path("movimenti/nuovo/", views.MovimentoNuovoView.as_view(), name="movimento_nuovo"),
    path("movimenti/<int:pk>/", views.MovimentoView.as_view(), name="movimento"),
    path(
        "movimenti/<int:pk>/modifica/",
        views.MovimentoModificaView.as_view(),
        name="movimento_modifica",
    ),
    path(
        "movimenti/<int:pk>/annulla/",
        views.AnnullaMovimentoView.as_view(),
        name="movimento_annulla",
    ),
    path(
        "movimenti/<int:pk>/giustificativo/",
        views.GiustificativoView.as_view(),
        name="giustificativo",
    ),
    path("quote/", views.QuoteView.as_view(), name="quote"),
    path("conti/", views.ContiView.as_view(), name="conti"),
    path("conti/nuovo/", views.ContoNuovoView.as_view(), name="conto_nuovo"),
    path("conti/<int:pk>/", views.ContoModificaView.as_view(), name="conto"),
    path("voci/", views.VociView.as_view(), name="voci"),
    path("voci/nuova/", views.SottovoceNuovaView.as_view(), name="sottovoce_nuova"),
    path("voci/<int:pk>/", views.SottovoceModificaView.as_view(), name="sottovoce"),
]
