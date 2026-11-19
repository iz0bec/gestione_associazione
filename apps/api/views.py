# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Sistema → Collegamenti API: identità dell'istanza, controparti, inviti,
# *              abbinamento con un invito ricevuto, conferma dell'impronta, prova del collegamento.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, FormView, ListView, UpdateView

from apps.core.audit import Azione, campi_modificati, registra
from apps.core.cifratura import cifratura_disponibile
from apps.core.views import PermessoMixin

from . import chiavi, feed, rappresentazioni, servizi
from .endpoint import impronte_tls
from .forms import ControparteForm, InvitoForm, UsaInvitoForm
from .models import AMBITI, ClienteApi, VerificaSoci


def _indirizzo_istanza(request):
    return request.build_absolute_uri("/").rstrip("/")


class ControparteElencoView(PermessoMixin, ListView):
    permission_required = "api.view_clienteapi"
    template_name = "api/elenco.html"
    context_object_name = "controparti"

    def get_queryset(self):
        return ClienteApi.objects.all().order_by("stato", "nome")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cifratura"] = cifratura_disponibile()
        if ctx["cifratura"]:
            ctx.update(
                istanza=chiavi.istanza(),
                jwks=chiavi.jwks()["keys"],
                tls_spki=impronte_tls(),
                indirizzo=_indirizzo_istanza(self.request),
                flussi=[(nome, feed.ultimo(nome)) for nome in rappresentazioni.FLUSSI],
            )
        ctx["https"] = self.request.is_secure()
        return ctx


class _ConCifratura:
    def dispatch(self, request, *args, **kwargs):
        if not cifratura_disponibile():
            messages.error(request, "Manca la chiave di cifratura (CHIAVE_CIFRATURA).")
            return redirect("api:elenco")
        return super().dispatch(request, *args, **kwargs)


def _mostra_codice(request, cliente, codice):
    """Il codice si mostra una volta sola (mai in URL, sessione o registro)."""
    return render(request, "api/invito.html", {
        "cliente": cliente, "codice": codice, "indirizzo": _indirizzo_istanza(request),
        "validita_ore": int(servizi.VALIDITA_INVITO.total_seconds() // 3600),
    })  # fmt: skip


class InvitoNuovoView(PermessoMixin, _ConCifratura, FormView):
    permission_required = "api.gestisci_controparti"
    template_name = "api/invito_nuovo.html"
    form_class = InvitoForm

    def form_valid(self, form):
        d = form.cleaned_data
        cliente, codice = servizi.crea_invito(
            self.request.user, nome=d["nome"], tipo=d["tipo"], ambiti=d["ambiti"],
            note=d["note"], dati_personali_confermati=d["dati_personali"],
        )  # fmt: skip
        return _mostra_codice(self.request, cliente, codice)


class UsaInvitoView(PermessoMixin, _ConCifratura, FormView):
    permission_required = "api.gestisci_controparti"
    template_name = "api/usa_invito.html"
    form_class = UsaInvitoForm

    def form_valid(self, form):
        from apps.collegamenti import client

        d = form.cleaned_data
        try:
            cliente = client.abbina(
                self.request.user, codice=d["codice"], nome=d["nome"], ambiti=d["ambiti"],
                indirizzo_pubblico=d["indirizzo_pubblico"],
                indirizzo_interno=d["indirizzo_interno"], rete_interna=d["rete_interna"],
                verifica_tls=d["verifica_tls"], ca_pem=d["ca_pem"],
                tls_spki=d["tls_spki"], http_in_chiaro=d["http_in_chiaro"],
            )  # fmt: skip
        except (
            client.ErroreCollegamento,
            client.ErroreTrasporto,
            servizi.OperazioneNonValida,
        ) as e:
            form.add_error(None, str(e))
            return self.form_invalid(form)
        messages.success(
            self.request,
            "Abbinamento registrato. Confrontate l'impronta con l'altra installazione, "
            "poi attivate.",
        )
        return redirect("api:controparte", pk=cliente.pk)


class ControparteView(PermessoMixin, DetailView):
    permission_required = "api.view_clienteapi"
    template_name = "api/controparte.html"
    model = ClienteApi
    context_object_name = "cliente"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            ambiti=[(a, AMBITI[a]) for a in self.object.ambiti if a in AMBITI],
            chiamate=self.object.chiamate.all()[:20],
            invito_aperto=self.object.inviti.filter(usato_il__isnull=True).first(),
            adesso=timezone.now(),
            notifiche_in_coda=self.object.notifiche.filter(stato="in_coda").count(),
            adesioni_ricevute=self.object.adesioni.count(),
            domande_ricevute=self.object.domande.count(),
            verifiche_soci=self.object.verifiche_soci.select_related("creata_da")[:5],
            notifiche_fallite=self.object.notifiche.filter(stato="fallita")
            .select_related("cambiamento")
            .order_by("-prossimo_tentativo")[:10],
        )
        return ctx


class ControparteModificaView(PermessoMixin, UpdateView):
    permission_required = "api.gestisci_controparti"
    template_name = "api/modifica.html"
    model = ClienteApi
    form_class = ControparteForm
    context_object_name = "cliente"

    def get_queryset(self):
        return ClienteApi.objects.exclude(stato=ClienteApi.Stato.REVOCATA)

    def form_valid(self, form):
        dettagli = campi_modificati(form)
        risposta = super().form_valid(form)
        if dettagli.get("campi"):
            registra(Azione.MODIFICA, self.object, **dettagli)
        messages.success(self.request, "Controparte aggiornata.")
        return risposta

    def get_success_url(self):
        return reverse("api:controparte", args=[self.object.pk])


class ControparteAzioneView(PermessoMixin, View):
    permission_required = "api.gestisci_controparti"
    AZIONI = {"attiva", "sospendi", "riattiva", "revoca", "prova", "invito", "aggiorna",
              "riprova_notifiche"}  # fmt: skip

    def post(self, request, pk, azione):
        cliente = get_object_or_404(ClienteApi, pk=pk)
        if azione not in self.AZIONI:
            return redirect("api:controparte", pk=pk)
        try:
            if azione == "attiva":
                confermata = request.POST.get("impronta_confermata") == "1"
                servizi.attiva(cliente, request.user, impronta_confermata=confermata)
                messages.success(request, f"{cliente} attivata.")
            elif azione == "sospendi":
                servizi.sospendi(cliente, request.user, request.POST.get("motivo", "")[:200])
                messages.success(request, f"{cliente} sospesa.")
            elif azione == "riattiva":
                servizi.riattiva(cliente, request.user)
                messages.success(request, f"{cliente} riattivata.")
            elif azione == "revoca":
                servizi.revoca(cliente, request.user)
                messages.success(request, f"{cliente} revocata.")
            elif azione == "invito":
                if not cifratura_disponibile():
                    raise servizi.OperazioneNonValida("Manca la chiave di cifratura.")
                return _mostra_codice(request, cliente, servizi.nuovo_invito(cliente, request.user))
            elif azione == "riprova_notifiche":
                n = servizi.riprova_notifiche(cliente, request.user)
                messages.success(request, f"Notifiche rimesse in coda: {n}.")
            elif azione == "aggiorna":
                from apps.collegamenti import client

                cambiate, esito = client.aggiorna_identita(cliente)
                (messages.success if cambiate else messages.info)(request, esito)
            elif azione == "prova":
                from apps.collegamenti import client

                riuscita, esito = client.prova(cliente)
                (messages.success if riuscita else messages.error)(request, esito)
        except servizi.OperazioneNonValida as e:
            messages.error(request, str(e))
        return redirect("api:controparte", pk=pk)


class RuotaChiaviView(PermessoMixin, _ConCifratura, View):
    permission_required = "api.gestisci_controparti"

    def post(self, request):
        servizi.ruota_chiavi(request.user)
        messages.success(
            request,
            "Chiavi nuove in uso; le precedenti restano valide "
            f"{chiavi.SOVRAPPOSIZIONE_GIORNI} giorni.",
        )
        return redirect("api:elenco")


class VerificaSociNuovaView(PermessoMixin, View):
    """Legge i soci della sezione presso la controparte e prepara la verifica."""

    permission_required = "soci.importa_soci"

    def post(self, request, pk):
        from apps.collegamenti import soci as verifica_soci
        from apps.soci import sezioni

        from . import tessere

        cliente = get_object_or_404(ClienteApi, pk=pk)
        if sezione := tessere.sezione_per(cliente):
            sezioni.controlla(request.user, sezione.pk)
        try:
            verifica = verifica_soci.verifica(cliente, request.user)
        except verifica_soci.OperazioneNonValida as e:
            messages.error(request, str(e))
            return redirect("api:controparte", pk=pk)
        return redirect("api:verifica_soci", pk=verifica.pk)


class VerificaSociView(PermessoMixin, DetailView):
    """Proposta della verifica (soci da creare, modifiche campo per campo) e sua applicazione."""

    permission_required = "soci.importa_soci"
    template_name = "api/verifica_soci.html"
    context_object_name = "verifica"

    def get_queryset(self):
        from apps.soci import sezioni

        qs = VerificaSoci.objects.select_related("cliente", "sezione", "creata_da", "applicata_da")
        return sezioni.filtra(qs, self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        v = self.object
        ctx["voci"] = [x for x in v.proposta.get("voci", []) if x["stato"] != "invariato"]
        ctx["proposte"] = [x for x in ctx["voci"] if x["stato"] in ("nuovo", "differenze")]
        return ctx

    def post(self, request, pk):
        from apps.collegamenti import soci as verifica_soci

        verifica = get_object_or_404(self.get_queryset(), pk=pk)
        scelti = [int(x) for x in request.POST.getlist("scelti") if x.isdigit()]
        if not scelti:
            messages.warning(request, "Nessun socio scelto: nulla è stato modificato.")
            return redirect("api:verifica_soci", pk=pk)
        try:
            verifica = verifica_soci.applica(verifica, scelti, request.user)
        except verifica_soci.OperazioneNonValida as e:
            messages.error(request, str(e))
        else:
            errori = sum(1 for e in verifica.esiti if e["esito"] == "errore")
            fatti = len(verifica.esiti) - errori
            testo = f"Soci creati o aggiornati: {fatti}"
            testo += f"; errori: {errori}." if errori else "."
            (messages.warning if errori else messages.success)(request, testo)
        return redirect("api:verifica_soci", pk=pk)
