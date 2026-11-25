# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Viste del modulo Progetti (P1): idee e necessità, valutazione, progetti,
# *              finalità statutarie e criteri. Viste sottili: la logica è in servizi.py.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.contrib import messages
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.formats import localize
from django.views import View
from django.views.generic import ListView

from apps.core.views import PermessoMixin

from . import servizi
from .forms import (
    ESITI,
    AllegatoForm,
    AvvioForm,
    BandoForm,
    CandidaForm,
    CriterioForm,
    FinalitaForm,
    IdeaForm,
    MembroForm,
    PrioritaForm,
    ProgettoForm,
    RequisitoForm,
    ScadenzaForm,
    StatoForm,
)
from .models import (
    Allegato,
    Bando,
    CriterioValutazione,
    FinalitaStatutaria,
    Idea,
    Membro,
    Progetto,
    Requisito,
    Scadenza,
)
from .servizi import OperazioneNonValida

# --- idee ----------------------------------------------------------------------------------------


class IdeeView(PermessoMixin, ListView):
    permission_required = "progetti.view_idea"
    template_name = "progetti/idee.html"
    context_object_name = "idee"
    paginate_by = 30

    def get_queryset(self):
        g = self.request.GET
        qs = Idea.objects.select_related("fonte_soggetto", "proponente").prefetch_related(
            "finalita", "valutazioni"
        )
        stato = g.get("stato", "aperte")
        if stato == "aperte":
            qs = qs.filter(stato__in=[Idea.Stato.NUOVA, Idea.Stato.IN_VALUTAZIONE])
        elif stato in Idea.Stato.values:
            qs = qs.filter(stato=stato)
        for campo in ("fonte", "priorita"):
            if g.get(campo):
                qs = qs.filter(**{campo: g[campo]})
        if g.get("finalita"):
            qs = qs.filter(finalita=g["finalita"])
        if g.get("q"):
            qs = qs.filter(Q(titolo__icontains=g["q"]) | Q(descrizione__icontains=g["q"]))
        return qs.distinct()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        for idea in ctx["idee"]:
            idea.media = servizi.media_idea(idea)
        ctx.update(
            stati=Idea.Stato.choices,
            fonti=Idea.Fonte.choices,
            priorita=Idea.Priorita.choices,
            finalita=FinalitaStatutaria.objects.filter(attiva=True),
            filtri=self.request.GET,
        )
        return ctx


class IdeaNuovaView(PermessoMixin, View):
    """Nuova idea; con ?protocollo= o ?messaggio= nasce da una sollecitazione esterna."""

    permission_required = "progetti.add_idea"

    def _origine(self, request):
        from apps.protocollo.models import MessaggioRicevuto, Protocollo

        protocollo = messaggio = None
        if pk := request.GET.get("protocollo") or request.POST.get("protocollo"):
            protocollo = get_object_or_404(Protocollo.objects.visibili_a(request.user), pk=pk)
        if pk := request.GET.get("messaggio") or request.POST.get("messaggio"):
            if not request.user.has_perm("protocollo.view_messaggioricevuto"):
                raise Http404
            messaggio = get_object_or_404(MessaggioRicevuto, pk=pk)
        return protocollo, messaggio

    def get(self, request):
        protocollo, messaggio = self._origine(request)
        iniziali = {}
        if protocollo:
            iniziali = servizi.dati_da_protocollo(protocollo)
        elif messaggio:
            iniziali = servizi.dati_da_messaggio(messaggio)
        return render(
            request,
            "progetti/idea_modulo.html",
            {
                "form": IdeaForm(initial=iniziali),
                "protocollo": protocollo,
                "messaggio": messaggio,
            },
        )

    def post(self, request):
        protocollo, messaggio = self._origine(request)
        form = IdeaForm(request.POST)
        if form.is_valid():
            idea = servizi.crea_idea(form, request.user, protocollo=protocollo, messaggio=messaggio)
            messages.success(request, f"Idea {idea.codice} registrata.")
            return redirect(idea)
        return render(
            request,
            "progetti/idea_modulo.html",
            {"form": form, "protocollo": protocollo, "messaggio": messaggio},
        )


class IdeaModificaView(PermessoMixin, View):
    permission_required = "progetti.change_idea"

    def get(self, request, pk):
        idea = get_object_or_404(Idea, pk=pk)
        return render(
            request, "progetti/idea_modulo.html", {"form": IdeaForm(instance=idea), "idea": idea}
        )

    def post(self, request, pk):
        idea = get_object_or_404(Idea, pk=pk)
        form = IdeaForm(request.POST, instance=idea)
        if form.is_valid():
            try:
                servizi.modifica_idea(form, request.user)
            except OperazioneNonValida as e:
                messages.error(request, str(e))
            else:
                messages.success(request, "Idea aggiornata.")
            return redirect(idea)
        return render(request, "progetti/idea_modulo.html", {"form": form, "idea": idea})


class IdeaView(PermessoMixin, View):
    permission_required = "progetti.view_idea"

    def get(self, request, pk):
        idea = get_object_or_404(
            Idea.objects.select_related(
                "fonte_soggetto", "protocollo", "messaggio", "proponente", "delibera_priorita"
            ),
            pk=pk,
        )
        mia = idea.valutazioni.filter(utente=request.user).first()
        return render(
            request,
            "progetti/idea.html",
            {
                "idea": idea,
                "riepilogo": servizi.riepilogo_valutazioni(idea),
                "criteri": servizi.criteri(),
                "mia": mia,
                "priorita_form": PrioritaForm(
                    initial={"priorita": idea.priorita, "delibera": idea.delibera_priorita}
                ),
                "allegato_form": AllegatoForm(),
                "progetto": getattr(idea, "progetto", None),
            },
        )


class IdeaAzioneView(PermessoMixin, View):
    """Azioni sull'idea: valuta, commenta, allega, stato, priorità."""

    permission_required = "progetti.view_idea"
    PERMESSI = {
        "valuta": "progetti.valuta_idea",
        "commenta": "progetti.view_idea",
        "allega": "progetti.change_idea",
        "stato": "progetti.gestisci_idee",
        "priorita": "progetti.gestisci_idee",
    }

    def post(self, request, pk, azione):
        if azione not in self.PERMESSI or not request.user.has_perm(self.PERMESSI[azione]):
            raise Http404
        idea = get_object_or_404(Idea, pk=pk)
        p = request.POST
        try:
            if azione == "valuta":
                punteggi = {
                    k.removeprefix("criterio_"): v
                    for k, v in p.items()
                    if k.startswith("criterio_")
                }
                v = servizi.valuta(idea, request.user, punteggi, p.get("commento", ""))
                messages.success(request, f"Valutazione registrata (media {localize(v.media)}).")
            elif azione == "commenta":
                servizi.commenta(idea, request.user, p.get("testo", ""))
            elif azione == "allega":
                form = AllegatoForm(p, request.FILES)
                if not form.is_valid():
                    raise OperazioneNonValida("Scegliere il file da allegare.")
                servizi.allega(
                    idea, form.cleaned_data["file"], request.user, form.cleaned_data["descrizione"]
                )
                messages.success(request, "Documento allegato.")
            elif azione == "stato":
                servizi.cambia_stato_idea(
                    idea, p.get("stato", ""), request.user, p.get("motivo", "")
                )
                messages.success(request, f"Stato: {idea.get_stato_display()}.")
            elif azione == "priorita":
                form = PrioritaForm(p)
                if not form.is_valid():
                    raise OperazioneNonValida("Priorità non valida.")
                servizi.imposta_priorita(
                    idea,
                    form.cleaned_data["priorita"],
                    request.user,
                    delibera=form.cleaned_data["delibera"],
                )
                messages.success(request, "Priorità aggiornata.")
        except OperazioneNonValida as e:
            messages.error(request, str(e))
        return redirect(idea)


# --- progetti ------------------------------------------------------------------------------------


class ProgettiView(PermessoMixin, ListView):
    permission_required = "progetti.view_progetto"
    template_name = "progetti/progetti.html"
    context_object_name = "progetti"
    paginate_by = 30

    def get_queryset(self):
        g = self.request.GET
        qs = Progetto.objects.select_related("responsabile").prefetch_related("finalita")
        stato = g.get("stato", "aperti")
        if stato == "aperti":
            qs = qs.exclude(stato__in=[Progetto.Stato.CHIUSO, Progetto.Stato.ACCANTONATO])
        elif stato in Progetto.Stato.values:
            qs = qs.filter(stato=stato)
        if g.get("finalita"):
            qs = qs.filter(finalita=g["finalita"])
        if g.get("q"):
            qs = qs.filter(Q(titolo__icontains=g["q"]) | Q(sintesi__icontains=g["q"]))
        return qs.distinct()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        oggi = timezone.localdate()
        for p in ctx["progetti"]:
            p.prossima = p.scadenze.filter(fatta=False, data__gte=oggi).order_by("data").first()
        ctx.update(
            stati=Progetto.Stato.choices,
            finalita=FinalitaStatutaria.objects.filter(attiva=True),
            filtri=self.request.GET,
        )
        return ctx


class ProgettoNuovoView(PermessoMixin, View):
    """Nuovo progetto, eventualmente da un'idea (?idea=): titolo, finalità e sintesi proposti."""

    permission_required = "progetti.add_progetto"

    def _idea(self, request):
        pk = request.GET.get("idea") or request.POST.get("idea")
        return get_object_or_404(Idea, pk=pk) if pk else None

    def get(self, request):
        idea = self._idea(request)
        iniziali = {"responsabile": request.user}
        if idea:
            iniziali.update(
                titolo=idea.titolo, sintesi=idea.descrizione, finalita=list(idea.finalita.all())
            )
        return render(
            request,
            "progetti/progetto_modulo.html",
            {"form": ProgettoForm(initial=iniziali), "avvio": AvvioForm(), "idea": idea},
        )

    def post(self, request):
        idea = self._idea(request)
        form, avvio = ProgettoForm(request.POST), AvvioForm(request.POST)
        if form.is_valid() and avvio.is_valid():
            try:
                progetto = servizi.crea_progetto(
                    form, request.user, idea=idea, delibera=avvio.cleaned_data["delibera"]
                )
            except OperazioneNonValida as e:
                messages.error(request, str(e))
            else:
                messages.success(request, f"Progetto {progetto.codice} avviato.")
                return redirect(progetto)
        return render(
            request, "progetti/progetto_modulo.html", {"form": form, "avvio": avvio, "idea": idea}
        )


class ProgettoModificaView(PermessoMixin, View):
    permission_required = "progetti.change_progetto"

    def get(self, request, pk):
        progetto = get_object_or_404(Progetto, pk=pk)
        return render(
            request,
            "progetti/progetto_modulo.html",
            {"form": ProgettoForm(instance=progetto), "progetto": progetto},
        )

    def post(self, request, pk):
        progetto = get_object_or_404(Progetto, pk=pk)
        form = ProgettoForm(request.POST, instance=progetto)
        if form.is_valid():
            try:
                servizi.modifica_progetto(form, request.user)
            except OperazioneNonValida as e:
                messages.error(request, str(e))
            else:
                messages.success(request, "Progetto aggiornato.")
            return redirect(progetto)
        return render(
            request, "progetti/progetto_modulo.html", {"form": form, "progetto": progetto}
        )


class ProgettoView(PermessoMixin, View):
    permission_required = "progetti.view_progetto"

    def get(self, request, pk):
        progetto = get_object_or_404(Progetto.objects.select_related("responsabile", "idea"), pk=pk)
        allegati = Allegato.objects.filter(
            Q(progetto=progetto) | Q(idea_id=progetto.idea_id)
            if progetto.idea_id
            else Q(progetto=progetto)
        )
        return render(
            request,
            "progetti/progetto.html",
            {
                "progetto": progetto,
                "passaggi": progetto.passaggi.select_related("utente", "delibera"),
                "membri": progetto.membri.select_related("utente", "soggetto"),
                "scadenze": progetto.scadenze.all(),
                "allegati": allegati,
                "commenti": progetto.commenti.select_related("utente"),
                "stato_form": StatoForm(progetto=progetto),
                "membro_form": MembroForm(),
                "scadenza_form": ScadenzaForm(),
                "allegato_form": AllegatoForm(),
                "candida_form": CandidaForm(progetto=progetto),
                "oggi": timezone.localdate(),
            },
        )


class ProgettoAzioneView(PermessoMixin, View):
    """Azioni sul progetto: stato, gruppo, scadenze, commenti, allegati."""

    permission_required = "progetti.view_progetto"

    def post(self, request, pk, azione):
        progetto = get_object_or_404(Progetto, pk=pk)
        gestione = request.user.has_perm("progetti.gestisci_progetti")
        if azione != "commenta" and not gestione:
            raise Http404
        p = request.POST
        try:
            if azione == "stato":
                form = StatoForm(p, progetto=progetto)
                if not form.is_valid():
                    raise OperazioneNonValida("Scegliere uno stato ammesso.")
                servizi.cambia_stato(
                    progetto,
                    form.cleaned_data["stato"],
                    request.user,
                    motivo=form.cleaned_data["motivo"],
                    delibera=form.cleaned_data["delibera"],
                )
                messages.success(request, "Stato del progetto aggiornato.")
            elif azione == "membro":
                form = MembroForm(p)
                if not form.is_valid():
                    raise OperazioneNonValida("Dati del membro non validi.")
                d = form.cleaned_data
                servizi.aggiungi_membro(
                    progetto,
                    request.user,
                    ruolo=d["ruolo"],
                    membro_utente=d["utente"],
                    soggetto=d["soggetto"],
                    volontario=d["volontario"],
                )
            elif azione == "togli_membro":
                servizi.togli_membro(
                    get_object_or_404(Membro, pk=p.get("membro"), progetto=progetto), request.user
                )
            elif azione == "scadenza":
                form = ScadenzaForm(p)
                if not form.is_valid():
                    raise OperazioneNonValida("Indicare titolo e data della scadenza.")
                servizi.aggiungi_scadenza(progetto, request.user, **form.cleaned_data)
            elif azione == "segna":
                s = get_object_or_404(Scadenza, pk=p.get("scadenza"), progetto=progetto)
                servizi.segna_scadenza(s, request.user, fatta=p.get("fatta") == "1")
            elif azione == "commenta":
                servizi.commenta(progetto, request.user, p.get("testo", ""))
            elif azione == "candida":
                form = CandidaForm(p, progetto=progetto)
                if not form.is_valid():
                    raise OperazioneNonValida("Scegliere un bando aperto.")
                servizi.candida(progetto, form.cleaned_data["bando"], request.user,
                                delibera=form.cleaned_data["delibera"])  # fmt: skip
                messages.success(request, f"Progetto candidato al bando «{progetto.bando}».")
            elif azione == "allega":
                form = AllegatoForm(p, request.FILES)
                if not form.is_valid():
                    raise OperazioneNonValida("Scegliere il file da allegare.")
                servizi.allega(
                    progetto,
                    form.cleaned_data["file"],
                    request.user,
                    form.cleaned_data["descrizione"],
                )
                messages.success(request, "Documento allegato.")
            else:
                raise Http404
        except OperazioneNonValida as e:
            messages.error(request, str(e))
        return redirect(progetto)


# --- bandi ---------------------------------------------------------------------------------------


class BandiView(PermessoMixin, ListView):
    permission_required = "progetti.view_bando"
    template_name = "progetti/bandi.html"
    context_object_name = "bandi"
    paginate_by = 30

    def get_queryset(self):
        g = self.request.GET
        oggi = timezone.localdate()
        qs = Bando.objects.select_related("finanziatore").prefetch_related("finalita", "progetti")
        stato = g.get("stato", "aperti")
        if stato == "aperti":
            qs = qs.exclude(stato=Bando.Stato.SCARTATO).filter(
                Q(scadenza__gte=oggi) | Q(scadenza__isnull=True)
            )
        elif stato == "scaduti":
            qs = qs.filter(scadenza__lt=oggi)
        elif stato in Bando.Stato.values:
            qs = qs.filter(stato=stato)
        if g.get("finalita"):
            qs = qs.filter(finalita=g["finalita"])
        if g.get("q"):
            qs = qs.filter(
                Q(titolo__icontains=g["q"])
                | Q(descrizione__icontains=g["q"])
                | Q(finanziatore_testo__icontains=g["q"])
                | Q(finanziatore__denominazione__icontains=g["q"])
            )
        return qs.distinct()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        oggi = timezone.localdate()
        for b in ctx["bandi"]:
            b.giorni = b.giorni_alla_scadenza(oggi)
        ctx.update(
            stati=Bando.Stato.choices,
            finalita=FinalitaStatutaria.objects.filter(attiva=True),
            filtri=self.request.GET,
        )
        return ctx


class BandoNuovoView(PermessoMixin, View):
    permission_required = "progetti.add_bando"

    def get(self, request):
        return render(request, "progetti/bando_modulo.html", {"form": BandoForm()})

    def post(self, request):
        form = BandoForm(request.POST)
        if form.is_valid():
            bando = servizi.crea_bando(form, request.user)
            messages.success(request, "Bando registrato: ora si aggiungono i requisiti.")
            return redirect(bando)
        return render(request, "progetti/bando_modulo.html", {"form": form})


class BandoModificaView(PermessoMixin, View):
    permission_required = "progetti.change_bando"

    def get(self, request, pk):
        bando = get_object_or_404(Bando, pk=pk)
        return render(request, "progetti/bando_modulo.html",
                      {"form": BandoForm(instance=bando), "bando": bando})  # fmt: skip

    def post(self, request, pk):
        bando = get_object_or_404(Bando, pk=pk)
        form = BandoForm(request.POST, instance=bando)
        if form.is_valid():
            servizi.modifica_bando(form, request.user)
            messages.success(request, "Bando aggiornato.")
            return redirect(bando)
        return render(request, "progetti/bando_modulo.html", {"form": form, "bando": bando})


class BandoView(PermessoMixin, View):
    permission_required = "progetti.view_bando"

    def get(self, request, pk):
        from . import requisiti

        bando = get_object_or_404(Bando.objects.select_related("finanziatore"), pk=pk)
        return render(request, "progetti/bando.html", {
            "bando": bando, "giorni": bando.giorni_alla_scadenza(),
            "riepilogo": requisiti.riepilogo(bando),
            "progetti": bando.progetti.select_related("responsabile"),
            "requisito_form": RequisitoForm(), "candida_form": CandidaForm(bando=bando),
            "stati": Bando.Stato.choices, "esiti": ESITI,
        })  # fmt: skip


class BandoAzioneView(PermessoMixin, View):
    """Azioni sul bando: stato, requisiti ed esiti, candidatura di un progetto."""

    permission_required = "progetti.gestisci_bandi"

    def post(self, request, pk, azione):
        bando = get_object_or_404(Bando, pk=pk)
        p = request.POST
        try:
            if azione == "stato":
                servizi.cambia_stato_bando(bando, p.get("stato", ""), request.user,
                                           p.get("motivo", ""))  # fmt: skip
                messages.success(request, f"Stato: {bando.get_stato_display()}.")
            elif azione == "requisito":
                form = RequisitoForm(p)
                if not form.is_valid():
                    raise OperazioneNonValida("Requisito non valido.")
                servizi.aggiungi_requisito(bando, request.user, **form.cleaned_data)
            elif azione == "esito":
                r = get_object_or_404(Requisito, pk=p.get("requisito"), bando=bando)
                servizi.indica_esito(r, request.user, esito=p.get("esito", ""),
                                     nota=p.get("nota", ""))  # fmt: skip
            elif azione == "togli_requisito":
                r = get_object_or_404(Requisito, pk=p.get("requisito"), bando=bando)
                servizi.togli_requisito(r, request.user)
            elif azione == "candida":
                if not request.user.has_perm("progetti.gestisci_progetti"):
                    raise Http404
                form = CandidaForm(p, bando=bando)
                if not form.is_valid():
                    raise OperazioneNonValida("Scegliere un progetto in progettazione.")
                progetto = servizi.candida(form.cleaned_data["progetto"], bando, request.user,
                                           delibera=form.cleaned_data["delibera"])  # fmt: skip
                messages.success(request, f"{progetto.codice} candidato al bando.")
            else:
                raise Http404
        except OperazioneNonValida as e:
            messages.error(request, str(e))
        return redirect(bando)


class AllegatoView(PermessoMixin, View):
    """Scarica un allegato (mai servito direttamente dal web server)."""

    permission_required = "progetti.view_idea"

    def get(self, request, pk):
        from apps.protocollo.servizi import tipo_file

        a = get_object_or_404(Allegato, pk=pk)
        if a.progetto_id and not request.user.has_perm("progetti.view_progetto"):
            raise Http404
        r = FileResponse(
            a.file.open("rb"), as_attachment=True, filename=a.nome, content_type=tipo_file(a.nome)
        )
        r["Content-Security-Policy"] = "default-src 'none'; sandbox"
        return r


# --- configurazione: finalità statutarie e criteri ------------------------------------------------


class _ElencoConfigurazione(PermessoMixin, View):
    modello = form_class = None
    template_name = "progetti/configurazione.html"
    titolo = ""
    url = ""

    def _render(self, request, form, modifica=None):
        return render(
            request,
            self.template_name,
            {
                "titolo": self.titolo,
                "voci": self.modello.objects.all(),
                "form": form,
                "modifica": modifica,
                "url": self.url,
            },
        )

    def get(self, request):
        modifica = None
        if pk := request.GET.get("modifica"):
            modifica = get_object_or_404(self.modello, pk=pk)
        return self._render(request, self.form_class(instance=modifica), modifica)

    def post(self, request):
        from apps.core.audit import Azione, registra

        modifica = None
        if pk := request.POST.get("pk"):
            modifica = get_object_or_404(self.modello, pk=pk)
        form = self.form_class(request.POST, instance=modifica)
        if form.is_valid():
            voce = form.save()
            registra(Azione.MODIFICA if modifica else Azione.CREAZIONE, voce, utente=request.user)
            messages.success(request, f"«{voce}» salvato.")
            return redirect(self.url)
        return self._render(request, form, modifica)


class FinalitaView(_ElencoConfigurazione):
    permission_required = "progetti.change_finalitastatutaria"
    modello, form_class = FinalitaStatutaria, FinalitaForm
    titolo, url = "Finalità statutarie", "progetti:finalita"


class CriteriView(_ElencoConfigurazione):
    permission_required = "progetti.change_criteriovalutazione"
    modello, form_class = CriterioValutazione, CriterioForm
    titolo, url = "Criteri di valutazione delle idee", "progetti:criteri"
