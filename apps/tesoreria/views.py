# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Viste della tesoreria: cruscotto dell'esercizio, prima nota, movimenti,
# *              quote da registrare, preventivo, rendiconto (pagina, PDF, CSV), esercizi,
# *              conti e piano dei conti.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import csv
import io
from datetime import date

import django_filters
from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView
from django_filters.views import FilterView

from apps.anagrafica.forms import CampoData
from apps.core.audit import Azione, campi_modificati, registra
from apps.core.models import Organizzazione
from apps.core.pdf import risposta_pdf
from apps.core.views import PermessoMixin

from . import servizi
from .forms import ContoForm, ImportoField, MovimentoForm, SottovoceForm
from .models import Conto, Esercizio, Movimento, Voce


def _errore(request, e):
    messages.error(request, " ".join(e.messages))


def _esercizio(request):
    """Esercizio scelto (?anno=) o quello dell'anno in corso, o l'ultimo esistente."""
    anno = request.GET.get("anno") or request.POST.get("anno")
    qs = Esercizio.objects.all()
    if anno and anno.isdigit():
        return qs.filter(anno=int(anno)).first()
    return qs.filter(anno=date.today().year).first() or qs.first()


class CruscottoView(PermessoMixin, TemplateView):
    permission_required = "tesoreria.view_movimento"
    template_name = "tesoreria/cruscotto.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        e = _esercizio(self.request)
        ctx["esercizio"] = e
        ctx["esercizi"] = Esercizio.objects.all()
        ctx["anno_corrente"] = date.today().year
        ctx["conti_presenti"] = Conto.objects.exists()
        if e:
            ctx["saldi"] = servizi.saldi(e)
            ctx["totale"] = sum((s for _, s in ctx["saldi"]), servizi.ZERO)
            ctx["riepilogo"] = servizi.riepilogo(e)
            ctx["ultimi"] = e.movimenti.select_related("conto", "voce__padre")[:10]
            ctx["quote"] = servizi.quote_da_registrare(e).count() if e.aperto else 0
            ctx["confronto"] = servizi.confronto_preventivo(e)
            ctx["saldi_modificabili"] = servizi.saldi_iniziali_modificabili(e)
        return ctx


class EsercizioNuovoView(PermessoMixin, View):
    permission_required = "tesoreria.add_esercizio"
    http_method_names = ["post"]

    def post(self, request):
        try:
            anno = int(request.POST.get("anno", ""))
            e = servizi.apri_esercizio(anno, request.user)
            messages.success(request, f"Esercizio {e.anno} aperto.")
            return redirect(f"{reverse('tesoreria:cruscotto')}?anno={e.anno}")
        except ValueError:
            messages.error(request, "Anno non valido.")
        except ValidationError as e:
            _errore(request, e)
        return redirect("tesoreria:cruscotto")


class SaldiInizialiView(PermessoMixin, View):
    permission_required = "tesoreria.change_saldoconto"
    http_method_names = ["post"]

    def post(self, request, anno):
        e = get_object_or_404(Esercizio, anno=anno)
        valori = {}
        for conto in Conto.objects.filter(attivo=True):
            campo = ImportoField()
            try:
                valori[conto] = campo.clean(request.POST.get(f"saldo-{conto.pk}", ""))
            except ValidationError:
                messages.error(request, f"Saldo non valido per {conto}.")
                return redirect(e)
        try:
            servizi.imposta_saldi_iniziali(e, valori, request.user)
            messages.success(request, "Saldi iniziali salvati.")
        except ValidationError as err:
            _errore(request, err)
        return redirect(e)


class ChiudiEsercizioView(PermessoMixin, View):
    permission_required = "tesoreria.chiudi_esercizio"
    http_method_names = ["post"]

    def post(self, request, anno):
        e = get_object_or_404(Esercizio, anno=anno)
        try:
            if request.POST.get("azione") == "riapri":
                servizi.riapri_esercizio(e, request.user, request.POST.get("motivo", ""))
                messages.success(request, f"Esercizio {anno} riaperto.")
            else:
                servizi.chiudi_esercizio(e, request.user, request.POST.get("approvazione", ""))
                messages.success(
                    request, f"Esercizio {anno} chiuso: saldi riportati nel {anno + 1}."
                )
        except ValidationError as err:
            _errore(request, err)
        return redirect(e)


# --- prima nota ----------------------------------------------------------------------------------


class MovimentoFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(method="cerca", label="Cerca")
    tipo = django_filters.ChoiceFilter(choices=Movimento.Tipo.choices, empty_label="Tutti i tipi")
    conto = django_filters.ModelChoiceFilter(
        queryset=Conto.objects.all(), method="per_conto", empty_label="Tutti i conti"
    )
    voce = django_filters.ModelChoiceFilter(
        queryset=Voce.objects.filter(padre__isnull=True),
        method="per_voce",
        empty_label="Tutte le voci",
    )
    dal = django_filters.DateFilter(field_name="data", lookup_expr="gte", widget=CampoData)
    al = django_filters.DateFilter(field_name="data", lookup_expr="lte", widget=CampoData)

    class Meta:
        model = Movimento
        fields = ["q", "tipo", "conto", "voce", "dal", "al"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.form.fields.values():
            campo.widget.attrs["class"] = (
                "form-select" if isinstance(campo.widget, forms.Select) else "form-control"
            )
        self.form.fields["q"].widget.attrs.update(
            {"placeholder": "Descrizione, controparte, documento", "type": "search"}
        )

    def cerca(self, qs, name, value):
        for parola in value.split():
            filtro = (
                Q(descrizione__icontains=parola)
                | Q(controparte_testo__icontains=parola)
                | Q(documento__icontains=parola)
            )
            if parola.isdigit():
                filtro |= Q(numero=int(parola))
            qs = qs.filter(filtro)
        return qs

    def per_conto(self, qs, name, value):
        return qs.filter(Q(conto=value) | Q(conto_destinazione=value))

    def per_voce(self, qs, name, value):
        return qs.filter(Q(voce=value) | Q(voce__padre=value))


class PrimaNotaView(PermessoMixin, FilterView):
    permission_required = "tesoreria.view_movimento"
    filterset_class = MovimentoFilter
    template_name = "tesoreria/prima_nota.html"
    paginate_by = 50

    def dispatch(self, request, *args, **kwargs):
        self.esercizio = _esercizio(request)
        if self.esercizio is None:
            messages.info(request, "Aprire prima un esercizio.")
            return redirect("tesoreria:cruscotto")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return self.esercizio.movimenti.select_related(
            "conto", "conto_destinazione", "voce__padre"
        ).order_by("-data", "-numero")

    def get_template_names(self):
        if self.request.htmx and not self.request.htmx.boosted:
            return ["tesoreria/prima_nota.html#tabella"]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        validi = [m for m in self.filterset.qs if not m.annullato]
        ctx["esercizio"] = self.esercizio
        ctx["esercizi"] = Esercizio.objects.all()
        ctx["tot_entrate"] = sum((m.importo for m in validi if m.tipo == "entrata"), servizi.ZERO)
        ctx["tot_uscite"] = sum((m.importo for m in validi if m.tipo == "uscita"), servizi.ZERO)
        return ctx


class EsportaPrimaNotaView(PermessoMixin, View):
    permission_required = "tesoreria.view_movimento"

    def get(self, request):
        e = _esercizio(request)
        if e is None:
            raise Http404
        filtro = MovimentoFilter(request.GET, queryset=e.movimenti.order_by("data", "numero"))
        buffer = io.StringIO()
        servizi.esporta_prima_nota(filtro.qs, buffer, request.user)
        r = HttpResponse("﻿" + buffer.getvalue(), content_type="text/csv; charset=utf-8")
        r["Content-Disposition"] = f'attachment; filename="prima_nota_{e.anno}.csv"'
        return r


class MovimentoNuovoView(PermessoMixin, View):
    permission_required = "tesoreria.add_movimento"
    template_name = "tesoreria/movimento_modulo.html"

    def get(self, request):
        iniziali = {"tipo": request.GET.get("tipo", "uscita")}
        return self._render(MovimentoForm(initial=iniziali))

    def post(self, request):
        form = MovimentoForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                m = servizi.registra_movimento(
                    form.dati(), request.user, giustificativo=form.cleaned_data["file"]
                )
                messages.success(request, f"Movimento {m.codice} registrato.")
                if request.POST.get("altro"):
                    return redirect(f"{reverse('tesoreria:movimento_nuovo')}?tipo={m.tipo}")
                return redirect(f"{reverse('tesoreria:prima_nota')}?anno={m.esercizio.anno}")
            except ValidationError as e:
                form.add_error(None, e)
        return self._render(form)

    def _render(self, form):
        from django.shortcuts import render

        return render(self.request, self.template_name, {"form": form, "movimento": None})


class MovimentoView(PermessoMixin, DetailView):
    permission_required = "tesoreria.view_movimento"
    model = Movimento
    template_name = "tesoreria/movimento.html"
    context_object_name = "movimento"


class MovimentoModificaView(PermessoMixin, UpdateView):
    permission_required = "tesoreria.change_movimento"
    model = Movimento
    form_class = MovimentoForm
    template_name = "tesoreria/movimento_modulo.html"
    context_object_name = "movimento"

    def get_object(self, queryset=None):
        m = super().get_object(queryset)
        if m.annullato or not m.esercizio.aperto:
            raise Http404("Movimento non modificabile.")
        return m

    def form_valid(self, form):
        try:
            m = servizi.modifica_movimento(
                form, self.request.user, giustificativo=form.cleaned_data["file"]
            )
        except ValidationError as e:
            form.add_error(None, e)
            return self.form_invalid(form)
        messages.success(self.request, "Movimento aggiornato.")
        return redirect(m)


class AnnullaMovimentoView(PermessoMixin, View):
    permission_required = "tesoreria.annulla_movimento"
    http_method_names = ["post"]

    def post(self, request, pk):
        m = get_object_or_404(Movimento, pk=pk)
        try:
            servizi.annulla_movimento(m, request.user, request.POST.get("motivo", ""))
            messages.success(request, "Movimento annullato.")
        except ValidationError as e:
            _errore(request, e)
        return redirect(m)


class GiustificativoView(PermessoMixin, View):
    permission_required = "tesoreria.view_movimento"

    def get(self, request, pk):
        m = get_object_or_404(Movimento, pk=pk)
        if not m.giustificativo:
            raise Http404
        from apps.protocollo.servizi import tipo_file

        r = FileResponse(
            m.giustificativo.open("rb"),
            as_attachment=True,
            filename=m.giustificativo_nome,
            content_type=tipo_file(m.giustificativo_nome),
        )
        r["Content-Security-Policy"] = "default-src 'none'; sandbox"
        return r


class QuoteView(PermessoMixin, View):
    """Registra in prima nota le quote incassate che non lo sono ancora."""

    permission_required = "tesoreria.add_movimento"
    http_method_names = ["post"]

    def post(self, request):
        e = _esercizio(request)
        if e is None:
            raise Http404
        fatte, saltate = servizi.registra_quote_mancanti(e, request.user)
        messages.success(request, f"Quote registrate in prima nota: {fatte}.")
        for t, motivo in saltate[:5]:
            messages.warning(request, f"{t.socio.soggetto}: {motivo}")
        return redirect(e)


# --- preventivo e rendiconto ---------------------------------------------------------------------


class PreventivoView(PermessoMixin, TemplateView):
    permission_required = "tesoreria.view_previsione"
    template_name = "tesoreria/preventivo.html"

    def dispatch(self, request, *args, **kwargs):
        self.esercizio = get_object_or_404(Esercizio, anno=kwargs["anno"])
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, anno):
        if not request.user.has_perm("tesoreria.change_previsione"):
            return self.handle_no_permission()
        valori = {}
        for v in servizi.voci_ufficiali():
            try:
                valori[v] = ImportoField().clean(request.POST.get(f"voce-{v.pk}", ""))
            except ValidationError:
                messages.error(request, f"Importo non valido: {v}")
                return redirect("tesoreria:preventivo", anno=anno)
        try:
            servizi.salva_preventivo(self.esercizio, valori, request.user)
            messages.success(request, "Preventivo salvato.")
        except ValidationError as e:
            _errore(request, e)
        return redirect("tesoreria:preventivo", anno=anno)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        previsti = {p.voce_id: p.importo for p in self.esercizio.previsioni.all()}
        effettivi = servizi.totali_per_voce(self.esercizio)
        precedente = Esercizio.objects.filter(anno=self.esercizio.anno - 1).first()
        prec = servizi.totali_per_voce(precedente)
        ctx["esercizio"] = self.esercizio
        ctx["gruppi"] = []
        for tipo, etichetta in Voce.Tipo.choices:
            righe = [
                {
                    "voce": v,
                    "previsto": previsti.get(v.pk, servizi.ZERO),
                    "effettivo": effettivi[v.pk],
                    "precedente": prec[v.pk],
                    "differenza": effettivi[v.pk] - previsti.get(v.pk, servizi.ZERO),
                }
                for v in servizi.voci_ufficiali().filter(tipo=tipo).order_by("sezione", "numero")
            ]
            ctx["gruppi"].append(
                (
                    etichetta,
                    righe,
                    sum((r["previsto"] for r in righe), servizi.ZERO),
                    sum((r["effettivo"] for r in righe), servizi.ZERO),
                )
            )
        return ctx


class RendicontiView(PermessoMixin, ListView):
    """Elenco dei rendiconti per chi consulta solo i conti consuntivi (es. consiglieri)."""

    permission_required = "tesoreria.view_esercizio"
    model = Esercizio
    template_name = "tesoreria/rendiconti.html"
    context_object_name = "esercizi"


class RendicontoView(PermessoMixin, TemplateView):
    permission_required = "tesoreria.view_esercizio"
    template_name = "tesoreria/rendiconto.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        e = get_object_or_404(Esercizio, anno=self.kwargs["anno"])
        ctx.update(servizi.rendiconto(e))
        ctx["organizzazione"] = Organizzazione.corrente()
        return ctx

    def get(self, request, *args, **kwargs):
        formato = request.GET.get("formato")
        if formato == "pdf":
            ctx = self.get_context_data(**kwargs)
            registra(
                Azione.ESPORTAZIONE,
                ctx["esercizio"],
                descrizione=f"Rendiconto {ctx['esercizio'].anno} PDF",
            )
            return risposta_pdf(
                "tesoreria/pdf/rendiconto.html", ctx, f"rendiconto_{ctx['esercizio'].anno}.pdf"
            )
        if formato == "csv":
            return self._csv(self.get_context_data(**kwargs))
        return super().get(request, *args, **kwargs)

    def _csv(self, ctx):
        buffer = io.StringIO()
        w = csv.writer(buffer, delimiter=";")
        anno = ctx["esercizio"].anno
        w.writerow(["sezione", "tipo", "voce", str(anno), str(anno - 1)])
        for s in [*ctx["gestione"], ctx["investimenti"], ctx["imposte"]]:
            for tipo, righe in (("uscite", s.uscite), ("entrate", s.entrate)):
                for v, cor, prec in righe:
                    w.writerow(
                        [
                            s.codice,
                            tipo,
                            v.etichetta,
                            str(cor).replace(".", ","),
                            str(prec).replace(".", ","),
                        ]
                    )
        registra(Azione.ESPORTAZIONE, ctx["esercizio"], descrizione=f"Rendiconto {anno} CSV")
        r = HttpResponse("﻿" + buffer.getvalue(), content_type="text/csv; charset=utf-8")
        r["Content-Disposition"] = f'attachment; filename="rendiconto_{anno}.csv"'
        return r


# --- configurazione ------------------------------------------------------------------------------


class _ConfigMixin:
    def form_valid(self, form):
        nuovo = form.instance.pk is None
        dettagli = {} if nuovo else campi_modificati(form)
        risposta = super().form_valid(form)
        registra(Azione.CREAZIONE if nuovo else Azione.MODIFICA, self.object, **dettagli)
        messages.success(self.request, f"«{self.object}» salvato.")
        return risposta


class ContiView(PermessoMixin, ListView):
    permission_required = "tesoreria.view_conto"
    model = Conto
    template_name = "tesoreria/conti.html"
    context_object_name = "conti"


class ContoNuovoView(PermessoMixin, _ConfigMixin, CreateView):
    permission_required = "tesoreria.add_conto"
    form_class = ContoForm
    template_name = "tesoreria/modulo.html"
    success_url = reverse_lazy("tesoreria:conti")
    extra_context = {"titolo": "Nuovo conto", "indietro": reverse_lazy("tesoreria:conti")}


class ContoModificaView(PermessoMixin, _ConfigMixin, UpdateView):
    permission_required = "tesoreria.change_conto"
    model = Conto
    form_class = ContoForm
    template_name = "tesoreria/modulo.html"
    success_url = reverse_lazy("tesoreria:conti")
    extra_context = {"titolo": "Conto", "indietro": reverse_lazy("tesoreria:conti")}


class VociView(PermessoMixin, ListView):
    permission_required = "tesoreria.view_voce"
    template_name = "tesoreria/voci.html"
    context_object_name = "voci"

    def get_queryset(self):
        return (
            Voce.objects.filter(padre__isnull=True)
            .prefetch_related("sottovoci")
            .order_by("tipo", "sezione", "numero")
        )


class SottovoceNuovaView(PermessoMixin, _ConfigMixin, CreateView):
    permission_required = "tesoreria.add_voce"
    form_class = SottovoceForm
    template_name = "tesoreria/modulo.html"
    success_url = reverse_lazy("tesoreria:voci")
    extra_context = {"titolo": "Nuova sottovoce", "indietro": reverse_lazy("tesoreria:voci")}

    def get_initial(self):
        return {"padre": self.request.GET.get("padre")}


class SottovoceModificaView(PermessoMixin, _ConfigMixin, UpdateView):
    permission_required = "tesoreria.change_voce"
    form_class = SottovoceForm
    template_name = "tesoreria/modulo.html"
    success_url = reverse_lazy("tesoreria:voci")
    extra_context = {"titolo": "Sottovoce", "indietro": reverse_lazy("tesoreria:voci")}

    def get_queryset(self):
        return Voce.objects.filter(padre__isnull=False)
