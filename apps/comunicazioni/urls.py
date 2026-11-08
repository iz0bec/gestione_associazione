# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Indirizzi del modulo Comunicazioni e anniversari
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.urls import path

from . import views

app_name = "comunicazioni"

urlpatterns = [
    path("", views.InviiView.as_view(), name="invii"),
    path("nuova/", views.InvioNuovoView.as_view(), name="nuovo"),
    path("nuova/cerca/", views.CercaSoggettiView.as_view(), name="cerca"),
    path("nuova/scelta/", views.SceltaSoggettoView.as_view(), name="scelta"),
    path("<int:pk>/", views.InvioView.as_view(), name="invio"),
    path("<int:pk>/conferma/", views.ConfermaView.as_view(), name="conferma"),
    path("<int:pk>/annulla/", views.AnnullaInvioView.as_view(), name="annulla"),
    path("<int:pk>/ritenta/", views.RitentaView.as_view(), name="ritenta"),
    path("da/riunione/<int:pk>/", views.DaRiunioneView.as_view(), name="da_riunione"),
    path("da/tessera/<int:pk>/", views.DaTesseraView.as_view(), name="da_tessera"),
    path("da/domanda/<int:pk>/", views.DaDomandaView.as_view(), name="da_domanda"),
    path("modelli/", views.ModelliView.as_view(), name="modelli"),
    path("modelli/nuovo/", views.ModelloNuovoView.as_view(), name="modello_nuovo"),
    path("modelli/<int:pk>/", views.ModelloModificaView.as_view(), name="modello"),
    path("liste/", views.ListeView.as_view(), name="liste"),
    path("liste/nuova/", views.ListaNuovaView.as_view(), name="lista_nuova"),
    path("liste/<int:pk>/", views.ListaView.as_view(), name="lista"),
    path("liste/<int:pk>/modifica/", views.ListaModificaView.as_view(), name="lista_modifica"),
    path("anniversari/", views.AnniversariView.as_view(), name="anniversari"),
    path("auguri/", views.AuguriView.as_view(), name="auguri"),
    path("promemoria-rinnovo/", views.PromemoriaRinnovoView.as_view(), name="promemoria_rinnovo"),
    path(
        "promemoria-rinnovo/prepara/",
        views.PromemoriaPreparaView.as_view(),
        name="promemoria_prepara",
    ),
    path("auguri/<int:pk>/", views.AutomazioneView.as_view(), name="automazione"),
    path("ricorrenze/nuova/", views.RicorrenzaNuovaView.as_view(), name="ricorrenza_nuova"),
    path("ricorrenze/<int:pk>/", views.RicorrenzaModificaView.as_view(), name="ricorrenza"),
    path("onomastici/", views.OnomasticiView.as_view(), name="onomastici"),
    path("onomastici/nuovo/", views.OnomasticoNuovoView.as_view(), name="onomastico_nuovo"),
    path("onomastici/<int:pk>/", views.OnomasticoModificaView.as_view(), name="onomastico"),
]
