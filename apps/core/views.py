# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Viste di sistema: cruscotto, dati dell'organizzazione, registro
# *              attività, controllo di salute per il monitoraggio.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from datetime import date

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import connection
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.generic import CreateView, ListView, TemplateView, UpdateView

from .audit import Azione, campi_modificati, registra
from .forms import AspettoForm, OrganizzazioneCompletaForm, ServiziPostaForm
from .models import EventoAudit, Organizzazione


class PermessoMixin(LoginRequiredMixin, PermissionRequiredMixin):
    """Accesso solo ad utenti autenticati con il permesso indicato (altrimenti 403)."""

    raise_exception = False

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            self.raise_exception = True
        return super().handle_no_permission()


class CruscottoView(LoginRequiredMixin, TemplateView):
    template_name = "core/cruscotto.html"

    def get(self, request, *args, **kwargs):
        from .configurazione import da_configurare

        if da_configurare(request.user):  # primo accesso: configurazione guidata
            return redirect("configurazione", passo="ente")
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        from apps.anagrafica.models import Soggetto

        ctx = super().get_context_data(**kwargs)
        attivi = Soggetto.objects.filter(attivo=True)
        ctx["statistiche"] = {
            "soggetti": attivi.count(),
            "persone": attivi.filter(tipo=Soggetto.Tipo.PERSONA).count(),
            "enti": attivi.filter(tipo=Soggetto.Tipo.ENTE).count(),
        }
        from apps.comunicazioni.anniversari import eventi

        ctx["anniversari"] = [e for e in eventi(giorni=14) if e.tipo != "scomparsa"][:10]
        if self.request.user.has_perm("soci.view_socio"):
            ctx["soci"] = _riepilogo_soci()
        from apps.calendario import servizi as calendario

        ctx["impegni"] = calendario.prossimi(self.request.user, giorni=14)[:8]
        ctx["scadenze"] = calendario.scadenze_aperte(self.request.user)
        if self.request.user.has_perm("protocollo.view_protocollo"):
            ctx["protocollo"] = _riepilogo_protocollo(self.request.user)
        ctx["ultimi_eventi"] = EventoAudit.objects.filter(utente=self.request.user).select_related(
            "utente"
        )[:8]
        return ctx


def _riepilogo_soci():
    from apps.soci.models import DomandaIscrizione, Socio

    anno = date.today().year
    attivi = Socio.objects.attivi()
    return {
        "anno": anno,
        "attivi": attivi.count(),
        "in_regola": attivi.in_regola(anno).count(),
        "morosi": Socio.objects.morosi(anno).count(),
        "domande": DomandaIscrizione.objects.filter(
            stato=DomandaIscrizione.Stato.IN_ATTESA
        ).count(),
    }


def _riepilogo_protocollo(utente):
    from django.utils import timezone

    from apps.protocollo.models import MessaggioRicevuto, Protocollo

    visibili = Protocollo.objects.visibili_a(utente)
    return {
        "anno": visibili.filter(anno=timezone.localdate().year).count(),
        "ultimi": visibili.prefetch_related("corrispondenti")[:5],
        "posta": MessaggioRicevuto.objects.da_esaminare().count()
        if utente.has_perm("protocollo.view_messaggioricevuto")
        else 0,
    }


class OrganizzazioneView(PermessoMixin, UpdateView):
    permission_required = "core.gestisci_organizzazione"
    form_class = OrganizzazioneCompletaForm
    template_name = "core/organizzazione.html"
    success_url = reverse_lazy("core:organizzazione")

    def get_object(self, queryset=None):
        return Organizzazione.corrente()

    def form_valid(self, form):
        from .immagini import ImmagineNonValida, ripulisci

        dettagli = campi_modificati(form)
        org = form.save(commit=False)
        nuovo, togli = (
            form.cleaned_data.get("nuovo_logo_modulo"),
            form.cleaned_data.get("togli_logo_modulo"),
        )
        try:
            if nuovo:
                pulito = ripulisci(nuovo, lato=600, formato="PNG")
                if org.modulo_logo:
                    org.modulo_logo.delete(save=False)
                org.modulo_logo.save("logo.png", pulito, save=False)
            elif togli and org.modulo_logo:
                org.modulo_logo.delete(save=False)
        except ImmagineNonValida as e:
            form.add_error("nuovo_logo_modulo", e)
            return self.form_invalid(form)
        org.save()
        if dettagli.get("campi") or nuovo or togli:
            registra(Azione.MODIFICA, org, logo_modulo=bool(nuovo) or None, **dettagli)
        messages.success(self.request, "Dati dell'organizzazione salvati.")
        return redirect(self.success_url)


def _stato_smtp():
    """Configurazione dell'invio presa dalle impostazioni (mai la password)."""
    from django.conf import settings

    mailer = settings.MAILERS.get("default", {})
    backend = mailer.get("BACKEND", "")
    opzioni = mailer.get("OPTIONS", {})
    smtp = backend.endswith("smtp.EmailBackend")
    host = opzioni.get("host", "")
    return {
        "smtp": smtp,
        "backend": backend.rsplit(".", 2)[-2] if "." in backend else backend,
        "host": host,
        "porta": opzioni.get("port", ""),
        "utente": opzioni.get("username", ""),
        "configurato": smtp and host not in ("", "localhost", "127.0.0.1"),
        "mittente": settings.DEFAULT_FROM_EMAIL,
    }


class ServiziPostaView(PermessoMixin, UpdateView):
    """Interruttori generali dell'invio delle email e della lettura delle caselle IMAP."""

    permission_required = "core.gestisci_servizi_posta"
    form_class = ServiziPostaForm
    template_name = "core/servizi_posta.html"
    success_url = reverse_lazy("core:servizi_posta")

    def get_object(self, queryset=None):
        return Organizzazione.corrente()

    def form_valid(self, form):
        dettagli = campi_modificati(form)
        risposta = super().form_valid(form)
        if dettagli.get("campi"):
            registra(Azione.MODIFICA, self.object, descrizione="Servizi di posta",
                     invio_email=self.object.invio_email,
                     ricezione_posta=self.object.ricezione_posta, **dettagli)  # fmt: skip
        messages.success(self.request, "Servizi di posta aggiornati.")
        return risposta

    def get_context_data(self, **kwargs):
        from apps.comunicazioni.models import Destinatario, Invio
        from apps.protocollo.models import CasellaPosta

        ctx = super().get_context_data(**kwargs)
        ctx.update(
            smtp=_stato_smtp(),
            in_coda=Destinatario.objects.filter(
                invio__stato=Invio.Stato.IN_CODA, stato=Destinatario.Stato.IN_ATTESA
            ).count(),
            caselle=CasellaPosta.objects.all(),
        )
        return ctx


class VerificaCasellaView(PermessoMixin, View):
    """Prova di accesso a una casella IMAP (nulla viene scaricato)."""

    permission_required = "core.gestisci_servizi_posta"

    def post(self, request, pk):
        from django.shortcuts import get_object_or_404

        from apps.protocollo.models import CasellaPosta
        from apps.protocollo.posta import ErroreCasella, verifica_casella

        casella = get_object_or_404(CasellaPosta, pk=pk)
        try:
            esito = verifica_casella(casella)
        except ErroreCasella as e:
            messages.error(request, f"{casella}: {e}")
        except Exception as e:  # noqa: BLE001 - es. password non decifrabile
            messages.error(request, f"{casella}: verifica non riuscita ({type(e).__name__}).")
        else:
            messages.success(request, f"{casella}: {esito}")
        return redirect("core:servizi_posta")


class VerificaSmtpView(PermessoMixin, View):
    """Prova di accesso al server di invio (nessuna email spedita)."""

    permission_required = "core.gestisci_servizi_posta"

    def post(self, request):
        from django.core.mail import mailers

        stato = _stato_smtp()
        if not stato["smtp"]:
            messages.warning(request, f"Nessun server SMTP: le email vanno a «{stato['backend']}».")
            return redirect("core:servizi_posta")
        try:
            connessione = mailers.default
            if getattr(connessione, "timeout", None) is None:
                connessione.timeout = 20  # la verifica non deve bloccare la pagina
            connessione.open()
            connessione.close()
        except Exception as e:  # noqa: BLE001 - l'esito si mostra all'amministratore
            dettaglio = f"{type(e).__name__}: {str(e)[:150]}"
            messages.error(request, f"Server di invio {stato['host']}:{stato['porta']}: accesso "
                                    f"non riuscito ({dettaglio}).")  # fmt: skip
        else:
            messages.success(request, f"Server di invio {stato['host']}:{stato['porta']}: accesso "
                                      "riuscito (nessuna email spedita).")  # fmt: skip
        return redirect("core:servizi_posta")


class DocumentiPubbliciView(TemplateView):
    """Pagina pubblica (senza accesso) con statuto, regolamento e altri documenti pubblicati."""

    template_name = "core/pubblici/elenco.html"

    def get_context_data(self, **kwargs):
        from . import pubblici

        ctx = super().get_context_data(**kwargs)
        ctx["documenti"] = pubblici.pubblicati()
        return ctx


class DocumentoPubblicoView(View):
    """Il PDF di un documento pubblicato: nel browser, o da scaricare con ?scarica=1."""

    def get(self, request, pk, slug=None):
        from django.http import FileResponse, Http404

        from . import pubblici

        doc = pubblici.pubblicati().filter(pk=pk).first()
        if doc is None or not doc.file:
            raise Http404
        try:
            contenuto = doc.file.open("rb")
        except FileNotFoundError:
            raise Http404 from None
        risposta = FileResponse(
            contenuto, as_attachment=request.GET.get("scarica") == "1",
            filename=doc.nome_file or "documento.pdf", content_type="application/pdf",
        )  # fmt: skip
        risposta["X-Content-Type-Options"] = "nosniff"
        risposta["Cache-Control"] = "public, max-age=3600"
        return risposta


class GestioneDocumentiPubbliciView(PermessoMixin, ListView):
    permission_required = "core.gestisci_organizzazione"
    template_name = "core/pubblici/gestione.html"
    context_object_name = "documenti"

    def get_queryset(self):
        from .models import DocumentoPubblico

        return DocumentoPubblico.objects.all()


class _DocumentoPubblicoMixin:
    template_name = "core/pubblici/modulo.html"
    success_url = reverse_lazy("core:documenti_pubblici_gestione")

    def get_form_class(self):
        from .forms import DocumentoPubblicoForm

        return DocumentoPubblicoForm

    def form_valid(self, form):
        from . import pubblici

        try:
            self.object = pubblici.salva(form, self.request.user,
                                         form.cleaned_data.get("nuovo_file"))  # fmt: skip
        except pubblici.FileNonValido as e:
            form.add_error("nuovo_file", e)
            return self.form_invalid(form)
        messages.success(self.request, f"«{self.object}» salvato.")
        return redirect(self.success_url)


class DocumentoPubblicoNuovoView(PermessoMixin, _DocumentoPubblicoMixin, CreateView):
    permission_required = "core.gestisci_organizzazione"


class DocumentoPubblicoModificaView(PermessoMixin, _DocumentoPubblicoMixin, UpdateView):
    permission_required = "core.gestisci_organizzazione"

    def get_queryset(self):
        from .models import DocumentoPubblico

        return DocumentoPubblico.objects.all()


class AspettoView(PermessoMixin, UpdateView):
    permission_required = "core.gestisci_organizzazione"
    form_class = AspettoForm
    template_name = "core/aspetto.html"
    success_url = reverse_lazy("core:aspetto")

    def get_object(self, queryset=None):
        return Organizzazione.corrente()

    def form_valid(self, form):
        from .aspetto import salva_aspetto
        from .immagini import ImmagineNonValida

        try:
            salva_aspetto(
                form,
                self.request.user,
                logo=form.cleaned_data.get("nuovo_logo"),
                togli_logo=form.cleaned_data.get("togli_logo"),
            )
        except ImmagineNonValida as e:
            form.add_error("nuovo_logo", e)
            return self.form_invalid(form)
        messages.success(self.request, "Aspetto dell'interfaccia salvato.")
        return redirect(self.success_url)


class LogoModuloView(PermessoMixin, View):
    permission_required = "core.gestisci_organizzazione"

    def get(self, request):
        from .immagini import risposta_immagine

        return risposta_immagine(Organizzazione.corrente().modulo_logo)


class RegistroAttivitaView(PermessoMixin, ListView):
    permission_required = "core.view_eventoaudit"
    template_name = "core/registro_attivita.html"
    paginate_by = 50

    def get_queryset(self):
        qs = EventoAudit.objects.select_related("oggetto_tipo")
        if azione := self.request.GET.get("azione"):
            qs = qs.filter(azione=azione)
        if utente := self.request.GET.get("utente"):
            qs = qs.filter(utente_descrizione__icontains=utente)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["azioni"] = EventoAudit.Azione.choices
        return ctx


@never_cache
def salute(request):
    """Controllo per il monitoraggio: 200 se applicazione e database rispondono."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return HttpResponse("ok", content_type="text/plain")


# --- help in linea e crediti ------------------------------------------------------------


class AiutoView(LoginRequiredMixin, TemplateView):
    """Manuale operativo consultabile dall'applicazione (docs/operativo)."""

    template_name = "core/aiuto.html"

    def get_context_data(self, **kwargs):
        from . import aiuto

        ctx = super().get_context_data(**kwargs)
        nome = kwargs.get("pagina", aiuto.INDICE)
        titolo, html, indice = aiuto.pagina(nome)
        ctx.update(pagina=nome, titolo=titolo, html=html, indice=indice, pagine=aiuto.elenco())
        return ctx


class ManualePdfView(LoginRequiredMixin, View):
    """Il manuale operativo completo in PDF, con le immagini."""

    def get(self, request):
        from django.http import FileResponse

        from . import aiuto

        percorso = aiuto.pdf_manuale()
        return FileResponse(percorso.open("rb"), filename="manuale-operativo.pdf",
                            content_type="application/pdf")  # fmt: skip


class InformazioniView(LoginRequiredMixin, TemplateView):
    """Versione, autore, licenza e componenti di terze parti."""

    template_name = "core/informazioni.html"

    def get_context_data(self, **kwargs):
        from django.conf import settings

        from . import aiuto

        ctx = super().get_context_data(**kwargs)
        ctx.update(
            licenze=aiuto.licenze(), novita=aiuto.novita(), repository=settings.APP_REPOSITORY
        )
        return ctx
