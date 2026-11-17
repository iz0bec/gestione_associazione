# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Pagine dell'area personale del socio (accesso con collegamento via email) e
# *              gestione delle richieste
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import time

from django import forms
from django.contrib import messages
from django.core import signing
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from apps.core.middleware import ip_richiesta
from apps.core.models import Organizzazione
from apps.core.pdf import risposta_pdf
from apps.core.views import PermessoMixin

from . import servizi
from .models import RichiestaArea

SALE_MODULO = "area.modulo"


class EmailForm(forms.Form):
    email = forms.EmailField(label="La tua email", max_length=254)
    sito = forms.CharField(required=False)  # trappola per i programmi
    token = forms.CharField(widget=forms.HiddenInput)

    def clean(self):
        if self.cleaned_data.get("sito"):
            raise forms.ValidationError("Invio non accettato.")
        try:
            emesso = float(signing.loads(self.data.get("token", ""), salt=SALE_MODULO,
                                         max_age=3600))  # fmt: skip
        except (signing.BadSignature, TypeError, ValueError):
            raise forms.ValidationError("Il modulo è scaduto: ricaricare la pagina.") from None
        if time.time() - emesso < 2:
            raise forms.ValidationError("Invio troppo rapido: riprovare.")
        return super().clean()


class _Attiva:
    def dispatch(self, request, *args, **kwargs):
        if not servizi.attiva():
            raise Http404("Area personale non attiva.")
        return super().dispatch(request, *args, **kwargs)


class AccessoView(_Attiva, TemplateView):
    template_name = "area/accesso.html"

    def get_context_data(self, **kwargs):
        form = kwargs.pop("form", None) or EmailForm(
            initial={"token": signing.dumps(time.time(), salt=SALE_MODULO)}
        )
        return super().get_context_data(form=form, **kwargs)

    def post(self, request):
        form = EmailForm(request.POST)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form))
        try:
            servizi.chiedi_accesso(form.cleaned_data["email"], base_url=servizi.base_url(request),
                                   ip=ip_richiesta(request))  # fmt: skip
        except servizi.OperazioneNonValida as e:
            form.add_error(None, " ".join(e.messages))
            return self.render_to_response(self.get_context_data(form=form))
        return redirect("area:inviato")


class InviatoView(_Attiva, TemplateView):
    template_name = "area/inviato.html"


class EntraView(_Attiva, View):
    def get(self, request, firmato):
        soggetto = servizi.entra(firmato, ip_richiesta(request))
        if soggetto is None:
            messages.error(request, "Il collegamento non è valido o è scaduto: chiedine un altro.")
            return redirect("area:accesso")
        servizi.apri_sessione(request, soggetto)
        return redirect("area:area")


class _SocioMixin(_Attiva):
    def dispatch(self, request, *args, **kwargs):
        if not servizi.attiva():
            raise Http404("Area personale non attiva.")
        self.soggetto = servizi.soggetto_in_sessione(request)
        if self.soggetto is None:
            return redirect("area:accesso")
        return super().dispatch(request, *args, **kwargs)


class AreaView(_SocioMixin, TemplateView):
    template_name = "area/area.html"

    def get_context_data(self, **kwargs):
        from apps.anagrafica.models import Consenso
        from apps.core.models import CanaleTelegram
        from apps.eventi.models import Evento

        s = self.soggetto
        socio = getattr(s, "socio", None)
        consensi = {}
        for c in Consenso.objects.filter(soggetto=s).order_by("data", "registrato_il"):
            consensi[c.get_finalita_display()] = c
        mie = {a.evento_id: a for a in s.adesioni.filter(annullata=False)}
        eventi = [
            (e, mie.get(e.pk))
            for e in Evento.objects.filter(annullato=False, inizio__gte=timezone.now()).order_by(
                "inizio"
            )
            if e.si_puo_aderire or e.pk in mie
        ]
        return super().get_context_data(
            soggetto=s, socio=socio,
            tessere=socio.tessere.filter(annullata=False).order_by("-anno") if socio else [],
            consensi=consensi.values(), eventi=eventi,
            telegram=CanaleTelegram.corrente().pronto,
            richieste=s.richieste_area.all()[:5], **kwargs,
        )  # fmt: skip


class RicevutaView(_SocioMixin, View):
    def get(self, request, pk):
        socio = getattr(self.soggetto, "socio", None)
        if socio is None:
            raise Http404
        tessere = socio.tessere.select_related("socio__soggetto", "socio__tipologia")
        tessera = get_object_or_404(tessere, pk=pk, ricevuta_numero__isnull=False)
        nome = f"ricevuta_{tessera.ricevuta_anno}_{tessera.ricevuta_numero:04d}.pdf"
        contesto = {"tessera": tessera, "organizzazione": Organizzazione.corrente()}
        return risposta_pdf("soci/pdf/ricevuta.html", contesto, nome)


class AderisciView(_SocioMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        from apps.eventi import servizi as eventi
        from apps.eventi.models import Adesione, Evento

        evento = get_object_or_404(Evento, pk=pk, annullato=False)
        s = self.soggetto
        try:
            eventi.aderisci(evento, {
                "cognome": s.cognome or s.nome_completo, "nome": s.nome, "email": s.email,
                "telefono": s.cellulare or s.telefono,
                "accompagnatori": request.POST.get("accompagnatori") or 0,
            }, origine=Adesione.Origine.AREA, soggetto=s, ip=ip_richiesta(request))  # fmt: skip
            messages.success(request, f"Adesione a «{evento}» registrata.")
        except eventi.OperazioneNonValida as e:
            messages.error(request, " ".join(e.messages))
        return redirect("area:area")


class RinunciaView(_SocioMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        from apps.eventi import servizi as eventi

        adesione = get_object_or_404(self.soggetto.adesioni, evento_id=pk, annullata=False)
        eventi.annulla_adesione(adesione)
        messages.success(request, f"Adesione a «{adesione.evento}» annullata.")
        return redirect("area:area")


class RichiestaView(_SocioMixin, View):
    http_method_names = ["post"]

    def post(self, request):
        try:
            servizi.chiedi_correzione(self.soggetto, request.POST.get("testo", ""))
            messages.success(request, "Richiesta inviata: la segreteria la esaminerà.")
        except servizi.OperazioneNonValida as e:
            messages.error(request, " ".join(e.messages))
        return redirect("area:area")


class TelegramView(_SocioMixin, TemplateView):
    template_name = "area/telegram.html"

    def get_context_data(self, **kwargs):
        from apps.comunicazioni import telegram
        from apps.core.models import CanaleTelegram
        from apps.patrimonio.servizi import qr_svg

        if not CanaleTelegram.corrente().pronto:
            raise Http404
        link = telegram.link_invito(self.soggetto)
        return super().get_context_data(link=link, qr=qr_svg(link), **kwargs)


class EsciView(View):
    http_method_names = ["post"]

    def post(self, request):
        servizi.chiudi_sessione(request)
        messages.success(request, "Sei uscito dall'area personale.")
        return redirect("area:accesso")


# --- per la segreteria ---------------------------------------------------------------------


class RichiestaGestitaView(PermessoMixin, View):
    permission_required = "anagrafica.change_soggetto"
    http_method_names = ["post"]

    def post(self, request, pk):
        r = get_object_or_404(RichiestaArea, pk=pk, gestita_il__isnull=True)
        servizi.segna_gestita(r, request.user)
        messages.success(request, f"Richiesta di {r.soggetto} segnata come gestita.")
        return redirect(request.POST.get("torna") or r.soggetto.get_absolute_url())
