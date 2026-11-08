# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Viste della gestione utenti e dei ruoli
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from allauth.mfa.models import Authenticator
from django.contrib import messages
from django.contrib.auth.models import Group
from django.db.models import Count, Exists, OuterRef, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import CreateView, FormView, ListView, UpdateView

from apps.core.audit import campi_modificati
from apps.core.views import PermessoMixin

from . import servizi
from .forms import ImpostaPasswordForm, RuoliMfaForm, UtenteForm
from .models import PoliticaRuolo, Utente
from .ruoli import RUOLI


def _senza_cache(risposta):
    """La pagina con la password temporanea non deve restare nella cache del browser."""
    risposta["Cache-Control"] = "no-store"
    return risposta


def _con_secondo_fattore(queryset):
    fattori = Authenticator.objects.filter(user=OuterRef("pk"), type__in=servizi.FATTORI_FORTI)
    obblighi = PoliticaRuolo.objects.filter(ruolo__user=OuterRef("pk"), mfa_obbligatoria=True)
    return queryset.annotate(ha_mfa=Exists(fattori), mfa_obbligo=Exists(obblighi))


class UtentiView(PermessoMixin, ListView):
    permission_required = "accounts.view_utente"
    template_name = "accounts/utenti.html"
    context_object_name = "utenti"
    paginate_by = 50

    def get_queryset(self):
        qs = _con_secondo_fattore(
            Utente.objects.select_related("soggetto__socio").prefetch_related("groups", "sezioni")
        )
        self.q = self.request.GET.get("q", "").strip()
        self.ruolo = self.request.GET.get("ruolo", "")
        self.stato = self.request.GET.get("stato", "attivi")
        if self.q:
            qs = qs.filter(
                Q(username__icontains=self.q)
                | Q(first_name__icontains=self.q)
                | Q(last_name__icontains=self.q)
                | Q(email__icontains=self.q)
            )
        if self.ruolo.isdigit():
            qs = qs.filter(groups=int(self.ruolo))
        if self.stato == "attivi":
            qs = qs.filter(is_active=True)
        elif self.stato == "disattivati":
            qs = qs.filter(is_active=False)
        return qs

    def get_template_names(self):
        if self.request.htmx:
            return ["accounts/utenti.html#elenco"]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            q=self.q,
            ruolo=self.ruolo,
            stato=self.stato,
            ruoli=Group.objects.order_by("name"),
        )
        return ctx


class UtenteNuovoView(PermessoMixin, CreateView):
    permission_required = "accounts.add_utente"
    model = Utente
    form_class = UtenteForm
    template_name = "accounts/utente_modulo.html"

    def form_valid(self, form):
        utente, password = servizi.crea_utente(form, self.request.user)
        return _senza_cache(
            render(
                self.request,
                "accounts/password_temporanea.html",
                {"utente": utente, "password": password, "nuovo": True},
            )
        )


class UtenteView(PermessoMixin, UpdateView):
    permission_required = "accounts.change_utente"
    model = Utente
    form_class = UtenteForm
    template_name = "accounts/utente_modulo.html"
    context_object_name = "utente"

    def get_queryset(self):
        return _con_secondo_fattore(Utente.objects.all())

    def form_valid(self, form):
        dettagli = campi_modificati(form)
        try:
            servizi.aggiorna_utente(form, self.request.user, dettagli)
        except servizi.OperazioneNonValida as e:
            form.add_error(None, e)
            return self.form_invalid(form)
        messages.success(self.request, f"Utente «{self.object}» salvato.")
        return redirect("utenti:utente", self.object.pk)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        u = self.object
        ctx.update(
            fattori=Authenticator.objects.filter(user=u).values_list("type", flat=True),
            mfa_richiesta=servizi.mfa_richiesta(u),
            modificabile=not (u.is_superuser and not self.request.user.is_superuser),
            se_stesso=u.pk == self.request.user.pk,
        )
        return ctx


class _AzioneUtente(PermessoMixin, View):
    permission_required = "accounts.change_utente"
    http_method_names = ["post"]

    def post(self, request, pk):
        utente = get_object_or_404(Utente, pk=pk)
        try:
            return self.esegui(request, utente) or redirect("utenti:utente", pk)
        except servizi.OperazioneNonValida as e:
            messages.error(request, " ".join(e.messages))
            return redirect("utenti:utente", pk)


class ReimpostaPasswordView(_AzioneUtente):
    def esegui(self, request, utente):
        password = servizi.reimposta_password(utente, request.user)
        return _senza_cache(
            render(
                request,
                "accounts/password_temporanea.html",
                {"utente": utente, "password": password},
            )
        )


class ImpostaPasswordView(PermessoMixin, View):
    """L'amministratore sceglie la password dell'utente (non viene mai mostrata né registrata)."""

    permission_required = "accounts.change_utente"
    template_name = "accounts/imposta_password.html"

    def _pagina(self, request, utente, form):
        return _senza_cache(render(request, self.template_name, {"utente": utente, "form": form}))

    def get(self, request, pk):
        utente = get_object_or_404(Utente, pk=pk)
        return self._pagina(request, utente, ImpostaPasswordForm(utente=utente))

    def post(self, request, pk):
        utente = get_object_or_404(Utente, pk=pk)
        form = ImpostaPasswordForm(request.POST, utente=utente)
        if not form.is_valid():
            return self._pagina(request, utente, form)
        try:
            obbligo = form.cleaned_data.get("obbligo_cambio", False)
            password = form.cleaned_data["password1"]
            servizi.imposta_password(utente, request.user, password, obbligo_cambio=obbligo)
        except servizi.OperazioneNonValida as e:
            messages.error(request, " ".join(e.messages))
            return redirect("utenti:utente", pk)
        messages.success(request, f"Password di «{utente}» impostata.")
        return redirect("utenti:utente", pk)


class AzzeraSecondoFattoreView(_AzioneUtente):
    def esegui(self, request, utente):
        servizi.azzera_secondo_fattore(utente, request.user)
        messages.success(
            request,
            f"Secondo fattore di «{utente}» azzerato: al prossimo accesso entrerà solo con la "
            "password (e dovrà configurarlo di nuovo se il ruolo lo richiede).",
        )


class AttivaView(_AzioneUtente):
    def esegui(self, request, utente):
        attivo = request.POST.get("attivo") == "1"
        servizi.imposta_attivo(utente, request.user, attivo)
        messages.success(request, f"Utente «{utente}» {'riattivato' if attivo else 'disattivato'}.")


class RuoliView(PermessoMixin, FormView):
    permission_required = "accounts.change_utente"
    template_name = "accounts/ruoli.html"
    form_class = RuoliMfaForm

    def get_initial(self):
        return {"ruoli": list(servizi.ruoli_con_mfa())}

    def form_valid(self, form):
        scelti = {g.pk for g in form.cleaned_data["ruoli"]}
        cambiati = servizi.imposta_mfa_ruoli(scelti, Group.objects.all())
        if cambiati:
            messages.success(self.request, "Regole aggiornate: " + ", ".join(cambiati) + ".")
        else:
            messages.info(self.request, "Nessuna modifica.")
        return redirect("utenti:ruoli")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["ruoli"] = Group.objects.annotate(
            n_permessi=Count("permissions", distinct=True),
            n_utenti=Count("user", filter=Q(user__is_active=True), distinct=True),
        ).order_by("name")
        ctx["predefiniti"] = set(RUOLI)
        ctx["ruoli_mfa"] = servizi.ruoli_con_mfa()
        return ctx
