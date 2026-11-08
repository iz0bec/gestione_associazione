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
from django.views.decorators.cache import never_cache
from django.views.generic import ListView, TemplateView, UpdateView

from .audit import Azione, campi_modificati, registra
from .forms import AspettoForm, OrganizzazioneForm
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
        if self.request.user.has_perm("organi.view_riunione"):
            from apps.organi.models import Riunione

            ctx["riunioni"] = (
                Riunione.objects.filter(
                    stato=Riunione.Stato.CONVOCATA, prima_convocazione__date__gte=date.today()
                )
                .select_related("organo")
                .order_by("prima_convocazione")[:5]
            )
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
    form_class = OrganizzazioneForm
    template_name = "core/organizzazione.html"
    success_url = reverse_lazy("core:organizzazione")

    def get_object(self, queryset=None):
        return Organizzazione.corrente()

    def form_valid(self, form):
        dettagli = campi_modificati(form)
        risposta = super().form_valid(form)
        if dettagli.get("campi"):
            registra(Azione.MODIFICA, self.object, **dettagli)
        messages.success(self.request, "Dati dell'organizzazione salvati.")
        return risposta


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
