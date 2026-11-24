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

import contextlib
from datetime import date

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import FormView, TemplateView

from apps.api.models import ClienteApi, DocumentoRicevuto
from apps.core.models import Organizzazione
from apps.core.pdf import risposta_pdf
from apps.core.views import PermessoMixin

from . import ciclo, temporanei
from .forms import (
    AvvisiTessereForm,
    BloccoTessereForm,
    ConsegnaTessereForm,
    ImportaConsegnaForm,
    ImportaModuloForm,
    OrdineTessereForm,
    PagamentoTessereForm,
    RichiestaModificaForm,
    RichiestaTessereForm,
)
from .models import ConsegnaTessere, LottoTessere, OrdineTessere, RichiestaTessere, Sezione
from .servizi import FORNITORE_REGISTRO, OperazioneNonValida

PERMESSO = "soci.gestisci_ciclo_tessere"


def anno_campagna():
    """La campagna delle tessere riguarda sempre l'anno successivo a quello in corso."""
    return date.today().year + 1


def _anno(request, kwargs):
    try:
        scelto = kwargs.get("anno") or request.GET.get("anno") or request.POST.get("anno")
        return int(scelto or anno_campagna())
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
            in_arrivo=DocumentoRicevuto.objects.filter(
                stato=DocumentoRicevuto.Stato.DA_ESAMINARE
            ).select_related("cliente"),
            collegamenti=ClienteApi.objects.filter(
                stato=ClienteApi.Stato.ATTIVA,
                ruolo__in=[ClienteApi.Ruolo.FEDERAZIONE, ClienteApi.Ruolo.SEZIONE],
            ).prefetch_related("cursori"),
            sezioni_attive=Sezione.objects.filter(attiva=True),
            canale=ciclo.canale_richiesta(),
            superiore=ciclo.quadratura_superiore(anno),
            ricevute_da_registrare=DocumentoRicevuto.objects.filter(
                tipo=DocumentoRicevuto.Tipo.RICEVUTA,
                stato=DocumentoRicevuto.Stato.APPLICATO,
                movimento__isnull=True,
                dati__anno=anno,
            ).select_related("cliente"),
            in_preparazione=[
                (r, ciclo.fabbisogno(anno, r.sezione), ciclo.email_in_corso(r))
                for r in RichiestaTessere.objects.filter(
                    anno=anno, inviata_il__isnull=True, uuid_origine__isnull=True
                ).select_related("sezione")
            ],
        )
        ctx["richieste"] = list(ctx["richieste"].filter(inviata_il__isnull=False))
        conferme = ciclo.conferme_inviate(ctx["richieste"])
        for r in ctx["richieste"]:
            r.correggibile = ciclo.motivo_non_modificabile(r) is None
            r.confermata = r.pk in conferme
        federazione = ciclo.e_federazione()
        if federazione:  # le richieste dal collegamento si registrano nella fase 2
            ctx["richieste_arrivo"] = [d for d in ctx["in_arrivo"] if d.tipo == "richiesta"]
            ctx["in_arrivo"] = [d for d in ctx["in_arrivo"] if d.tipo != "richiesta"]
        ctx.update(
            federazione=federazione,
            superiore_nome=ciclo.nome_superiore(),
            fasi_sezioni=ciclo.fasi_verso_sezioni(anno) if federazione else [],
            fasi_superiore=ciclo.fasi_verso_superiore(anno),
            stato_inviti=ciclo.stato_inviti(anno) if federazione else [],
            invito=ciclo.invito(anno),
            invito_suggerito=ciclo.invito_suggerito(anno),
            lotti_ricevuti=(
                []
                if federazione
                else LottoTessere.objects.filter(anno=anno).exclude(fornitore=FORNITORE_REGISTRO)
            ),
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
        # nel gestionale di una sezione la richiesta si prepara e poi si invia alla federazione
        # (collegamento o email); nella federazione si registra quella arrivata da una sezione
        sezione_locale = ciclo.canale_richiesta() != "registro"
        if sezione_locale and (bozza := ciclo.in_preparazione(self.anno, d["sezione"])):
            ciclo.modifica_in_preparazione(self.request.user, bozza, quantita=d["quantita"],
                                           note=d["note"])  # fmt: skip
            return (
                f"Richiesta in preparazione aggiornata: {bozza.quantita} tessere. Inviala "
                "alla federazione dal riquadro «Richieste in preparazione»."
            )
        r = ciclo.registra_richiesta(
            self.request.user, anno=self.anno, sezione=d["sezione"], quantita=d["quantita"],
            data=d["data"], note=d["note"], in_preparazione=sezione_locale,
        )  # fmt: skip
        if sezione_locale:
            return (f"Richiesta preparata: {r.quantita} tessere. Inviala alla federazione dal "
                    "riquadro «Richieste in preparazione».")  # fmt: skip
        return f"Richiesta registrata: {r}."


class RichiestaModificaView(_ModuloCiclo):
    """Correzione di una richiesta registrata a mano (quantità, data, note)."""

    form_class = RichiestaModificaForm

    def dispatch(self, request, *args, **kwargs):
        self.richiesta = get_object_or_404(RichiestaTessere.objects.select_related("sezione"),
                                           pk=kwargs["pk"])  # fmt: skip
        kwargs["anno"] = self.richiesta.anno
        if motivo := ciclo.motivo_non_modificabile(self.richiesta):
            messages.error(request, motivo)
            return _alla_campagna(self.richiesta.anno)
        return super().dispatch(request, *args, **kwargs)

    @property
    def titolo(self):
        return f"Correggi la richiesta di tessere: {self.richiesta.sezione}"

    @property
    def aiuto(self):
        testo = ("La correzione cambia il fabbisogno dell'anno e la quadratura. Per un doppione "
                 "(es. la stessa richiesta arrivata anche via API) annullate la richiesta dalla "
                 "campagna.")  # fmt: skip
        if OrdineTessere.objects.filter(anno=self.richiesta.anno).exists():
            testo += (" Gli ordini già fatti alla sede nazionale non cambiano: una quantità in più "
                      "finisce nel prossimo ordine.")  # fmt: skip
        return testo

    def get_initial(self):
        r = self.richiesta
        return {"quantita": r.quantita, "data": r.data, "note": r.note}

    def esegui(self, d):
        r = ciclo.modifica_richiesta(self.request.user, self.richiesta, quantita=d["quantita"],
                                     data=d["data"], note=d["note"])  # fmt: skip
        return f"Richiesta corretta: {r}."


class RichiestaAnnullaView(PermessoMixin, View):
    permission_required = PERMESSO

    def post(self, request, pk):
        richiesta = get_object_or_404(RichiestaTessere.objects.select_related("sezione"), pk=pk)
        try:
            descrizione = ciclo.annulla_richiesta(
                request.user, richiesta, motivo=request.POST.get("motivo", "")
            )
        except OperazioneNonValida as e:
            messages.error(request, " ".join(e.messages))
        else:
            messages.success(request, f"Richiesta annullata: {descrizione}.")
        return _alla_campagna(richiesta.anno)


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


class InvitoView(PermessoMixin, View):
    """Prima fase verso l'ente sovraordinato: l'invito ricevuto, collegato al protocollo."""

    permission_required = PERMESSO

    def post(self, request, anno):
        from apps.protocollo.models import Protocollo

        segnatura = request.POST.get("segnatura", "").strip()
        protocollo = None
        if segnatura:
            try:
                a, n = segnatura.split("-")
                protocollo = Protocollo.objects.get(anno=int(a), numero=int(n), annullato=False)
            except (ValueError, Protocollo.DoesNotExist):
                messages.error(request, f"Protocollo «{segnatura}» non trovato (es. 2026-00003).")
                return _alla_campagna(anno)
        try:
            ricevuto = date.fromisoformat(request.POST.get("ricevuto_il", ""))
        except ValueError:
            ricevuto = protocollo.registrato_il.date() if protocollo else date.today()
        ciclo.registra_invito(request.user, anno=anno, ricevuto_il=ricevuto, protocollo=protocollo,
                              note=request.POST.get("note", "")[:255])  # fmt: skip
        messages.success(request, "Invito ricevuto registrato.")
        return _alla_campagna(anno)


class ConfermaRichiestaView(PermessoMixin, View):
    """Lato federazione: prepara in bozza la conferma di ricezione della richiesta alla sezione."""

    permission_required = PERMESSO

    def post(self, request, pk):
        richiesta = get_object_or_404(RichiestaTessere.objects.select_related("sezione"), pk=pk)
        if not request.user.has_perm("comunicazioni.add_invio"):
            raise PermissionDenied
        try:
            invio = ciclo.prepara_conferma(
                request.user, richiesta,
                protocolla=request.user.has_perm("protocollo.add_protocollo"),
            )  # fmt: skip
        except OperazioneNonValida as e:
            messages.error(request, " ".join(e.messages))
            return _alla_campagna(richiesta.anno)
        messages.success(request, f"Conferma alla {richiesta.sezione.denominazione} in bozza: "
                         "controllala e confermala per spedirla.")  # fmt: skip
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
        from django.http import FileResponse

        r = get_object_or_404(RichiestaTessere.objects.select_related("sezione"), pk=pk)
        nome = f"richiesta-tessere-{r.anno}-{r.sezione.codice}.pdf"
        if originale := ciclo.pdf_originale_richiesta(r):
            # arrivata via API: il documento della sezione, con la sua firma e la sua intestazione
            risposta = FileResponse(originale.open("rb"), content_type="application/pdf",
                                    filename=nome)  # fmt: skip
            risposta["Content-Security-Policy"] = "default-src 'none'; sandbox"
            return risposta
        risposta = HttpResponse(ciclo.pdf_richiesta(r), content_type="application/pdf")
        risposta["Content-Disposition"] = f'inline; filename="{nome}"'
        return risposta


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


# --- documenti in arrivo dai collegamenti (ADR-030, F4) ------------------------------------


class ArrivoConfermaView(PermessoMixin, View):
    permission_required = PERMESSO

    def post(self, request, pk):
        from apps.api import arrivi

        documento = get_object_or_404(DocumentoRicevuto, pk=pk)
        sezione = Sezione.objects.filter(pk=request.POST.get("sezione") or 0).first()
        try:
            protocolla = request.POST.get("protocolla") == "1"
            arrivi.conferma(documento, request.user, protocolla=protocolla, sezione=sezione)
        except arrivi.OperazioneNonValida as e:
            messages.error(request, f"{documento}: {e}")
        else:
            testo = f"{documento} confermato"
            if documento.protocollo_id:
                documento.refresh_from_db()
                testo += f", protocollo {documento.protocollo.segnatura}"
            messages.success(request, testo + ".")
        return _alla_campagna(_anno(request, {}))


class ArrivoScartaView(PermessoMixin, View):
    permission_required = PERMESSO

    def post(self, request, pk):
        from apps.api import arrivi

        documento = get_object_or_404(DocumentoRicevuto, pk=pk)
        try:
            arrivi.scarta(documento, request.user, request.POST.get("motivo", ""))
        except arrivi.OperazioneNonValida as e:
            messages.error(request, f"{documento}: {e}")
        else:
            messages.success(request, f"{documento} scartato.")
        return _alla_campagna(_anno(request, {}))


class ArrivoPdfView(PermessoMixin, View):
    permission_required = PERMESSO

    def get(self, request, pk):
        from django.http import FileResponse, Http404

        documento = get_object_or_404(DocumentoRicevuto, pk=pk)
        if not documento.pdf:
            raise Http404("Documento senza PDF.")
        nome = f"{documento.tipo}-{documento.uuid_origine}.pdf"
        risposta = FileResponse(documento.pdf.open("rb"), content_type="application/pdf",
                                filename=nome)  # fmt: skip
        risposta["Content-Security-Policy"] = "default-src 'none'; sandbox"
        return risposta


class SincronizzaView(PermessoMixin, View):
    """Legge subito i flussi della federazione o delle sezioni collegate."""

    permission_required = PERMESSO

    def post(self, request):
        from apps.collegamenti import sincronizza

        esiti = sincronizza.sincronizza_tutti()
        if not esiti:
            messages.info(request, "Nessun collegamento con la federazione o con le sezioni.")
        for nome, ricevuti in esiti.items():
            cursore = ClienteApi.objects.get(nome=nome).cursori.filter(flusso="tessere").first()
            if cursore and cursore.ultimo_errore:
                messages.warning(request, f"{nome}: {cursore.ultimo_errore}")
            else:
                messages.success(request, f"{nome}: {ricevuti} documenti ricevuti o aggiornati.")
        return _alla_campagna(_anno(request, {}))


# --- modulo Excel della richiesta, compilato dalle sezioni senza gestionale ------------------


class RichiestaDaMessaggioView(PermessoMixin, View):
    """Posta da protocollare: protocolla il messaggio e registra la richiesta del modulo."""

    permission_required = ("protocollo.add_protocollo", "protocollo.gestisci_posta", PERMESSO)

    def post(self, request, pk, indice):
        from django.db import transaction

        from apps.protocollo import servizi as protocollo
        from apps.protocollo.models import MessaggioRicevuto

        from . import modulo_tessere

        messaggio = get_object_or_404(MessaggioRicevuto, pk=pk)
        try:
            contenuto = modulo_tessere.contenuto_allegato(messaggio, indice)
            dati = modulo_tessere.leggi(contenuto)
            with transaction.atomic():
                oggetto = (
                    f"Richiesta di tessere {dati['anno']} della {dati['sezione'].denominazione}"
                )
                p = protocollo.protocolla_messaggio(messaggio, request.user, oggetto=oggetto)
                richiesta = ciclo.richiesta_da_modulo(request.user, contenuto, protocollo=p)
        except (IndexError, OSError):
            messages.error(request, "Allegato non trovato.")
            return redirect(messaggio)
        except (modulo_tessere.ModuloNonValido, OperazioneNonValida,
                protocollo.OperazioneNonValida) as e:  # fmt: skip
            messages.error(request, " ".join(getattr(e, "messages", [str(e)])))
            return redirect(messaggio)
        messages.success(request, f"Protocollo {p.segnatura}: richiesta registrata ({richiesta}).")
        return _alla_campagna(richiesta.anno)


class ImportaModuloView(PermessoMixin, View):
    """Caricamento a mano del modulo compilato (es. arrivato su carta o per altra via)."""

    permission_required = PERMESSO
    template_name = "soci/importa_modulo.html"

    def get(self, request):
        return render(request, self.template_name, {"form": ImportaModuloForm()})

    def post(self, request):
        from . import modulo_tessere

        nome = request.POST.get("temporaneo", "")
        if nome and request.POST.get("conferma"):
            contenuto = temporanei.leggi_temporaneo(nome)
            if contenuto is None:
                messages.error(request, "Il file non è più disponibile: caricatelo di nuovo.")
                return redirect("soci:importa_modulo")
            try:
                richiesta = ciclo.richiesta_da_modulo(request.user, contenuto)
            except OperazioneNonValida as e:
                messages.error(request, " ".join(e.messages))
                return redirect("soci:importa_modulo")
            temporanei.elimina_temporaneo(nome)
            messages.success(request, f"Richiesta registrata: {richiesta}.")
            return _alla_campagna(richiesta.anno)
        form = ImportaModuloForm(request.POST, request.FILES)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})
        contenuto = form.cleaned_data["file"].read()
        try:
            dati = modulo_tessere.leggi(contenuto)
        except modulo_tessere.ModuloNonValido as e:
            form.add_error("file", str(e))
            return render(request, self.template_name, {"form": form})
        return render(request, self.template_name, {
            "form": form, "dati": dati, "temporaneo": temporanei.salva_temporaneo(contenuto),
        })  # fmt: skip


class ModuloRichiestaView(PermessoMixin, View):
    """Scarica il modulo Excel della richiesta di tessere di una sezione (dall'elenco dei soci,
    Stampa ed esporta), per la campagna in preparazione o l'anno indicato."""

    permission_required = PERMESSO

    def get(self, request):
        from . import modulo_tessere, sezioni

        anno = _anno(request, {})
        scelta = request.GET.get("sezione", "")
        if scelta.isdigit():
            sezione = get_object_or_404(Sezione, pk=int(scelta))
        elif not sezioni.multisezione():
            sezione = Sezione.predefinita()
        else:
            messages.warning(request, "Scegliete prima una sezione nel filtro dell'elenco.")
            return redirect("soci:elenco")
        sezioni.controlla(request.user, sezione.pk)
        voce = ciclo.listino(anno)
        contenuto = modulo_tessere.genera(
            anno, sezione, quota=voce.prezzo_sezioni if voce else None,
            scadenza=voce.scadenza_richieste if voce else None,
            precedente=ciclo.tessere_anno_precedente(anno, sezione),
        )  # fmt: skip
        tipo = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        risposta = HttpResponse(contenuto, content_type=tipo)
        risposta["Content-Disposition"] = (
            f'attachment; filename="richiesta-tessere-{anno}-{sezione.codice}.xlsx"'
        )
        risposta["Content-Security-Policy"] = "default-src 'none'; sandbox"
        return risposta


class RichiestaPreparazioneView(PermessoMixin, View):
    """Richiesta in preparazione: salva quantità e note, ricalcola dal fabbisogno, invia."""

    permission_required = PERMESSO

    def post(self, request, pk):
        richiesta = get_object_or_404(
            RichiestaTessere.objects.select_related("sezione"), pk=pk, inviata_il__isnull=True,
            uuid_origine__isnull=True,
        )  # fmt: skip
        azione = request.POST.get("azione")
        try:
            if azione == "ricalcola":
                bozza, calcolo = ciclo.aggiorna_in_preparazione(
                    request.user, richiesta.anno, richiesta.sezione, togli=True
                )
                testo = (f"Richiesta in preparazione: {bozza.quantita} tessere." if bozza
                         else "Non servono altre tessere: richiesta tolta.")  # fmt: skip
                messages.success(request, testo)
            elif azione in ("salva", "invia"):
                try:
                    quantita = int(request.POST.get("quantita", ""))
                except ValueError:
                    raise OperazioneNonValida("Quantità non valida.") from None
                ciclo.modifica_in_preparazione(request.user, richiesta, quantita=quantita,
                                               note=request.POST.get("note", "")[:255])  # fmt: skip
                if azione == "invia":
                    canale, invio = ciclo.invia_richiesta(request.user, richiesta)
                    if invio is not None:
                        messages.success(request, "Email della richiesta preparata in bozza "
                                         "con il modulo allegato: controllala e confermala. La "
                                         "richiesta risulta inviata quando l'email "
                                         "parte.")  # fmt: skip
                        return redirect(invio)
                    messages.success(request, {
                        "api": "Richiesta inviata alla federazione tramite il collegamento.",
                        "registro": "Richiesta registrata nel fabbisogno dell'anno.",
                    }[canale])  # fmt: skip
                else:
                    messages.success(request, "Richiesta in preparazione aggiornata.")
        except OperazioneNonValida as e:
            messages.error(request, " ".join(e.messages))
        return _alla_campagna(richiesta.anno)


class OrdineEmailView(PermessoMixin, View):
    """Ordine alla sede nazionale in bozza email con il PDF (non parte da solo)."""

    permission_required = PERMESSO

    def post(self, request, pk):
        ordine = get_object_or_404(OrdineTessere, pk=pk)
        try:
            invio = ciclo.prepara_ordine_email(request.user, ordine)
        except OperazioneNonValida as e:
            messages.error(request, " ".join(e.messages))
            return _alla_campagna(ordine.anno)
        messages.success(request, "Ordine preparato in bozza email con il PDF allegato: "
                         "controllalo e confermalo per spedirlo.")  # fmt: skip
        return redirect(invio)


class PagamentoTessereView(_ModuloCiclo):
    """Uscita per le tessere al livello superiore: da un ordine, da una ricevuta arrivata o
    libera (acconto o saldo)."""

    permission_required = (PERMESSO, "tesoreria.add_movimento")
    form_class = PagamentoTessereForm
    titolo = "Pagamento delle tessere"

    def dispatch(self, request, *args, **kwargs):
        self.ordine = self.documento = None
        if pk := request.GET.get("ordine") or request.POST.get("ordine"):
            self.ordine = get_object_or_404(OrdineTessere, pk=pk)
        if pk := request.GET.get("ricevuta") or request.POST.get("ricevuta"):
            self.documento = get_object_or_404(
                DocumentoRicevuto, pk=pk, tipo=DocumentoRicevuto.Tipo.RICEVUTA
            )
        return super().dispatch(request, *args, **kwargs)

    @property
    def aiuto(self):
        q = ciclo.quadratura_superiore(self.anno)
        testo = (f"Uscita in prima nota sulla voce «Acquisto delle tessere» verso "
                 f"{q['destinatario']}: dovuto € {q['dovuto']:.2f} ({q['quantita']} "
                 f"{q['descrizione']}), pagato € {q['pagato']:.2f}, da pagare "
                 f"€ {q['da_pagare']:.2f}. Si può pagare in più volte: ogni versamento è "
                 "un'uscita.")  # fmt: skip
        if self.ordine:
            testo += f" Ordine n. {self.ordine.anno}/{self.ordine.numero}."
        if self.documento:
            testo += " La ricevuta arrivata diventa il giustificativo."
        return testo

    def get_initial(self):
        iniziali = super().get_initial()
        if self.documento:
            from decimal import Decimal, InvalidOperation

            with contextlib.suppress(InvalidOperation, TypeError):
                iniziali["importo"] = Decimal(self.documento.dati.get("importo"))
            iniziali["riferimento"] = f"Ricevuta n. {self.documento.dati.get('ricevuta', '')}"
            if d := self.documento.dati.get("data"):
                iniziali["data"] = d
        return iniziali

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["nascosti"] = {"ordine": getattr(self.ordine, "pk", ""),
                           "ricevuta": getattr(self.documento, "pk", "")}  # fmt: skip
        return ctx

    def esegui(self, d):
        m = ciclo.registra_pagamento(
            self.request.user, anno=self.anno, data=d["data"], importo=d["importo"],
            conto=d["conto"], riferimento=d["riferimento"], ordine=self.ordine,
            documento=self.documento, giustificativo=d.get("giustificativo"),
        )  # fmt: skip
        return f"Pagamento registrato in prima nota: n. {m.numero}, € {m.importo:.2f}."
