# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Viste delle comunicazioni: invii (preparazione, anteprima, conferma,
# *              registro), modelli, liste, anniversari e auguri automatici, invii collegati
# *              a riunioni, quote e domande di iscrizione.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import base64
from datetime import date

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count, Prefetch, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import (
    CreateView,
    DetailView,
    FormView,
    ListView,
    TemplateView,
    UpdateView,
)

from apps.anagrafica.models import Soggetto
from apps.core.audit import Azione, campi_modificati, registra
from apps.core.views import PermessoMixin

from . import anniversari, carta, scambio_liste, servizi
from .forms import (
    AutomazioneForm,
    ImportaListaForm,
    InvioForm,
    ListaForm,
    ModelloForm,
    OnomasticoForm,
    PromemoriaRinnovoForm,
    RicorrenzaForm,
)
from .models import (
    Automazione,
    Destinatario,
    Invio,
    Lista,
    Modello,
    Onomastico,
    PromemoriaRinnovo,
    Ricorrenza,
)
from .servizi import OperazioneNonValida


def _errore(request, e):
    messages.error(request, " ".join(e.messages))


# --- invii -------------------------------------------------------------------------------------


class InviiView(PermessoMixin, ListView):
    permission_required = "comunicazioni.view_invio"
    template_name = "comunicazioni/invii.html"
    context_object_name = "invii"
    paginate_by = 30

    def get_queryset(self):
        qs = (
            Invio.objects.annotate(
                n_inviati=Count("destinatari", filter=Q(destinatari__stato="inviato")),
                n_totale=Count("destinatari", filter=~Q(destinatari__stato="escluso")),
            )
            .select_related("creato_da")
            .prefetch_related(
                Prefetch(
                    "destinatari",
                    queryset=Destinatario.objects.select_related("soggetto", "soggetto__socio"),
                )
            )
            .order_by("-creato_il", "-pk")
        )
        if stato := self.request.GET.get("stato"):
            qs = qs.filter(stato=stato)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["stati"] = Invio.Stato.choices
        ctx["stato"] = self.request.GET.get("stato", "")
        ctx["oggi"] = anniversari.eventi(giorni=0)
        return ctx


class InvioNuovoView(PermessoMixin, FormView):
    permission_required = "comunicazioni.add_invio"
    form_class = InvioForm
    template_name = "comunicazioni/invio_nuovo.html"

    def get_initial(self):
        iniziali = {}
        if modello := Modello.objects.filter(pk=self.request.GET.get("modello") or 0).first():
            iniziali.update(modello=modello, oggetto=modello.oggetto, corpo=modello.corpo)
            if modello.uso in ("compleanno", "onomastico", "anzianita", "ricorrenza"):
                iniziali["finalita"] = "auguri"
        if soggetto := Soggetto.objects.filter(pk=self.request.GET.get("soggetto") or 0).first():
            iniziali["soggetti"] = [soggetto]
        if lista := Lista.objects.filter(pk=self.request.GET.get("lista") or 0).first():
            iniziali["liste"] = [lista]
        return iniziali

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        valore = ctx["form"]["soggetti"].value() or []
        ctx["scelti"] = Soggetto.objects.filter(pk__in=[getattr(v, "pk", v) for v in valore])
        ctx["modelli"] = Modello.objects.filter(attivo=True)
        ctx["segnaposto"] = servizi.SEGNAPOSTO
        return ctx

    def form_valid(self, form):
        d = form.cleaned_data
        soggetti = list(d["soggetti"])
        for lista in d["liste"]:
            soggetti += list(servizi.soggetti_lista(lista))
        try:
            invio = servizi.crea_invio(
                self.request.user,
                oggetto=d["oggetto"],
                corpo=d["corpo"],
                finalita=d["finalita"],
                soggetti=soggetti,
                indirizzi=form.indirizzi_validi,
                modello=d["modello"],
                allegati=[(f.name, f.read()) for f in d["allegati"]],
                protocolla=d["protocolla"],
                programmato_il=d["programmato_il"],
                servizio=form.servizio(),
                telegram=d.get("telegram", False),
                sms=d.get("sms", False),
                whatsapp=d.get("whatsapp", False),
                testo_breve=d.get("testo_breve", ""),
            )
        except OperazioneNonValida as e:
            form.add_error(None, e)
            return self.form_invalid(form)
        return redirect(invio)


class CercaSoggettiView(PermessoMixin, TemplateView):
    permission_required = "comunicazioni.add_invio"
    template_name = "comunicazioni/_cerca_soggetti.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        q = self.request.GET.get("cerca", "").strip()
        ctx["risultati"] = Soggetto.objects.attivi().ricerca(q)[:10] if len(q) >= 2 else []
        return ctx


class SceltaSoggettoView(PermessoMixin, TemplateView):
    permission_required = "comunicazioni.add_invio"
    template_name = "comunicazioni/_soggetto_scelto.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["s"] = get_object_or_404(Soggetto, pk=self.request.GET.get("id"))
        return ctx


class InvioView(PermessoMixin, DetailView):
    permission_required = "comunicazioni.view_invio"
    model = Invio
    template_name = "comunicazioni/invio.html"
    context_object_name = "invio"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        inv = self.object
        destinatari = inv.destinatari.select_related("soggetto__socio").prefetch_related("consegne")
        filtro = self.request.GET.get("stato")
        ctx["destinatari"] = destinatari.filter(stato=filtro) if filtro else destinatari
        ctx["conteggi"] = {
            s: inv.destinatari.filter(stato=s).count() for s in Destinatario.Stato.values
        }
        primo = destinatari.filter(stato__in=["in_attesa", "inviato"]).first()
        if primo:
            email = servizi.messaggio(inv, primo)
            ctx["anteprima"] = {"a": email.to[0], "oggetto": email.subject, "testo": email.body}
        ctx["filtro"] = filtro or ""
        ctx["su_carta"] = carta.righe(inv)
        ctx["incompleti"] = [r for r in ctx["su_carta"] if r["Avviso"]]
        ctx["senza_consenso"] = carta.senza_consenso(inv)
        return ctx


class InvioCartaView(PermessoMixin, View):
    """Destinatari senza email: elenco CSV, buste DL in Word, lettere in PDF."""

    permission_required = "comunicazioni.view_invio"
    TIPI = {
        "csv": "text/csv; charset=utf-8",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pdf": "application/pdf",
    }

    def get(self, request, pk, formato):
        invio = get_object_or_404(Invio, pk=pk)
        if formato not in ("csv", "stampa-unione", "buste", "lettere", "etichette"):
            raise Http404
        if not carta.destinatari_su_carta(invio):
            raise Http404("Nessun destinatario su carta per questa comunicazione.")
        if formato == "csv":
            dati, nome = carta.csv(invio, request.user)
        elif formato == "lettere":
            dati, nome = carta.lettere(invio, request.user)
        elif formato == "etichette":
            from apps.protocollo import buste

            foglio = buste.formato_etichette(request.GET.get("foglio"))
            inizio = buste.posizione_iniziale(request.GET.get("inizio"), foglio)
            dati, nome = carta.etichette(invio, request.user, foglio, inizio)
        else:
            dati, nome = carta.docx(invio, request.user, compilate=formato == "buste")
        tipo = self.TIPI[nome.rsplit(".", 1)[1]]
        risposta = HttpResponse(dati, content_type=tipo)
        risposta["Content-Disposition"] = f'attachment; filename="{nome}"'
        risposta["Content-Security-Policy"] = "default-src 'none'; sandbox"
        risposta["X-Content-Type-Options"] = "nosniff"
        return risposta


class _AzioneInvioView(PermessoMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        invio = get_object_or_404(Invio, pk=pk)
        try:
            self.esegui(request, invio)
        except OperazioneNonValida as e:
            _errore(request, e)
        return redirect(invio)


class ConfermaView(_AzioneInvioView):
    permission_required = "comunicazioni.conferma_invio"

    def esegui(self, request, invio):
        invio = servizi.conferma(invio, request.user)
        if invio.programmato_il:
            messages.success(request, "Invio confermato: partirà alla data programmata.")
            return
        # i primi messaggi partono subito, il resto con il pianificatore
        inviati, errori = servizi.elabora_coda(invio=invio)
        invio.refresh_from_db()
        testo = f"Inviati {inviati} messaggi."
        if invio.stato == Invio.Stato.IN_CODA:
            testo += " Gli altri partiranno a breve."
        messages.success(request, testo)
        if errori:
            messages.warning(request, f"{errori} messaggi non partiti: verranno ritentati.")


class AnnullaInvioView(_AzioneInvioView):
    permission_required = "comunicazioni.conferma_invio"

    def esegui(self, request, invio):
        servizi.annulla(invio, request.user)
        messages.success(request, "Invio annullato.")


class RitentaView(_AzioneInvioView):
    permission_required = "comunicazioni.conferma_invio"

    def esegui(self, request, invio):
        n = invio.destinatari.filter(stato=Destinatario.Stato.ERRORE).update(
            stato=Destinatario.Stato.IN_ATTESA, tentativi=0
        )
        if not n:
            raise OperazioneNonValida("Nessun messaggio in errore.")
        Invio.objects.filter(pk=invio.pk).update(stato=Invio.Stato.IN_CODA, completato_il=None)
        inviati, errori = servizi.elabora_coda(invio=invio)
        messages.info(request, f"Ritentati {n}: inviati {inviati}, errori {errori}.")


# --- invii collegati ---------------------------------------------------------------------------


class _DaOrigineView(PermessoMixin, View):
    permission_required = "comunicazioni.add_invio"
    http_method_names = ["post"]

    def post(self, request, pk):
        oggetto = self.oggetto(pk)
        try:
            invio = self.crea(oggetto, request.user)
        except OperazioneNonValida as e:
            _errore(request, e)
            return redirect(self.ritorno(oggetto))
        messages.info(request, "Controllare l'anteprima e confermare l'invio.")
        return redirect(invio)

    def ritorno(self, oggetto):
        return oggetto


class DaRiunioneView(_DaOrigineView):
    permission_required = ("comunicazioni.add_invio", "organi.view_riunione")

    def oggetto(self, pk):
        from apps.organi.models import Riunione

        r = get_object_or_404(Riunione, pk=pk)
        if r.stato != Riunione.Stato.CONVOCATA:
            raise Http404
        return r

    def crea(self, r, utente):
        return servizi.da_riunione(r, utente)


class DaTesseraView(_DaOrigineView):
    permission_required = ("comunicazioni.add_invio", "soci.view_tessera")

    def oggetto(self, pk):
        from apps.soci import sezioni
        from apps.soci.models import Tessera

        t = get_object_or_404(Tessera.objects.select_related("socio__soggetto"), pk=pk)
        sezioni.controlla(self.request.user, t.socio.sezione_id)
        return t

    def crea(self, t, utente):
        return servizi.da_tessera(t, utente)

    def ritorno(self, t):
        return t.socio


class DaTesseraDigitaleView(DaTesseraView):
    def crea(self, t, utente):
        return servizi.da_tessera_digitale(t, utente, self.request.build_absolute_uri("/"))


class DaDomandaView(_DaOrigineView):
    permission_required = ("comunicazioni.add_invio", "soci.view_domandaiscrizione")

    def oggetto(self, pk):
        from apps.soci import sezioni
        from apps.soci.models import DomandaIscrizione

        d = get_object_or_404(DomandaIscrizione, pk=pk)
        sezioni.controlla(self.request.user, d.sezione_id)
        return d

    def crea(self, d, utente):
        return servizi.da_domanda(d, utente)


# --- modelli e liste -----------------------------------------------------------------------------


class _ConfigMixin:
    def form_valid(self, form):
        nuovo = form.instance.pk is None
        dettagli = {} if nuovo else campi_modificati(form)
        risposta = super().form_valid(form)
        registra(Azione.CREAZIONE if nuovo else Azione.MODIFICA, self.object, **dettagli)
        messages.success(self.request, f"«{self.object}» salvato.")
        return risposta


class ModelliView(PermessoMixin, ListView):
    permission_required = "comunicazioni.view_modello"
    model = Modello
    template_name = "comunicazioni/modelli.html"
    context_object_name = "modelli"


class ModelloNuovoView(PermessoMixin, _ConfigMixin, CreateView):
    permission_required = "comunicazioni.add_modello"
    form_class = ModelloForm
    template_name = "comunicazioni/modulo.html"
    success_url = reverse_lazy("comunicazioni:modelli")
    extra_context = {"titolo": "Nuovo modello", "indietro": reverse_lazy("comunicazioni:modelli")}

    def get_initial(self):
        return {"uso": self.request.GET.get("uso", "generico")}


class ModelloModificaView(PermessoMixin, _ConfigMixin, UpdateView):
    permission_required = "comunicazioni.change_modello"
    model = Modello
    form_class = ModelloForm
    template_name = "comunicazioni/modulo.html"
    success_url = reverse_lazy("comunicazioni:modelli")
    extra_context = {"titolo": "Modello", "indietro": reverse_lazy("comunicazioni:modelli")}


class ListeView(PermessoMixin, ListView):
    permission_required = "comunicazioni.view_lista"
    model = Lista
    template_name = "comunicazioni/liste.html"
    context_object_name = "liste"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        for lista in ctx["liste"]:
            lista.n_membri = servizi.soggetti_lista(lista).count()
        return ctx


class ListaView(PermessoMixin, DetailView):
    permission_required = "comunicazioni.view_lista"
    model = Lista
    template_name = "comunicazioni/lista.html"
    context_object_name = "lista"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["membri"] = servizi.soggetti_lista(self.object).order_by(
            "cognome", "denominazione", "nome"
        )
        return ctx


class _ListaMixin(_ConfigMixin):
    form_class = ListaForm
    template_name = "comunicazioni/lista_modulo.html"

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "utente": self.request.user}

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        valore = ctx["form"]["soggetti"].value() or []
        ctx["scelti"] = Soggetto.objects.filter(pk__in=[getattr(v, "pk", v) for v in valore])
        return ctx


class ListaNuovaView(PermessoMixin, _ListaMixin, CreateView):
    permission_required = "comunicazioni.add_lista"


class ListaModificaView(PermessoMixin, _ListaMixin, UpdateView):
    permission_required = "comunicazioni.change_lista"
    model = Lista


class ListaEsportaView(PermessoMixin, View):
    """La lista in Excel, da modificare fuori linea e reimportare."""

    permission_required = "comunicazioni.view_lista"

    def get(self, request, pk):
        from django.utils.text import slugify

        lista = get_object_or_404(Lista, pk=pk)
        contenuto = scambio_liste.esporta(lista, request.user)
        nome = f"lista_{slugify(lista.nome) or lista.pk}_{date.today():%Y%m%d}.xlsx"
        risposta = HttpResponse(contenuto, content_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))  # fmt: skip
        risposta["Content-Disposition"] = f'attachment; filename="{nome}"'
        risposta["Content-Security-Policy"] = "default-src 'none'; sandbox"
        return risposta


class ListaEtichetteView(PermessoMixin, View):
    """Etichette adesive (PDF) per i membri della lista con un indirizzo postale completo."""

    permission_required = "comunicazioni.view_lista"

    def get(self, request, pk):
        from django.utils.text import slugify

        from apps.protocollo import buste

        lista = get_object_or_404(Lista, pk=pk)
        foglio = buste.formato_etichette(request.GET.get("foglio"))
        inizio = buste.posizione_iniziale(request.GET.get("inizio"), foglio)
        righe = [
            buste.riga_busta(
                s.intestazione, s.qualifica, s.indirizzo, s.cap, s.comune, s.provincia
            )  # fmt: skip
            for s in servizi.soggetti_lista(lista).order_by("cognome", "denominazione", "nome")
        ]
        dati, n, scartate = buste.pdf_etichette(righe, foglio, inizio)
        registra(Azione.ESPORTAZIONE, lista, descrizione=f"Etichette della lista «{lista}»",
                 etichette=n, senza_indirizzo=scartate, formato=foglio)  # fmt: skip
        nome = f"etichette_{slugify(lista.nome) or lista.pk}.pdf"
        risposta = HttpResponse(dati, content_type="application/pdf")
        risposta["Content-Disposition"] = f'attachment; filename="{nome}"'
        risposta["Content-Security-Policy"] = "default-src 'none'; sandbox"
        return risposta


class TelegramInvitoView(PermessoMixin, TemplateView):
    """Link personale (e QR) per collegarsi al bot: da mandare o stampare per la persona."""

    permission_required = "anagrafica.change_soggetto"
    template_name = "comunicazioni/telegram_invito.html"

    def get_context_data(self, **kwargs):
        from apps.core.models import CanaleTelegram
        from apps.patrimonio.servizi import qr_svg

        from . import telegram

        ctx = super().get_context_data(**kwargs)
        soggetto = get_object_or_404(Soggetto, pk=self.kwargs["pk"])
        if not CanaleTelegram.corrente().pronto:
            raise Http404("Telegram non è attivo.")
        link = telegram.link_invito(soggetto)
        ctx.update(soggetto=soggetto, link=link, qr=qr_svg(link),
                   bot=CanaleTelegram.corrente().nome_bot)  # fmt: skip
        return ctx


class WhatsAppConsensoView(PermessoMixin, View):
    """Registra o ritira il consenso della persona a ricevere messaggi su WhatsApp."""

    permission_required = "anagrafica.change_soggetto"
    http_method_names = ["post"]

    def post(self, request, pk):
        from django.utils import timezone

        soggetto = get_object_or_404(Soggetto, pk=pk)
        consenso = request.POST.get("consenso") == "on"
        soggetto.whatsapp_consenso_il = timezone.now() if consenso else None
        soggetto.save(update_fields=["whatsapp_consenso_il"])
        registra(Azione.MODIFICA, soggetto, whatsapp_consenso=consenso)
        stato = "registrato" if consenso else "ritirato"
        messages.success(request, f"Consenso WhatsApp {stato} per {soggetto}.")
        return redirect(soggetto)


class TelegramScollegaView(PermessoMixin, View):
    permission_required = "anagrafica.change_soggetto"
    http_method_names = ["post"]

    def post(self, request, pk):
        from . import telegram

        soggetto = get_object_or_404(Soggetto, pk=pk)
        telegram.scollega(soggetto, request.user)
        messages.success(request, f"Telegram scollegato per {soggetto}.")
        return redirect(soggetto)


class ListaImportaView(PermessoMixin, FormView):
    """Caricamento del file Excel, anteprima (nulla viene salvato) e conferma."""

    permission_required = "comunicazioni.change_lista"
    form_class = ImportaListaForm
    template_name = "comunicazioni/lista_importa.html"
    CHIAVE = "importa_lista"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["puo_creare_schede"] = self.request.user.has_perm("anagrafica.add_soggetto")
        return kwargs

    def _prepara(self, contenuto, crea_schede):
        piano = scambio_liste.prepara(
            scambio_liste.leggi(contenuto), crea_schede=crea_schede, utente=self.request.user
        )
        if piano.nuova and not self.request.user.has_perm("comunicazioni.add_lista"):
            raise scambio_liste.FileNonValido("Non si possono creare liste nuove.")
        return piano

    def form_valid(self, form):
        contenuto = form.cleaned_data["file"].read()
        crea = bool(form.cleaned_data.get("crea_schede"))
        try:
            piano = self._prepara(contenuto, crea)
        except scambio_liste.FileNonValido as e:
            form.add_error("file", e)
            return self.form_invalid(form)
        self.request.session[self.CHIAVE] = {
            "contenuto": base64.b64encode(contenuto).decode("ascii"),
            "nome": form.cleaned_data["file"].name,
            "crea_schede": crea,
        }
        return self.render_to_response(self.get_context_data(
            piano=piano, conteggi=piano.riepilogo(), nome_file=form.cleaned_data["file"].name
        ))  # fmt: skip

    def post(self, request, *args, **kwargs):
        if request.POST.get("azione") != "esegui":
            return super().post(request, *args, **kwargs)
        dati = request.session.pop(self.CHIAVE, None)
        if not dati:
            messages.error(request, "Anteprima scaduta: caricare di nuovo il file.")
            return redirect("comunicazioni:lista_importa")
        try:
            piano = self._prepara(base64.b64decode(dati["contenuto"]), dati["crea_schede"])
            lista, creati = scambio_liste.applica(piano, request.user)
        except ValidationError as e:
            _errore(request, e)
            return redirect("comunicazioni:lista_importa")
        testo = f"Lista «{lista}» importata."
        if creati:
            testo += f" {creati} schede nuove in anagrafica."
        messages.success(request, testo)
        return redirect(lista)


# --- anniversari -------------------------------------------------------------------------------


class AnniversariView(PermessoMixin, TemplateView):
    permission_required = "comunicazioni.view_ricorrenza"
    template_name = "comunicazioni/anniversari.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        try:
            giorni = min(max(int(self.request.GET.get("giorni", 30)), 1), 366)
        except ValueError:
            giorni = 30
        tipi = [t for t in self.request.GET.getlist("tipo") if t in anniversari.TIPI] or None
        eventi = anniversari.eventi(giorni=giorni, tipi=tipi)
        per_giorno = {}
        for e in eventi:
            per_giorno.setdefault(e.data, []).append(e)
        ctx.update(
            giorni=giorni,
            per_giorno=sorted(per_giorno.items()),
            tipi=anniversari.TIPI,
            tipi_scelti=tipi or list(anniversari.TIPI),
            oggi=date.today(),
            modelli={m.uso: m for m in Modello.objects.filter(attivo=True).order_by("-pk")},
        )
        return ctx


class AuguriView(PermessoMixin, TemplateView):
    """Auguri automatici, ricorrenze e calendario degli onomastici."""

    permission_required = "comunicazioni.view_ricorrenza"
    template_name = "comunicazioni/auguri.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["automazioni"] = Automazione.objects.select_related("modello")
        ctx["ricorrenze"] = Ricorrenza.objects.select_related("lista", "modello")
        ctx["n_onomastici"] = Onomastico.objects.count()
        return ctx


class AutomazioneView(PermessoMixin, _ConfigMixin, UpdateView):
    permission_required = "comunicazioni.change_automazione"
    model = Automazione
    form_class = AutomazioneForm
    template_name = "comunicazioni/modulo.html"
    success_url = reverse_lazy("comunicazioni:auguri")
    extra_context = {
        "titolo": "Auguri automatici",
        "indietro": reverse_lazy("comunicazioni:auguri"),
    }


class RicorrenzaNuovaView(PermessoMixin, _ConfigMixin, CreateView):
    permission_required = "comunicazioni.add_ricorrenza"
    form_class = RicorrenzaForm
    template_name = "comunicazioni/modulo.html"
    success_url = reverse_lazy("comunicazioni:auguri")
    extra_context = {"titolo": "Nuova ricorrenza", "indietro": reverse_lazy("comunicazioni:auguri")}


class RicorrenzaModificaView(PermessoMixin, _ConfigMixin, UpdateView):
    permission_required = "comunicazioni.change_ricorrenza"
    model = Ricorrenza
    form_class = RicorrenzaForm
    template_name = "comunicazioni/modulo.html"
    success_url = reverse_lazy("comunicazioni:auguri")
    extra_context = {"titolo": "Ricorrenza", "indietro": reverse_lazy("comunicazioni:auguri")}


class OnomasticiView(PermessoMixin, ListView):
    permission_required = "comunicazioni.view_onomastico"
    model = Onomastico
    template_name = "comunicazioni/onomastici.html"
    context_object_name = "onomastici"

    def get_queryset(self):
        qs = super().get_queryset()
        if q := self.request.GET.get("q", "").strip():
            qs = qs.filter(nome__icontains=anniversari.normalizza_nome(q))
        return qs


class OnomasticoNuovoView(PermessoMixin, _ConfigMixin, CreateView):
    permission_required = "comunicazioni.add_onomastico"
    form_class = OnomasticoForm
    template_name = "comunicazioni/modulo.html"
    success_url = reverse_lazy("comunicazioni:onomastici")
    extra_context = {
        "titolo": "Nuovo onomastico",
        "indietro": reverse_lazy("comunicazioni:onomastici"),
    }


class OnomasticoModificaView(PermessoMixin, _ConfigMixin, UpdateView):
    permission_required = "comunicazioni.change_onomastico"
    model = Onomastico
    form_class = OnomasticoForm
    template_name = "comunicazioni/modulo.html"
    success_url = reverse_lazy("comunicazioni:onomastici")
    extra_context = {"titolo": "Onomastico", "indietro": reverse_lazy("comunicazioni:onomastici")}


class PromemoriaRinnovoView(PermessoMixin, UpdateView):
    """Impostazioni dei promemoria di rinnovo, soci da sollecitare e ultimi invii."""

    permission_required = "comunicazioni.view_promemoriarinnovo"
    form_class = PromemoriaRinnovoForm
    template_name = "comunicazioni/promemoria_rinnovo.html"
    success_url = reverse_lazy("comunicazioni:promemoria_rinnovo")

    def get_object(self, queryset=None):
        return PromemoriaRinnovo.corrente()

    def post(self, request, *args, **kwargs):
        if not request.user.has_perm("comunicazioni.change_promemoriarinnovo"):
            raise PermissionDenied
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        dettagli = campi_modificati(form)
        risposta = super().form_valid(form)
        registra(Azione.MODIFICA, self.object, **dettagli)
        messages.success(self.request, "Promemoria di rinnovo salvati.")
        return risposta

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        anno = date.today().year
        soci = servizi.soci_da_sollecitare(anno)
        ctx.update(
            anno=anno,
            da_sollecitare=len(soci),
            senza_email=sum(1 for s, _c in soci if not s.soggetto.email),
            invii=Invio.objects.filter(origine="rinnovo").order_by("-creato_il")[:10],
        )
        return ctx


class PromemoriaPreparaView(PermessoMixin, View):
    """Prepara subito il promemoria in bozza, da controllare e confermare."""

    permission_required = ("comunicazioni.view_promemoriarinnovo", "comunicazioni.add_invio")

    def post(self, request):
        try:
            invio = servizi.promemoria_rinnovo(utente=request.user, subito=True)
        except OperazioneNonValida as e:
            messages.error(request, " ".join(e.messages))
            return redirect("comunicazioni:promemoria_rinnovo")
        messages.success(
            request, "Promemoria preparato in bozza: controllare e confermare l'invio."
        )
        return redirect("comunicazioni:invio", invio.pk)
