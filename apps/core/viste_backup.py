# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Backup e ripristino dall'interfaccia. Il ripristino gira in un processo
# *              separato (sostituisce anche le sessioni): la pagina di avanzamento non usa il
# *              database ed è raggiungibile con un indirizzo firmato.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import subprocess  # noqa: S404 - avvio di manage.py con argomenti fissi, senza shell
import sys
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.core import signing
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache

from . import backup
from .audit import Azione, registra
from .views import PermessoMixin

SALE_STATO = "core.ripristino"
CONFERMA = "RIPRISTINA"


class BackupView(PermessoMixin, View):
    permission_required = "core.gestisci_backup"

    def get(self, request):
        return render(request, "core/backup.html", {
            "backup": backup.elenco(),
            "cartella": backup.cartella(),
            "automatico": settings.BACKUP_AUTOMATICO,
            "ora": settings.BACKUP_ORA,
            "conserva": settings.BACKUP_CONSERVA,
            "formato": backup.formato_dimensione,
        })  # fmt: skip

    def post(self, request):
        try:
            if request.POST.get("azione") == "carica":
                file = request.FILES.get("file")
                if not file:
                    raise backup.BackupNonValido("Scegliere il file del backup.")
                p = backup.salva_caricato(file)
                registra(Azione.CREAZIONE, descrizione="Backup caricato", file=p.name)
                messages.success(request, f"Backup caricato e verificato: {p.name}.")
            else:
                p = backup.crea(motivo="manuale", utente=request.user)
                messages.success(request, f"Backup creato: {p.name}.")
        except backup.BackupNonValido as e:
            messages.error(request, " ".join(e.messages))
        return redirect("core:backup")


class ScaricaBackupView(PermessoMixin, View):
    permission_required = "core.gestisci_backup"

    def get(self, request, nome):
        try:
            p = backup.percorso(nome)
        except backup.BackupNonValido:
            raise Http404 from None
        registra(Azione.ESPORTAZIONE, descrizione="Backup scaricato", file=nome)
        return FileResponse(p.open("rb"), as_attachment=True, filename=nome,
                            content_type="application/x-tar")  # fmt: skip


class EliminaBackupView(PermessoMixin, View):
    permission_required = "core.gestisci_backup"
    http_method_names = ["post"]

    def post(self, request, nome):
        try:
            backup.elimina(nome, request.user)
            messages.success(request, f"Backup {nome} eliminato.")
        except backup.BackupNonValido as e:
            messages.error(request, " ".join(e.messages))
        return redirect("core:backup")


class RipristinoView(PermessoMixin, View):
    permission_required = "core.ripristina_backup"

    def _backup(self, nome):
        try:
            p = backup.percorso(nome)
            return p, backup.verifica(p), None
        except backup.BackupNonValido as e:
            return None, None, " ".join(e.messages)

    def get(self, request, nome):
        p, manifesto, errore = self._backup(nome)
        return render(request, "core/ripristino.html",
                      {"nome": nome, "manifesto": manifesto, "errore": errore,
                       "conferma": CONFERMA})  # fmt: skip

    def post(self, request, nome):
        p, manifesto, errore = self._backup(nome)
        if errore:
            messages.error(request, errore)
            return redirect("core:backup")
        if request.POST.get("conferma", "").strip() != CONFERMA or not request.user.check_password(
            request.POST.get("password", "")
        ):
            messages.error(request, f"Scrivere {CONFERMA} e la propria password per confermare.")
            return redirect("core:ripristino", nome=nome)
        if (backup.cartella() / ".ripristino.lock").exists():
            messages.error(request, "Un ripristino è già in corso.")
            return redirect("core:backup")
        registra(Azione.MODIFICA, descrizione="Ripristino avviato", file=nome)
        (backup.cartella() / ".ripristino.json").unlink(missing_ok=True)
        backup.scrivi_stato(esito="in_corso", fase="Avvio", file=nome, messaggio="")
        avvia_ripristino(nome, str(request.user))
        token = signing.dumps(nome, salt=SALE_STATO)
        return redirect(reverse("stato_ripristino") + f"?t={token}")


def avvia_ripristino(nome, utente):
    base = Path(settings.BASE_DIR)
    registro = backup.cartella() / ".ripristino.log"
    with open(registro, "w") as uscita:
        subprocess.Popen(  # noqa: S603
            [sys.executable, str(base / "manage.py"), "ripristina", nome, "--stato",
             "--conferma", settings.DATABASES["default"]["NAME"], "--utente", utente],
            cwd=base, stdout=uscita, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
            start_new_session=True,
        )  # fmt: skip


@method_decorator(never_cache, name="dispatch")
class StatoRipristinoView(View):
    """Avanzamento del ripristino: nessun accesso al database (le sessioni vengono sostituite)."""

    def get(self, request):
        try:
            nome = signing.loads(request.GET.get("t", ""), salt=SALE_STATO, max_age=3 * 3600)
        except signing.BadSignature:
            raise Http404 from None
        stato = backup.stato_ripristino() or {}
        if stato.get("file") != nome:
            raise Http404
        return render(request, "core/stato_ripristino.html", {"stato": stato, "nome": nome})
