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


# --- verifica pubblica della tessera ----------------------------------------------------------

LIMITE_VERIFICHE = 20  # ricerche per numero e cognome, per indirizzo IP e per ora


def _troppe_verifiche(request):
    from django.core.cache import cache

    chiave = f"verifica-tessera:{ip_richiesta(request)}"
    tentativi = cache.get(chiave, 0) + 1
    cache.set(chiave, tentativi, 3600)
    return tentativi > LIMITE_VERIFICHE


@method_decorator(never_cache, name="dispatch")
class VerificaTesseraView(TemplateView):
    """Verifica con numero di tessera e cognome (dalla pagina pubblica)."""

    template_name = "soci/pubblico/verifica.html"

    def get_context_data(self, **kwargs):
        from . import tessera_digitale

        ctx = super().get_context_data(**kwargs)
        numero = self.request.GET.get("numero", "").strip()[:30]
        cognome = self.request.GET.get("cognome", "").strip()[:100]
        ctx.update(numero=numero, cognome=cognome)
        if numero or cognome:
            if not (numero and cognome):
                ctx["errore"] = "Indicare sia il numero della tessera sia il cognome."
            elif _troppe_verifiche(self.request):
                ctx["errore"] = "Troppe verifiche in poco tempo: riprovare più tardi."
            else:
                tessera = tessera_digitale.da_numero(numero, cognome)
                ctx["cercato"] = True
                ctx["esito"] = tessera_digitale.esito(tessera) if tessera else None
        return ctx


@method_decorator(never_cache, name="dispatch")
class VerificaCodiceView(TemplateView):
    """Verifica dal QR della tessera digitale."""

    template_name = "soci/pubblico/verifica.html"

    def get_context_data(self, **kwargs):
        from . import tessera_digitale

        ctx = super().get_context_data(**kwargs)
        tessera = tessera_digitale.da_codice(kwargs.get("codice"))
        if tessera is None:
            raise Http404("Codice di verifica sconosciuto.")
        ctx.update(cercato=True, esito=tessera_digitale.esito(tessera), da_qr=True)
        return ctx
