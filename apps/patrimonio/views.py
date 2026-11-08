# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Viste del patrimonio: inventario con ricerca, scheda del bene, foto
# *              (solo con permesso), valutazioni, prestiti e uscite, etichette QR, stampa
# *              dell'inventario, passaggi di consegne, scheda pubblica del QR.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import io
from datetime import date

import django_filters
from django import forms
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView
from django_filters.views import FilterView

from apps.core.audit import Azione, registra
from apps.core.immagini import risposta_immagine
from apps.core.models import Organizzazione
from apps.core.pdf import risposta_pdf
from apps.core.views import PermessoMixin

from . import servizi
from .forms import (
    BeneForm,
    CategoriaForm,
    PassaggioForm,
    RestituzioneForm,
    UscitaForm,
    ValutazioneForm,
)
from .models import Bene, CategoriaBene, PassaggioConsegne, Uscita


def _errore(request, e):
    messages.error(request, " ".join(e.messages))


def url_pubblico(request, bene):
    percorso = reverse("bene_pubblico", args=[bene.token])
    # i QR stampati devono puntare al sito pubblico, non all'indirizzo interno
    if settings.URL_PUBBLICO:
        return settings.URL_PUBBLICO + percorso
    return request.build_absolute_uri(percorso)


class BeneFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(method="cerca", label="Cerca")
    categoria = django_filters.ModelChoiceFilter(
        queryset=CategoriaBene.objects.all(), empty_label="Tutte le categorie"
    )
    stato = django_filters.ChoiceFilter(
        choices=[("patrimonio", "Nel patrimonio"), *Bene.Stato.choices, ("tutti", "Tutti")],
        method="per_stato",
        empty_label=None,
    )

    class Meta:
        model = Bene
        fields = ["q", "categoria", "stato"]

    def __init__(self, data=None, *args, **kwargs):
        data = data.copy() if data is not None else {}
        data.setdefault("stato", "patrimonio")
        super().__init__(data, *args, **kwargs)
        for campo in self.form.fields.values():
            campo.widget.attrs["class"] = (
                "form-select" if isinstance(campo.widget, forms.Select) else "form-control"
            )
        self.form.fields["q"].widget.attrs.update(
            {"placeholder": "Numero, nome, ubicazione, provenienza", "type": "search"}
        )

    def cerca(self, qs, name, value):
        for parola in value.split():
            filtro = (
                Q(nome__icontains=parola) | Q(descrizione__icontains=parola)
                | Q(ubicazione__icontains=parola) | Q(provenienza_testo__icontains=parola)
                | Q(codice_precedente__iexact=parola)
            )  # fmt: skip
            if parola.isdigit():
                filtro |= Q(numero=int(parola))
            qs = qs.filter(filtro)
        return qs

    def per_stato(self, qs, name, value):
        if value == "patrimonio":
            return qs.exclude(stato=Bene.Stato.USCITO)
        return qs if value == "tutti" else qs.filter(stato=value)


class InventarioView(PermessoMixin, FilterView):
    permission_required = "patrimonio.view_bene"
    filterset_class = BeneFilter
    template_name = "patrimonio/inventario.html"
    paginate_by = 30

    def get_queryset(self):
        return Bene.objects.select_related("categoria")

    def get_template_names(self):
        if self.request.htmx and not self.request.htmx.boosted:
            return ["patrimonio/inventario.html#tabella"]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["totali"] = servizi.totali()
        ctx["scaduti"] = servizi.prestiti_scaduti()
        return ctx


class BeneView(PermessoMixin, DetailView):
    permission_required = "patrimonio.view_bene"
    model = Bene
    template_name = "patrimonio/bene.html"
    context_object_name = "bene"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        b = self.object
        ctx["uscite"] = b.uscite.select_related("controparte")
        ctx["prestito"] = b.uscite.filter(
            tipo=Uscita.Tipo.PRESTITO, restituito_il__isnull=True
        ).first()
        ctx["form_valutazione"] = ValutazioneForm(prefix="val")
        ctx["form_uscita"] = UscitaForm(prefix="usc")
        ctx["form_restituzione"] = RestituzioneForm(prefix="res")
        ctx["qr"] = servizi.qr_svg(url_pubblico(self.request, b)) if b.pubblico else ""
        ctx["url_pubblico"] = url_pubblico(self.request, b)
        return ctx


class _BeneFormMixin:
    model = Bene
    form_class = BeneForm
    template_name = "patrimonio/bene_modulo.html"
    context_object_name = "bene"

    def form_valid(self, form):
        try:
            self.object = servizi.salva_bene(
                form, self.request.user, foto=form.cleaned_data.get("file_foto"),
                togli_foto=form.cleaned_data.get("togli_foto"),
            )  # fmt: skip
        except ValidationError as e:
            form.add_error("file_foto", e)
            return self.form_invalid(form)
        messages.success(self.request, f"{self.object} salvato.")
        return redirect(self.object)


class BeneNuovoView(PermessoMixin, _BeneFormMixin, CreateView):
    permission_required = "patrimonio.add_bene"


class BeneModificaView(PermessoMixin, _BeneFormMixin, UpdateView):
    permission_required = "patrimonio.change_bene"


class FotoView(PermessoMixin, View):
    permission_required = "patrimonio.view_bene"

    def get(self, request, pk):
        return risposta_immagine(get_object_or_404(Bene, pk=pk).foto)


class _AzioneBeneView(PermessoMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        b = get_object_or_404(Bene, pk=pk)
        try:
            self.esegui(request, b)
        except ValidationError as e:
            _errore(request, e)
        return redirect(b)


class ValutazioneView(_AzioneBeneView):
    permission_required = "patrimonio.valuta_bene"

    def esegui(self, request, b):
        form = ValutazioneForm(request.POST, prefix="val")
        if not form.is_valid():
            raise ValidationError("Valutazione non valida: controllare data e valore.")
        servizi.valuta(b, request.user, **form.cleaned_data)
        messages.success(request, "Valutazione registrata.")


class UscitaView(_AzioneBeneView):
    permission_required = "patrimonio.movimenta_bene"

    def esegui(self, request, b):
        form = UscitaForm(request.POST, prefix="usc")
        if not form.is_valid():
            raise ValidationError([m for errori in form.errors.values() for m in errori])
        u = servizi.registra_uscita(b, request.user, **form.cleaned_data)
        messages.success(request, f"{u.get_tipo_display()} registrato.")


class RestituzioneView(_AzioneBeneView):
    permission_required = "patrimonio.movimenta_bene"

    def esegui(self, request, b):
        prestito = b.uscite.filter(tipo=Uscita.Tipo.PRESTITO, restituito_il__isnull=True).first()
        form = RestituzioneForm(request.POST, prefix="res")
        if prestito is None or not form.is_valid():
            raise ValidationError("Restituzione non valida.")
        servizi.restituzione(prestito, request.user, **form.cleaned_data)
        messages.success(request, "Restituzione registrata.")


# --- stampe ------------------------------------------------------------------------------------


class StampaInventarioView(PermessoMixin, View):
    permission_required = "patrimonio.view_bene"

    def get(self, request):
        filtro = BeneFilter(request.GET, queryset=Bene.objects.select_related("categoria"))
        beni = filtro.qs.order_by("categoria__ordine", "categoria__nome", "numero")
        if request.GET.get("formato") == "csv":
            buffer = io.StringIO()
            servizi.esporta_csv(beni, buffer, request.user)
            r = HttpResponse("﻿" + buffer.getvalue(), content_type="text/csv; charset=utf-8")
            r["Content-Disposition"] = (
                f'attachment; filename="inventario_{date.today():%Y%m%d}.csv"'
            )
            return r
        registra(Azione.ESPORTAZIONE, descrizione=f"Inventario PDF ({beni.count()} beni)")
        return risposta_pdf(
            "patrimonio/pdf/inventario.html",
            {
                "beni": beni,
                "totali": servizi.totali(),
                "organizzazione": Organizzazione.corrente(),
                "oggi": date.today(),
            },
            f"inventario_{date.today():%Y%m%d}.pdf",
        )


class EtichetteView(PermessoMixin, View):
    """Foglio A4 di etichette con QR (schede pubbliche) e numero di inventario."""

    permission_required = "patrimonio.view_bene"

    def get(self, request):
        filtro = BeneFilter(request.GET, queryset=Bene.objects.select_related("categoria"))
        beni = filtro.qs.order_by("numero")
        etichette = [
            {
                "bene": b,
                "qr": servizi.qr_svg(url_pubblico(request, b), scala=3) if b.pubblico else "",
            }
            for b in beni
        ]
        return risposta_pdf(
            "patrimonio/pdf/etichette.html",
            {"etichette": etichette, "organizzazione": Organizzazione.corrente()},
            "etichette_inventario.pdf",
        )


# --- passaggi di consegne ----------------------------------------------------------------------


class PassaggiView(PermessoMixin, ListView):
    permission_required = "patrimonio.view_passaggioconsegne"
    model = PassaggioConsegne
    template_name = "patrimonio/passaggi.html"
    context_object_name = "passaggi"


class PassaggioNuovoView(PermessoMixin, View):
    permission_required = "patrimonio.add_passaggioconsegne"
    template_name = "patrimonio/passaggio_modulo.html"

    def get(self, request):
        return self._render(PassaggioForm())

    def post(self, request):
        form = PassaggioForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data
            protocolla = d.pop("protocolla") and request.user.has_perm("protocollo.add_protocollo")
            try:
                p = servizi.crea_passaggio(request.user, protocolla=protocolla, **d)
                messages.success(
                    request, f"Passaggio di consegne registrato ({p.numero_beni} beni)."
                )
                return redirect("patrimonio:passaggi")
            except ValidationError as e:
                form.add_error(None, e)
        return self._render(form)

    def _render(self, form):
        return render(
            self.request,
            self.template_name,
            {"form": form, "totali": servizi.totali(), "beni": servizi.fotografia()},
        )


class PassaggioPdfView(PermessoMixin, View):
    permission_required = "patrimonio.view_passaggioconsegne"

    def get(self, request, pk):
        p = get_object_or_404(PassaggioConsegne, pk=pk)
        return FileResponse(
            p.file.open("rb"),
            filename=f"passaggio_consegne_{p.data:%Y%m%d}.pdf",
            content_type="application/pdf",
        )


# --- categorie ---------------------------------------------------------------------------------


class CategorieView(PermessoMixin, ListView):
    permission_required = "patrimonio.view_categoriabene"
    model = CategoriaBene
    template_name = "patrimonio/categorie.html"
    context_object_name = "categorie"


class CategoriaNuovaView(PermessoMixin, CreateView):
    permission_required = "patrimonio.add_categoriabene"
    form_class = CategoriaForm
    template_name = "patrimonio/modulo.html"
    success_url = reverse_lazy("patrimonio:categorie")
    extra_context = {"titolo": "Nuova categoria", "indietro": reverse_lazy("patrimonio:categorie")}


class CategoriaModificaView(PermessoMixin, UpdateView):
    permission_required = "patrimonio.change_categoriabene"
    model = CategoriaBene
    form_class = CategoriaForm
    template_name = "patrimonio/modulo.html"
    success_url = reverse_lazy("patrimonio:categorie")
    extra_context = {"titolo": "Categoria", "indietro": reverse_lazy("patrimonio:categorie")}


# --- scheda pubblica ---------------------------------------------------------------------------


@method_decorator(never_cache, name="dispatch")
class BenePubblicoView(TemplateView):
    """Scheda del cimelio per chi inquadra il QR: solo dati scelti per la pubblicazione."""

    template_name = "patrimonio/pubblico.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        b = get_object_or_404(
            Bene.objects.select_related("categoria"), token=kwargs["token"], pubblico=True
        )
        ctx["bene"] = b
        ctx["organizzazione"] = Organizzazione.corrente()
        return ctx


class FotoPubblicaView(View):
    def get(self, request, token):
        b = get_object_or_404(Bene, token=token, pubblico=True, foto_pubblica=True)
        return risposta_immagine(b.foto, privata=False)
