# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Viste del rinnovo degli organi: elenco, scheda della procedura con le fasi,
# *              compilazione delle liste, esiti, nomine, documenti PDF, profili elettorali.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from datetime import date

from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, ListView, TemplateView, UpdateView

from apps.anagrafica.models import Soggetto
from apps.core.views import PermessoMixin

from . import servizi
from .forms import (
    AssembleaForm,
    ConsegneForm,
    DecadenzaForm,
    EsitiForm,
    NuovoRinnovoForm,
    ProfiloForm,
)
from .models import Candidato, Decadenza, Lista, ProfiloElettorale, Ricorso, Rinnovo

LETTURA = "elezioni.view_rinnovo"
GESTIONE = "elezioni.gestisci_rinnovi"


def _avvisa(request, avvisi):
    for a in avvisi or []:
        messages.warning(request, a)


def _data(valore, predefinita=None):
    try:
        return date.fromisoformat(valore) if valore else predefinita
    except ValueError:
        raise servizi.OperazioneNonValida("Data non valida.") from None


def _rinnovi(utente):
    return servizi.filtra_per_utente(Rinnovo.objects.select_related("profilo", "sezione"), utente)


class RinnoviView(PermessoMixin, ListView):
    permission_required = LETTURA
    template_name = "elezioni/rinnovi.html"
    context_object_name = "rinnovi"

    def get_queryset(self):
        return _rinnovi(self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from apps.soci import sezioni

        da_avviare = servizi.da_avviare()
        ids = sezioni.id_sezioni(self.request.user)
        if ids is not None:
            da_avviare = [d for d in da_avviare if d["sezione"] and d["sezione"].pk in ids]
        ctx["da_avviare"] = da_avviare
        rinnovi = list(ctx["rinnovi"])
        for r in rinnovi:
            r.prossimo = servizi.prossimo_termine(r) if r.aperto else None
        ctx["rinnovi"] = rinnovi
        return ctx


class RinnovoNuovoView(PermessoMixin, View):
    permission_required = GESTIONE
    template_name = "elezioni/rinnovo_nuovo.html"

    def _sezioni(self):
        from apps.soci import sezioni
        from apps.soci.models import Sezione

        return sezioni.filtra(Sezione.objects.filter(attiva=True), self.request.user, campo="pk")

    def get(self, request):
        iniziale = {}
        if request.GET.get("sezione", "").isdigit():
            iniziale["sezione"] = int(request.GET["sezione"])
        form = NuovoRinnovoForm(initial=iniziale, sezioni=self._sezioni())
        return render(request, self.template_name, {"form": form})

    def post(self, request):
        from apps.soci import sezioni

        form = NuovoRinnovoForm(request.POST, sezioni=self._sezioni())
        if form.is_valid():
            sezione = form.cleaned_data["sezione"]
            if sezione is None and sezioni.id_sezioni(request.user) is not None:
                form.add_error("sezione", "Indicare la sezione.")
            else:
                try:
                    rinnovo = servizi.nuovo_rinnovo(
                        request.user, profilo=form.cleaned_data["profilo"], sezione=sezione,
                        quadriennio=form.cleaned_data["quadriennio"],
                    )  # fmt: skip
                except servizi.OperazioneNonValida as e:
                    form.add_error(None, e)
                else:
                    messages.success(request, f"{rinnovo} avviato.")
                    return redirect(rinnovo)
        return render(request, self.template_name, {"form": form})


class _RinnovoMixin:
    def rinnovo(self, pk):
        return get_object_or_404(_rinnovi(self.request.user), pk=pk)


class RinnovoView(_RinnovoMixin, PermessoMixin, TemplateView):
    permission_required = LETTURA
    template_name = "elezioni/rinnovo.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        r = self.rinnovo(kwargs["pk"])
        liste = list(r.liste.prefetch_related("candidati__soggetto"))
        for lista in liste:
            lista.problemi = (servizi.problemi_lista(lista) if lista.stato in (
                Lista.Stato.BOZZA, Lista.Stato.PRESENTATA) else [])  # fmt: skip
        ctx.update(
            rinnovo=r, termini=servizi.termini(r), liste=liste,
            composizione=servizi.descrizione_composizione(r),
            soci_soglia=servizi.soci_per_soglia(r),
            avvisi_assemblea=servizi.controlla_assemblea(r),
            dopo_avviso=servizi.iscritti_dopo_avviso(r), eletti=servizi.eletti(r),
            ricorsi=list(r.ricorsi.all()),
            documenti=[(codice, nome, servizi.sigla_modello(r, codice))
                       for codice, nome in servizi.DOCUMENTI.items() if codice != "lista"],
            modalita=servizi.modalita_voto(r) if r.fase in ("liste", "votato") else "",
            voti_totali=servizi.voti_totali(r), oggi=timezone.localdate(),
            puo_gestire=self.request.user.has_perm(GESTIONE),
        )  # fmt: skip
        return ctx


class _AzioneRinnovo(_RinnovoMixin, PermessoMixin, View):
    """POST su una procedura: esegue `azione` e torna alla scheda con gli avvisi."""

    permission_required = GESTIONE
    http_method_names = ["post"]

    def post(self, request, pk):
        r = self.rinnovo(pk)
        try:
            esito = self.azione(request, r)
        except servizi.OperazioneNonValida as e:
            messages.error(request, " ".join(e.messages))
        else:
            if isinstance(esito, HttpResponse):
                return esito
            _avvisa(request, esito)
        return redirect(reverse("elezioni:rinnovo", args=[r.pk]) + self.ancora)

    ancora = ""


class IndiciView(_AzioneRinnovo):
    def azione(self, request, r):
        giorno = _data(request.POST.get("giorno"), timezone.localdate())
        avvisi = servizi.indici(r, request.user, giorno=giorno, atto=request.POST.get("atto", ""))
        messages.success(request, "Rinnovo indetto: ora si fissano data e luogo dell'assemblea.")
        return avvisi


class AssembleaView(_RinnovoMixin, PermessoMixin, View):
    permission_required = GESTIONE
    template_name = "elezioni/assemblea.html"

    def get(self, request, pk):
        r = self.rinnovo(pk)
        return render(
            request, self.template_name, {"rinnovo": r, "form": AssembleaForm(instance=r)}
        )

    def post(self, request, pk):
        r = self.rinnovo(pk)
        form = AssembleaForm(request.POST, instance=r)
        if form.is_valid():
            try:
                _avvisa(request, servizi.salva_assemblea(form, request.user))
            except servizi.OperazioneNonValida as e:
                form.add_error(None, e)
            else:
                messages.success(request, "Assemblea salvata.")
                return redirect(r)
        return render(request, self.template_name, {"rinnovo": r, "form": form})


class ConvocaView(_AzioneRinnovo):
    def azione(self, request, r):
        avvisi = servizi.convoca(r, request.user,
                                 giorno=_data(request.POST.get("giorno"), timezone.localdate()),
                                 comunicazione=bool(request.POST.get("comunicazione")))  # fmt: skip
        r.refresh_from_db()
        testo = (
            f"Convocato: {servizi.voti_totali(r)} {'voti' if r.federazione else 'aventi diritto'}."
        )
        if r.invio_avviso_id:
            testo += " L'avviso è in bozza in Comunicazioni: controllarlo e confermarlo."
        messages.success(request, testo)
        return avvisi


class ListaNuovaView(_AzioneRinnovo):
    def azione(self, request, r):
        lista = servizi.nuova_lista(r, request.user, motto=request.POST.get("motto", ""))
        return redirect(lista)


class _ListaMixin:
    def lista(self, pk):
        return get_object_or_404(
            Lista.objects.filter(rinnovo__in=_rinnovi(self.request.user)).select_related(
                "rinnovo__profilo"), pk=pk)  # fmt: skip


class ListaView(_ListaMixin, PermessoMixin, TemplateView):
    permission_required = LETTURA
    template_name = "elezioni/lista.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        lista = self.lista(kwargs["pk"])
        regole = servizi.composizione(lista.rinnovo)
        conteggi = {}
        for c in lista.candidati.all():
            conteggi[c.incarico] = conteggi.get(c.incarico, 0) + 1
        ctx.update(
            lista=lista, rinnovo=lista.rinnovo,
            candidati=lista.candidati.select_related("soggetto"),
            problemi=servizi.problemi_lista(lista),
            incarichi=[(valore, nome, regole[valore], conteggi.get(valore, 0))
                       for valore, nome in Candidato.Incarico.choices if regole[valore][1]],
            modificabile=lista.stato == Lista.Stato.BOZZA and lista.rinnovo.aperto,
            puo_gestire=self.request.user.has_perm(GESTIONE),
            puo_protocollare=self.request.user.has_perm("protocollo.add_protocollo"),
        )  # fmt: skip
        return ctx


class CercaCandidatiView(_ListaMixin, PermessoMixin, View):
    """Ricerca in anagrafica: i soci in regola prima, con l'indicazione di chi non lo è."""

    permission_required = GESTIONE

    def get(self, request, pk):
        lista = self.lista(pk)
        q = request.GET.get("cerca", "").strip()
        risultati = []
        if len(q) >= 2:
            trovati = list(Soggetto.objects.attivi().ricerca(q).filter(tipo="persona")[:12])
            in_regola = servizi._in_regola(lista.rinnovo, [s.pk for s in trovati])
            risultati = [(s, s.pk in in_regola) for s in trovati]
        return render(request, "elezioni/_candidati_trovati.html",
                      {"risultati": risultati, "lista": lista, "q": q,
                       "incarichi": Candidato.Incarico.choices})  # fmt: skip


class _AzioneLista(_ListaMixin, PermessoMixin, View):
    permission_required = GESTIONE
    http_method_names = ["post"]

    def post(self, request, pk, **kwargs):
        lista = self.lista(pk)
        try:
            esito = self.azione(request, lista, **kwargs)
        except servizi.OperazioneNonValida as e:
            messages.error(request, " ".join(e.messages))
        else:
            if isinstance(esito, HttpResponse):
                return esito
            _avvisa(request, esito)
        return redirect(lista)


class CandidatoAggiungiView(_AzioneLista):
    def azione(self, request, lista):
        soggetto = get_object_or_404(Soggetto, pk=request.POST.get("soggetto") or 0)
        servizi.aggiungi_candidato(lista, request.user, soggetto=soggetto,
                                   incarico=request.POST.get("incarico", ""),
                                   accettazione=bool(request.POST.get("accettazione")))  # fmt: skip


class CandidatoAzioneView(_AzioneLista):
    def azione(self, request, lista, candidato, azione):
        c = get_object_or_404(Candidato, pk=candidato, lista=lista)
        if azione == "togli":
            servizi.togli_candidato(c, request.user)
        elif azione == "accettazione":
            servizi.imposta_accettazione(c, request.user, request.POST.get("valore") == "1")
        elif azione == "rinuncia":
            servizi.registra_rinuncia(c, request.user, request.POST.get("valore") == "1")
            return redirect(reverse("elezioni:rinnovo", args=[lista.rinnovo_id]) + "#eletti")
        else:
            raise Http404


class ListaAzioneView(_AzioneLista):
    def azione(self, request, lista, azione):
        rinnovo = lista.rinnovo
        if azione == "presenta":
            protocolla = bool(request.POST.get("protocolla"))
            avvisi = servizi.presenta_lista(lista, request.user, protocolla=protocolla)
            messages.success(request, f"Lista presentata con il n. {lista.numero}.")
            return avvisi
        if azione == "elimina":
            servizi.elimina_bozza(lista, request.user)
            messages.success(request, "Lista in compilazione eliminata.")
            return redirect(rinnovo)
        if azione == "ritira":
            servizi.ritira_lista(lista, request.user)
        elif azione == "esamina":
            ammessa = request.POST.get("ammessa") == "1"
            servizi.esamina_lista(lista, request.user, ammessa=ammessa,
                                  motivo=request.POST.get("motivo", ""),
                                  giorno=_data(request.POST.get("giorno")))  # fmt: skip
            messages.success(request, f"{lista}: {'ammessa' if ammessa else 'esclusa'}.")
            return redirect(reverse("elezioni:rinnovo", args=[rinnovo.pk]) + "#liste")
        elif azione == "programma":
            if lista.stato != Lista.Stato.BOZZA:
                raise servizi.OperazioneNonValida("La lista è già stata presentata.")
            lista.motto = request.POST.get("motto", "")[:150]
            lista.presentatore = request.POST.get("presentatore", "")[:150]
            lista.programma = request.POST.get("programma", "")
            lista.save(update_fields=["motto", "presentatore", "programma"])
        else:
            raise Http404
        return None


class EsitiView(_RinnovoMixin, PermessoMixin, View):
    permission_required = GESTIONE
    template_name = "elezioni/esiti.html"

    def _pagina(self, request, r, form):
        ammesse = r.liste.filter(stato=Lista.Stato.AMMESSA).prefetch_related("candidati__soggetto")
        return render(request, self.template_name, {
            "rinnovo": r, "form": form, "ammesse": ammesse,
            "modalita": servizi.modalita_voto(r), "voti_totali": servizi.voti_totali(r),
        })  # fmt: skip

    def get(self, request, pk):
        r = self.rinnovo(pk)
        return self._pagina(request, r, EsitiForm(instance=r))

    def post(self, request, pk):
        r = self.rinnovo(pk)
        form = EsitiForm(request.POST, instance=r)
        if form.is_valid():
            if r.federazione:  # presenze e delegati delle sezioni (verifica dei poteri)
                righe = list(r.aventi_diritto)
                for riga in righe:
                    chiave = str(riga["sezione"])
                    riga["presente"] = bool(request.POST.get(f"presente_{chiave}"))
                    riga["delegato"] = request.POST.get(f"delegato_{chiave}", riga["delegato"])[
                        :150
                    ]
                form.instance.aventi_diritto = righe
            voti = {}
            for lista in r.liste.filter(stato=Lista.Stato.AMMESSA):
                valore = request.POST.get(f"voti_{lista.pk}", "0") or "0"
                voti[lista.pk] = int(valore) if valore.isdigit() else 0
            dati = {campo: form.cleaned_data[campo] for campo in form.fields}
            if r.federazione:
                dati["aventi_diritto"] = form.instance.aventi_diritto
            try:
                avvisi = servizi.registra_esiti(Rinnovo.objects.get(pk=r.pk), request.user,
                                                dati, voti)  # fmt: skip
            except servizi.OperazioneNonValida as e:
                form.add_error(None, e)
            else:
                _avvisa(request, avvisi)
                messages.success(request, "Esiti registrati.")
                return redirect(reverse("elezioni:rinnovo", args=[r.pk]) + "#esiti")
        return self._pagina(request, r, form)


class ProclamaView(_AzioneRinnovo):
    ancora = "#eletti"

    def azione(self, request, r):
        servizi.proclama(r, request.user)
        messages.success(request, "Eletti proclamati.")


class RicorsoView(_AzioneRinnovo):
    ancora = "#ricorsi"

    def azione(self, request, r):
        if request.POST.get("ricorso"):
            ricorso = get_object_or_404(Ricorso, pk=request.POST["ricorso"], rinnovo=r)
            servizi.decidi_ricorso(ricorso, request.user, esito=request.POST.get("esito", ""),
                                   decisione=request.POST.get("decisione", ""))  # fmt: skip
            return None
        if not request.POST.get("presentato_da") or not request.POST.get("motivi"):
            raise servizi.OperazioneNonValida("Indicare chi presenta il ricorso e i motivi.")
        return servizi.aggiungi_ricorso(
            r, request.user, presentato_il=_data(request.POST.get("presentato_il"),
                                                 timezone.localdate()),
            presentato_da=request.POST["presentato_da"][:200], motivi=request.POST["motivi"],
        )  # fmt: skip


class InsediaView(_AzioneRinnovo):
    def azione(self, request, r):
        n = servizi.insedia(
            r, request.user, giorno=_data(request.POST.get("giorno"), timezone.localdate())
        )
        messages.success(request, f"Nuovi organi insediati: {n} cariche registrate negli organi "
                                  "sociali, quelle uscenti chiuse.")  # fmt: skip


class ConsegneView(_RinnovoMixin, PermessoMixin, View):
    permission_required = GESTIONE
    template_name = "elezioni/consegne.html"

    def get(self, request, pk):
        r = self.rinnovo(pk)
        iniziale = dict(r.consegne) or {}
        if not iniziale:
            uscente = _presidente_uscente(r)
            eletto = next((c for c in servizi.eletti(r) if c.incarico == "presidente"), None)
            iniziale = {
                "giorno": timezone.localdate(), "sede": r.luogo,
                "consegnante": uscente or "", "ricevente": eletto.soggetto.nome_completo if eletto
                else "",
            }  # fmt: skip
        return render(request, self.template_name,
                      {"rinnovo": r, "form": ConsegneForm(initial=iniziale)})  # fmt: skip

    def post(self, request, pk):
        r = self.rinnovo(pk)
        form = ConsegneForm(request.POST)
        if form.is_valid():
            try:
                servizi.registra_consegne(r, request.user, form.dati(),
                                          giorno=form.cleaned_data["giorno"])  # fmt: skip
            except servizi.OperazioneNonValida as e:
                form.add_error(None, e)
            else:
                messages.success(request, "Passaggio di consegne registrato: si stampa il verbale.")
                return redirect(r)
        return render(request, self.template_name, {"rinnovo": r, "form": form})


def _presidente_uscente(r):
    from apps.organi.models import Carica

    organo = servizi.organo_consiglio(r.sezione)
    if organo is None:
        return ""
    carica = (Carica.objects.filter(organo=organo, ruolo="presidente").exclude(
        nomina__contains=r.quadriennio).order_by("-dal").first())  # fmt: skip
    return carica.soggetto.nome_completo if carica else ""


class TrasmettiView(_AzioneRinnovo):
    def azione(self, request, r):
        servizi.trasmetti(r, request.user, giorno=_data(request.POST.get("giorno")),
                          protocolla=bool(request.POST.get("protocolla")))  # fmt: skip
        messages.success(request, "Trasmissione dei verbali registrata.")


class ConcludiView(_AzioneRinnovo):
    def azione(self, request, r):
        if request.POST.get("ratificato_il"):
            r.ratificato_il = _data(request.POST["ratificato_il"])
            r.save(update_fields=["ratificato_il"])
        servizi.concludi(r, request.user)
        messages.success(request, "Rinnovo concluso.")


class AnnullaView(_AzioneRinnovo):
    def azione(self, request, r):
        servizi.annulla(r, request.user, request.POST.get("motivo", ""))
        messages.success(request, "Rinnovo annullato.")


class DocumentoView(_RinnovoMixin, PermessoMixin, View):
    permission_required = LETTURA

    def get(self, request, pk, codice):
        from apps.core.pdf import risposta_pdf

        r = self.rinnovo(pk)
        if codice not in servizi.DOCUMENTI:
            raise Http404
        extra = {}
        if codice == "lista":
            extra["lista"] = get_object_or_404(r.liste, pk=request.GET.get("lista") or 0)
        nome = f"{codice}-{r.quadriennio}.pdf"
        return risposta_pdf(f"elezioni/pdf/{codice}.html",
                            servizi.contesto_documento(codice, r, **extra), nome)  # fmt: skip


class ProfiliView(PermessoMixin, ListView):
    permission_required = "elezioni.view_profiloelettorale"
    template_name = "elezioni/profili.html"
    context_object_name = "profili"
    model = ProfiloElettorale


class _ProfiloMixin:
    model = ProfiloElettorale
    form_class = ProfiloForm
    template_name = "elezioni/profilo.html"
    success_url = reverse_lazy("elezioni:profili")

    def form_valid(self, form):
        from apps.core.audit import Azione, registra

        nuovo = form.instance.pk is None
        risposta = super().form_valid(form)
        registra(Azione.CREAZIONE if nuovo else Azione.MODIFICA, self.object,
                 utente=self.request.user)  # fmt: skip
        messages.success(self.request, f"Profilo «{self.object}» salvato.")
        return risposta


class ProfiloNuovoView(_ProfiloMixin, PermessoMixin, CreateView):
    permission_required = "elezioni.add_profiloelettorale"


class ProfiloModificaView(_ProfiloMixin, PermessoMixin, UpdateView):
    permission_required = "elezioni.change_profiloelettorale"


class DecadenzaView(PermessoMixin, View):
    """Decadenza anticipata degli organi o commissariamento: apre il rinnovo straordinario."""

    permission_required = GESTIONE
    template_name = "elezioni/decadenza.html"

    def _sezioni(self):
        from apps.soci import sezioni
        from apps.soci.models import Sezione

        return sezioni.filtra(Sezione.objects.filter(attiva=True), self.request.user, campo="pk")

    def _pagina(self, request, form, commissario=None):
        return render(request, self.template_name, {"form": form, "commissario": commissario})

    def get(self, request):
        iniziale = {"giorno": timezone.localdate()}
        if request.GET.get("sezione", "").isdigit():
            iniziale["sezione"] = int(request.GET["sezione"])
        return self._pagina(request, DecadenzaForm(initial=iniziale, sezioni=self._sezioni()))

    def post(self, request):
        from apps.soci import sezioni

        form = DecadenzaForm(request.POST, sezioni=self._sezioni())
        commissario = Soggetto.objects.filter(pk=request.POST.get("commissario") or 0).first()
        if form.is_valid():
            d = form.cleaned_data
            if d["sezione"] is None and sezioni.id_sezioni(request.user) is not None:
                form.add_error("sezione", "Indicare la sezione.")
            else:
                organi = servizi.organi_da_sciogliere(d["sezione"]).filter(tipo__in=form.tipi())
                try:
                    decadenza = servizi.dichiara_decadenza(
                        request.user, sezione=d["sezione"], giorno=d["giorno"],
                        motivo=d["motivo"], organi_ids=list(organi.values_list("pk", flat=True)),
                        commissario=commissario, termine=d["termine"],
                        disposto_da=d["disposto_da"], atto=d["atto"], profilo=d["profilo"],
                        note=d["note"],
                    )  # fmt: skip
                except servizi.OperazioneNonValida as e:
                    form.add_error(None, e)
                else:
                    messages.success(request, f"{decadenza}: {decadenza.cariche_chiuse} cariche "
                                              "chiuse, rinnovo straordinario aperto entro il "
                                              f"{decadenza.termine:%d/%m/%Y}.")  # fmt: skip
                    return redirect(decadenza.rinnovo)
        return self._pagina(request, form, commissario)


class CercaPersonaView(PermessoMixin, View):
    """Ricerca in anagrafica per scegliere il commissario."""

    permission_required = GESTIONE

    def get(self, request):
        q = request.GET.get("cerca", "").strip()
        risultati = []
        if len(q) >= 2:
            risultati = list(Soggetto.objects.attivi().ricerca(q).filter(tipo="persona")[:10])
        return render(request, "elezioni/_persone_trovate.html", {"risultati": risultati, "q": q})


class ProrogaView(_AzioneRinnovo):
    def azione(self, request, r):
        decadenza = get_object_or_404(Decadenza, rinnovo=r, chiusa_il__isnull=True)
        fino = _data(request.POST.get("fino"))
        if fino is None:
            raise servizi.OperazioneNonValida("Indicare la data della proroga.")
        servizi.proroga(decadenza, request.user, fino=fino, atto=request.POST.get("atto", ""))
        messages.success(request, "Commissariamento prorogato.")
