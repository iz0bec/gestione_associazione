# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Soci → Campagna delle tessere: richieste delle sezioni, ordine al nazionale,
# *              magazzino, consegne (PDF e file), quadratura, avvisi alle sezioni; lato sezione
# *              l'importazione del file della consegna con anteprima.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from datetime import date

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import FormView, TemplateView

from apps.core.models import Organizzazione
from apps.core.pdf import risposta_pdf
from apps.core.views import PermessoMixin

from . import ciclo, temporanei
from .forms import (
    AvvisiTessereForm,
    BloccoTessereForm,
    ConsegnaTessereForm,
    ImportaConsegnaForm,
    OrdineTessereForm,
    RichiestaTessereForm,
)
from .models import ConsegnaTessere, OrdineTessere, RichiestaTessere, Sezione
from .servizi import OperazioneNonValida

PERMESSO = "soci.gestisci_ciclo_tessere"


def anno_campagna():
    """La campagna delle tessere riguarda sempre l'anno successivo a quello in corso."""
    return date.today().year + 1


def _anno(request, kwargs):
    try:
        return int(kwargs.get("anno") or request.GET.get("anno") or anno_campagna())
    except ValueError:
        return anno_campagna()


def _alla_campagna(anno):
    return redirect("soci:campagna", anno=anno)


class CampagnaView(PermessoMixin, TemplateView):
    permission_required = PERMESSO
    template_name = "soci/campagna.html"

    def get_context_data(self, **kwargs):
        anno = _anno(self.request, kwargs)
        ctx = super().get_context_data(**kwargs)
        magazzino = ciclo.riepilogo_magazzino(anno)
        ctx.update(
            anno=anno,
            anni=range(anno_campagna() + 1, anno_campagna() - 5, -1),
            anno_campagna=anno_campagna(),
            listino=ciclo.listino(anno),
            quadratura=ciclo.quadratura(anno),
            magazzino=magazzino,
            blocchi=[(b, ciclo.intervalli_liberi(b)) for b in magazzino["blocchi"]],
            richieste=RichiestaTessere.objects.filter(anno=anno).select_related("sezione"),
            consegne=ConsegnaTessere.objects.filter(anno=anno).select_related("sezione", "blocco"),
            ordini=OrdineTessere.objects.filter(anno=anno),
            da_ordinare=ciclo.da_ordinare(anno),
            senza_richiesta=ciclo.sezioni_senza_richiesta(anno),
            senza_email=Sezione.objects.filter(attiva=True, email=""),
        )
        return ctx


class _ModuloCiclo(PermessoMixin, FormView):
    permission_required = PERMESSO
    template_name = "soci/ciclo_modulo.html"
    titolo = ""
    aiuto = ""

    def dispatch(self, request, *args, **kwargs):
        self.anno = _anno(request, kwargs)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        return super().get_context_data(anno=self.anno, titolo=self.titolo, aiuto=self.aiuto,
                                        **kwargs)  # fmt: skip

    def form_valid(self, form):
        try:
            esito = self.esegui(form.cleaned_data)
        except OperazioneNonValida as e:
            form.add_error(None, " ".join(e.messages))
            return self.form_invalid(form)
        messages.success(self.request, esito)
        return _alla_campagna(self.anno)


class RichiestaNuovaView(_ModuloCiclo):
    form_class = RichiestaTessereForm
    titolo = "Richiesta di tessere di una sezione"
    aiuto = ("Registra il fabbisogno comunicato da una sezione (anche le integrazioni durante la "
             "campagna). La richiesta arrivata per email o PEC va prima protocollata.")  # fmt: skip

    def esegui(self, d):
        r = ciclo.registra_richiesta(
            self.request.user, anno=self.anno, sezione=d["sezione"], quantita=d["quantita"],
            data=d["data"], note=d["note"],
        )  # fmt: skip
        return f"Richiesta registrata: {r}."


class BloccoNuovoView(_ModuloCiclo):
    form_class = BloccoTessereForm
    titolo = "Tessere arrivate dalla sede nazionale"
    aiuto = ("Il blocco entra nel magazzino: le tessere diventano utilizzabili solo quando si "
             "consegnano a una sezione.")  # fmt: skip

    def esegui(self, d):
        b = ciclo.carica_blocco(
            self.request.user, anno=self.anno, numero_da=d["numero_da"], numero_a=d["numero_a"],
            serie=d["serie"], cifre=d["cifre"] or 0, data_arrivo=d["data_arrivo"],
            fornitore=d["fornitore"], riferimento=d["riferimento"],
        )  # fmt: skip
        return f"Blocco caricato in magazzino: {b} ({b.quantita} tessere)."


class ConsegnaNuovaView(_ModuloCiclo):
    form_class = ConsegnaTessereForm
    titolo = "Consegna di tessere a una sezione"
    aiuto = ("Si consegna anche senza pagamento: la quadratura lo segnala. Dopo la consegna "
             "scaricate il documento e il file dei numeri e inviate l'avviso di "
             "attribuzione.")  # fmt: skip

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "anno": self.anno}

    def get_initial(self):
        iniziali = super().get_initial()
        for blocco, liberi in ((b, ciclo.intervalli_liberi(b)) for b in
                               ciclo.riepilogo_magazzino(self.anno)["blocchi"]):  # fmt: skip
            if liberi:
                iniziali.update(blocco=blocco, numero_da=liberi[0][0], numero_a=liberi[0][1])
                break
        if sezione := self.request.GET.get("sezione"):
            iniziali["sezione"] = sezione
        return iniziali

    def esegui(self, d):
        c = ciclo.consegna(
            self.request.user, blocco=d["blocco"], sezione=d["sezione"],
            numero_da=d["numero_da"], numero_a=d["numero_a"], data=d["data"],
            modalita=d["modalita"], note_distribuzione=d["note_distribuzione"],
            prezzo_unitario=d["prezzo_unitario"],
        )  # fmt: skip
        return f"{c}: {c.quantita} tessere, € {c.importo:.2f}."


class OrdineNuovoView(_ModuloCiclo):
    form_class = OrdineTessereForm
    template_name = "soci/ordine_nuovo.html"
    titolo = "Ordine alla sede nazionale"

    def get_context_data(self, **kwargs):
        return super().get_context_data(da_ordinare=ciclo.da_ordinare(self.anno), **kwargs)

    def esegui(self, d):
        o = ciclo.crea_ordine(self.request.user, anno=self.anno, data=d["data"], note=d["note"])
        return f"{o} registrato: scaricate il PDF, protocollatelo e speditelo."


class PresaInCaricoView(PermessoMixin, View):
    permission_required = PERMESSO

    def post(self, request, pk):
        documento = get_object_or_404(ConsegnaTessere, pk=pk)
        ciclo.prendi_in_carico(documento, request.user, date.today())
        messages.success(request, f"{documento}: presa in carico registrata.")
        return _alla_campagna(documento.anno)


def _contesto_pdf(**extra):
    return {"organizzazione": Organizzazione.corrente(), "oggi": date.today(), **extra}


class RispostaRichiestaView(PermessoMixin, View):
    """Lato sezione: prepara in bozza la richiesta di tessere da spedire alla federazione."""

    permission_required = PERMESSO

    def post(self, request, pk):
        richiesta = get_object_or_404(RichiestaTessere.objects.select_related("sezione"), pk=pk)
        try:
            invio = ciclo.prepara_risposta(
                request.user, richiesta,
                riferimento_avviso=request.POST.get("riferimento_avviso", "")[:200],
            )  # fmt: skip
        except OperazioneNonValida as e:
            messages.error(request, " ".join(e.messages))
            return _alla_campagna(richiesta.anno)
        messages.success(request, "Richiesta preparata in bozza: controllala, modificala se serve "
                         "e confermala per spedirla alla federazione.")  # fmt: skip
        return redirect(invio)


class ConsegnaPdfView(PermessoMixin, View):
    permission_required = PERMESSO

    def get(self, request, pk):
        c = get_object_or_404(ConsegnaTessere.objects.select_related("sezione", "blocco"), pk=pk)
        riga = next((r for r in ciclo.quadratura(c.anno) if r.sezione.pk == c.sezione_id), None)
        contesto = _contesto_pdf(consegna=c, riga=riga)
        return risposta_pdf("soci/pdf/consegna_tessere.html", contesto,
                            f"consegna-tessere-{c.anno}-{c.numero}.pdf")  # fmt: skip


class ConsegnaCsvView(PermessoMixin, View):
    permission_required = PERMESSO

    def get(self, request, pk):
        c = get_object_or_404(ConsegnaTessere, pk=pk)
        risposta = HttpResponse(ciclo.csv_consegna(c), content_type="text/csv; charset=utf-8")
        risposta["Content-Disposition"] = (
            f'attachment; filename="consegna-tessere-{c.anno}-{c.numero}.csv"'
        )
        risposta["Content-Security-Policy"] = "default-src 'none'; sandbox"
        return risposta


class OrdinePdfView(PermessoMixin, View):
    permission_required = PERMESSO

    def get(self, request, pk):
        o = get_object_or_404(OrdineTessere, pk=pk)
        listino = ciclo.listino(o.anno)
        totale = o.quantita * listino.costo_acquisto if listino else None
        return risposta_pdf("soci/pdf/ordine_tessere.html",
                            _contesto_pdf(ordine=o, listino=listino, totale=totale),
                            f"ordine-tessere-{o.anno}-{o.numero}.pdf")  # fmt: skip


class RichiestaPdfView(PermessoMixin, View):
    """Richiesta di tessere stampabile: la sezione la protocolla e la spedisce alla federazione."""

    permission_required = PERMESSO

    def get(self, request, pk):
        r = get_object_or_404(RichiestaTessere.objects.select_related("sezione"), pk=pk)
        return risposta_pdf("soci/pdf/richiesta_tessere.html",
                            _contesto_pdf(richiesta=r, listino=ciclo.listino(r.anno)),
                            f"richiesta-tessere-{r.anno}-{r.sezione.codice}.pdf")  # fmt: skip


class AvvisiView(PermessoMixin, FormView):
    """Avvisi del ciclo alle sezioni: prepara le bozze, che si confermano da Comunicazioni."""

    permission_required = PERMESSO
    template_name = "soci/avvisi_tessere.html"
    form_class = AvvisiTessereForm
    TITOLI = {
        "tesseramento": "Avviso di nuovo tesseramento",
        "sollecito": "Sollecito della richiesta di tessere",
        "attribuzione": "Avviso di attribuzione delle tessere",
    }

    def dispatch(self, request, *args, **kwargs):
        self.anno = _anno(request, kwargs)
        self.tipo = kwargs["tipo"]
        if self.tipo not in self.TITOLI:
            return _alla_campagna(self.anno)
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        puo = self.request.user.has_perm("comunicazioni.change_modello")
        return {**super().get_form_kwargs(), "tipo": self.tipo, "anno": self.anno,
                "puo_modificare_modello": puo}  # fmt: skip

    def get_initial(self):
        modello = ciclo.modello_avviso(self.tipo)
        testo = {"oggetto": modello.oggetto, "corpo": modello.corpo} if modello else {}
        if self.tipo == "sollecito":
            return {"sezioni": list(ciclo.sezioni_senza_richiesta(self.anno)), **testo}
        if self.tipo == "tesseramento":
            return {"sezioni": list(Sezione.objects.filter(attiva=True)), **testo}
        return {"consegne": list(ConsegnaTessere.objects.filter(anno=self.anno)), **testo}

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            anno=self.anno, tipo=self.tipo, titolo=self.TITOLI[self.tipo],
            contesto=ciclo.contesto_anno(self.anno), modello=ciclo.modello_avviso(self.tipo),
            **kwargs,
        )  # fmt: skip

    def form_valid(self, form):
        d = form.cleaned_data
        try:
            invii, saltate = ciclo.prepara_avvisi(
                self.request.user, tipo=self.tipo, anno=self.anno,
                sezioni=d.get("sezioni") or (), consegne=d.get("consegne") or (),
                riferimento_avviso=d.get("riferimento_avviso") or "",
                nuova_scadenza=d.get("nuova_scadenza"), servizio=d.get("servizio"),
                protocolla=d.get("protocolla"), oggetto=d.get("oggetto"), corpo=d.get("corpo"),
                salva_modello=d.get("salva_modello", False),
            )  # fmt: skip
        except OperazioneNonValida as e:
            form.add_error(None, " ".join(e.messages))
            return self.form_invalid(form)
        for sezione, motivo in saltate:
            messages.warning(self.request, f"{sezione}: non preparato ({motivo}).")
        if invii:
            messages.success(
                self.request,
                f"Preparati {len(invii)} messaggi in bozza: controllateli e confermateli qui.",
            )
            return redirect("comunicazioni:invii")
        return _alla_campagna(self.anno)


class ImportaConsegnaView(PermessoMixin, View):
    """Lato sezione: carica i numeri dal file della consegna della federazione (con anteprima)."""

    permission_required = PERMESSO
    template_name = "soci/importa_consegna.html"

    def get(self, request):
        return render(request, self.template_name, {"form": ImportaConsegnaForm()})

    def post(self, request):
        from .models import Sezione

        nome = request.POST.get("temporaneo", "")
        if nome and request.POST.get("conferma"):
            contenuto = temporanei.leggi_temporaneo(nome)
            sezione = Sezione.objects.filter(pk=request.POST.get("sezione") or 0).first()
            if contenuto is None:
                messages.error(request, "Il file non è più disponibile: caricatelo di nuovo.")
                return redirect("soci:importa_consegna")
            try:
                _, lotti = ciclo.importa_consegna(request.user, contenuto, sezione=sezione,
                                                  esegui=True)  # fmt: skip
            except OperazioneNonValida as e:
                messages.error(request, " ".join(e.messages))
                return redirect("soci:importa_consegna")
            temporanei.elimina_temporaneo(nome)
            messages.success(
                request, f"Tessere caricate: {sum(lotto.quantita for lotto in lotti)}."
            )
            return redirect(reverse("soci:tessere_fisiche"))
        form = ImportaConsegnaForm(request.POST, request.FILES)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})
        contenuto = form.cleaned_data["file"].read()
        try:
            righe, _ = ciclo.importa_consegna(request.user, contenuto,
                                              sezione=form.cleaned_data["sezione"])  # fmt: skip
        except OperazioneNonValida as e:
            form.add_error("file", " ".join(e.messages))
            return render(request, self.template_name, {"form": form})
        return render(request, self.template_name, {
            "form": form, "righe": righe, "temporaneo": temporanei.salva_temporaneo(contenuto),
            "sezione": form.cleaned_data["sezione"],
        })  # fmt: skip
