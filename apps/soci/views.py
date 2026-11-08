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

from . import importazione, lavori_importazione, servizi, sezioni
from .filtri import SocioFilter
from .forms import (
    AccoglimentoForm,
    AmmissioneForm,
    CessazioneForm,
    DomandaForm,
    ImportaForm,
    IncassoMassivoForm,
    ListinoForm,
    LottoForm,
    MotivoForm,
    PagamentoForm,
    RinnovoForm,
    SezioneForm,
    SocioForm,
    StatoCartaForm,
    TesseraForm,
    TipologiaForm,
)
from .models import (
    CartaTessera,
    DomandaIscrizione,
    ListinoTessere,
    LottoTessere,
    Sezione,
    Socio,
    Tessera,
    TipologiaSocio,
)
from .servizi import OperazioneNonValida


def _errore(request, eccezione):
    messages.error(request, " ".join(eccezione.messages))


def _soci(request):
    """Soci delle sezioni visibili all'utente."""
    return sezioni.filtra(Socio.objects.all(), request.user)


def _tessere(request):
    return sezioni.filtra(Tessera.objects.all(), request.user, "socio__sezione")


def _carte(request):
    return sezioni.filtra(CartaTessera.objects.all(), request.user, "lotto__sezione")


def _domande(request):
    ids = sezioni.id_sezioni(request.user)
    qs = DomandaIscrizione.objects.all()
    return qs if ids is None else qs.filter(Q(sezione__in=ids) | Q(sezione__isnull=True))


# --- libro soci --------------------------------------------------------------------------


class ElencoView(PermessoMixin, FilterView):
    permission_required = "soci.view_socio"
    filterset_class = SocioFilter
    paginate_by = 25
    template_name = "soci/elenco.html"

    def get_queryset(self):
        return _soci(self.request).select_related("soggetto", "tipologia", "sezione")

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
        return _soci(self.request).select_related("soggetto", "tipologia", "sezione")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        anno = date.today().year
        ctx["anno"] = anno
        ctx["tessere"] = self.object.tessere.all()
        ctx["tessera_corrente"] = self.object.tessera_anno(anno)
        ctx["form_tessera"] = TesseraForm(
            initial={"importo": servizi.quota_per(self.object.tipologia, anno)}, prefix="tessera"
        )
        ctx["form_pagamento"] = PagamentoForm(prefix="pagamento")
        from apps.organi.models import cariche_di

        ctx["cariche"] = cariche_di(self.object.soggetto)
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

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "utente": self.request.user}

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
                sezione=d["sezione"],
                matricola=d["matricola"],
            )
            if d["tessera"]:
                servizi.rilascia_tessera(
                    socio, date.today().year, self.request.user, carta="prossima"
                )
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

    def get_queryset(self):
        return _soci(self.request)

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "utente": self.request.user}

    def form_valid(self, form):
        from apps.core.immagini import ImmagineNonValida

        try:
            self.object = servizi.salva_socio(
                form,
                self.request.user,
                foto=form.cleaned_data.get("nuova_foto"),
                togli_foto=form.cleaned_data.get("togli_foto"),
            )
        except ImmagineNonValida as e:
            form.add_error("nuova_foto", e)
            return self.form_invalid(form)
        messages.success(self.request, "Dati di iscrizione salvati.")
        return redirect(self.object)


class _AzioneSocioView(PermessoMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        socio = get_object_or_404(_soci(request), pk=pk)
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
            raise OperazioneNonValida(
                [m for errori in form.errors.values() for m in errori] or "Dati non validi."
            )
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
            carta=form.carta(),
        )
        messages.success(request, f"Tesseramento {tessera.anno}: tessera {tessera.codice}.")


# --- tessere -----------------------------------------------------------------------------


class _AzioneTesseraView(PermessoMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        tessera = get_object_or_404(_tessere(request).select_related("socio"), pk=pk)
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
        servizi.annulla_tessera(
            tessera,
            request.user,
            request.POST.get("annulla-motivo", ""),
            libera_carta=request.POST.get("annulla-libera") == "on",
        )
        messages.success(request, f"Tessera {tessera.codice} annullata.")


class RicevutaView(PermessoMixin, View):
    permission_required = "soci.view_tessera"

    def get(self, request, pk):
        tessera = get_object_or_404(
            _tessere(request).select_related("socio__soggetto", "socio__tipologia"),
            pk=pk,
            pagata_il__isnull=False,
            ricevuta_numero__isnull=False,
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
        qs = (
            _tessere(self.request)
            .filter(anno=self.get_anno())
            .select_related("socio__soggetto", "socio__sezione", "carta")
        )
        filtro = self.request.GET.get("stato")
        if filtro == "da_attribuire":
            qs = qs.valide().filter(carta__isnull=True)
        elif filtro == "da_pagare":
            qs = qs.da_pagare()
        elif filtro == "pagate":
            qs = qs.pagate()
        elif filtro == "annullate":
            qs = qs.filter(annullata=True)
        return qs.order_by("socio__numero")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        anno = self.get_anno()
        valide = _tessere(self.request).valide().filter(anno=anno)
        ids = sezioni.id_sezioni(self.request.user)
        ctx["anno"] = anno
        ctx["listino"] = servizi.listino(anno)
        ctx["anni"] = range(date.today().year + 1, date.today().year - 6, -1)
        ctx["stato"] = self.request.GET.get("stato", "")
        ctx["riepilogo"] = valide.aggregate(
            rilasciate=Count("id"),
            pagate=Count("id", filter=Q(pagata_il__isnull=False)),
            incassato=Sum("importo", filter=Q(pagata_il__isnull=False), default=0),
            da_incassare=Sum("importo", filter=Q(pagata_il__isnull=True), default=0),
        )
        ctx["da_rinnovare"] = servizi.soci_da_rinnovare(anno, ids).count()
        ctx["morosi"] = _soci(self.request).morosi(anno).count()
        ctx["da_attribuire"] = servizi.da_attribuire(anno, ids).count()
        ctx["disponibili"] = _carte(self.request).disponibili().filter(anno=anno).count()
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
        ctx["da_rinnovare"] = servizi.soci_da_rinnovare(
            anno, sezioni.id_sezioni(self.request.user)
        ).order_by("numero")
        ctx["disponibili"] = _carte(self.request).disponibili().filter(anno=anno).count()
        ctx["listino"] = servizi.listino(anno)
        return ctx

    def form_valid(self, form):
        if self.request.method == "GET" or self.request.POST.get("conferma") != "1":
            return self.render_to_response(self.get_context_data(form=form))
        anno = form.cleaned_data["anno"]
        rilasciate, errori = servizi.rinnovo_massivo(
            anno,
            self.request.user,
            attribuisci=form.cleaned_data["attribuisci"],
            sezioni=sezioni.id_sezioni(self.request.user),
        )
        senza = sum(1 for t in rilasciate if not t.attribuita)
        messages.success(
            self.request,
            f"Tesseramento {anno}: {len(rilasciate)} soci rinnovati"
            + (f", {senza} ancora senza tessera fisica." if senza else "."),
        )
        for socio, errore in errori:
            messages.warning(self.request, f"{socio}: {errore}")
        return redirect(f"{reverse('soci:tessere')}?anno={anno}")

    def get(self, request, *args, **kwargs):
        form = self.get_form()
        if form.is_bound:
            form.is_valid()
        return self.render_to_response(self.get_context_data(form=form))


class IncassoMassivoView(PermessoMixin, FormView):
    """Incasso di più quote dell'anno con la stessa data e lo stesso metodo."""

    permission_required = "soci.incassa_quota"
    form_class = IncassoMassivoForm
    template_name = "soci/incasso_massivo.html"

    def get_anno(self):
        try:
            return int(self.request.GET.get("anno") or self.request.POST.get("anno"))
        except (TypeError, ValueError):
            return date.today().year

    def da_pagare(self):
        return (
            _tessere(self.request)
            .da_pagare()
            .filter(anno=self.get_anno())
            .select_related("socio__soggetto", "socio__sezione", "carta")
            .order_by("socio__numero")
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["tessere"] = self.da_pagare()
        kwargs["prefix"] = "incasso"
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["anno"] = self.get_anno()
        ctx["da_pagare"] = self.da_pagare()
        ctx["anni"] = range(date.today().year + 1, date.today().year - 6, -1)
        ctx["scelte"] = {str(v) for v in (ctx["form"]["tessere"].value() or [])}
        return ctx

    def form_valid(self, form):
        d = form.cleaned_data
        fatte, errori = servizi.incasso_massivo(
            list(d["tessere"]), self.request.user, pagata_il=d["pagata_il"], metodo=d["metodo"],
            riferimento=d["riferimento"],
        )  # fmt: skip
        if fatte:
            totale = sum(t.importo for t in fatte)
            messages.success(
                self.request,
                f"Incassate {len(fatte)} quote per {totale} €: ricevute dalla "
                f"{fatte[0].codice_ricevuta} alla {fatte[-1].codice_ricevuta}.",
            )
        for t, errore in errori:
            messages.warning(self.request, f"{t.socio.soggetto.nome_completo}: {errore}")
        return redirect(f"{reverse('soci:tessere')}?anno={self.get_anno()}&stato=pagate")


class AttribuisciView(_AzioneTesseraView):
    permission_required = "soci.add_tessera"

    def esegui(self, request, tessera):
        t = servizi.attribuisci_carta(tessera, request.user, request.POST.get("codice", "").strip())
        messages.success(request, f"Attribuita la tessera {t.codice}.")


class AttribuzioneMassivaView(PermessoMixin, View):
    permission_required = "soci.add_tessera"
    http_method_names = ["post"]

    def post(self, request):
        try:
            anno = int(request.POST.get("anno"))
        except (TypeError, ValueError):
            anno = date.today().year
        ordine = "cognome" if request.POST.get("ordine") == "cognome" else "numero"
        fatte, mancanti = servizi.attribuzione_massiva(
            anno, request.user, ordine, sezioni.id_sezioni(request.user)
        )
        messages.success(request, f"Attribuite {len(fatte)} tessere.")
        if mancanti:
            messages.warning(
                request, f"{mancanti} soci restano senza tessera: caricare un nuovo lotto."
            )
        return redirect(f"{reverse('soci:tessere')}?anno={anno}")


# --- tessere fisiche dalla sede centrale -------------------------------------------------


class TessereFisicheView(PermessoMixin, ListView):
    permission_required = "soci.view_lottotessere"
    template_name = "soci/tessere_fisiche.html"
    context_object_name = "carte"
    paginate_by = 100

    def get_anno(self):
        try:
            return int(self.request.GET.get("anno") or date.today().year)
        except ValueError:
            return date.today().year

    def get_queryset(self):
        qs = (
            _carte(self.request)
            .filter(anno=self.get_anno())
            .select_related("lotto__sezione", "tessera__socio__soggetto")
        )
        if stato := self.request.GET.get("stato"):
            qs = qs.filter(stato=stato)
        if lotto := self.request.GET.get("lotto"):
            qs = qs.filter(lotto_id=lotto)
        if q := self.request.GET.get("q", "").strip():
            qs = qs.filter(
                Q(codice__icontains=q) | Q(tessera__socio__soggetto__cognome__icontains=q)
            )
        return qs.order_by("lotto__serie", "numero")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        anno = self.get_anno()
        ctx["anno"] = anno
        ctx["anni"] = range(date.today().year + 1, date.today().year - 6, -1)
        ctx["lotti"] = sezioni.filtra(
            LottoTessere.objects.filter(anno=anno).select_related("sezione"), self.request.user
        ).annotate(
            disponibili=Count("carte", filter=Q(carte__stato=CartaTessera.Stato.DISPONIBILE)),
            attribuite=Count("carte", filter=Q(carte__stato=CartaTessera.Stato.ATTRIBUITA)),
        )
        ctx["giacenza"] = servizi.giacenza(anno, sezioni.id_sezioni(self.request.user))
        ctx["listino"] = servizi.listino(anno)
        ctx["stati"] = CartaTessera.Stato.choices
        ctx["stato"] = self.request.GET.get("stato", "")
        ctx["q"] = self.request.GET.get("q", "")
        ctx["form_stato"] = StatoCartaForm()
        return ctx


class LottoNuovoView(PermessoMixin, FormView):
    permission_required = "soci.gestisci_tessere_fisiche"
    form_class = LottoForm
    template_name = "soci/lotto_modulo.html"

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "utente": self.request.user}

    def form_valid(self, form):
        d = form.cleaned_data
        try:
            lotto = servizi.carica_lotto(self.request.user, **d)
        except OperazioneNonValida as e:
            form.add_error(None, e)
            return self.form_invalid(form)
        messages.success(self.request, f"Caricate {lotto.quantita} tessere ({lotto}).")
        return redirect(f"{reverse('soci:tessere_fisiche')}?anno={lotto.anno}")


class StatoCartaView(PermessoMixin, View):
    permission_required = "soci.gestisci_tessere_fisiche"
    http_method_names = ["post"]

    def post(self, request, pk):
        carta = get_object_or_404(_carte(request), pk=pk)
        form = StatoCartaForm(request.POST)
        try:
            if not form.is_valid():
                raise OperazioneNonValida("Stato non valido.")
            servizi.cambia_stato_carta(
                carta, form.cleaned_data["stato"], request.user, form.cleaned_data["motivo"]
            )
            messages.success(request, f"Tessera {carta.codice} aggiornata.")
        except OperazioneNonValida as e:
            _errore(request, e)
        return redirect(f"{reverse('soci:tessere_fisiche')}?anno={carta.anno}&q={carta.codice}")


class EsportaTesseratiView(PermessoMixin, View):
    permission_required = "soci.esporta_libro_soci"

    def get(self, request):
        try:
            anno = int(request.GET.get("anno") or date.today().year)
        except ValueError:
            anno = date.today().year
        buffer = io.StringIO()
        servizi.esporta_tesserati_csv(anno, buffer, request.user, sezioni.id_sezioni(request.user))
        risposta = HttpResponse(
            "\ufeff" + buffer.getvalue(), content_type="text/csv; charset=utf-8"
        )
        risposta["Content-Disposition"] = f'attachment; filename="tesserati_{anno}.csv"'
        return risposta


# --- stampe ed esportazioni --------------------------------------------------------------


class LibroSociPdfView(PermessoMixin, View):
    permission_required = "soci.esporta_libro_soci"

    def get(self, request):
        soci = _soci(request).select_related("soggetto", "tipologia", "sezione")
        if (sezione := request.GET.get("sezione", "")).isdigit():
            soci = soci.filter(sezione_id=int(sezione))
        soci = soci.order_by("numero")
        registra(Azione.ESPORTAZIONE, descrizione=f"Libro soci PDF ({soci.count()} iscritti)")
        return risposta_pdf(
            "soci/pdf/libro_soci.html",
            {"soci": soci, "organizzazione": Organizzazione.corrente(), "oggi": date.today()},
            f"libro_soci_{date.today():%Y%m%d}.pdf",
        )


class LibroSociCsvView(PermessoMixin, View):
    permission_required = "soci.esporta_libro_soci"

    def get(self, request):
        filtro = SocioFilter(request.GET, queryset=_soci(request), request=request)
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
        qs = _domande(self.request).select_related("socio", "sezione")
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

    def get_queryset(self):
        return _domande(self.request)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["esistente"] = servizi.soggetto_per_domanda(self.object)
        ctx["form_accoglimento"] = AccoglimentoForm(
            initial={"tipologia": self.object.tipologia, "sezione": self.object.sezione},
            prefix="accogli",
            utente=self.request.user,
        )
        ctx["form_rigetto"] = MotivoForm(prefix="respingi")
        return ctx


class NuovaDomandaView(PermessoMixin, CreateView):
    permission_required = "soci.add_domandaiscrizione"
    model = DomandaIscrizione
    form_class = DomandaForm
    template_name = "soci/domanda_modulo.html"

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "utente": self.request.user}

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
        domanda = get_object_or_404(_domande(request), pk=pk)
        form = AccoglimentoForm(request.POST, prefix="accogli", utente=request.user)
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
                sezione=d["sezione"],
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
        domanda = get_object_or_404(_domande(request), pk=pk)
        try:
            servizi.respingi_domanda(domanda, request.user, request.POST.get("respingi-motivo", ""))
            messages.success(request, "Domanda respinta.")
        except OperazioneNonValida as e:
            _errore(request, e)
        return redirect(domanda)


# --- listino del tesseramento ------------------------------------------------------------


class ListinoView(PermessoMixin, FormView):
    """Costo d'acquisto delle tessere e prezzi di distribuzione per tipologia di un anno."""

    permission_required = "soci.change_listinotessere"
    form_class = ListinoForm
    template_name = "soci/listino.html"

    def get_anno(self):
        try:
            return int(self.request.GET.get("anno") or date.today().year)
        except ValueError:
            return date.today().year

    def get_form_kwargs(self):
        self.anno = self.get_anno()
        self.listino = servizi.listino(self.anno)
        return {**super().get_form_kwargs(), "listino": self.listino}

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["anno"] = self.anno
        ctx["listino"] = self.listino
        ctx["anni"] = range(date.today().year + 1, date.today().year - 6, -1)
        ctx["storico"] = ListinoTessere.objects.prefetch_related("quote__tipologia")[:6]
        return ctx

    def form_valid(self, form):
        servizi.salva_listino(
            self.anno,
            self.request.user,
            costo_acquisto=form.cleaned_data["costo_acquisto"],
            quote=form.quote(),
            note=form.cleaned_data["note"],
        )
        messages.success(self.request, f"Listino {self.anno} salvato.")
        return redirect(f"{reverse('soci:tessere')}?anno={self.anno}")


# --- sezioni -----------------------------------------------------------------------------


class SezioniView(PermessoMixin, ListView):
    permission_required = "soci.view_sezione"
    template_name = "soci/sezioni.html"
    context_object_name = "sezioni"

    def get_queryset(self):
        return Sezione.objects.annotate(
            n_soci=Count("soci", filter=Q(soci__stato=Socio.Stato.ATTIVO)),
            n_utenti=Count("utenti", distinct=True),
        )


class _SezioneMixin:
    model = Sezione
    form_class = SezioneForm
    template_name = "soci/sezione_modulo.html"
    success_url = reverse_lazy("soci:sezioni")

    def form_valid(self, form):
        nuova = form.instance.pk is None
        dettagli = {} if nuova else campi_modificati(form)
        risposta = super().form_valid(form)
        if nuova:
            registra(Azione.CREAZIONE, self.object)
        elif dettagli.get("campi"):
            registra(Azione.MODIFICA, self.object, **dettagli)
        messages.success(self.request, f"Sezione «{self.object}» salvata.")
        return risposta


class SezioneNuovaView(PermessoMixin, _SezioneMixin, CreateView):
    permission_required = "soci.add_sezione"


class SezioneModificaView(PermessoMixin, _SezioneMixin, UpdateView):
    permission_required = "soci.change_sezione"


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


# --- importazione dal registro soci nazionale --------------------------------------------


class ImportaView(PermessoMixin, FormView):
    """Caricamento del file; anteprima ed esecuzione girano in un processo separato e
    l'avanzamento compare in una finestra modale."""

    permission_required = "soci.importa_soci"
    form_class = ImportaForm
    template_name = "soci/importa.html"

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "utente": self.request.user}

    def _opzioni(self, d):
        utente = self.request.user
        consentite = sezioni.id_sezioni(utente)
        return {
            "sezione": d["sezione"].pk if d.get("sezione") else None,
            "abbina": d.get("abbina") or "comune",
            "tipologia": d["tipologia"].pk if d.get("tipologia") else None,
            "crea_sezioni": bool(d.get("crea_sezioni")) and utente.has_perm("soci.add_sezione"),
            "allinea_sezione": bool(d.get("allinea_sezione")),
            "tessere": bool(d.get("tessere")),
            "crea_tessere": bool(d.get("crea_tessere"))
            and utente.has_perm("soci.gestisci_tessere_fisiche"),
            "cessazioni": bool(d.get("cessazioni")),
            "quote_pagate": d.get("quote") == "pagate",
            "anno_tessere": d.get("anno_tessere"),
            "sezioni_consentite": sorted(consentite) if consentite is not None else None,
        }

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        lavoro = lavori_importazione.leggi(self.request.GET.get("lavoro", ""), self.request.user)
        if lavoro:
            ctx["lavoro"] = lavoro
            ctx["in_corso"] = lavoro["stato"] in ("in_attesa", "in_corso")
            if lavoro["stato"] == "completato":
                ctx["rapporto"] = lavoro["rapporto"]
                ctx["nome_file"] = lavoro["nome_file"]
                ctx["colonne"] = lavoro["colonne"]
                ctx["ignorate"] = lavoro["ignorate"]
        return ctx

    def form_valid(self, form):
        f = form.cleaned_data["file"]
        contenuto = f.read()
        try:
            mappa, righe, ignorate = importazione.leggi(f.name, contenuto)
        except importazione.FileNonValido as e:
            form.add_error("file", e)
            return self.form_invalid(form)
        lavoro_id = lavori_importazione.nuovo(
            self.request.user, f.name, contenuto, self._opzioni(form.cleaned_data),
            sorted(set(mappa.values())), ignorate, len(righe),
        )  # fmt: skip
        lavori_importazione.avvia(lavoro_id, "anteprima")
        return redirect(f"{reverse('soci:importa')}?lavoro={lavoro_id}")

    def post(self, request, *args, **kwargs):
        if request.POST.get("azione") != "esegui":
            return super().post(request, *args, **kwargs)
        lavoro_id = request.POST.get("lavoro", "")
        lavoro = lavori_importazione.leggi(lavoro_id, request.user)
        if not lavoro or lavoro["fase"] != "anteprima" or lavoro["stato"] != "completato":
            messages.error(request, "Anteprima scaduta o già usata: caricare di nuovo il file.")
            return redirect("soci:importa")
        registra(Azione.CREAZIONE, descrizione=f"Importazione avviata: {lavoro['nome_file']}")
        lavori_importazione.avvia(lavoro_id, "esecuzione")
        return redirect(f"{reverse('soci:importa')}?lavoro={lavoro_id}")


class AvanzamentoImportazioneView(PermessoMixin, View):
    """Contenuto della finestra di avanzamento, richiesto ogni secondo (HTMX)."""

    permission_required = "soci.importa_soci"

    def get(self, request, lavoro):
        from django.http import Http404
        from django.shortcuts import render

        dati = lavori_importazione.leggi(lavoro, request.user)
        if dati is None:
            raise Http404
        if dati["stato"] not in ("in_attesa", "in_corso"):
            risposta = HttpResponse(status=204)
            risposta["HX-Redirect"] = f"{reverse('soci:importa')}?lavoro={lavoro}"
            return risposta
        return render(request, "soci/_avanzamento_importazione.html", {"lavoro": dati})


# --- modulo di adesione (Allegato A) e richiesta firmata ---------------------------------


class DomandaPdfView(PermessoMixin, View):
    """Modulo compilato con i dati della domanda, da stampare e far firmare."""

    permission_required = "soci.view_domandaiscrizione"

    def get(self, request, pk):
        from . import modulo

        d = get_object_or_404(_domande(request).select_related("sezione"), pk=pk)
        risposta = HttpResponse(modulo.pdf(modulo.dati_domanda(d)), content_type="application/pdf")
        risposta["Content-Disposition"] = f'inline; filename="allegato_a_domanda_{d.pk}.pdf"'
        return risposta


class ModuloVuotoView(PermessoMixin, View):
    """Modulo in bianco da compilare a mano."""

    permission_required = "soci.view_domandaiscrizione"

    def get(self, request):
        from . import modulo

        risposta = HttpResponse(modulo.pdf(), content_type="application/pdf")
        risposta["Content-Disposition"] = 'inline; filename="allegato_a.pdf"'
        return risposta


class ModuloSocioPdfView(PermessoMixin, View):
    """Modulo precompilato con i dati del socio (per far firmare chi non l'ha ancora fatto)."""

    permission_required = "soci.view_socio"

    def get(self, request, pk):
        from . import modulo

        socio = get_object_or_404(_soci(request).select_related("soggetto", "sezione"), pk=pk)
        risposta = HttpResponse(
            modulo.pdf(modulo.dati_socio(socio)), content_type="application/pdf"
        )
        risposta["Content-Disposition"] = f'inline; filename="allegato_a_{socio.numero}.pdf"'
        return risposta


class ModuloFirmatoView(PermessoMixin, View):
    """La richiesta firmata, mostrata nel browser (anche dentro la scheda del socio)."""

    permission_required = "soci.view_socio"

    def get(self, request, pk):
        from django.http import FileResponse, Http404

        socio = get_object_or_404(_soci(request), pk=pk)
        if not socio.modulo_adesione:
            raise Http404
        registra(Azione.CONSULTAZIONE, socio, descrizione="Richiesta di adesione firmata")
        risposta = FileResponse(socio.modulo_adesione.open("rb"), content_type="application/pdf")
        risposta["Content-Disposition"] = f'inline; filename="richiesta_firmata_{socio.numero}.pdf"'
        # consultabile solo dalle pagine dell'applicazione (riquadro nella scheda del socio)
        risposta["X-Frame-Options"] = "SAMEORIGIN"
        risposta["Content-Security-Policy"] = "frame-ancestors 'self'"
        risposta["Cache-Control"] = "private, no-store"
        return risposta


class CaricaModuloView(PermessoMixin, View):
    permission_required = "soci.change_socio"
    http_method_names = ["post"]

    def post(self, request, pk):
        socio = get_object_or_404(_soci(request), pk=pk)
        try:
            servizi.carica_modulo(socio, request.FILES.getlist("modulo"), request.user)
            messages.success(request, "Richiesta di adesione firmata salvata.")
        except OperazioneNonValida as e:
            _errore(request, e)
        return redirect(f"{socio.get_absolute_url()}#modulo-adesione")
