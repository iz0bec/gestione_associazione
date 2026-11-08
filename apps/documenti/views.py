# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Viste dei modelli di stampa e della stampa dei documenti
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, FormView, ListView, UpdateView

from apps.anagrafica.models import Soggetto
from apps.core.audit import Azione, campi_modificati, registra
from apps.core.views import PermessoMixin

from . import servizi
from .forms import ModelloForm, StampaForm
from .models import ModelloStampa


def _pdf(dati, nome):
    risposta = HttpResponse(dati, content_type="application/pdf")
    risposta["Content-Disposition"] = f'inline; filename="{nome}"'
    return risposta


class ModelliView(PermessoMixin, ListView):
    permission_required = "documenti.view_modellostampa"
    template_name = "documenti/modelli.html"
    context_object_name = "modelli"
    model = ModelloStampa


class _ModelloMixin:
    model = ModelloStampa
    form_class = ModelloForm
    template_name = "documenti/modello.html"
    success_url = reverse_lazy("documenti:modelli")

    def form_valid(self, form):
        nuovo = form.instance.pk is None
        dettagli = {} if nuovo else campi_modificati(form)
        risposta = super().form_valid(form)
        if nuovo:
            registra(Azione.CREAZIONE, self.object)
        elif dettagli.get("campi"):
            registra(Azione.MODIFICA, self.object, **dettagli)
        messages.success(self.request, f"Modello «{self.object}» salvato.")
        return risposta

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["segnaposto"] = servizi.SEGNAPOSTO_STAMPA
        return ctx


class ModelloNuovoView(PermessoMixin, _ModelloMixin, CreateView):
    permission_required = "documenti.add_modellostampa"


class ModelloModificaView(PermessoMixin, _ModelloMixin, UpdateView):
    permission_required = "documenti.change_modellostampa"


class AnteprimaView(PermessoMixin, View):
    """PDF di prova del modello, con i dati della scheda dell'utente se collegata."""

    permission_required = "documenti.view_modellostampa"

    def get(self, request, pk):
        modello = get_object_or_404(ModelloStampa, pk=pk)
        soggetto = getattr(request.user, "soggetto", None)
        return _pdf(servizi.anteprima(modello, soggetto), servizi.nome_file(modello))


class StampaView(PermessoMixin, FormView):
    permission_required = "documenti.stampa_documento"
    template_name = "documenti/stampa.html"
    form_class = StampaForm

    def _soggetto(self):
        pk = self.request.GET.get("soggetto") or self.request.POST.get("da_scheda")
        if pk and str(pk).isdigit():
            return get_object_or_404(Soggetto, pk=pk)
        return None

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["soggetto"] = self._soggetto()
        modello = self.request.GET.get("modello")
        if modello and modello.isdigit():
            kwargs.setdefault("initial", {})["modello"] = int(modello)
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["da_scheda"] = self._soggetto()
        return ctx

    def form_valid(self, form):
        if form.cleaned_data["protocolla"] and not self.request.user.has_perm(
            "protocollo.add_protocollo"
        ):
            form.add_error(None, "Non hai il permesso di registrare protocolli.")
            return self.form_invalid(form)
        destinatari, esclusi = form.destinatari()
        if form.cleaned_data["destinazione"] != "nessuno" and not destinatari:
            form.add_error(None, "Nessun destinatario stampabile (schede archiviate o decedute).")
            return self.form_invalid(form)
        modello = form.cleaned_data["modello"]
        try:
            pdf, protocollo = servizi.stampa(
                modello, destinatari, self.request.user,
                protocolla=form.cleaned_data["protocolla"],
                mezzo=form.cleaned_data.get("mezzo") or "posta",
            )  # fmt: skip
        except servizi.OperazioneNonValida as e:
            form.add_error(None, e)
            return self.form_invalid(form)
        nome = servizi.nome_file(modello)
        if protocollo:
            nome = f"{protocollo.segnatura}_{nome}"
        risposta = _pdf(pdf, nome)
        if esclusi:
            risposta["X-Esclusi"] = str(len(esclusi))
        return risposta
