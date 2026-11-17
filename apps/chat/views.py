# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Pagine della chat interna: elenco delle conversazioni, nuova conversazione,
# *              conversazione con aggiornamento automatico (HTMX), invio, ritiro, gruppi
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import FormView, TemplateView

from apps.core.views import PermessoMixin

from . import servizi
from .forms import AggiungiForm, NuovaConversazioneForm
from .models import MAX_TESTO, Messaggio

MOSTRATI = 200  # messaggi caricati all'apertura di una conversazione


class _ChatMixin(PermessoMixin):
    permission_required = servizi.PERMESSO


class _ConversazioneMixin(_ChatMixin):
    """Carica la conversazione solo se l'utente ne fa parte (altrimenti 404, anche per l'admin)."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.has_perm(servizi.PERMESSO):
            self.conversazione = (
                servizi.conversazioni_di(request.user).filter(pk=kwargs["pk"]).first()
            )
            if self.conversazione is None:
                raise Http404
        return super().dispatch(request, *args, **kwargs)


def _dopo(request):
    try:
        return max(int(request.GET.get("dopo", 0)), 0)
    except ValueError:
        return 0


class ChatView(_ChatMixin, TemplateView):
    template_name = "chat/elenco.html"

    def get_context_data(self, **kwargs):
        u = self.request.user
        conversazioni = list(servizi.conversazioni_di(u))
        for c in conversazioni:
            c.nome = c.nome_per(u)
        return super().get_context_data(
            conversazioni=conversazioni, persone=servizi.utenti_chat(escluso=u), **kwargs
        )


class NuovaView(_ChatMixin, FormView):
    form_class = NuovaConversazioneForm
    template_name = "chat/nuova.html"

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "utente": self.request.user}

    def get_initial(self):
        return {"persone": self.request.GET.getlist("con")}

    def form_valid(self, form):
        persone = list(form.cleaned_data["persone"])
        titolo = form.cleaned_data["titolo"]
        try:
            if len(persone) == 1 and not titolo.strip():
                c = servizi.conversazione_diretta(self.request.user, persone[0])
            else:
                c = servizi.crea_gruppo(self.request.user, titolo, persone)
        except servizi.OperazioneNonValida as e:
            form.add_error(None, str(e))
            return self.form_invalid(form)
        return redirect(c)


class ConDirettaView(_ChatMixin, View):
    """Apre (o crea) la conversazione a due con un utente: /chat/con/<id>/."""

    def get(self, request, utente):
        altro = get_object_or_404(servizi.utenti_chat(escluso=request.user), pk=utente)
        try:
            return redirect(servizi.conversazione_diretta(request.user, altro))
        except servizi.OperazioneNonValida as e:
            messages.error(request, str(e))
            return redirect("chat:elenco")


class ConversazioneView(_ConversazioneMixin, TemplateView):
    template_name = "chat/conversazione.html"

    def get_context_data(self, **kwargs):
        c, u = self.conversazione, self.request.user
        ultimi = list(c.messaggi.select_related("autore").order_by("-pk")[:MOSTRATI])[::-1]
        ultimo = ultimi[-1].pk if ultimi else 0
        servizi.segna_letti(c, u, ultimo)
        conversazioni = list(servizi.conversazioni_di(u)[:30])
        for x in conversazioni:
            x.nome = x.nome_per(u)
        return super().get_context_data(
            conversazione=c, nome=c.nome_per(u), elenco=ultimi, ultimo=ultimo,
            altri_messaggi=c.messaggi.count() > len(ultimi), presenti=c.presenti(),
            conversazioni=conversazioni, max_testo=MAX_TESTO,
            aggiungi=AggiungiForm(utente=u, conversazione=c) if c.gruppo else None,
            **kwargs,
        )  # fmt: skip


class MessaggiView(_ConversazioneMixin, View):
    """Messaggi arrivati dopo «dopo» (richiamata ogni pochi secondi dalla pagina)."""

    def get(self, request, pk):
        c = self.conversazione
        dopo = _dopo(request)
        nuovi = list(c.messaggi.select_related("autore").filter(pk__gt=dopo)[:MOSTRATI])
        ultimo = nuovi[-1].pk if nuovi else dopo
        if nuovi:
            servizi.segna_letti(c, request.user, ultimo)
        return render(request, "chat/_messaggi.html", {
            "conversazione": c, "elenco": nuovi, "ultimo": ultimo, "coda": True,
        })  # fmt: skip


class InviaView(_ConversazioneMixin, View):
    def post(self, request, pk):
        try:
            servizi.invia(self.conversazione, request.user, request.POST.get("testo", ""))
        except servizi.OperazioneNonValida as e:
            if request.htmx:
                return HttpResponse(str(e), status=422)
            messages.error(request, str(e))
            return redirect(self.conversazione)
        if request.htmx:  # la pagina chiede subito i nuovi messaggi
            return HttpResponse(status=204, headers={"HX-Trigger": "chat-nuovi"})
        return redirect(self.conversazione)


class RitiraView(_ChatMixin, View):
    def post(self, request, pk):
        m = get_object_or_404(Messaggio.objects.select_related("conversazione"), pk=pk)
        try:
            servizi.ritira(m, request.user)
        except servizi.OperazioneNonValida as e:
            raise Http404 from e
        return redirect(m.conversazione)


class AggiungiView(_ConversazioneMixin, View):
    def post(self, request, pk):
        c = self.conversazione
        form = AggiungiForm(request.POST, utente=request.user, conversazione=c)
        if form.is_valid():
            try:
                servizi.aggiungi(c, request.user, list(form.cleaned_data["persone"]))
            except servizi.OperazioneNonValida as e:
                messages.error(request, str(e))
        else:
            messages.error(request, "Scegli almeno una persona da aggiungere.")
        return redirect(c)


class EsciView(_ConversazioneMixin, View):
    def post(self, request, pk):
        try:
            servizi.esci(self.conversazione, request.user)
        except servizi.OperazioneNonValida as e:
            messages.error(request, str(e))
            return redirect(self.conversazione)
        messages.success(request, f"Hai lasciato il gruppo «{self.conversazione}».")
        return redirect("chat:elenco")


class ContatoreView(_ChatMixin, View):
    """Numero dei messaggi non letti, per la barra superiore."""

    def get(self, request):
        return render(request, "chat/_contatore.html", {"n": servizi.non_letti(request.user)})
