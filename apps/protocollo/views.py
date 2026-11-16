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

from . import buste, servizi, spedizioni
from .filtri import ProtocolloFilter
from .forms import (
    AllegatiForm,
    CasellaForm,
    ClassificazioneForm,
    ManualeGestioneForm,
    ModelloProtocolloForm,
    ModificaForm,
    ProtocollaMessaggioForm,
    ProtocolloForm,
    SpedizioneForm,
)
from .models import (
    Allegato,
    CasellaPosta,
    Classificazione,
    ManualeGestione,
    MessaggioRicevuto,
    ModelloProtocollo,
    Protocollo,
    RegistroGiornaliero,
    Spedizione,
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
        if buste.con_buste(p):
            righe = buste.righe_destinatari(p)
            ctx["spedizione"] = [r for r in righe if r["Avviso"]]
            ctx["su_carta"] = len(righe) if buste.solo_senza_email(p) else None
        ctx["spedizioni"] = p.spedizioni.select_related("casella", "creato_da").prefetch_related(
            "destinatari", "allegati"
        )
        ctx["puo_spedire"] = spedizioni.puo_spedire(p) and self.request.user.has_perm(
            spedizioni.PERMESSO
        )
        ctx["invio_attivo"] = spedizioni.invio_attivo()
        if self.request.user.has_perm("core.view_eventoaudit"):
            ctx["storia"] = EventoAudit.objects.filter(
                oggetto_tipo=ContentType.objects.get_for_model(Protocollo), oggetto_id=str(p.pk)
            )[:30]
        return ctx


class NuovoView(PermessoMixin, FormView):
    permission_required = "protocollo.add_protocollo"
    form_class = ProtocolloForm
    template_name = "protocollo/nuovo.html"

    def _modello(self):
        pk = self.request.GET.get("modello", "")
        if pk.isdigit():
            return ModelloProtocollo.objects.filter(pk=pk, attivo=True).first()
        return None

    def get_initial(self):
        iniziali = {"direzione": self.request.GET.get("direzione", Protocollo.Direzione.ENTRATA)}
        if modello := self._modello():
            iniziali.update(modello.valori())
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
        ctx["modelli"] = ModelloProtocollo.objects.filter(attivo=True)
        ctx["modello_scelto"] = self._modello()
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


class SpedizioneView(PermessoMixin, _ProtocolloVisibileMixin, View):
    """Destinatari in CSV e buste DL in Word per le spedizioni su carta."""

    permission_required = "protocollo.view_protocollo"
    TIPI = {
        "csv": "text/csv; charset=utf-8",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }

    def get(self, request, pk, formato):
        p = self.protocollo(pk)
        if formato not in ("csv", "stampa-unione", "buste") or not buste.con_buste(p):
            raise Http404("Nessuna spedizione su carta per questo protocollo.")
        if formato == "csv":
            dati, nome = buste.csv_destinatari(p, request.user)
            tipo = self.TIPI["csv"]
        else:
            dati, nome = buste.docx_buste(p, request.user, compilate=formato == "buste")
            tipo = self.TIPI["docx"]
        risposta = HttpResponse(dati, content_type=tipo)
        risposta["Content-Disposition"] = f'attachment; filename="{nome}"'
        risposta["Content-Security-Policy"] = "default-src 'none'; sandbox"
        risposta["X-Content-Type-Options"] = "nosniff"
        return risposta


class SpedisciView(PermessoMixin, _ProtocolloVisibileMixin, TemplateView):
    """Spedizione per email o PEC di un protocollo in uscita."""

    permission_required = spedizioni.PERMESSO
    template_name = "protocollo/spedisci.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.has_perm(self.permission_required):
            self.p = self.protocollo(kwargs["pk"])
            if not spedizioni.puo_spedire(self.p):
                messages.error(request, "Si spediscono solo i protocolli in uscita non annullati.")
                return redirect(self.p)
        return super().dispatch(request, *args, **kwargs)

    def _casella(self, valore):
        caselle = list(spedizioni.caselle_invio())
        if valore is None:  # proposta: la PEC se il protocollo è per PEC, altrimenti l'email
            pec = self.p.mezzo == Protocollo.Mezzo.PEC
            scelta = next((c for c in caselle if c.pec == pec), None)
            return caselle, scelta
        return caselle, next((c for c in caselle if str(c.pk) == str(valore)), None)

    def _form(self, dati=None, valore=None):
        caselle, casella = self._casella(valore)
        proposti = spedizioni.indirizzi_proposti(self.p, pec=bool(casella and casella.pec))
        iniziali = {
            "da": str(casella.pk) if casella else "",
            "testo": spedizioni.testo_proposto(self.p),
            "documenti": list(self.p.allegati.values_list("pk", flat=True)),
        }
        if self.request.htmx and dati is None:  # ricarica per il cambio di casella
            iniziali["testo"] = self.request.GET.get("testo") or iniziali["testo"]
            iniziali["documenti"] = self.request.GET.getlist("documenti") or iniziali["documenti"]
        form = SpedizioneForm(
            dati, initial=iniziali, protocollo=self.p, caselle=caselle, proposti=proposti,
            url_ricarica=reverse("protocollo:spedisci", args=[self.p.pk]),
        )  # fmt: skip
        return form, casella

    def get(self, request, *args, **kwargs):
        form, _ = self._form(valore=request.GET.get("da"))
        return self.render_to_response(self.get_context_data(form=form))

    def post(self, request, *args, **kwargs):
        form, casella = self._form(request.POST, valore=request.POST.get("da", ""))
        if form.is_valid():
            try:
                sped = spedizioni.prepara_spedizione(
                    self.p, request.user, casella=casella, destinatari=form.destinatari(),
                    testo=form.cleaned_data["testo"], allegati=form.cleaned_data["documenti"],
                )  # fmt: skip
            except OperazioneNonValida as e:
                _errore(request, e)
            else:
                _esito_spedizione(request, sped)
                return redirect(self.p)
        return self.render_to_response(self.get_context_data(form=form))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            protocollo=self.p,
            invio_attivo=spedizioni.invio_attivo(),
            massimo_mb=settings.PROTOCOLLO_SPEDIZIONE_MAX_MB,
        )
        return ctx


def _esito_spedizione(request, sped):
    """Invio immediato (se l'invio è acceso), con l'esito per l'utente."""
    totale = sped.destinatari.count()
    if not spedizioni.invio_attivo():
        messages.warning(request, f"Spedizione in coda ({totale} destinatari): l'invio delle "
                                  "email è spento in Sistema → Servizi di posta.")  # fmt: skip
        return
    inviati, errori = spedizioni.spedisci(sped)
    if errori:
        messages.error(request, f"Spediti {inviati} messaggi su {totale}; {errori} non riusciti: "
                                "si riprova in automatico, l'errore è nella scheda.")  # fmt: skip
    else:
        canale = sped.get_canale_display()
        seguito = " Le ricevute di accettazione e consegna si aggiungono da sole." if sped.canale \
            == Spedizione.Canale.PEC else ""  # fmt: skip
        messages.success(request, f"{canale} spedita a {inviati} destinatari.{seguito}")


class RiprovaSpedizioneView(PermessoMixin, View):
    permission_required = spedizioni.PERMESSO
    http_method_names = ["post"]

    def post(self, request, pk):
        sped = get_object_or_404(
            Spedizione.objects.select_related("protocollo"),
            pk=pk,
            protocollo__in=Protocollo.objects.visibili_a(request.user),
        )
        try:
            spedizioni.riprova(sped, request.user)
        except OperazioneNonValida as e:
            _errore(request, e)
        else:
            _esito_spedizione(request, sped)
        return redirect(sped.protocollo)


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
        from apps.soci.estrazione import probabile_iscrizione

        ctx["iscrizioni"] = {
            m.pk
            for m in ctx["messaggi"]
            if m.stato == MessaggioRicevuto.Stato.NUOVO and probabile_iscrizione(m)
        }
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
        from apps.soci.estrazione import probabile_iscrizione

        ctx["probabile_iscrizione"] = probabile_iscrizione(m)
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


class ModelliView(PermessoMixin, ListView):
    permission_required = "protocollo.view_modelloprotocollo"
    template_name = "protocollo/modelli.html"
    context_object_name = "modelli"

    def get_queryset(self):
        return ModelloProtocollo.objects.select_related("classificazione").prefetch_related("liste")


class ModelloNuovoView(PermessoMixin, _ConfigMixin, CreateView):
    permission_required = "protocollo.add_modelloprotocollo"
    form_class = ModelloProtocolloForm
    template_name = "protocollo/modulo_config.html"
    success_url = reverse_lazy("protocollo:modelli")
    extra_context = {
        "titolo": "Nuovo modello di registrazione",
        "indietro": reverse_lazy("protocollo:modelli"),
    }


class ModelloModificaView(PermessoMixin, _ConfigMixin, UpdateView):
    permission_required = "protocollo.change_modelloprotocollo"
    model = ModelloProtocollo
    form_class = ModelloProtocolloForm
    template_name = "protocollo/modulo_config.html"
    success_url = reverse_lazy("protocollo:modelli")
    extra_context = {
        "titolo": "Modello di registrazione",
        "indietro": reverse_lazy("protocollo:modelli"),
    }


# --- manuale di gestione documentale ---------------------------------------------------------


class ManualeGestioneView(PermessoMixin, UpdateView):
    """Dati organizzativi del manuale; il resto si compone dalla configurazione reale."""

    permission_required = "protocollo.view_manualegestione"
    form_class = ManualeGestioneForm
    template_name = "protocollo/manuale.html"

    def get_object(self, queryset=None):
        return ManualeGestione.corrente()

    def get_context_data(self, **kwargs):
        from . import manuale

        return super().get_context_data(
            versioni=manuale.versioni(), pubblicato=manuale.pubblicato(), **kwargs
        )

    def post(self, request, *args, **kwargs):
        if not request.user.has_perm("protocollo.gestisci_manuale"):
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        dettagli = campi_modificati(form)
        risposta = super().form_valid(form)
        if dettagli.get("campi"):
            registra(Azione.MODIFICA, self.object, **dettagli)
        messages.success(self.request, "Dati del manuale salvati.")
        return risposta

    def get_success_url(self):
        return reverse("protocollo:manuale")


class ManualeGestionePdfView(PermessoMixin, View):
    """Bozza aggiornata alla configurazione di oggi (la versione adottata è nel protocollo)."""

    permission_required = "protocollo.view_protocollo"

    def get(self, request):
        from . import manuale

        risposta = HttpResponse(manuale.pdf(bozza=True), content_type="application/pdf")
        risposta["Content-Disposition"] = 'inline; filename="manuale_gestione_bozza.pdf"'
        return risposta


class ManualeGestioneAdottaView(PermessoMixin, View):
    permission_required = "protocollo.gestisci_manuale"
    http_method_names = ["post"]

    def post(self, request):
        from . import manuale

        try:
            m = manuale.adotta(request.user, pubblica=request.POST.get("pubblica") == "on")
        except OperazioneNonValida as e:
            _errore(request, e)
            return redirect("protocollo:manuale")
        messages.success(
            request,
            f"Manuale adottato (versione {m.versione}), protocollo n. {m.protocollo.segnatura}.",
        )
        return redirect("protocollo:manuale")


class VersioneManualeView(PermessoMixin, View):
    """PDF di una versione adottata: consultabile da tutti gli utenti."""

    permission_required = "protocollo.view_manualegestione"

    def get(self, request, versione):
        from .models import VersioneManuale

        v = get_object_or_404(VersioneManuale.objects.select_related("allegato"), versione=versione)
        return _scarica(v.allegato.file, v.allegato.nome, "application/pdf", in_linea=True)


class PubblicazioneManualeView(PermessoMixin, View):
    """Pubblica la versione in vigore fra i documenti pubblici, oppure la ritira."""

    permission_required = "protocollo.gestisci_manuale"
    http_method_names = ["post"]

    def post(self, request):
        from . import manuale

        if request.POST.get("azione") == "ritira":
            manuale.ritira(request.user)
            messages.success(request, "Manuale tolto dalla pagina dei documenti pubblici.")
            return redirect("protocollo:manuale")
        try:
            v = manuale.pubblica_in_vigore(request.user)
        except OperazioneNonValida as e:
            _errore(request, e)
        else:
            messages.success(request, f"Versione {v.versione} pubblicata fra i documenti pubblici.")
        return redirect("protocollo:manuale")
