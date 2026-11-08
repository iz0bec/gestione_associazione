# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Viste del calendario: prossimi impegni, mese, appuntamenti e scadenze, file .ics,
# *              collegamento personale per i calendari (pubblico, protetto dal codice segreto).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DetailView, TemplateView, UpdateView

from apps.core.views import PermessoMixin

from . import servizi
from .forms import AppuntamentoForm
from .models import Appuntamento, FeedCalendario

CHIAVE_NUOVO = "calendario_codice_nuovo"


def _risposta_ics(testo, *, scarica):
    risposta = HttpResponse(testo, content_type="text/calendar; charset=utf-8")
    modo = "attachment" if scarica else "inline"
    risposta["Content-Disposition"] = f'{modo}; filename="calendario.ics"'
    risposta["Content-Security-Policy"] = "default-src 'none'; sandbox"
    return risposta


class CalendarioView(LoginRequiredMixin, TemplateView):
    template_name = "calendario/calendario.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        utente = self.request.user
        feed = FeedCalendario.objects.filter(utente=utente).first()
        compleanni = self.request.GET.get("compleanni") == "1"
        ctx.update(
            prossimi=servizi.prossimi(utente, compleanni=compleanni),
            compleanni=compleanni,
            puo_compleanni=utente.has_perm("soci.view_socio"),
            feed=feed,
            oggi=timezone.localdate(),
            scadenze=servizi.scadenze_aperte(utente),
        )
        codice = self.request.session.pop(CHIAVE_NUOVO, None)
        if codice and feed:
            url = self.request.build_absolute_uri(reverse("calendario:feed_pubblico",
                                                          args=[codice]))  # fmt: skip
            ctx.update(url_feed=url, url_webcal="webcal://" + url.split("://", 1)[1])
        return ctx


class ScaricaView(LoginRequiredMixin, View):
    def get(self, request):
        compleanni = request.GET.get("compleanni") == "1"
        testo = servizi.calendario_di(request.user, compleanni=compleanni,
                                      base_url=request.build_absolute_uri("/"))  # fmt: skip
        return _risposta_ics(testo, scarica=True)


class CollegamentoView(LoginRequiredMixin, View):
    def post(self, request):
        if request.POST.get("azione") == "revoca":
            servizi.revoca_collegamento(request.user)
            messages.success(request, "Collegamento revocato: i calendari abbonati non si "
                                      "aggiornano più.")  # fmt: skip
        else:
            compleanni = bool(request.POST.get("compleanni")) and request.user.has_perm(
                "soci.view_socio"
            )
            request.session[CHIAVE_NUOVO] = servizi.crea_collegamento(
                request.user, compleanni=compleanni
            )
            messages.success(request, "Nuovo collegamento creato: copiarlo ora, non sarà più "
                                      "mostrato.")  # fmt: skip
        return redirect("calendario:calendario")


class FeedPubblicoView(View):
    """Letto dai calendari senza accesso: vale il codice segreto, con i permessi del titolare."""

    def get(self, request, codice):
        feed = servizi.feed_da_codice(codice)
        if feed is None:
            raise Http404
        testo = servizi.calendario_di(feed.utente, compleanni=feed.compleanni,
                                      base_url=request.build_absolute_uri("/"))  # fmt: skip
        risposta = _risposta_ics(testo, scarica=False)
        risposta["Cache-Control"] = "private, max-age=900"
        risposta["X-Robots-Tag"] = "noindex"
        return risposta


class MeseView(LoginRequiredMixin, TemplateView):
    template_name = "calendario/mese.html"

    def _mese(self):
        oggi = timezone.localdate()
        try:
            anno, numero = (int(x) for x in self.request.GET.get("m", "").split("-"))
            return date(anno, numero, 1)
        except ValueError:
            return oggi.replace(day=1)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        primo = self._mese()
        compleanni = self.request.GET.get("compleanni") == "1"
        precedente = (primo.replace(day=1) - timedelta(days=1)).replace(day=1)
        successivo = (primo.replace(day=28) + timedelta(days=4)).replace(day=1)
        settimane = servizi.mese(self.request.user, primo.year, primo.month,
                                 compleanni=compleanni)  # fmt: skip
        ctx.update(
            primo=primo, settimane=settimane, compleanni=compleanni,
            precedente=f"{precedente:%Y-%m}", successivo=f"{successivo:%Y-%m}",
            oggi=timezone.localdate(), puo_compleanni=self.request.user.has_perm("soci.view_socio"),
            giorni_mese=[c for s in settimane for c in s if c["nel_mese"] and c["eventi"]],
        )  # fmt: skip
        return ctx


class AppuntamentoView(PermessoMixin, DetailView):
    permission_required = "calendario.view_appuntamento"
    model = Appuntamento
    template_name = "calendario/appuntamento.html"
    context_object_name = "appuntamento"


class _AppuntamentoMixin:
    model = Appuntamento
    form_class = AppuntamentoForm
    template_name = "calendario/appuntamento_modulo.html"

    def form_valid(self, form):
        self.object = servizi.salva_appuntamento(form, self.request.user)
        messages.success(self.request, f"«{self.object.titolo}» salvato.")
        return redirect(self.object)


class AppuntamentoNuovoView(PermessoMixin, _AppuntamentoMixin, CreateView):
    permission_required = "calendario.add_appuntamento"

    def get_initial(self):
        iniziali = super().get_initial()
        try:
            iniziali["giorno"] = date.fromisoformat(self.request.GET.get("giorno", ""))
        except ValueError:
            iniziali["giorno"] = timezone.localdate()
        if self.request.GET.get("tipo") in Appuntamento.Tipo.values:
            iniziali["tipo"] = self.request.GET["tipo"]
        return iniziali


class AppuntamentoModificaView(PermessoMixin, _AppuntamentoMixin, UpdateView):
    permission_required = "calendario.change_appuntamento"

    def get_queryset(self):
        return Appuntamento.objects.filter(annullato=False)


class AppuntamentoAzioneView(PermessoMixin, View):
    """Segna fatta o riapre una scadenza; annulla un appuntamento."""

    permission_required = "calendario.change_appuntamento"

    def post(self, request, pk):
        a = get_object_or_404(Appuntamento, pk=pk, annullato=False)
        azione = request.POST.get("azione")
        if azione == "fatto" and a.scadenza:
            servizi.segna_fatto(a, request.user)
            messages.success(request, f"Scadenza «{a.titolo}» segnata come fatta.")
        elif azione == "riapri" and a.scadenza:
            servizi.segna_fatto(a, request.user, fatto=False)
            messages.success(request, f"Scadenza «{a.titolo}» riaperta.")
        elif azione == "annulla":
            servizi.annulla_appuntamento(a, request.user)
            messages.success(request, f"«{a.titolo}» annullato.")
            return redirect("calendario:calendario")
        return redirect(request.POST.get("torna") if request.POST.get("torna", "").startswith(
            "/calendario/") else a.get_absolute_url())  # fmt: skip
