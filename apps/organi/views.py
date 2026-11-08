# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Viste degli organi sociali: organi e cariche, riunioni e convocazioni,
# *              presenze (HTMX), verbale e delibere, libro dei verbali, registro delibere.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from datetime import timedelta

from django.contrib import messages
from django.db.models import Count, Q
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, FormView, ListView, TemplateView, UpdateView

from apps.core.audit import Azione, campi_modificati, registra
from apps.core.views import PermessoMixin

from . import servizi
from .forms import CaricaForm, DeliberaForm, FineCaricaForm, OrganoForm, RiunioneForm, VerbaleForm
from .models import Carica, Delibera, Organo, Presenza, Riunione, Verbale
from .servizi import OperazioneNonValida


def _errore(request, e):
    messages.error(request, " ".join(e.messages))


# --- organi e cariche ------------------------------------------------------------------------


class OrganiView(PermessoMixin, ListView):
    permission_required = "organi.view_organo"
    template_name = "organi/organi.html"
    context_object_name = "organi"

    def get_queryset(self):
        oggi = timezone.localdate()
        in_carica = Q(cariche__dal__lte=oggi) & (
            Q(cariche__al__isnull=True) | Q(cariche__al__gt=oggi)
        )
        return Organo.objects.filter(attivo=True).annotate(
            componenti=Count("cariche", filter=in_carica)
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["prossime"] = (
            Riunione.objects.filter(
                stato=Riunione.Stato.CONVOCATA,
                prima_convocazione__gte=timezone.now() - timedelta(days=1),
            )
            .select_related("organo")
            .order_by("prima_convocazione")[:10]
        )
        ctx["in_preparazione"] = Riunione.objects.filter(stato=Riunione.Stato.BOZZA).select_related(
            "organo"
        )
        return ctx


class OrganigrammaView(PermessoMixin, View):
    """Organigramma dei componenti in carica, in PDF."""

    permission_required = "organi.view_organo"

    def get(self, request, pk):
        from django.utils.text import slugify

        organo = get_object_or_404(Organo, pk=pk)
        pdf = servizi.pdf_organigramma(organo, request.user)
        risposta = HttpResponse(pdf, content_type="application/pdf")
        nome = f"organigramma_{slugify(organo.sigla or organo.nome)}.pdf"
        risposta["Content-Disposition"] = f'inline; filename="{nome}"'
        return risposta


class OrganoView(PermessoMixin, DetailView):
    permission_required = "organi.view_organo"
    model = Organo
    template_name = "organi/organo.html"
    context_object_name = "organo"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        o = self.object
        ctx["in_carica"] = o.cariche_al().select_related("soggetto")
        ctx["storico"] = o.cariche.select_related("soggetto").exclude(
            pk__in=ctx["in_carica"].values("pk")
        )
        ctx["riunioni"] = o.riunioni.select_related("verbale")[:30]
        ctx["verbali"] = (
            Verbale.objects.filter(riunione__organo=o, chiuso=True)
            .select_related("riunione")
            .order_by("-numero")
        )
        ctx["form_carica"] = CaricaForm()
        ctx["form_fine"] = FineCaricaForm()
        return ctx


class OrganoModificaView(PermessoMixin, UpdateView):
    permission_required = "organi.change_organo"
    model = Organo
    form_class = OrganoForm
    template_name = "organi/modulo.html"
    extra_context = {"titolo": "Regole dell'organo"}

    def form_valid(self, form):
        dettagli = campi_modificati(form)
        risposta = super().form_valid(form)
        if dettagli.get("campi"):
            registra(Azione.MODIFICA, self.object, **dettagli)
        messages.success(self.request, "Regole dell'organo salvate.")
        return risposta


class NominaView(PermessoMixin, View):
    permission_required = "organi.gestisci_cariche"
    http_method_names = ["post"]

    def post(self, request, pk):
        organo = get_object_or_404(Organo, pk=pk)
        form = CaricaForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Dati della carica non validi.")
            return redirect(organo)
        d = form.cleaned_data
        try:
            servizi.nomina(
                organo,
                d["soggetto"],
                d["ruolo"],
                d["dal"],
                request.user,
                atto=d["atto"],
                note=d["note"],
            )
            messages.success(request, "Carica registrata.")
        except OperazioneNonValida as e:
            _errore(request, e)
        return redirect(organo)


class FineCaricaView(PermessoMixin, View):
    permission_required = "organi.gestisci_cariche"
    http_method_names = ["post"]

    def post(self, request, pk):
        carica = get_object_or_404(Carica, pk=pk)
        form = FineCaricaForm(request.POST)
        if form.is_valid():
            try:
                servizi.termina_carica(
                    carica, form.cleaned_data["al"], request.user, form.cleaned_data["motivo"]
                )
                messages.success(request, "Fine della carica registrata.")
            except OperazioneNonValida as e:
                _errore(request, e)
        else:
            errori = [e for lista in form.errors.values() for e in lista]
            messages.error(request, "Fine carica non registrata: " + " ".join(errori))
        return redirect(carica.organo)


# --- riunioni ----------------------------------------------------------------------------------


class RiunioniView(PermessoMixin, ListView):
    permission_required = "organi.view_riunione"
    template_name = "organi/riunioni.html"
    context_object_name = "riunioni"
    paginate_by = 30

    def get_queryset(self):
        qs = Riunione.objects.select_related("organo", "verbale")
        if organo := self.request.GET.get("organo"):
            qs = qs.filter(organo_id=organo)
        if anno := self.request.GET.get("anno"):
            qs = qs.filter(anno=anno) if anno.isdigit() else qs
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["organi"] = Organo.objects.all()
        ctx["organo_scelto"] = self.request.GET.get("organo", "")
        return ctx


class _RiunioneFormMixin:
    form_class = RiunioneForm
    template_name = "organi/riunione_modulo.html"

    def form_valid(self, form):
        try:
            self.object = servizi.salva_riunione(form, form.titoli_punti(), self.request.user)
        except OperazioneNonValida as e:
            form.add_error(None, e)
            return self.form_invalid(form)
        messages.success(self.request, "Riunione salvata.")
        return redirect(self.object)


class RiunioneNuovaView(PermessoMixin, _RiunioneFormMixin, FormView):
    permission_required = "organi.add_riunione"

    def get_initial(self):
        return {"organo": self.request.GET.get("organo")}

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "instance": Riunione()}


class RiunioneModificaView(PermessoMixin, _RiunioneFormMixin, UpdateView):
    permission_required = "organi.change_riunione"
    model = Riunione

    def get_object(self, queryset=None):
        r = super().get_object(queryset)
        if not r.modificabile:
            raise Http404("Riunione non modificabile.")
        return r


class RiunioneView(PermessoMixin, DetailView):
    permission_required = "organi.view_riunione"
    model = Riunione
    template_name = "organi/riunione.html"
    context_object_name = "riunione"

    def get_queryset(self):
        return Riunione.objects.select_related("organo", "protocollo_convocazione")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        r = self.object
        ctx["punti"] = r.punti.all()
        ctx["verbale"] = getattr(r, "verbale", None)
        if r.presenze.exists():
            ctx["quorum_prima"] = servizi.quorum(r, "prima")
            ctx["quorum_seconda"] = servizi.quorum(r, "seconda") if r.seconda_convocazione else None
        ctx["aventi_diritto"] = (
            sum(1 for _ in servizi.aventi_diritto(r)) if r.stato == "bozza" else None
        )
        return ctx


class _AzioneRiunioneView(PermessoMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        r = get_object_or_404(Riunione, pk=pk)
        try:
            risposta = self.esegui(request, r)
        except OperazioneNonValida as e:
            _errore(request, e)
            risposta = None
        return risposta or redirect(r)


class ConvocaView(_AzioneRiunioneView):
    permission_required = "organi.convoca_riunione"

    def esegui(self, request, r):
        protocolla = request.POST.get("protocolla") == "on"
        if protocolla and not request.user.has_perm("protocollo.add_protocollo"):
            raise OperazioneNonValida("Non si ha il permesso di protocollare.")
        r = servizi.convoca(r, request.user, protocolla=protocolla)
        testo = f"Riunione convocata: {r.titolo}."
        if r.protocollo_convocazione:
            testo += f" Protocollo n. {r.protocollo_convocazione.segnatura}."
        messages.success(request, testo)


class AnnullaRiunioneView(_AzioneRiunioneView):
    permission_required = "organi.convoca_riunione"

    def esegui(self, request, r):
        servizi.annulla_riunione(r, request.user, request.POST.get("motivo", ""))
        messages.success(request, "Riunione annullata.")


class ConvocazionePdfView(PermessoMixin, View):
    permission_required = "organi.view_riunione"

    def get(self, request, pk):
        r = get_object_or_404(Riunione.objects.select_related("organo"), pk=pk)
        risposta = HttpResponse(servizi.pdf_convocazione(r), content_type="application/pdf")
        risposta["Content-Disposition"] = (
            f'inline; filename="convocazione_{r.organo.sigla}_{r.anno}.pdf"'
        )
        return risposta


# --- presenze ----------------------------------------------------------------------------------


class PresenzeView(PermessoMixin, TemplateView):
    permission_required = "organi.view_riunione"
    template_name = "organi/presenze.html"

    def dispatch(self, request, *args, **kwargs):
        self.riunione = get_object_or_404(
            Riunione.objects.select_related("organo"), pk=kwargs["pk"]
        )
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, pk):
        if not request.user.has_perm("organi.verbalizza"):
            return self.handle_no_permission()
        try:
            n = servizi.apri_presenze(self.riunione)
            messages.success(request, f"Elenco degli aventi diritto aggiornato ({n} aggiunti).")
        except OperazioneNonValida as e:
            _errore(request, e)
        return redirect("organi:presenze", pk=pk)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        r = self.riunione
        ctx["riunione"] = r
        ctx["presenze"] = r.presenze.select_related("delegato").annotate(
            n_deleghe=Count("deleghe_ricevute")
        )
        ctx["stati"] = Presenza.Stato.choices
        ctx["intervenuti"] = [p for p in ctx["presenze"] if p.intervenuto and p.vota]
        ctx["modificabile"] = r.stato == Riunione.Stato.CONVOCATA and not (
            hasattr(r, "verbale") and r.verbale.chiuso
        )
        ctx["quorum_prima"] = servizi.quorum(r, "prima")
        ctx["quorum_seconda"] = servizi.quorum(r, "seconda") if r.seconda_convocazione else None
        return ctx


class PresenzaView(PermessoMixin, View):
    """Aggiorna una presenza e restituisce la pagina delle presenze (o la parte, con HTMX)."""

    permission_required = "organi.verbalizza"
    http_method_names = ["post"]

    def post(self, request, pk):
        p = get_object_or_404(Presenza.objects.select_related("riunione"), pk=pk)
        delegato = None
        if request.POST.get("delegato"):
            delegato = Presenza.objects.filter(
                pk=request.POST["delegato"], riunione=p.riunione
            ).first()
        stato = request.POST.get("stato", "")
        # scegliere un delegato (diverso da quello attuale) vale come «rappresentato per delega»
        if (
            delegato
            and delegato.pk != p.delegato_id
            and stato in (Presenza.Stato.ASSENTE, Presenza.Stato.GIUSTIFICATO)
        ):
            stato = Presenza.Stato.DELEGA
        if stato != Presenza.Stato.DELEGA:
            delegato = None
        try:
            servizi.imposta_presenza(p, stato, delegato)
        except OperazioneNonValida as e:
            _errore(request, e)
        if request.htmx:
            vista = PresenzeView()
            vista.setup(request, pk=p.riunione_id)
            vista.riunione = p.riunione
            return render(request, "organi/presenze.html#elenco", vista.get_context_data())
        return redirect("organi:presenze", pk=p.riunione_id)


# --- verbale e delibere --------------------------------------------------------------------------


class VerbaleView(PermessoMixin, TemplateView):
    permission_required = "organi.view_verbale"
    template_name = "organi/verbale.html"

    def dispatch(self, request, *args, **kwargs):
        self.riunione = get_object_or_404(
            Riunione.objects.select_related("organo"), pk=kwargs["pk"]
        )
        return super().dispatch(request, *args, **kwargs)

    def _verbale(self, crea=False):
        v = Verbale.objects.filter(riunione=self.riunione).first()
        if v is None and crea:
            v = servizi.apri_verbale(self.riunione, self.request.user)
        return v

    def get(self, request, *args, **kwargs):
        v = self._verbale(crea=request.user.has_perm("organi.verbalizza"))
        if v is None:
            raise Http404("Verbale non ancora redatto.")
        return self.render_to_response(self.get_context_data(verbale=v))

    def post(self, request, pk):
        if not request.user.has_perm("organi.verbalizza"):
            return self.handle_no_permission()
        v = self._verbale(crea=True)
        form = VerbaleForm(request.POST, instance=v)
        discussioni = {
            p.pk: request.POST.get(f"punto-{p.pk}", "") for p in self.riunione.punti.all()
        }
        if form.is_valid():
            try:
                servizi.salva_verbale(form, discussioni, request.user)
                messages.success(request, "Verbale salvato.")
                return redirect("organi:verbale", pk=pk)
            except OperazioneNonValida as e:
                form.add_error(None, e)
        return self.render_to_response(self.get_context_data(verbale=v, form=form))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        v = ctx["verbale"]
        ctx["riunione"] = self.riunione
        ctx.setdefault("form", VerbaleForm(instance=v))
        ctx["punti"] = self.riunione.punti.prefetch_related("delibere")
        ctx["delibere_senza_punto"] = v.delibere.filter(punto__isnull=True)
        ctx["form_delibera"] = DeliberaForm(riunione=self.riunione, prefix="nuova")
        ctx["quorum"] = servizi.quorum(self.riunione, v.convocazione)
        ctx["ha_presenze"] = self.riunione.presenze.exists()
        return ctx


class DeliberaView(PermessoMixin, View):
    permission_required = "organi.verbalizza"
    http_method_names = ["post"]

    def post(self, request, pk, delibera=None):
        riunione = get_object_or_404(Riunione, pk=pk)
        v = get_object_or_404(Verbale, riunione=riunione)
        istanza = get_object_or_404(Delibera, pk=delibera, verbale=v) if delibera else None
        try:
            if request.POST.get("elimina") and istanza:
                servizi.elimina_delibera(istanza)
                messages.success(request, "Delibera eliminata.")
            else:
                prefisso = f"d{istanza.pk}" if istanza else "nuova"
                form = DeliberaForm(
                    request.POST, instance=istanza, riunione=riunione, prefix=prefisso
                )
                if form.is_valid():
                    servizi.salva_delibera(form, v)
                    messages.success(request, "Delibera salvata.")
                else:
                    errori = [
                        f"{form.fields[c].label if c in form.fields else ''}: {m}"
                        for c, ms in form.errors.items()
                        for m in ms
                    ]
                    messages.error(request, "Delibera non salvata. " + " ".join(errori))
        except OperazioneNonValida as e:
            _errore(request, e)
        return redirect(reverse("organi:verbale", args=[pk]) + "#delibere")


class ChiudiVerbaleView(PermessoMixin, View):
    permission_required = "organi.verbalizza"
    http_method_names = ["post"]

    def post(self, request, pk):
        v = get_object_or_404(Verbale, riunione_id=pk)
        protocolla = request.POST.get("protocolla") == "on"
        try:
            if protocolla and not request.user.has_perm("protocollo.add_protocollo"):
                raise OperazioneNonValida("Non si ha il permesso di protocollare.")
            v = servizi.chiudi_verbale(v, request.user, protocolla=protocolla)
            messages.success(request, f"Verbale n. {v.numero} chiuso.")
        except OperazioneNonValida as e:
            _errore(request, e)
        return redirect("organi:verbale", pk=pk)


class VerbalePdfView(PermessoMixin, View):
    """Verbale chiuso: il PDF conservato. Verbale aperto: bozza generata al momento."""

    permission_required = "organi.view_verbale"

    def get(self, request, pk):
        v = get_object_or_404(Verbale.objects.select_related("riunione__organo"), riunione_id=pk)
        if v.chiuso:
            try:
                f = v.file.open("rb")
            except FileNotFoundError:
                raise Http404 from None
            return FileResponse(
                f, filename=f"verbale_{v.numero}.pdf", content_type="application/pdf"
            )
        risposta = HttpResponse(servizi.pdf_verbale(v), content_type="application/pdf")
        risposta["Content-Disposition"] = 'inline; filename="verbale_bozza.pdf"'
        return risposta


class DelibereView(PermessoMixin, ListView):
    permission_required = "organi.view_delibera"
    template_name = "organi/delibere.html"
    context_object_name = "delibere"
    paginate_by = 50

    def get_queryset(self):
        qs = servizi.delibere_registro()
        if organo := self.request.GET.get("organo"):
            qs = qs.filter(verbale__riunione__organo_id=organo)
        if q := self.request.GET.get("q", "").strip():
            qs = qs.filter(Q(oggetto__icontains=q) | Q(testo__icontains=q))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["organi"] = Organo.objects.all()
        ctx["organo_scelto"] = self.request.GET.get("organo", "")
        ctx["q"] = self.request.GET.get("q", "")
        return ctx
