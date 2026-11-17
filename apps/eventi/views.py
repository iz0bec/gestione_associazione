# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Pagine degli eventi: elenco, scheda con adesioni, esportazioni, modulo pubblico
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.conf import settings
from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import (
    CreateView,
    DetailView,
    FormView,
    ListView,
    TemplateView,
    UpdateView,
)

from apps.core.audit import Azione, campi_modificati, registra
from apps.core.middleware import ip_richiesta
from apps.core.models import Organizzazione
from apps.core.pdf import risposta_pdf
from apps.core.views import PermessoMixin

from . import servizi
from .forms import AdesioneForm, AdesionePubblicaForm, EventoForm
from .models import Adesione, Evento


class EventiView(PermessoMixin, ListView):
    permission_required = "eventi.view_evento"
    template_name = "eventi/elenco.html"
    context_object_name = "eventi"
    paginate_by = 30

    def get_queryset(self):
        adesso = timezone.now()
        self.passati = self.request.GET.get("passati") == "1"
        qs = Evento.objects.all()
        if self.passati:
            return qs.filter(inizio__lt=adesso).order_by("-inizio")
        return qs.filter(inizio__gte=adesso - timezone.timedelta(hours=12)).order_by("inizio")

    def get_context_data(self, **kwargs):
        return super().get_context_data(passati=self.passati, **kwargs)


class _EventoMixin:
    form_class = EventoForm
    template_name = "eventi/modulo.html"

    def form_valid(self, form):
        nuovo = form.instance.pk is None
        dettagli = {} if nuovo else campi_modificati(form)
        if nuovo:
            form.instance.creato_da = self.request.user
        form.instance.modificato_da = self.request.user
        risposta = super().form_valid(form)
        registra(Azione.CREAZIONE if nuovo else Azione.MODIFICA, self.object, **dettagli)
        messages.success(self.request, f"Evento «{self.object}» salvato.")
        return risposta


class EventoNuovoView(PermessoMixin, _EventoMixin, CreateView):
    permission_required = "eventi.add_evento"


class EventoModificaView(PermessoMixin, _EventoMixin, UpdateView):
    permission_required = "eventi.change_evento"
    model = Evento


class EventoView(PermessoMixin, DetailView):
    permission_required = "eventi.view_evento"
    model = Evento
    template_name = "eventi/evento.html"
    context_object_name = "evento"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        e = self.object
        ctx.update(
            adesioni=e.adesioni.select_related("soggetto").order_by("annullata", "cognome", "nome"),
            form=AdesioneForm(evento=e),
            link_pubblico=self.request.build_absolute_uri(
                reverse("evento_pubblico", args=[e.token])
            ) if not settings.URL_PUBBLICO else
            f"{settings.URL_PUBBLICO}{reverse('evento_pubblico', args=[e.token])}",
        )  # fmt: skip
        return ctx


class AdesioneNuovaView(PermessoMixin, View):
    permission_required = "eventi.change_evento"
    http_method_names = ["post"]

    def post(self, request, pk):
        evento = get_object_or_404(Evento, pk=pk)
        form = AdesioneForm(request.POST, evento=evento)
        if not form.is_valid():
            messages.error(request, "Controllare i dati dell'adesione: " + " ".join(
                str(e) for errori in form.errors.values() for e in errori))  # fmt: skip
            return redirect(evento)
        try:
            a = servizi.aderisci(evento, form.cleaned_data, origine=Adesione.Origine.SEGRETERIA,
                                 utente=request.user)  # fmt: skip
        except servizi.OperazioneNonValida as e:
            messages.error(request, " ".join(e.messages))
        else:
            messages.success(request, f"Adesione di {a} registrata.")
        return redirect(evento)


class AdesioneAnnullaView(PermessoMixin, View):
    permission_required = "eventi.change_evento"
    http_method_names = ["post"]

    def post(self, request, pk):
        a = get_object_or_404(Adesione.objects.select_related("evento"), pk=pk)
        try:
            servizi.annulla_adesione(a, request.user)
            messages.success(request, f"Adesione di {a} annullata.")
        except servizi.OperazioneNonValida as e:
            messages.error(request, " ".join(e.messages))
        return redirect(a.evento)


class AderentiView(PermessoMixin, View):
    """Elenco degli aderenti in Excel o foglio presenze in PDF."""

    permission_required = "eventi.view_evento"

    def get(self, request, pk, formato):
        evento = get_object_or_404(Evento, pk=pk)
        registra(Azione.ESPORTAZIONE, evento, descrizione=f"Aderenti a «{evento}»", formato=formato)
        if formato == "xlsx":
            risposta = HttpResponse(servizi.aderenti_xlsx(evento), content_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))  # fmt: skip
            risposta["Content-Disposition"] = f'attachment; filename="aderenti_{evento.pk}.xlsx"'
            risposta["Content-Security-Policy"] = "default-src 'none'; sandbox"
            return risposta
        if formato == "pdf":
            return risposta_pdf("eventi/pdf/presenze.html", {
                "evento": evento, "adesioni": evento.adesioni_valide(),
                "organizzazione": Organizzazione.corrente(),
            }, f"presenze_{evento.pk}.pdf")  # fmt: skip
        raise Http404


# --- modulo pubblico -------------------------------------------------------------------------


class EventoPubblicoView(FormView):
    template_name = "eventi/pubblico/evento.html"
    form_class = AdesionePubblicaForm

    def dispatch(self, request, *args, **kwargs):
        self.evento = get_object_or_404(Evento, token=kwargs["token"], pubblico=True)
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "evento": self.evento,
                "ip": ip_richiesta(self.request)}  # fmt: skip

    def get_context_data(self, **kwargs):
        return super().get_context_data(evento=self.evento, **kwargs)

    def form_valid(self, form):
        if not self.evento.si_puo_aderire:
            form.add_error(None, "Le adesioni sono chiuse o i posti sono esauriti.")
            return self.form_invalid(form)
        dati = {k: v for k, v in form.cleaned_data.items() if k not in ("sito", "token")}
        try:
            servizi.aderisci(self.evento, dati, origine=Adesione.Origine.PUBBLICO, ip=form.ip)
        except servizi.OperazioneNonValida as e:
            form.add_error(None, " ".join(e.messages))
            return self.form_invalid(form)
        return redirect("evento_pubblico_inviato", self.evento.token)


class EventoPubblicoInviatoView(TemplateView):
    template_name = "eventi/pubblico/inviata.html"

    def get_context_data(self, **kwargs):
        evento = get_object_or_404(Evento, token=kwargs["token"], pubblico=True)
        return super().get_context_data(evento=evento, **kwargs)
