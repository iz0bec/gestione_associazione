# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Trasferimenti di soci fra installazioni collegate e verifica di una tessera di
# *              un'altra installazione (ADR-030, F5): viste sottili sui servizi di
# *              apps.collegamenti.trasferimenti.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from datetime import date

from django import forms
from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.core.forms import StileMixin
from apps.core.views import PermessoMixin

from . import sezioni
from .models import Sezione, Socio, TrasferimentoEsterno


class RichiestaForm(StileMixin, forms.Form):
    cliente = forms.ModelChoiceField(
        label="Installazione di arrivo",
        queryset=None,
        help_text="Sezione (o federazione) collegata che accoglierà il socio.",
    )
    consenso_il = forms.DateField(
        label="Il socio ha dato il consenso il", widget=forms.DateInput(attrs={"type": "date"})
    )
    consenso_modo = forms.CharField(
        label="Come",
        max_length=150,
        help_text="Es. «domanda scritta protocollata n. 2026-00012», «email del 10/11», "
        "«di persona».",
    )
    motivo = forms.CharField(
        label="Motivo", max_length=255, required=False, help_text="Es. cambio di residenza."
    )

    def __init__(self, *args, **kwargs):
        from apps.collegamenti.trasferimenti import destinazioni

        super().__init__(*args, **kwargs)
        self.fields["cliente"].queryset = destinazioni()


class RichiestaView(PermessoMixin, View):
    """Dalla scheda del socio: chiede a un'installazione collegata di accoglierlo."""

    permission_required = "soci.cessa_socio"

    def _socio(self, request, pk):
        socio = get_object_or_404(
            sezioni.filtra(Socio.objects.select_related("soggetto", "sezione"), request.user), pk=pk
        )
        return socio

    def get(self, request, pk):
        socio = self._socio(request, pk)
        return render(
            request,
            "soci/trasferimento_esterno_nuovo.html",
            {"socio": socio, "form": RichiestaForm()},
        )

    def post(self, request, pk):
        from apps.collegamenti import trasferimenti

        socio = self._socio(request, pk)
        form = RichiestaForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data
            try:
                t = trasferimenti.invia(
                    socio,
                    d["cliente"],
                    request.user,
                    motivo=d["motivo"],
                    consenso_il=d["consenso_il"],
                    consenso_modo=d["consenso_modo"],
                )
            except trasferimenti.OperazioneNonValida as e:
                messages.error(request, str(e))
            else:
                messages.success(
                    request,
                    f"Richiesta inviata a «{t.cliente}»: il socio cesserà qui "
                    "quando l'installazione di arrivo lo accoglierà.",
                )
                return redirect(t.get_absolute_url())
        return render(
            request, "soci/trasferimento_esterno_nuovo.html", {"socio": socio, "form": form}
        )


class ElencoView(PermessoMixin, View):
    permission_required = "soci.view_socio"

    def get(self, request):
        qs = TrasferimentoEsterno.objects.select_related("cliente", "socio", "socio__sezione")
        consentite = sezioni.id_sezioni(request.user)
        if consentite is not None:  # in uscita solo i propri soci; in arrivo chi può accogliere
            qs = qs.filter(direzione="entrata") | qs.filter(socio__sezione__in=consentite)
        return render(
            request,
            "soci/trasferimenti_esterni.html",
            {
                "in_attesa": [t for t in qs if t.direzione == "entrata" and t.stato == "in_attesa"],
                "altri": [
                    t for t in qs if not (t.direzione == "entrata" and t.stato == "in_attesa")
                ][:100],
            },
        )


class DettaglioView(PermessoMixin, View):
    permission_required = "soci.view_socio"

    def get(self, request, pk):
        t = get_object_or_404(
            TrasferimentoEsterno.objects.select_related("cliente", "socio"), pk=pk
        )
        return render(
            request,
            "soci/trasferimento_esterno.html",
            {
                "t": t,
                "sezioni": Sezione.objects.filter(attiva=True).order_by("ordine", "nome"),
                "multisezione": sezioni.multisezione(),
            },
        )

    def post(self, request, pk):
        from apps.collegamenti import trasferimenti

        if not request.user.has_perm("soci.add_socio"):
            raise Http404
        t = get_object_or_404(TrasferimentoEsterno, pk=pk, direzione="entrata")
        try:
            if request.POST.get("azione") == "accogli":
                sezione = None
                if request.POST.get("sezione"):
                    sezione = get_object_or_404(Sezione, pk=request.POST["sezione"], attiva=True)
                    sezioni.controlla(request.user, sezione.pk)
                trasferimenti.accogli(t, request.user, sezione=sezione)
                messages.success(
                    request,
                    f"{t.nome} è iscritto nel libro soci; l'esito è stato "
                    "comunicato all'installazione di partenza.",
                )
            elif request.POST.get("azione") == "respingi":
                trasferimenti.respingi(t, request.user, request.POST.get("motivo", ""))
                messages.success(request, "Richiesta respinta; l'esito è stato comunicato.")
        except trasferimenti.OperazioneNonValida as e:
            messages.error(request, str(e))
        return redirect(t.get_absolute_url())


class VerificaTesseraView(PermessoMixin, View):
    """Verifica di una tessera dal codice del QR, qui e presso le installazioni collegate."""

    permission_required = "soci.view_tessera"

    def get(self, request):
        from apps.collegamenti import client
        from apps.collegamenti.trasferimenti import destinazioni
        from apps.collegamenti.trasporto import ErroreTrasporto

        from . import tessera_digitale

        codice = (request.GET.get("codice") or "").strip()
        if "/" in codice:  # incollato l'indirizzo del QR: conta l'ultima parte
            codice = codice.rstrip("/").rsplit("/", 1)[-1]
        esiti = []
        if codice:
            if tessera := tessera_digitale.da_codice(codice):
                e = tessera_digitale.esito(tessera)
                esiti.append(
                    {
                        "fonte": "questa installazione",
                        "valida": e.valida,
                        "motivo": e.motivo,
                        "anno": e.anno,
                        "sezione": e.sezione,
                        "nome": e.nome,
                    }
                )
            else:
                for c in destinazioni():
                    if not c.abbinata:
                        continue
                    try:
                        r, _, _ = client.chiama(c, "GET", f"/tessere/{codice}")
                    except (client.ErroreCollegamento, ErroreTrasporto):
                        continue
                    if r.stato == 200:
                        d = client.json_risposta(r)
                        esiti.append({"fonte": c.nome, **d})
                        break
        return render(
            request,
            "soci/verifica_tessera_collegata.html",
            {"codice": codice, "esiti": esiti, "oggi": date.today()},
        )
