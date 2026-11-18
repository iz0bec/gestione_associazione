# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Pagine degli incassi diversi dalle quote, delle note di storno e del registro
# *              degli incassi (PDF ed Excel).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from datetime import date

from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import DetailView, FormView, ListView, TemplateView

from apps.anagrafica.models import Soggetto
from apps.core.audit import Azione, registra
from apps.core.models import Organizzazione
from apps.core.pdf import risposta_pdf
from apps.core.views import PermessoMixin

from . import incassi
from .forms import IncassoForm, StornoForm
from .models import Incasso, Storno
from .servizi import OperazioneNonValida


class IncassiView(PermessoMixin, ListView):
    permission_required = "tesoreria.view_incasso"
    template_name = "tesoreria/incassi.html"
    context_object_name = "incassi"
    paginate_by = 50

    def get_queryset(self):
        return Incasso.objects.select_related("soggetto").prefetch_related("storni")


class IncassoNuovoView(PermessoMixin, FormView):
    permission_required = "tesoreria.registra_incasso"
    template_name = "tesoreria/incasso_modulo.html"
    form_class = IncassoForm

    def _soggetto(self):
        pk = self.request.GET.get("soggetto") or self.request.POST.get("soggetto")
        return Soggetto.objects.filter(pk=pk).first() if str(pk or "").isdigit() else None

    def get_initial(self):
        iniziali = super().get_initial()
        if s := self._soggetto():
            iniziali.update(nominativo=s.nome_completo, codice_fiscale=s.codice_fiscale or "")
        if self.request.GET.get("tipo") == "tessere":  # dalla quadratura del ciclo delle tessere
            from apps.soci.models import Sezione

            sezione = Sezione.objects.filter(pk=self.request.GET.get("sezione") or 0).first()
            anno = self.request.GET.get("anno", "")
            iniziali.update(tipo="tessere", sezione=sezione,
                            anno_tessere=int(anno) if anno.isdigit() else None,
                            nominativo=f"Sezione {sezione.nome}" if sezione else "",
                            causale=f"Tessere {anno}" if anno.isdigit() else "")  # fmt: skip
        return iniziali

    def get_context_data(self, **kwargs):
        return super().get_context_data(soggetto=self._soggetto(), **kwargs)

    def form_valid(self, form):
        try:
            incasso = incassi.registra_incasso(
                {**form.cleaned_data, "soggetto": self._soggetto()}, self.request.user
            )
        except OperazioneNonValida as e:
            form.add_error(None, " ".join(e.messages))
            return self.form_invalid(form)
        testo = f"Incasso registrato: ricevuta n. {incasso.codice_ricevuta}."
        messages.success(self.request, testo)
        return redirect(incasso)


class IncassoView(PermessoMixin, DetailView):
    permission_required = "tesoreria.view_incasso"
    model = Incasso
    template_name = "tesoreria/incasso.html"
    context_object_name = "incasso"


class RicevutaIncassoView(PermessoMixin, View):
    permission_required = "tesoreria.view_incasso"

    def get(self, request, pk):
        incasso = get_object_or_404(Incasso, pk=pk)
        registra(Azione.CONSULTAZIONE, incasso, descrizione=f"Ricevuta {incasso.codice_ricevuta}")
        return risposta_pdf(
            "tesoreria/pdf/ricevuta_incasso.html",
            {"incasso": incasso, "organizzazione": Organizzazione.corrente()},
            f"ricevuta_{incasso.ricevuta_anno}_{incasso.ricevuta_numero:04d}.pdf",
        )


class StornoView(PermessoMixin, FormView):
    """Nota di storno di una quota (?tessera=) o di un incasso (?incasso=)."""

    permission_required = "tesoreria.storna"
    template_name = "tesoreria/storno_modulo.html"
    form_class = StornoForm

    def documento(self):
        from apps.soci.models import Tessera

        dati = self.request.GET if self.request.method == "GET" else self.request.POST
        if str(dati.get("tessera", "")).isdigit():
            return get_object_or_404(Tessera.objects.select_related("socio__soggetto"),
                                     pk=dati["tessera"])  # fmt: skip
        if str(dati.get("incasso", "")).isdigit():
            return get_object_or_404(Incasso, pk=dati["incasso"])
        raise Http404

    def get_context_data(self, **kwargs):
        from apps.soci.models import Tessera

        doc = self.documento()
        return super().get_context_data(documento=doc, quota=isinstance(doc, Tessera), **kwargs)

    def form_valid(self, form):
        doc = self.documento()
        d = form.cleaned_data
        try:
            storno = incassi.storna(doc, self.request.user, data=d["data"], motivo=d["motivo"],
                                    rimborso=d["rimborso"], metodo=d["metodo"],
                                    annulla_tessera=d["annulla_tessera"])  # fmt: skip
        except OperazioneNonValida as e:
            form.add_error(None, " ".join(e.messages))
            return self.form_invalid(form)
        messages.success(self.request, f"Nota di storno n. {storno.codice} registrata.")
        return redirect("tesoreria:nota_storno", storno.pk)


class NotaStornoView(PermessoMixin, View):
    permission_required = "tesoreria.view_storno"

    def get(self, request, pk):
        storno = get_object_or_404(
            Storno.objects.select_related("tessera__socio__soggetto", "incasso"), pk=pk
        )
        return risposta_pdf("tesoreria/pdf/nota_storno.html",
                            {"storno": storno, "organizzazione": Organizzazione.corrente()},
                            f"nota_storno_{storno.anno}_{storno.numero:04d}.pdf")  # fmt: skip


def _periodo(request):
    oggi = date.today()
    try:
        dal = date.fromisoformat(request.GET.get("dal", ""))
    except ValueError:
        dal = oggi.replace(day=1)
    try:
        al = date.fromisoformat(request.GET.get("al", ""))
    except ValueError:
        al = oggi
    return (dal, al) if dal <= al else (al, dal)


class RegistroIncassiView(PermessoMixin, TemplateView):
    permission_required = "tesoreria.view_incasso"
    template_name = "tesoreria/registro_incassi.html"

    def get(self, request, *args, **kwargs):
        dal, al = _periodo(request)
        r = incassi.registro(dal, al)
        formato = request.GET.get("formato")
        if formato in ("pdf", "xlsx"):
            registra(Azione.ESPORTAZIONE, descrizione=f"Registro incassi {dal} - {al}",
                     formato=formato, righe=len(r.righe))  # fmt: skip
            nome = f"registro_incassi_{dal:%Y%m%d}_{al:%Y%m%d}"
        if formato == "pdf":
            return risposta_pdf("tesoreria/pdf/registro_incassi.html",
                                {"r": r, "organizzazione": Organizzazione.corrente()},
                                f"{nome}.pdf", scarica=True)  # fmt: skip
        if formato == "xlsx":
            risposta = HttpResponse(incassi.registro_xlsx(r), content_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))  # fmt: skip
            risposta["Content-Disposition"] = f'attachment; filename="{nome}.xlsx"'
            risposta["Content-Security-Policy"] = "default-src 'none'; sandbox"
            return risposta
        return self.render_to_response(self.get_context_data(r=r))
