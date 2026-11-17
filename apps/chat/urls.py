# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Indirizzi della chat interna
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.urls import path

from . import views

app_name = "chat"

urlpatterns = [
    path("", views.ChatView.as_view(), name="elenco"),
    path("nuova/", views.NuovaView.as_view(), name="nuova"),
    path("con/<int:utente>/", views.ConDirettaView.as_view(), name="con"),
    path("non-letti/", views.ContatoreView.as_view(), name="contatore"),
    path("<int:pk>/", views.ConversazioneView.as_view(), name="conversazione"),
    path("<int:pk>/messaggi/", views.MessaggiView.as_view(), name="messaggi"),
    path("<int:pk>/invia/", views.InviaView.as_view(), name="invia"),
    path("<int:pk>/aggiungi/", views.AggiungiView.as_view(), name="aggiungi"),
    path("<int:pk>/esci/", views.EsciView.as_view(), name="esci"),
    path("messaggi/<int:pk>/ritira/", views.RitiraView.as_view(), name="ritira"),
]
