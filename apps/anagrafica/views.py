# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Viste dell'anagrafica: elenco con ricerca istantanea (HTMX),
# *              scheda, inserimento, modifica, archiviazione, consensi, esportazione.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import io
from datetime import date

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import CreateView, DetailView, UpdateView
from django_filters.views import FilterView

from apps.core.immagini import ImmagineNonValida, risposta_immagine
from apps.core.models import EventoAudit
from apps.core.views import PermessoMixin

from . import servizi
from .filtri import SoggettoFilter
from .forms import ConsensoForm, SoggettoForm
from .models import Soggetto


class ElencoView(PermessoMixin, FilterView):
    permission_required = "anagrafica.view_soggetto"
    filterset_class = SoggettoFilter
    paginate_by = 25
    template_name = "anagrafica/elenco.html"

    def get_queryset(self):
        return Soggetto.objects.prefetch_related("categorie")

    def get_template_names(self):
        # richiesta HTMX dalla ricerca: solo la tabella
        if self.request.htmx and not self.request.htmx.boosted:
            return ["anagrafica/elenco.html#tabella"]
        return [self.template_name]


class DettaglioView(PermessoMixin, DetailView):
    permission_required = "anagrafica.view_soggetto"
    model = Soggetto
    template_name = "anagrafica/dettaglio.html"
    context_object_name = "soggetto"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["consensi"] = self.object.consensi.all()
        ctx["form_consenso"] = ConsensoForm()
        ctx["socio"] = getattr(self.object, "socio", None)
        if self.request.user.has_perm("comunicazioni.view_invio"):
            ctx["comunicazioni"] = self.object.comunicazioni.select_related("invio").order_by(
                "-invio__creato_il"
            )[:10]
        if self.request.user.has_perm("protocollo.view_protocollo"):
            from apps.protocollo.models import Protocollo

            ctx["protocolli"] = (
                Protocollo.objects.visibili_a(self.request.user)
                .filter(corrispondenti__soggetto=self.object)
                .distinct()[:10]
            )
        if self.request.user.has_perm("core.view_eventoaudit"):
            ctx["storia"] = EventoAudit.objects.filter(
                oggetto_tipo=ContentType.objects.get_for_model(Soggetto),
                oggetto_id=str(self.object.pk),
            )[:20]
        return ctx


class _SalvaMixin:
    model = Soggetto
    form_class = SoggettoForm
    template_name = "anagrafica/modulo.html"
    context_object_name = "soggetto"

    def form_valid(self, form):
        try:
            self.object = servizi.salva_soggetto(
                form,
                self.request.user,
                foto=form.cleaned_data.get("nuova_foto"),
                togli_foto=form.cleaned_data.get("togli_foto"),
            )
        except ImmagineNonValida as e:
            form.add_error("nuova_foto", e)
            return self.form_invalid(form)
        messages.success(self.request, f"«{self.object}» salvato.")
        return redirect(self.object)


class CreaView(PermessoMixin, _SalvaMixin, CreateView):
    permission_required = "anagrafica.add_soggetto"

    def get_initial(self):
        iniziali = super().get_initial()
        if tipo := self.request.GET.get("tipo"):
            iniziali["tipo"] = tipo
        return iniziali


class ModificaView(PermessoMixin, _SalvaMixin, UpdateView):
    permission_required = "anagrafica.change_soggetto"


class FotoView(LoginRequiredMixin, View):
    """Foto del soggetto: per chi vede l'anagrafica o, se è un socio, il libro soci."""

    def get(self, request, pk):
        soggetto = get_object_or_404(Soggetto, pk=pk)
        utente = request.user
        if not (
            utente.has_perm("anagrafica.view_soggetto")
            or (utente.has_perm("soci.view_socio") and hasattr(soggetto, "socio"))
        ):
            raise PermissionDenied
        return risposta_immagine(soggetto.foto)


class ArchiviaView(PermessoMixin, View):
    permission_required = "anagrafica.archivia_soggetto"
    http_method_names = ["post"]

    def post(self, request, pk):
        soggetto = get_object_or_404(Soggetto, pk=pk)
        archivia = request.POST.get("azione") == "archivia"
        servizi.imposta_archiviato(soggetto, archivia, request.user)
        messages.success(request, f"«{soggetto}» {'archiviato' if archivia else 'ripristinato'}.")
        return redirect(soggetto)


class ConsensoView(PermessoMixin, View):
    permission_required = "anagrafica.add_consenso"
    http_method_names = ["post"]

    def post(self, request, pk):
        soggetto = get_object_or_404(Soggetto, pk=pk)
        form = ConsensoForm(request.POST)
        if form.is_valid():
            consenso = form.save(commit=False)
            consenso.soggetto = soggetto
            consenso.save()
            from apps.core.audit import Azione, registra

            registra(Azione.MODIFICA, soggetto, consenso=str(consenso))
            messages.success(request, "Consenso registrato.")
        else:
            messages.error(request, "Consenso non registrato: controllare i dati.")
        return redirect(soggetto)


class EsportaView(PermessoMixin, View):
    permission_required = "anagrafica.esporta_soggetti"

    def get(self, request):
        filtro = SoggettoFilter(request.GET, queryset=Soggetto.objects.all())
        buffer = io.StringIO()
        servizi.esporta_csv(filtro.qs, buffer, request.user)
        risposta = HttpResponse("﻿" + buffer.getvalue(), content_type="text/csv; charset=utf-8")
        risposta["Content-Disposition"] = (
            f'attachment; filename="anagrafica_{date.today():%Y%m%d}.csv"'
        )
        return risposta
