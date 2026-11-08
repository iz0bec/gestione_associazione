# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Viste del protocollo: registro con ricerca, registrazione, scheda,
# *              allegati (scaricati solo con permesso), annullamento, ricevuta, registri
# *              giornalieri, posta da protocollare, caselle e titolario.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import io
from datetime import date

from django.conf import settings
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.core.files.storage import default_storage
from django.http import FileResponse, Http404, HttpResponse
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
from apps.core.cifratura import cifratura_disponibile
from apps.core.models import EventoAudit, Organizzazione
from apps.core.pdf import risposta_pdf
from apps.core.views import PermessoMixin

from . import servizi
from .filtri import ProtocolloFilter
from .forms import (
    AllegatiForm,
    CasellaForm,
    ClassificazioneForm,
    ModificaForm,
    ProtocollaMessaggioForm,
    ProtocolloForm,
)
from .models import (
    Allegato,
    CasellaPosta,
    Classificazione,
    MessaggioRicevuto,
    Protocollo,
    RegistroGiornaliero,
)
from .servizi import OperazioneNonValida


def _errore(request, e):
    messages.error(request, " ".join(e.messages))


def _scarica(file_field, nome, tipo, *, in_linea=False):
    """Risposta di download sicura: nome ripulito, tipo dedotto dal server, niente esecuzione."""
    try:
        f = file_field.open("rb")
    except FileNotFoundError:
        raise Http404("File non trovato.") from None
    risposta = FileResponse(f, as_attachment=not in_linea, filename=nome, content_type=tipo)
    risposta["Content-Security-Policy"] = "default-src 'none'; sandbox"
    risposta["X-Content-Type-Options"] = "nosniff"
    return risposta


class _ProtocolloVisibileMixin:
    """Recupera il protocollo solo se visibile all'utente (i riservati richiedono il permesso)."""

    def protocollo(self, pk):
        return get_object_or_404(Protocollo.objects.visibili_a(self.request.user), pk=pk)


# --- registro --------------------------------------------------------------------------------


class ElencoView(PermessoMixin, FilterView):
    permission_required = "protocollo.view_protocollo"
    filterset_class = ProtocolloFilter
    paginate_by = 30
    template_name = "protocollo/elenco.html"

    def get_queryset(self):
        return (
            Protocollo.objects.visibili_a(self.request.user)
            .select_related("classificazione")
            .prefetch_related("corrispondenti", "allegati")
        )

    def get_template_names(self):
        if self.request.htmx and not self.request.htmx.boosted:
            return ["protocollo/elenco.html#tabella"]
        return [self.template_name]


class DettaglioView(PermessoMixin, _ProtocolloVisibileMixin, DetailView):
    permission_required = "protocollo.view_protocollo"
    template_name = "protocollo/dettaglio.html"
    context_object_name = "protocollo"

    def get_object(self, queryset=None):
        p = self.protocollo(self.kwargs["pk"])
        if p.riservato:
            registra(Azione.CONSULTAZIONE, p, descrizione=f"Protocollo riservato {p.segnatura}")
        return p

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        p = self.object
        ctx["risposte"] = p.risposte.visibili_a(self.request.user)
        ctx["form_allegati"] = AllegatiForm()
        if self.request.user.has_perm("core.view_eventoaudit"):
            ctx["storia"] = EventoAudit.objects.filter(
                oggetto_tipo=ContentType.objects.get_for_model(Protocollo), oggetto_id=str(p.pk)
            )[:30]
        return ctx


class NuovoView(PermessoMixin, FormView):
    permission_required = "protocollo.add_protocollo"
    form_class = ProtocolloForm
    template_name = "protocollo/nuovo.html"

    def get_initial(self):
        iniziali = {"direzione": self.request.GET.get("direzione", Protocollo.Direzione.ENTRATA)}
        if risposta := self.request.GET.get("risposta"):
            p = Protocollo.objects.visibili_a(self.request.user).filter(pk=risposta).first()
            if p:
                iniziali.update(
                    in_risposta_a=p.segnatura,
                    oggetto=f"Risposta: {p.oggetto}"[:500],
                    direzione=Protocollo.Direzione.USCITA,
                    classificazione=p.classificazione,
                    destinatari=[c.soggetto for c in p.mittenti if c.soggetto],
                    destinatari_altri="\n".join(
                        f"{c.descrizione} <{c.indirizzo}>" if "@" in c.indirizzo else c.descrizione
                        for c in p.mittenti
                        if not c.soggetto
                    ),
                )
        if soggetto := self.request.GET.get("soggetto"):
            s = Soggetto.objects.filter(pk=soggetto).first()
            if s:
                campo = "destinatari" if iniziali["direzione"] == "uscita" else "mittenti"
                iniziali[campo] = [s]
        return iniziali

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        form = ctx["form"]
        for campo in ("mittenti", "destinatari"):
            valore = form[campo].value() or []
            ids = [getattr(v, "pk", v) for v in valore]
            ctx[f"scelti_{campo}"] = Soggetto.objects.filter(pk__in=ids)
        ctx["estensioni"] = ", ".join(sorted(settings.PROTOCOLLO_ESTENSIONI))
        ctx["max_mb"] = settings.PROTOCOLLO_ALLEGATO_MAX_MB
        return ctx

    def form_valid(self, form):
        try:
            p = servizi.registra_protocollo(
                form.dati_protocollo(),
                form.corrispondenti,
                self.request.user,
                allegati=form.cleaned_data["allegati"],
            )
        except OperazioneNonValida as e:
            form.add_error(None, e)
            return self.form_invalid(form)
        messages.success(self.request, f"Registrato il protocollo n. {p.segnatura}.")
        return redirect(p)


class CercaSoggettiView(PermessoMixin, TemplateView):
    """Risultati della ricerca in anagrafica per scegliere i corrispondenti (HTMX)."""

    permission_required = "protocollo.add_protocollo"
    template_name = "protocollo/_cerca_soggetti.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        campo = self.request.GET.get("campo")
        if campo not in ("mittenti", "destinatari"):
            raise Http404
        q = self.request.GET.get(f"cerca_{campo}", "").strip()
        ctx["campo"] = campo
        ctx["risultati"] = Soggetto.objects.attivi().ricerca(q)[:10] if len(q) >= 2 else []
        return ctx


class SceltaSoggettoView(PermessoMixin, TemplateView):
    """Etichetta del soggetto scelto, con la casella che lo invia nel modulo (HTMX)."""

    permission_required = "protocollo.add_protocollo"
    template_name = "protocollo/_soggetto_scelto.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        campo = self.request.GET.get("campo")
        if campo not in ("mittenti", "destinatari"):
            raise Http404
        ctx["campo"] = campo
        ctx["s"] = get_object_or_404(Soggetto, pk=self.request.GET.get("id"))
        return ctx


class ModificaView(PermessoMixin, _ProtocolloVisibileMixin, UpdateView):
    permission_required = "protocollo.change_protocollo"
    form_class = ModificaForm
    template_name = "protocollo/modifica.html"
    context_object_name = "protocollo"

    def get_object(self, queryset=None):
        p = self.protocollo(self.kwargs["pk"])
        if p.annullato:
            raise Http404("Protocollo annullato.")
        return p

    def form_valid(self, form):
        self.object = servizi.modifica_protocollo(form, self.request.user)
        messages.success(self.request, "Dati aggiornati.")
        return redirect(self.object)


class _AzioneView(PermessoMixin, _ProtocolloVisibileMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        p = self.protocollo(pk)
        try:
            self.esegui(request, p)
        except OperazioneNonValida as e:
            _errore(request, e)
        return redirect(p)


class AnnullaView(_AzioneView):
    permission_required = "protocollo.annulla_protocollo"

    def esegui(self, request, p):
        servizi.annulla_protocollo(p, request.user, request.POST.get("motivo", ""))
        messages.success(request, f"Protocollo {p.segnatura} annullato.")


class AllegatiView(_AzioneView):
    permission_required = "protocollo.change_protocollo"

    def esegui(self, request, p):
        form = AllegatiForm(request.POST, request.FILES)
        if not form.is_valid() or not form.cleaned_data["allegati"]:
            raise OperazioneNonValida("Scegliere almeno un file.")
        nuovi = servizi.carica_allegati(p, form.cleaned_data["allegati"], request.user)
        messages.success(request, f"Aggiunti {len(nuovi)} documenti.")


class ScaricaAllegatoView(PermessoMixin, View):
    permission_required = "protocollo.view_protocollo"

    def get(self, request, pk):
        a = get_object_or_404(
            Allegato.objects.select_related("protocollo"),
            pk=pk,
            protocollo__in=Protocollo.objects.visibili_a(request.user),
        )
        if a.protocollo.riservato:
            registra(Azione.CONSULTAZIONE, a.protocollo, descrizione=f"Allegato «{a.nome}»")
        in_linea = request.GET.get("vedi") == "1" and a.tipo in (
            "application/pdf",
            "image/png",
            "image/jpeg",
        )
        return _scarica(a.file, a.nome, a.tipo, in_linea=in_linea)


class RicevutaView(PermessoMixin, _ProtocolloVisibileMixin, View):
    """Ricevuta di protocollazione (es. per chi consegna un documento a mano)."""

    permission_required = "protocollo.view_protocollo"

    def get(self, request, pk):
        p = self.protocollo(pk)
        return risposta_pdf(
            "protocollo/pdf/ricevuta.html",
            {"p": p, "organizzazione": Organizzazione.corrente()},
            f"protocollo_{p.anno}_{p.numero:05d}.pdf",
        )


class EsportaView(PermessoMixin, View):
    permission_required = "protocollo.esporta_protocollo"

    def get(self, request):
        qs = Protocollo.objects.visibili_a(request.user)
        filtro = ProtocolloFilter(request.GET, queryset=qs)
        buffer = io.StringIO()
        servizi.esporta_csv(filtro.qs.order_by("anno", "numero"), buffer, request.user)
        risposta = HttpResponse("﻿" + buffer.getvalue(), content_type="text/csv; charset=utf-8")
        risposta["Content-Disposition"] = (
            f'attachment; filename="protocollo_{date.today():%Y%m%d}.csv"'
        )
        return risposta


# --- registri giornalieri --------------------------------------------------------------------


class RegistriView(PermessoMixin, ListView):
    permission_required = "protocollo.view_registrogiornaliero"
    template_name = "protocollo/registri.html"
    context_object_name = "registri"
    paginate_by = 31
    model = RegistroGiornaliero

    def post(self, request):
        if not request.user.has_perm("protocollo.esporta_protocollo"):
            return self.handle_no_permission()
        creati = servizi.genera_registri_mancanti()
        messages.success(request, f"Registri generati: {len(creati)}.")
        return redirect("protocollo:registri")


class ScaricaRegistroView(PermessoMixin, View):
    permission_required = "protocollo.view_registrogiornaliero"

    def get(self, request, pk):
        r = get_object_or_404(RegistroGiornaliero, pk=pk)
        return _scarica(
            r.file, f"registro_protocollo_{r.data:%Y%m%d}.pdf", "application/pdf", in_linea=True
        )


# --- posta da protocollare -------------------------------------------------------------------


class PostaView(PermessoMixin, ListView):
    permission_required = "protocollo.view_messaggioricevuto"
    template_name = "protocollo/posta.html"
    context_object_name = "messaggi"
    paginate_by = 30

    def get_queryset(self):
        stato = self.request.GET.get("stato", MessaggioRicevuto.Stato.NUOVO)
        qs = MessaggioRicevuto.objects.select_related("casella", "protocollo")
        return qs if stato == "tutti" else qs.filter(stato=stato)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["stato"] = self.request.GET.get("stato", MessaggioRicevuto.Stato.NUOVO)
        ctx["stati"] = [*MessaggioRicevuto.Stato.choices, ("tutti", "Tutti")]
        ctx["caselle"] = CasellaPosta.objects.all()
        return ctx

    def post(self, request):
        """Scarica subito la posta (oltre al comando pianificato)."""
        if not request.user.has_perm("protocollo.gestisci_posta"):
            return self.handle_no_permission()
        from apps.core.models import Organizzazione

        from .posta import scarica_tutte

        if not Organizzazione.corrente().ricezione_posta:
            messages.warning(request, "La lettura della posta è disattivata (Sistema → Servizi "
                                      "di posta).")  # fmt: skip
            return redirect("protocollo:posta")
        for casella, esito in scarica_tutte().items():
            if isinstance(esito, int):
                messages.info(request, f"{casella}: {esito} nuovi messaggi.")
            else:
                messages.error(request, f"{casella}: {esito}")
        return redirect("protocollo:posta")


class MessaggioView(PermessoMixin, DetailView):
    permission_required = "protocollo.view_messaggioricevuto"
    model = MessaggioRicevuto
    template_name = "protocollo/messaggio.html"
    context_object_name = "messaggio"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        m = self.object
        ctx["form"] = ProtocollaMessaggioForm(initial={"oggetto": m.oggetto})
        ctx["mittente_noto"] = servizi.soggetto_per_indirizzo(m.mittente_email)
        return ctx


class ProtocollaMessaggioView(PermessoMixin, View):
    permission_required = ("protocollo.gestisci_posta", "protocollo.add_protocollo")
    http_method_names = ["post"]

    def post(self, request, pk):
        m = get_object_or_404(MessaggioRicevuto, pk=pk)
        form = ProtocollaMessaggioForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Indicare l'oggetto.")
            return redirect(m)
        try:
            p = servizi.protocolla_messaggio(m, request.user, **form.cleaned_data)
        except OperazioneNonValida as e:
            _errore(request, e)
            return redirect(m)
        messages.success(request, f"Messaggio protocollato con il n. {p.segnatura}.")
        return redirect(p)


class ScartaMessaggioView(PermessoMixin, View):
    permission_required = "protocollo.gestisci_posta"
    http_method_names = ["post"]

    def post(self, request, pk):
        m = get_object_or_404(MessaggioRicevuto, pk=pk)
        try:
            servizi.scarta_messaggio(m, request.user, request.POST.get("motivo", ""))
            messages.success(request, "Messaggio scartato.")
        except OperazioneNonValida as e:
            _errore(request, e)
            return redirect(m)
        return redirect("protocollo:posta")


class AzionePostaView(PermessoMixin, View):
    """Azioni sui messaggi selezionati nell'elenco: scarto (con motivo) o ripristino."""

    permission_required = "protocollo.gestisci_posta"
    http_method_names = ["post"]

    def post(self, request):
        ids = [i for i in request.POST.getlist("messaggi") if i.isdigit()]
        azione = request.POST.get("azione")
        torna = request.POST.get("stato", MessaggioRicevuto.Stato.NUOVO)
        indietro = redirect(f"{reverse('protocollo:posta')}?stato={torna}")
        if not ids:
            messages.warning(request, "Nessun messaggio selezionato.")
            return indietro
        scelti = MessaggioRicevuto.objects.filter(pk__in=ids).order_by("pk")
        try:
            if azione == "scarta":
                motivo = request.POST.get("motivo", "")
                fatti, saltati = servizi.scarta_messaggi(scelti, request.user, motivo)
                testo = f"{fatti} messaggi scartati."
            elif azione == "ripristina":
                fatti, saltati = servizi.ripristina_messaggi(scelti, request.user)
                testo = f"{fatti} messaggi riportati tra quelli da esaminare."
            else:
                return indietro
        except OperazioneNonValida as e:
            _errore(request, e)
            return indietro
        if saltati:
            testo += f" {saltati} saltati perché già gestiti da altri o non nello stato giusto."
        messages.success(request, testo)
        return indietro


class RipristinaMessaggioView(PermessoMixin, View):
    permission_required = "protocollo.gestisci_posta"
    http_method_names = ["post"]

    def post(self, request, pk):
        m = get_object_or_404(MessaggioRicevuto, pk=pk)
        try:
            servizi.ripristina_messaggio(m, request.user)
            messages.success(request, "Messaggio riportato tra quelli da esaminare.")
        except OperazioneNonValida as e:
            _errore(request, e)
        return redirect(m)


class ScaricaMessaggioView(PermessoMixin, View):
    """Il messaggio originale (.eml) o uno dei suoi allegati."""

    permission_required = "protocollo.view_messaggioricevuto"

    def get(self, request, pk, indice=None):
        m = get_object_or_404(MessaggioRicevuto, pk=pk)
        if indice is None:
            return _scarica(m.file_eml, "messaggio.eml", "message/rfc822")
        try:
            a = m.allegati[indice]
        except IndexError:
            raise Http404 from None
        f = default_storage.open(a["percorso"], "rb")
        tipo = servizi.tipo_file(a["nome"])
        risposta = FileResponse(f, as_attachment=True, filename=a["nome"], content_type=tipo)
        risposta["Content-Security-Policy"] = "default-src 'none'; sandbox"
        return risposta


# --- configurazione: caselle e titolario -----------------------------------------------------


class CaselleView(PermessoMixin, ListView):
    permission_required = "protocollo.view_casellaposta"
    model = CasellaPosta
    template_name = "protocollo/caselle.html"
    context_object_name = "caselle"

    def get_context_data(self, **kwargs):
        return super().get_context_data(cifratura=cifratura_disponibile(), **kwargs)


class _ConfigMixin:
    def form_valid(self, form):
        nuovo = form.instance.pk is None
        dettagli = {} if nuovo else campi_modificati(form)
        dettagli.get("campi", {}).pop("nuova_password", None)
        risposta = super().form_valid(form)
        if nuovo:
            registra(Azione.CREAZIONE, self.object)
        elif dettagli.get("campi") or form.cleaned_data.get("nuova_password"):
            registra(Azione.MODIFICA, self.object, **dettagli)
        messages.success(self.request, f"«{self.object}» salvato.")
        return risposta


class CasellaNuovaView(PermessoMixin, _ConfigMixin, CreateView):
    permission_required = "protocollo.add_casellaposta"
    form_class = CasellaForm
    template_name = "protocollo/modulo_config.html"
    success_url = reverse_lazy("protocollo:caselle")
    extra_context = {
        "titolo": "Nuova casella di posta",
        "indietro": reverse_lazy("protocollo:caselle"),
    }


class CasellaModificaView(PermessoMixin, _ConfigMixin, UpdateView):
    permission_required = "protocollo.change_casellaposta"
    model = CasellaPosta
    form_class = CasellaForm
    template_name = "protocollo/modulo_config.html"
    success_url = reverse_lazy("protocollo:caselle")
    extra_context = {"titolo": "Casella di posta", "indietro": reverse_lazy("protocollo:caselle")}


class ClassificazioniView(PermessoMixin, ListView):
    permission_required = "protocollo.view_classificazione"
    model = Classificazione
    template_name = "protocollo/classificazioni.html"
    context_object_name = "voci"


class ClassificazioneNuovaView(PermessoMixin, _ConfigMixin, CreateView):
    permission_required = "protocollo.add_classificazione"
    form_class = ClassificazioneForm
    template_name = "protocollo/modulo_config.html"
    success_url = reverse_lazy("protocollo:classificazioni")
    extra_context = {
        "titolo": "Nuova voce del titolario",
        "indietro": reverse_lazy("protocollo:classificazioni"),
    }


class ClassificazioneModificaView(PermessoMixin, _ConfigMixin, UpdateView):
    permission_required = "protocollo.change_classificazione"
    model = Classificazione
    form_class = ClassificazioneForm
    template_name = "protocollo/modulo_config.html"
    success_url = reverse_lazy("protocollo:classificazioni")
    extra_context = {
        "titolo": "Voce del titolario",
        "indietro": reverse_lazy("protocollo:classificazioni"),
    }
