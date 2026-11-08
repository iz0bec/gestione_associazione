# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Viste del calendario: prossimi impegni, file .ics, collegamento personale per
# *              l'abbonamento dai calendari (pubblico, protetto dal codice segreto).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from . import servizi
from .models import FeedCalendario

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
