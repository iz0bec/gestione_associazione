# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Viste del libro soci: elenco, scheda, ammissione, cessazione, tessere,
# *              incassi e ricevute, rinnovo annuale, domande di iscrizione, tipologie.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import io
from datetime import date

from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import (
    CreateView,
    DetailView,
    FormView,
    ListView,
    TemplateView,
    UpdateView,
)
from django_filters.views import FilterView

from apps.anagrafica.models import Soggetto
from apps.core.audit import Azione, campi_modificati, registra
from apps.core.models import EventoAudit, Organizzazione
from apps.core.pdf import risposta_pdf
from apps.core.views import PermessoMixin

from . import servizi
from .filtri import SocioFilter
from .forms import (
    AccoglimentoForm,
    AmmissioneForm,
    CessazioneForm,
    DomandaForm,
    MotivoForm,
    PagamentoForm,
    RinnovoForm,
    SocioForm,
    TesseraForm,
    TipologiaForm,
)
from .models import DomandaIscrizione, Socio, Tessera, TipologiaSocio
from .servizi import OperazioneNonValida


def _errore(request, eccezione):
    messages.error(request, " ".join(eccezione.messages))


# --- libro soci --------------------------------------------------------------------------


class ElencoView(PermessoMixin, FilterView):
    permission_required = "soci.view_socio"
    filterset_class = SocioFilter
    paginate_by = 25
    template_name = "soci/elenco.html"

    def get_queryset(self):
        return Socio.objects.select_related("soggetto", "tipologia")

    def get_template_names(self):
        if self.request.htmx and not self.request.htmx.boosted:
            return ["soci/elenco.html#tabella"]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        anno = self.filterset.anno_riferimento
        soci = list(ctx["page_obj"])
        tessere = Tessera.objects.valide().filter(anno=anno, socio__in=soci)
        per_socio = {t.socio_id: t for t in tessere}
        ctx["righe"] = [(s, per_socio.get(s.pk)) for s in soci]
        ctx["anno"] = anno
        return ctx


class DettaglioView(PermessoMixin, DetailView):
    permission_required = "soci.view_socio"
    model = Socio
    template_name = "soci/dettaglio.html"
    context_object_name = "socio"

    def get_queryset(self):
        return Socio.objects.select_related("soggetto", "tipologia")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        anno = date.today().year
        ctx["anno"] = anno
        ctx["tessere"] = self.object.tessere.all()
        ctx["tessera_corrente"] = self.object.tessera_anno(anno)
        ctx["form_tessera"] = TesseraForm(
            initial={"importo": self.object.tipologia.quota_annua}, prefix="tessera"
        )
        ctx["form_pagamento"] = PagamentoForm(prefix="pagamento")
        ctx["form_cessazione"] = CessazioneForm(prefix="cessazione")
        ctx["form_annullamento"] = MotivoForm(prefix="annulla")
        if self.request.user.has_perm("core.view_eventoaudit"):
            tipi = ContentType.objects.get_for_models(Socio, Tessera)
            ctx["storia"] = EventoAudit.objects.filter(
                Q(oggetto_tipo=tipi[Socio], oggetto_id=str(self.object.pk))
                | Q(
                    oggetto_tipo=tipi[Tessera],
                    oggetto_id__in=[str(t.pk) for t in ctx["tessere"]],
                )
            )[:30]
        return ctx


class NuovoView(PermessoMixin, TemplateView):
    """Ricerca in anagrafica della persona da iscrivere."""

    permission_required = "soci.add_socio"
    template_name = "soci/nuovo.html"

    def get_template_names(self):
        if self.request.htmx and not self.request.htmx.boosted:
            return ["soci/nuovo.html#risultati"]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        q = self.request.GET.get("q", "").strip()
        ctx["q"] = q
        ctx["risultati"] = (
            Soggetto.objects.attivi()
            .filter(tipo=Soggetto.Tipo.PERSONA, socio__isnull=True, data_decesso__isnull=True)
            .ricerca(q)[:20]
            if q
            else []
        )
        return ctx


class AmmissioneView(PermessoMixin, FormView):
    permission_required = "soci.add_socio"
    form_class = AmmissioneForm
    template_name = "soci/ammissione.html"

    def dispatch(self, request, *args, **kwargs):
        self.soggetto = get_object_or_404(Soggetto, pk=kwargs["soggetto"])
        if hasattr(self.soggetto, "socio"):
            messages.info(request, "La persona è già iscritta al libro soci.")
            return redirect(self.soggetto.socio)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        return super().get_context_data(soggetto=self.soggetto, **kwargs)

    def form_valid(self, form):
        d = form.cleaned_data
        try:
            socio = servizi.ammetti_socio(
                self.soggetto,
                d["tipologia"],
                self.request.user,
                data_ammissione=d["data_ammissione"],
                delibera=d["delibera"],
                note=d["note"],
            )
            if d["tessera"]:
                servizi.rilascia_tessera(socio, date.today().year, self.request.user)
        except OperazioneNonValida as e:
            form.add_error(None, e)
            return self.form_invalid(form)
        messages.success(
            self.request, f"{socio.soggetto} iscritto al libro soci con il n. {socio.numero}."
        )
        return redirect(socio)


class ModificaView(PermessoMixin, UpdateView):
    permission_required = "soci.change_socio"
    model = Socio
    form_class = SocioForm
    template_name = "soci/modifica.html"
    context_object_name = "socio"

    def form_valid(self, form):
        self.object = servizi.salva_socio(form, self.request.user)
        messages.success(self.request, "Dati di iscrizione salvati.")
        return redirect(self.object)


class _AzioneSocioView(PermessoMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        socio = get_object_or_404(Socio, pk=pk)
        try:
            self.esegui(request, socio)
        except OperazioneNonValida as e:
            _errore(request, e)
        return redirect(socio)


class CessazioneView(_AzioneSocioView):
    permission_required = "soci.cessa_socio"

    def esegui(self, request, socio):
        form = CessazioneForm(request.POST, prefix="cessazione")
        if not form.is_valid():
            raise OperazioneNonValida(
                [m for errori in form.errors.values() for m in errori] or "Dati non validi."
            )
        d = form.cleaned_data
        servizi.cessa_socio(
            socio,
            request.user,
            data_cessazione=d["data_cessazione"],
            causa=d["causa"],
            note=d["note"],
        )
        messages.success(request, "Cessazione registrata.")


class StatoView(_AzioneSocioView):
    permission_required = "soci.change_socio"

    def esegui(self, request, socio):
        stato = request.POST.get("stato")
        servizi.cambia_stato(socio, stato, request.user, motivo=request.POST.get("motivo", ""))
        messages.success(request, f"Stato del socio: {Socio.Stato(stato).label.lower()}.")


class TesseraNuovaView(_AzioneSocioView):
    permission_required = "soci.add_tessera"

    def esegui(self, request, socio):
        form = TesseraForm(request.POST, prefix="tessera")
        if not form.is_valid():
            raise OperazioneNonValida("Dati della tessera non validi.")
        d = form.cleaned_data
        if d["pagata"] and not request.user.has_perm("soci.incassa_quota"):
            raise OperazioneNonValida("Non si ha il permesso di registrare incassi.")
        tessera = servizi.rilascia_tessera(
            socio,
            d["anno"],
            request.user,
            importo=d["importo"],
            data_rilascio=d["data_rilascio"],
            pagata_il=date.today() if d["pagata"] else None,
            metodo=d["metodo"],
            riferimento=d["riferimento"],
        )
        messages.success(request, f"Tessera {tessera.codice} rilasciata.")


# --- tessere -----------------------------------------------------------------------------


class _AzioneTesseraView(PermessoMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        tessera = get_object_or_404(Tessera.objects.select_related("socio"), pk=pk)
        try:
            self.esegui(request, tessera)
        except OperazioneNonValida as e:
            _errore(request, e)
        if request.POST.get("ritorno") == "tessere":
            return redirect(f"{reverse('soci:tessere')}?anno={tessera.anno}")
        return redirect(tessera.socio)


class PagamentoView(_AzioneTesseraView):
    permission_required = "soci.incassa_quota"

    def esegui(self, request, tessera):
        form = PagamentoForm(request.POST, prefix="pagamento")
        if not form.is_valid():
            raise OperazioneNonValida(
                [m for errori in form.errors.values() for m in errori] or "Dati non validi."
            )
        d = form.cleaned_data
        tessera = servizi.registra_pagamento(
            tessera,
            request.user,
            pagata_il=d["pagata_il"],
            metodo=d["metodo"],
            importo=d["importo"],
            riferimento=d["riferimento"],
        )
        messages.success(request, f"Pagamento registrato, ricevuta n. {tessera.codice_ricevuta}.")


class AnnullaTesseraView(_AzioneTesseraView):
    permission_required = "soci.annulla_tessera"

    def esegui(self, request, tessera):
        servizi.annulla_tessera(tessera, request.user, request.POST.get("annulla-motivo", ""))
        messages.success(request, f"Tessera {tessera.codice} annullata.")


class RicevutaView(PermessoMixin, View):
    permission_required = "soci.view_tessera"

    def get(self, request, pk):
        tessera = get_object_or_404(
            Tessera.objects.select_related("socio__soggetto", "socio__tipologia"),
            pk=pk,
            pagata_il__isnull=False,
        )
        registra(Azione.CONSULTAZIONE, tessera, descrizione=f"Ricevuta {tessera.codice_ricevuta}")
        return risposta_pdf(
            "soci/pdf/ricevuta.html",
            {"tessera": tessera, "organizzazione": Organizzazione.corrente(), "oggi": date.today()},
            f"ricevuta_{tessera.ricevuta_anno}_{tessera.ricevuta_numero:04d}.pdf",
        )


class TessereView(PermessoMixin, ListView):
    """Tesseramento di un anno: riepilogo e tessere rilasciate."""

    permission_required = "soci.view_tessera"
    template_name = "soci/tessere.html"
    paginate_by = 50
    context_object_name = "tessere"

    def get_anno(self):
        try:
            return int(self.request.GET.get("anno") or date.today().year)
        except ValueError:
            return date.today().year

    def get_queryset(self):
        qs = Tessera.objects.filter(anno=self.get_anno()).select_related("socio__soggetto")
        filtro = self.request.GET.get("stato")
        if filtro == "da_pagare":
            qs = qs.da_pagare()
        elif filtro == "pagate":
            qs = qs.pagate()
        elif filtro == "annullate":
            qs = qs.filter(annullata=True)
        return qs.order_by("numero")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        anno = self.get_anno()
        valide = Tessera.objects.valide().filter(anno=anno)
        ctx["anno"] = anno
        ctx["anni"] = range(date.today().year + 1, date.today().year - 6, -1)
        ctx["stato"] = self.request.GET.get("stato", "")
        ctx["riepilogo"] = valide.aggregate(
            rilasciate=Count("id"),
            pagate=Count("id", filter=Q(pagata_il__isnull=False)),
            incassato=Sum("importo", filter=Q(pagata_il__isnull=False), default=0),
            da_incassare=Sum("importo", filter=Q(pagata_il__isnull=True), default=0),
        )
        ctx["da_rinnovare"] = servizi.soci_da_rinnovare(anno).count()
        ctx["morosi"] = Socio.objects.morosi(anno).count()
        ctx["form_pagamento"] = PagamentoForm(prefix="pagamento")
        return ctx


class RinnovoView(PermessoMixin, FormView):
    permission_required = "soci.add_tessera"
    form_class = RinnovoForm
    template_name = "soci/rinnovo.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if self.request.method == "GET" and "anno" in self.request.GET:
            kwargs["data"] = self.request.GET
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        form = ctx["form"]
        anno = form.cleaned_data["anno"] if form.is_bound and form.is_valid() else date.today().year
        ctx["anno"] = anno
        ctx["da_rinnovare"] = servizi.soci_da_rinnovare(anno).order_by("numero")
        return ctx

    def form_valid(self, form):
        if self.request.method == "GET" or self.request.POST.get("conferma") != "1":
            return self.render_to_response(self.get_context_data(form=form))
        anno = form.cleaned_data["anno"]
        rilasciate, errori = servizi.rinnovo_massivo(anno, self.request.user)
        messages.success(self.request, f"Rilasciate {len(rilasciate)} tessere per il {anno}.")
        for socio, errore in errori:
            messages.warning(self.request, f"{socio}: {errore}")
        return redirect(f"{reverse('soci:tessere')}?anno={anno}")

    def get(self, request, *args, **kwargs):
        form = self.get_form()
        if form.is_bound:
            form.is_valid()
        return self.render_to_response(self.get_context_data(form=form))


# --- stampe ed esportazioni --------------------------------------------------------------


class LibroSociPdfView(PermessoMixin, View):
    permission_required = "soci.esporta_libro_soci"

    def get(self, request):
        soci = Socio.objects.select_related("soggetto", "tipologia").order_by("numero")
        registra(Azione.ESPORTAZIONE, descrizione=f"Libro soci PDF ({soci.count()} iscritti)")
        return risposta_pdf(
            "soci/pdf/libro_soci.html",
            {"soci": soci, "organizzazione": Organizzazione.corrente(), "oggi": date.today()},
            f"libro_soci_{date.today():%Y%m%d}.pdf",
        )


class LibroSociCsvView(PermessoMixin, View):
    permission_required = "soci.esporta_libro_soci"

    def get(self, request):
        filtro = SocioFilter(request.GET, queryset=Socio.objects.all())
        buffer = io.StringIO()
        servizi.esporta_libro_csv(filtro.qs.order_by("numero"), buffer, request.user)
        risposta = HttpResponse("﻿" + buffer.getvalue(), content_type="text/csv; charset=utf-8")
        risposta["Content-Disposition"] = f'attachment; filename="soci_{date.today():%Y%m%d}.csv"'
        return risposta


# --- domande di iscrizione ---------------------------------------------------------------


class DomandeView(PermessoMixin, ListView):
    permission_required = "soci.view_domandaiscrizione"
    template_name = "soci/domande.html"
    paginate_by = 25
    context_object_name = "domande"

    def get_queryset(self):
        stato = self.request.GET.get("stato", DomandaIscrizione.Stato.IN_ATTESA)
        qs = DomandaIscrizione.objects.select_related("socio")
        return qs if stato == "tutte" else qs.filter(stato=stato)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["stato"] = self.request.GET.get("stato", DomandaIscrizione.Stato.IN_ATTESA)
        ctx["stati"] = [*DomandaIscrizione.Stato.choices, ("tutte", "Tutte")]
        return ctx


class DomandaView(PermessoMixin, DetailView):
    permission_required = "soci.view_domandaiscrizione"
    model = DomandaIscrizione
    template_name = "soci/domanda.html"
    context_object_name = "domanda"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["esistente"] = servizi.soggetto_per_domanda(self.object)
        ctx["form_accoglimento"] = AccoglimentoForm(
            initial={"tipologia": self.object.tipologia}, prefix="accogli"
        )
        ctx["form_rigetto"] = MotivoForm(prefix="respingi")
        return ctx


class NuovaDomandaView(PermessoMixin, CreateView):
    permission_required = "soci.add_domandaiscrizione"
    model = DomandaIscrizione
    form_class = DomandaForm
    template_name = "soci/domanda_modulo.html"

    def form_valid(self, form):
        form.instance.origine = DomandaIscrizione.Origine.SEGRETERIA
        risposta = super().form_valid(form)
        registra(Azione.CREAZIONE, self.object)
        messages.success(self.request, "Domanda registrata.")
        return risposta


class AccogliView(PermessoMixin, View):
    permission_required = "soci.valuta_domanda"
    http_method_names = ["post"]

    def post(self, request, pk):
        domanda = get_object_or_404(DomandaIscrizione, pk=pk)
        form = AccoglimentoForm(request.POST, prefix="accogli")
        if not form.is_valid():
            messages.error(
                request, "Dati dell'accoglimento non validi: controllare tipologia e data."
            )
            return redirect(domanda)
        d = form.cleaned_data
        try:
            socio = servizi.accogli_domanda(
                domanda,
                request.user,
                tipologia=d["tipologia"],
                data_ammissione=d["data_ammissione"],
                delibera=d["delibera"],
                tessera_anno=date.today().year if d["tessera"] else None,
            )
        except OperazioneNonValida as e:
            _errore(request, e)
            return redirect(domanda)
        messages.success(
            request, f"Domanda accolta: {socio.soggetto} è il socio n. {socio.numero}."
        )
        return redirect(socio)


class RespingiView(PermessoMixin, View):
    permission_required = "soci.valuta_domanda"
    http_method_names = ["post"]

    def post(self, request, pk):
        domanda = get_object_or_404(DomandaIscrizione, pk=pk)
        try:
            servizi.respingi_domanda(domanda, request.user, request.POST.get("respingi-motivo", ""))
            messages.success(request, "Domanda respinta.")
        except OperazioneNonValida as e:
            _errore(request, e)
        return redirect(domanda)


# --- tipologie ---------------------------------------------------------------------------


class TipologieView(PermessoMixin, ListView):
    permission_required = "soci.view_tipologiasocio"
    template_name = "soci/tipologie.html"
    context_object_name = "tipologie"

    def get_queryset(self):
        return TipologiaSocio.objects.annotate(
            n_soci=Count("soci", filter=Q(soci__stato=Socio.Stato.ATTIVO))
        )


class _TipologiaMixin:
    model = TipologiaSocio
    form_class = TipologiaForm
    template_name = "soci/tipologia_modulo.html"
    success_url = reverse_lazy("soci:tipologie")

    def form_valid(self, form):
        nuova = form.instance.pk is None
        dettagli = {} if nuova else campi_modificati(form)
        risposta = super().form_valid(form)
        if nuova:
            registra(Azione.CREAZIONE, self.object)
        elif dettagli.get("campi"):
            registra(Azione.MODIFICA, self.object, **dettagli)
        messages.success(self.request, f"Tipologia «{self.object}» salvata.")
        return risposta


class TipologiaNuovaView(PermessoMixin, _TipologiaMixin, CreateView):
    permission_required = "soci.add_tipologiasocio"


class TipologiaModificaView(PermessoMixin, _TipologiaMixin, UpdateView):
    permission_required = "soci.change_tipologiasocio"
