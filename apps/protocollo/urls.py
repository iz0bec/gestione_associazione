# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Indirizzi del modulo Protocollo
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.urls import path

from . import views

app_name = "protocollo"

urlpatterns = [
    path("", views.ElencoView.as_view(), name="elenco"),
    path("nuovo/", views.NuovoView.as_view(), name="nuovo"),
    path("nuovo/cerca/", views.CercaSoggettiView.as_view(), name="cerca_soggetti"),
    path("nuovo/scelta/", views.SceltaSoggettoView.as_view(), name="scelta_soggetto"),
    path("protocollo.csv", views.EsportaView.as_view(), name="esporta"),
    path("<int:pk>/", views.DettaglioView.as_view(), name="dettaglio"),
    path("<int:pk>/modifica/", views.ModificaView.as_view(), name="modifica"),
    path("<int:pk>/annulla/", views.AnnullaView.as_view(), name="annulla"),
    path("<int:pk>/allegati/", views.AllegatiView.as_view(), name="allegati"),
    path("<int:pk>/ricevuta.pdf", views.RicevutaView.as_view(), name="ricevuta"),
    path(
        "<int:pk>/spedizione/<str:formato>/",
        views.SpedizioneView.as_view(),
        name="spedizione",
    ),
    path("<int:pk>/spedisci/", views.SpedisciView.as_view(), name="spedisci"),
    path(
        "spedizioni/<int:pk>/riprova/",
        views.RiprovaSpedizioneView.as_view(),
        name="riprova_spedizione",
    ),
    path("allegati/<int:pk>/", views.ScaricaAllegatoView.as_view(), name="allegato"),
    path("registri/", views.RegistriView.as_view(), name="registri"),
    path("registri/<int:pk>/", views.ScaricaRegistroView.as_view(), name="registro"),
    path("posta/", views.PostaView.as_view(), name="posta"),
    path("posta/<int:pk>/", views.MessaggioView.as_view(), name="messaggio"),
    path("posta/<int:pk>/protocolla/", views.ProtocollaMessaggioView.as_view(), name="protocolla"),
    path("posta/<int:pk>/scarta/", views.ScartaMessaggioView.as_view(), name="scarta"),
    path("posta/<int:pk>/ripristina/", views.RipristinaMessaggioView.as_view(), name="ripristina"),
    path("posta/azione/", views.AzionePostaView.as_view(), name="azione_posta"),
    path("posta/<int:pk>/originale/", views.ScaricaMessaggioView.as_view(), name="messaggio_eml"),
    path(
        "posta/<int:pk>/allegati/<int:indice>/",
        views.ScaricaMessaggioView.as_view(),
        name="messaggio_allegato",
    ),
    path("caselle/", views.CaselleView.as_view(), name="caselle"),
    path("caselle/<int:pk>/uso/", views.CasellaUsoView.as_view(), name="casella_uso"),
    path("titolario/", views.ClassificazioniView.as_view(), name="classificazioni"),
    path("modelli/", views.ModelliView.as_view(), name="modelli"),
    path("manuale/", views.ManualeGestioneView.as_view(), name="manuale"),
    path("manuale/bozza.pdf", views.ManualeGestionePdfView.as_view(), name="manuale_pdf"),
    path("manuale/adotta/", views.ManualeGestioneAdottaView.as_view(), name="manuale_adotta"),
    path(
        "manuale/pubblicazione/", views.PubblicazioneManualeView.as_view(), name="manuale_pubblica"
    ),
    path(
        "manuale/versione-<int:versione>.pdf",
        views.VersioneManualeView.as_view(),
        name="manuale_versione",
    ),
    path("modelli/nuovo/", views.ModelloNuovoView.as_view(), name="modello_nuovo"),
    path("modelli/<int:pk>/", views.ModelloModificaView.as_view(), name="modello"),
    path(
        "titolario/nuova/", views.ClassificazioneNuovaView.as_view(), name="classificazione_nuova"
    ),
    path(
        "titolario/<int:pk>/",
        views.ClassificazioneModificaView.as_view(),
        name="classificazione_modifica",
    ),
]
