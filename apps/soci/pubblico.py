# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Modulo pubblico di domanda di iscrizione (senza accesso), attivabile
# *              dai dati dell'organizzazione. Protetto da campo trappola, tempo minimo
# *              di compilazione e limite di invii per indirizzo IP.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.http import Http404
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.generic import FormView, TemplateView

from apps.core.audit import Azione, registra
from apps.core.middleware import ip_richiesta
from apps.core.models import Organizzazione

from .forms import DomandaPubblicaForm
from .models import DomandaIscrizione


class _SoloSeAttiva:
    def dispatch(self, request, *args, **kwargs):
        if not Organizzazione.corrente().iscrizioni_online:
            raise Http404("Le domande di iscrizione online non sono attive.")
        return super().dispatch(request, *args, **kwargs)


@method_decorator(never_cache, name="dispatch")
class DomandaPubblicaView(_SoloSeAttiva, FormView):
    template_name = "soci/pubblico/domanda.html"
    form_class = DomandaPubblicaForm

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "ip": ip_richiesta(self.request)}

    def form_valid(self, form):
        domanda = form.save(commit=False)
        domanda.origine = DomandaIscrizione.Origine.PUBBLICA
        domanda.indirizzo_ip = form.ip
        domanda.save()
        registra(
            Azione.CREAZIONE,
            domanda,
            utente=None,
            ip=form.ip,
            descrizione=f"Domanda di iscrizione online n. {domanda.pk}",
        )
        return redirect("iscrizione_inviata")


class DomandaInviataView(_SoloSeAttiva, TemplateView):
    template_name = "soci/pubblico/inviata.html"
