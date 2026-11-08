# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: URL dell'app core
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.urls import path

from . import views, viste_backup

app_name = "core"

urlpatterns = [
    path("", views.CruscottoView.as_view(), name="cruscotto"),
    path("organizzazione/", views.OrganizzazioneView.as_view(), name="organizzazione"),
    path("organizzazione/aspetto/", views.AspettoView.as_view(), name="aspetto"),
    path("organizzazione/logo-modulo/", views.LogoModuloView.as_view(), name="logo_modulo"),
    path("sistema/backup/", viste_backup.BackupView.as_view(), name="backup"),
    path("sistema/posta/", views.ServiziPostaView.as_view(), name="servizi_posta"),
    path(
        "sistema/documenti-pubblici/",
        views.GestioneDocumentiPubbliciView.as_view(),
        name="documenti_pubblici_gestione",
    ),
    path(
        "sistema/documenti-pubblici/nuovo/",
        views.DocumentoPubblicoNuovoView.as_view(),
        name="documento_pubblico_nuovo",
    ),
    path(
        "sistema/documenti-pubblici/<int:pk>/",
        views.DocumentoPubblicoModificaView.as_view(),
        name="documento_pubblico_modifica",
    ),
    path(
        "sistema/posta/verifica/<int:pk>/",
        views.VerificaCasellaView.as_view(),
        name="verifica_casella",
    ),
    path("sistema/posta/verifica-invio/", views.VerificaSmtpView.as_view(), name="verifica_smtp"),
    path(
        "sistema/backup/<str:nome>/scarica/",
        viste_backup.ScaricaBackupView.as_view(),
        name="scarica_backup",
    ),
    path(
        "sistema/backup/<str:nome>/elimina/",
        viste_backup.EliminaBackupView.as_view(),
        name="elimina_backup",
    ),
    path(
        "sistema/backup/<str:nome>/ripristina/",
        viste_backup.RipristinoView.as_view(),
        name="ripristino",
    ),
    path("aiuto/", views.AiutoView.as_view(), name="aiuto"),
    path("aiuto/<slug:pagina>/", views.AiutoView.as_view(), name="aiuto_pagina"),
    path("informazioni/", views.InformazioniView.as_view(), name="informazioni"),
    path("registro-attivita/", views.RegistroAttivitaView.as_view(), name="registro_attivita"),
]
