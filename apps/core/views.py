# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Viste di sistema: cruscotto, dati dell'organizzazione, registro
# *              attività, controllo di salute per il monitoraggio.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from datetime import date

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import connection
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.generic import CreateView, ListView, TemplateView, UpdateView

from . import invio
from .audit import Azione, campi_modificati, registra
from .cifratura import cifratura_disponibile
from .forms import (
    AspettoEmailForm,
    AspettoForm,
    OrganizzazioneCompletaForm,
    ServizioInvioForm,
    ServiziPostaForm,
)
from .models import EventoAudit, Organizzazione


class PermessoMixin(LoginRequiredMixin, PermissionRequiredMixin):
    """Accesso solo ad utenti autenticati con il permesso indicato (altrimenti 403)."""

    raise_exception = False

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            self.raise_exception = True
        return super().handle_no_permission()


class CruscottoView(LoginRequiredMixin, TemplateView):
    template_name = "core/cruscotto.html"

    def dispatch(self, request, *args, **kwargs):
        # senza accesso: la pagina pubblica di presentazione, se attiva
        if not request.user.is_authenticated and Organizzazione.corrente().pagina_pubblica:
            return PresentazioneView.as_view()(request)
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        from .configurazione import da_configurare

        if da_configurare(request.user):  # primo accesso: configurazione guidata
            return redirect("configurazione", passo="ente")
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        from apps.anagrafica.models import Soggetto

        ctx = super().get_context_data(**kwargs)
        attivi = Soggetto.objects.filter(attivo=True)
        ctx["statistiche"] = {
            "soggetti": attivi.count(),
            "persone": attivi.filter(tipo=Soggetto.Tipo.PERSONA).count(),
            "enti": attivi.filter(tipo=Soggetto.Tipo.ENTE).count(),
        }
        from apps.comunicazioni.anniversari import eventi

        ctx["anniversari"] = [e for e in eventi(giorni=14) if e.tipo != "scomparsa"][:10]
        if self.request.user.has_perm("soci.view_socio"):
            ctx["soci"] = _riepilogo_soci()
        from apps.calendario import servizi as calendario

        ctx["impegni"] = calendario.prossimi(self.request.user, giorni=14)[:8]
        ctx["scadenze"] = calendario.scadenze_aperte(self.request.user)
        if self.request.user.has_perm("anagrafica.change_soggetto"):
            from apps.area.models import RichiestaArea

            ctx["richieste_area"] = RichiestaArea.objects.filter(
                gestita_il__isnull=True
            ).select_related("soggetto")[:10]
        if self.request.user.has_perm("organi.view_carica"):
            from apps.organi.servizi import mandati_in_scadenza

            ctx["mandati"] = mandati_in_scadenza()
        if self.request.user.has_perm("elezioni.view_rinnovo"):
            from apps.elezioni import servizi as elezioni

            rinnovi = list(elezioni.filtra_per_utente(elezioni.rinnovi_aperti(), self.request.user))
            for r in rinnovi:
                r.prossimo = elezioni.prossimo_termine(r)
            ctx["rinnovi_in_corso"] = rinnovi
        if self.request.user.has_perm("protocollo.view_protocollo"):
            ctx["protocollo"] = _riepilogo_protocollo(self.request.user)
        if self.request.user.has_perm("progetti.valuta_idea"):
            from apps.progetti.models import Idea

            ctx["idee_da_valutare"] = (
                Idea.objects.filter(stato__in=[Idea.Stato.NUOVA, Idea.Stato.IN_VALUTAZIONE])
                .exclude(valutazioni__utente=self.request.user)
                .count()
            )
        ctx["ultimi_eventi"] = EventoAudit.objects.filter(utente=self.request.user).select_related(
            "utente"
        )[:8]
        return ctx


def _riepilogo_soci():
    from apps.soci.models import DomandaIscrizione, Socio

    anno = date.today().year
    attivi = Socio.objects.attivi()
    return {
        "anno": anno,
        "attivi": attivi.count(),
        "in_regola": attivi.in_regola(anno).count(),
        "morosi": Socio.objects.morosi(anno).count(),
        "domande": DomandaIscrizione.objects.filter(
            stato=DomandaIscrizione.Stato.IN_ATTESA
        ).count(),
    }


def _riepilogo_protocollo(utente):
    from django.utils import timezone

    from apps.protocollo.models import MessaggioRicevuto, Protocollo

    visibili = Protocollo.objects.visibili_a(utente)
    return {
        "anno": visibili.filter(anno=timezone.localdate().year).count(),
        "ultimi": visibili.prefetch_related("corrispondenti")[:5],
        "posta": MessaggioRicevuto.objects.da_esaminare().count()
        if utente.has_perm("protocollo.view_messaggioricevuto")
        else 0,
    }


class OrganizzazioneView(PermessoMixin, UpdateView):
    permission_required = "core.gestisci_organizzazione"
    form_class = OrganizzazioneCompletaForm
    template_name = "core/organizzazione.html"
    success_url = reverse_lazy("core:organizzazione")

    def get_object(self, queryset=None):
        return Organizzazione.corrente()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.user.has_perm("organi.gestisci_timbri"):  # solo amministratore
            from apps.organi import servizi as organi
            from apps.organi import timbro_generico

            org = self.object
            ctx["organizzazione"] = org
            ctx["timbri"] = [
                (sezione, timbro, timbro_generico.svg(org, sezione))
                for sezione, timbro in organi.timbri_per_ente(self.request.user)
            ]
        return ctx

    def form_valid(self, form):
        from .immagini import ImmagineNonValida, ripulisci

        dettagli = campi_modificati(form)
        org = form.save(commit=False)
        nuovo, togli = (
            form.cleaned_data.get("nuovo_logo_modulo"),
            form.cleaned_data.get("togli_logo_modulo"),
        )
        try:
            if nuovo:
                pulito = ripulisci(nuovo, lato=600, formato="PNG")
                if org.modulo_logo:
                    org.modulo_logo.delete(save=False)
                org.modulo_logo.save("logo.png", pulito, save=False)
            elif togli and org.modulo_logo:
                org.modulo_logo.delete(save=False)
        except ImmagineNonValida as e:
            form.add_error("nuovo_logo_modulo", e)
            return self.form_invalid(form)
        org.save()
        if dettagli.get("campi") or nuovo or togli:
            registra(Azione.MODIFICA, org, logo_modulo=bool(nuovo) or None, **dettagli)
        messages.success(self.request, "Dati dell'organizzazione salvati.")
        return redirect(self.success_url)


def _stato_telegram():
    from apps.comunicazioni.telegram import collegati

    from .models import CanaleTelegram, ServizioMessaggi

    return {"telegram": CanaleTelegram.corrente(), "telegram_collegati": collegati(),
            "servizi_messaggi": ServizioMessaggi.objects.all()}  # fmt: skip


def _comandi_chiave():
    """Comandi da copiare per creare CHIAVE_CIFRATURA in questa installazione."""
    import shlex
    import sys

    from django.conf import settings

    cartella = shlex.quote(str(settings.BASE_DIR))
    python = shlex.quote(sys.executable)
    return {
        "comando_chiave": f'cd {cartella} && echo "CHIAVE_CIFRATURA=$({python} manage.py '
        f'genera_chiave_cifratura)" >> .env',
        "comando_riavvio": ""
        if settings.DEBUG
        else "systemctl restart gestione-associazione gestione-associazione-pianificatore",
    }


class ServiziPostaView(PermessoMixin, UpdateView):
    """Interruttori dell'invio e della lettura, servizi di invio (SMTP) e stato delle caselle."""

    permission_required = "core.gestisci_servizi_posta"
    form_class = ServiziPostaForm
    template_name = "core/servizi_posta.html"
    success_url = reverse_lazy("core:servizi_posta")

    def get_object(self, queryset=None):
        return Organizzazione.corrente()

    def form_valid(self, form):
        dettagli = campi_modificati(form)
        risposta = super().form_valid(form)
        if dettagli.get("campi"):
            registra(Azione.MODIFICA, self.object, descrizione="Servizi di posta",
                     invio_email=self.object.invio_email,
                     ricezione_posta=self.object.ricezione_posta, **dettagli)  # fmt: skip
        messages.success(self.request, "Servizi di posta aggiornati.")
        return risposta

    def get_context_data(self, **kwargs):
        from apps.comunicazioni.models import Destinatario, Invio
        from apps.protocollo.models import CasellaPosta, DestinatarioSpedizione

        ctx = super().get_context_data(**kwargs)
        from . import fornitori_posta
        from .models import FornitorePosta, ServizioInvio

        ctx.update(
            smtp=invio.stato_env(),
            servizi=ServizioInvio.objects.all(),
            fornitori_personalizzati=FornitorePosta.objects.all(),
            fornitori_predefiniti=fornitori_posta.predefiniti(),
            generale=invio.servizio_generale(),
            cifratura=cifratura_disponibile(),
            **_comandi_chiave(),
            **_stato_telegram(),
            in_coda=Destinatario.objects.filter(
                invio__stato=Invio.Stato.IN_CODA, stato=Destinatario.Stato.IN_ATTESA
            ).count(),
            caselle=CasellaPosta.objects.select_related("servizio_risposta"),
            protocolli_in_coda=DestinatarioSpedizione.objects.filter(
                stato=DestinatarioSpedizione.Stato.IN_ATTESA
            ).count(),
        )
        return ctx


class VerificaCasellaView(PermessoMixin, View):
    """Prova di accesso a una casella IMAP (nulla viene scaricato)."""

    permission_required = "core.gestisci_servizi_posta"

    def post(self, request, pk):
        from django.shortcuts import get_object_or_404

        from apps.protocollo.models import CasellaPosta

        _verifica_casella(request, get_object_or_404(CasellaPosta, pk=pk))
        return redirect("core:servizi_posta")


def _verifica_casella(request, casella):
    """Prova di accesso IMAP con l'esito nei messaggi della pagina."""
    from apps.protocollo.posta import ErroreCasella, verifica_casella

    try:
        esito = verifica_casella(casella)
    except ErroreCasella as e:
        messages.error(request, f"{casella}: {e}")
    except Exception as e:  # noqa: BLE001 - es. password non decifrabile
        messages.error(request, f"{casella}: verifica non riuscita ({type(e).__name__}).")
    else:
        messages.success(request, f"{casella}: {esito}")


class VerificaSmtpView(PermessoMixin, View):
    """Prova di accesso al server di invio del file .env (nessuna email spedita)."""

    permission_required = "core.gestisci_servizi_posta"

    def post(self, request):
        from django.core.mail import mailers

        stato = invio.stato_env()
        if not stato["smtp"]:
            messages.warning(request, f"Nessun server SMTP: le email vanno a «{stato['backend']}».")
            return redirect("core:servizi_posta")
        try:
            connessione = mailers.default
            if getattr(connessione, "timeout", None) is None:
                connessione.timeout = 20  # la verifica non deve bloccare la pagina
            connessione.open()
            connessione.close()
        except Exception as e:  # noqa: BLE001 - l'esito si mostra all'amministratore
            dettaglio = f"{type(e).__name__}: {str(e)[:150]}"
            messages.error(request, f"Server di invio {stato['host']}:{stato['porta']}: accesso "
                                    f"non riuscito ({dettaglio}).")  # fmt: skip
        else:
            messages.success(request, f"Server di invio {stato['host']}:{stato['porta']}: accesso "
                                      "riuscito (nessuna email spedita).")  # fmt: skip
        return redirect("core:servizi_posta")


class _CasellaMixin:
    """Configurazione delle caselle IMAP (email e PEC); l'uso si abilita in Protocollo → Caselle."""

    permission_required = "core.gestisci_servizi_posta"
    template_name = "core/casella.html"
    success_url = reverse_lazy("core:servizi_posta")

    def get_form_class(self):
        from .forms import CasellaForm

        return CasellaForm

    def get_queryset(self):
        from apps.protocollo.models import CasellaPosta

        return CasellaPosta.objects.all()

    def form_valid(self, form):
        nuovo = form.instance.pk is None
        if nuovo:
            form.instance.attiva = False  # la abilita il protocollo
        dettagli = {} if nuovo else campi_modificati(form)
        dettagli.get("campi", {}).pop("nuova_password", None)
        risposta = super().form_valid(form)
        if nuovo:
            registra(Azione.CREAZIONE, self.object, descrizione=f"Casella di posta {self.object}")
            messages.success(self.request, f"Casella «{self.object}» salvata: per leggerla va "
                                           "abilitata in Protocollo → Caselle.")  # fmt: skip
        else:
            if dettagli.get("campi") or form.cleaned_data.get("nuova_password"):
                registra(Azione.MODIFICA, self.object,
                         descrizione=f"Casella di posta {self.object}",
                         password_cambiata=bool(form.cleaned_data.get("nuova_password")) or None,
                         **dettagli)  # fmt: skip
            messages.success(self.request, f"Casella «{self.object}» salvata.")
        if form.cleaned_data.get("verifica"):
            _verifica_casella(self.request, self.object)
        return risposta


class CasellaNuovaView(_CasellaMixin, PermessoMixin, CreateView):
    pass


class CasellaModificaView(_CasellaMixin, PermessoMixin, UpdateView):
    pass


class CasellaEliminaView(PermessoMixin, View):
    """Elimina una casella che non ha mai scaricato messaggi; una con messaggi resta (sono nella
    storia del protocollo) e si toglie dalla lettura in Protocollo → Caselle."""

    permission_required = "core.gestisci_servizi_posta"
    http_method_names = ["post"]

    def post(self, request, pk):
        from django.shortcuts import get_object_or_404

        from apps.protocollo.models import CasellaPosta

        casella = get_object_or_404(CasellaPosta.objects.all(), pk=pk)
        if n := casella.messaggi.count():
            messages.error(request, f"«{casella}» ha già scaricato {n} messaggi, che restano nella "
                                    "posta del protocollo: non si elimina. Per non leggerla più, "
                                    "renderla «non usata» in Protocollo → Caselle.")  # fmt: skip
            return redirect("core:servizi_posta")
        casella.delete()
        registra(Azione.ELIMINAZIONE, None, descrizione=f"Casella di posta {casella}")
        messages.success(request, f"Casella «{casella}» eliminata.")
        return redirect("core:servizi_posta")


def _collega_caselle(servizio):
    """Le caselle con lo stesso indirizzo e senza «Rispondi con» rispondono con questo servizio."""
    from apps.protocollo.models import CasellaPosta

    if servizio.attivo:
        CasellaPosta.objects.filter(
            servizio_risposta__isnull=True, pec=servizio.pec, utente__iexact=servizio.indirizzo
        ).update(servizio_risposta=servizio)


class _ServizioInvioMixin:
    permission_required = "core.gestisci_servizi_posta"
    form_class = ServizioInvioForm
    template_name = "core/servizio_invio.html"
    success_url = reverse_lazy("core:servizi_posta")

    def get_queryset(self):
        from .models import ServizioInvio

        return ServizioInvio.objects.all()

    def form_valid(self, form):
        nuovo = form.instance.pk is None
        dettagli = {} if nuovo else campi_modificati(form)
        dettagli.get("campi", {}).pop("nuova_password", None)
        risposta = super().form_valid(form)
        _collega_caselle(self.object)
        if nuovo:
            registra(Azione.CREAZIONE, self.object, descrizione=f"Servizio di invio {self.object}")
        elif dettagli.get("campi") or form.cleaned_data.get("nuova_password"):
            registra(Azione.MODIFICA, self.object, descrizione=f"Servizio di invio {self.object}",
                     password_cambiata=bool(form.cleaned_data.get("nuova_password")) or None,
                     **dettagli)  # fmt: skip
        messages.success(self.request, f"Servizio di invio «{self.object}» salvato.")
        if form.cleaned_data.get("verifica"):
            _verifica_servizio(self.request, self.object)
        return risposta


class ServizioInvioNuovoView(_ServizioInvioMixin, PermessoMixin, CreateView):
    pass


class ServizioInvioModificaView(_ServizioInvioMixin, PermessoMixin, UpdateView):
    pass


class ServizioInvioAttivoView(PermessoMixin, View):
    """Attiva o disattiva un servizio dall'elenco (il server generale resta sempre attivo)."""

    permission_required = "core.gestisci_servizi_posta"
    http_method_names = ["post"]

    def post(self, request, pk):
        from django.shortcuts import get_object_or_404

        from .models import ServizioInvio

        servizio = get_object_or_404(ServizioInvio, pk=pk)
        attivo = request.POST.get("attivo") == "on"
        if not attivo and servizio.generale:
            messages.error(request, f"«{servizio}» è il server generale e non si disattiva: "
                                    "indicare prima un altro server generale.")  # fmt: skip
            return redirect("core:servizi_posta")
        if attivo != servizio.attivo:
            servizio.attivo = attivo
            servizio.save(update_fields=["attivo"])
            registra(Azione.MODIFICA, servizio, descrizione=f"Servizio di invio {servizio}",
                     attivo=attivo)  # fmt: skip
        stato = "attivo" if attivo else "disattivato: non si può più scegliere per spedire"
        messages.success(request, f"Servizio di invio «{servizio}» {stato}.")
        return redirect("core:servizi_posta")


class ServizioInvioEliminaView(PermessoMixin, View):
    """Elimina un servizio mai usato; uno con spedizioni si disattiva (restano nella storia)."""

    permission_required = "core.gestisci_servizi_posta"

    def post(self, request, pk):
        from django.db.models import ProtectedError
        from django.shortcuts import get_object_or_404

        from .models import ServizioInvio

        servizio = get_object_or_404(ServizioInvio, pk=pk)
        try:
            servizio.delete()
        except ProtectedError:
            messages.error(request, f"«{servizio}» è già stato usato per spedire comunicazioni o "
                                    "protocolli, che ne conservano il riferimento: non si elimina, "
                                    "si può disattivare con l'interruttore.")  # fmt: skip
        else:
            registra(Azione.ELIMINAZIONE, None, descrizione=f"Servizio di invio {servizio}")
            messages.success(request, f"Servizio di invio «{servizio}» eliminato.")
        return redirect("core:servizi_posta")


class VerificaServizioView(PermessoMixin, View):
    """Prova di accesso al server SMTP di un servizio (nessun messaggio spedito)."""

    permission_required = "core.gestisci_servizi_posta"

    def post(self, request, pk):
        from django.shortcuts import get_object_or_404

        from .models import ServizioInvio

        _verifica_servizio(request, get_object_or_404(ServizioInvio, pk=pk))
        return redirect("core:servizi_posta")


def _verifica_servizio(request, servizio):
    """Prova di accesso SMTP (nessun messaggio spedito) con l'esito nei messaggi della pagina."""
    try:
        messages.success(request, f"{servizio}: {invio.verifica(servizio)}.")
    except Exception as e:  # noqa: BLE001 - l'esito si mostra all'amministratore
        dettaglio = f"{type(e).__name__}: {str(e)[:150]}"
        messages.error(request, f"{servizio}: accesso a {servizio.server}:{servizio.porta} "
                                f"non riuscito ({dettaglio}).")  # fmt: skip


class CasellaInoltroView(PermessoMixin, View):
    """Inoltro dei messaggi scaricati da una casella alle persone scelte (es. la casella
    istituzionale della sezione, al posto dell'inoltro impostato presso il fornitore)."""

    permission_required = "core.gestisci_servizi_posta"
    template_name = "core/casella_inoltro.html"

    def _casella(self, pk):
        from django.shortcuts import get_object_or_404

        from apps.protocollo.models import CasellaPosta

        return get_object_or_404(CasellaPosta, pk=pk)

    def _pagina(self, request, casella, form, scelti, incaricato):
        from django.shortcuts import render

        from apps.protocollo.models import InoltroMessaggio

        recenti = InoltroMessaggio.objects.filter(messaggio__casella=casella).select_related(
            "messaggio"
        )[:20]
        return render(request, self.template_name, {
            "casella": casella, "form": form, "scelti": scelti, "incaricato": incaricato,
            "recenti": recenti,
        })  # fmt: skip

    def get(self, request, pk):
        from .forms import InoltroCasellaForm

        casella = self._casella(pk)
        return self._pagina(request, casella, InoltroCasellaForm(instance=casella),
                            list(casella.inoltro_destinatari.all()),
                            casella.inoltro_incaricato)  # fmt: skip

    def post(self, request, pk):
        from apps.anagrafica.models import Soggetto
        from apps.protocollo import inoltri

        from .forms import InoltroCasellaForm

        casella = self._casella(pk)
        prima = (casella.inoltro_attivo, sorted(casella.inoltro_destinatari.values_list("pk",
                 flat=True)), casella.inoltro_incaricato_id)  # fmt: skip
        attivo_prima = casella.inoltro_attivo
        form = InoltroCasellaForm(request.POST, instance=casella)
        ids = [i for i in request.POST.getlist("inoltro_destinatari") if i.isdigit()]
        scelti = list(Soggetto.objects.filter(pk__in=ids))
        incaricato = Soggetto.objects.filter(pk=request.POST.get("inoltro_incaricato") or 0).first()
        if form.is_valid() and form.cleaned_data["inoltro_attivo"]:
            senza = [s for s in scelti if not s.email]
            if senza:
                form.add_error(None, "Senza email, non possono ricevere: "
                               + ", ".join(s.nome_completo for s in senza) + ".")  # fmt: skip
            if not scelti and not inoltri.indirizzi_extra(form.cleaned_data["inoltro_indirizzi"]):
                form.add_error(None, "Indicare almeno una persona o un indirizzo a cui inoltrare.")
            if incaricato is not None and not incaricato.email:
                form.add_error(None, f"L'incaricato {incaricato.nome_completo} non ha un'email.")
        if not form.is_valid():
            return self._pagina(request, casella, form, scelti, incaricato)
        casella = form.save(commit=False)
        casella.inoltro_attivo = attivo_prima
        inoltri.attiva(casella, form.cleaned_data["inoltro_attivo"])
        casella.inoltro_incaricato = incaricato
        casella.save()
        casella.inoltro_destinatari.set(scelti)
        dopo = (casella.inoltro_attivo, sorted(s.pk for s in scelti), casella.inoltro_incaricato_id)
        if dopo != prima or form.changed_data:
            registra(Azione.MODIFICA, casella, descrizione=f"Inoltro della casella {casella}",
                     attivo=casella.inoltro_attivo, destinatari=[str(s) for s in scelti],
                     altri_indirizzi=len(inoltri.indirizzi_extra(casella.inoltro_indirizzi)),
                     incaricato=str(incaricato) if incaricato else "")  # fmt: skip
        if casella.inoltro_attivo:
            messages.success(
                request,
                f"Inoltro di «{casella}» attivo: {casella.descrizione_inoltro}. Si inoltrano i "
                "messaggi scaricati da ora in poi; togliere l'inoltro impostato presso il "
                "fornitore.",
            )
        else:
            messages.success(request, f"Inoltro di «{casella}» spento.")
        return redirect("core:servizi_posta")


class InoltroCercaView(PermessoMixin, View):
    """Ricerca in anagrafica per l'inoltro (destinatari o incaricato)."""

    permission_required = "core.gestisci_servizi_posta"

    def get(self, request):
        from django.shortcuts import render

        from apps.anagrafica.models import Soggetto

        q = request.GET.get("cerca", "").strip()
        nome = "inoltro_incaricato" if request.GET.get("nome") == "inoltro_incaricato" else (
            "inoltro_destinatari")  # fmt: skip
        risultati = Soggetto.objects.attivi().ricerca(q)[:10] if len(q) >= 2 else []
        return render(request, "core/_inoltro_risultati.html",
                      {"risultati": risultati, "nome": nome, "q": q})  # fmt: skip


class InoltroSceltaView(PermessoMixin, View):
    permission_required = "core.gestisci_servizi_posta"

    def get(self, request):
        from django.shortcuts import get_object_or_404, render

        from apps.anagrafica.models import Soggetto

        s = get_object_or_404(Soggetto, pk=request.GET.get("id"))
        nome = "inoltro_incaricato" if request.GET.get("nome") == "inoltro_incaricato" else (
            "inoltro_destinatari")  # fmt: skip
        return render(request, "core/_inoltro_scelto.html", {"s": s, "nome": nome})


class _FornitorePostaMixin:
    permission_required = "core.gestisci_servizi_posta"
    template_name = "core/fornitore_posta.html"
    success_url = reverse_lazy("core:servizi_posta")

    def get_form_class(self):
        from .forms import FornitorePostaForm

        return FornitorePostaForm

    def get_queryset(self):
        from .models import FornitorePosta

        return FornitorePosta.objects.all()

    def form_valid(self, form):
        nuovo = form.instance.pk is None
        dettagli = {} if nuovo else campi_modificati(form)
        risposta = super().form_valid(form)
        if nuovo or dettagli.get("campi"):
            registra(Azione.CREAZIONE if nuovo else Azione.MODIFICA, self.object,
                     descrizione=f"Fornitore di posta {self.object}", **dettagli)  # fmt: skip
        messages.success(self.request, f"Fornitore «{self.object}» salvato: si sceglie creando una "
                                       "casella o un servizio di invio.")  # fmt: skip
        return risposta


class FornitorePostaNuovoView(_FornitorePostaMixin, PermessoMixin, CreateView):
    pass


class FornitorePostaModificaView(_FornitorePostaMixin, PermessoMixin, UpdateView):
    pass


class FornitorePostaEliminaView(PermessoMixin, View):
    """Elimina un fornitore personalizzato: caselle e servizi già creati restano come sono."""

    permission_required = "core.gestisci_servizi_posta"

    def post(self, request, pk):
        from django.shortcuts import get_object_or_404

        from .models import FornitorePosta

        fornitore = get_object_or_404(FornitorePosta, pk=pk)
        registra(Azione.ELIMINAZIONE, fornitore, descrizione=f"Fornitore di posta {fornitore}")
        fornitore.delete()
        messages.success(request, f"Fornitore «{fornitore}» eliminato.")
        return redirect("core:servizi_posta")


class _ServizioMessaggiMixin:
    permission_required = "core.gestisci_servizi_posta"
    template_name = "core/servizio_messaggi.html"
    success_url = reverse_lazy("core:servizi_posta")

    def get_form_class(self):
        from .forms import ServizioMessaggiForm

        return ServizioMessaggiForm

    def get_queryset(self):
        from .models import ServizioMessaggi

        return ServizioMessaggi.objects.all()

    def form_valid(self, form):
        nuovo = form.instance.pk is None
        dettagli = {} if nuovo else campi_modificati(form)
        dettagli.get("campi", {}).pop("nuovo_segreto", None)
        risposta = super().form_valid(form)
        registra(Azione.CREAZIONE if nuovo else Azione.MODIFICA, self.object,
                 descrizione=f"Servizio di messaggistica {self.object}",
                 segreto_cambiato=bool(form.cleaned_data.get("nuovo_segreto")) or None,
                 **dettagli)  # fmt: skip
        messages.success(self.request, f"Servizio «{self.object}» salvato.")
        return risposta


class ServizioMessaggiNuovoView(_ServizioMessaggiMixin, PermessoMixin, CreateView):
    pass


class ServizioMessaggiModificaView(_ServizioMessaggiMixin, PermessoMixin, UpdateView):
    pass


class ServizioMessaggiAzioneView(PermessoMixin, View):
    """Attiva/disattiva, verifica (nessun messaggio inviato) o elimina un servizio."""

    permission_required = "core.gestisci_servizi_posta"
    http_method_names = ["post"]

    def post(self, request, pk, azione):
        from django.shortcuts import get_object_or_404

        from apps.comunicazioni import messaggi

        from .models import ServizioMessaggi

        s = get_object_or_404(ServizioMessaggi, pk=pk)
        if azione == "attivo":
            s.attivo = request.POST.get("attivo") == "on"
            s.save(update_fields=["attivo"])
            registra(Azione.MODIFICA, s, descrizione=f"Servizio di messaggistica {s}",
                     attivo=s.attivo)  # fmt: skip
            altri = ServizioMessaggi.objects.filter(attivo=True).exclude(pk=s.pk)
            if s.attivo and any(a.canale == s.canale for a in altri):
                messages.warning(request, "C'è già un altro servizio attivo per lo stesso canale: "
                                          "si usa il primo in elenco.")  # fmt: skip
            else:
                messages.success(request, f"«{s}» {'attivato' if s.attivo else 'disattivato'}.")
        elif azione == "verifica":
            try:
                esito = messaggi.verifica(s)
                messages.success(request, f"{s}: {esito} (nessun messaggio inviato).")
                s.ultimo_errore = ""
            except messaggi.ErroreMessaggi as e:
                messages.error(request, f"{s}: verifica non riuscita ({e}).")
                s.ultimo_errore = str(e)[:300]
            s.save(update_fields=["ultimo_errore"])
        elif azione == "elimina":
            s.delete()
            registra(Azione.ELIMINAZIONE, None, descrizione=f"Servizio di messaggistica {s}")
            messages.success(request, f"«{s}» eliminato.")
        return redirect("core:servizi_posta")


class TelegramView(PermessoMixin, View):
    """Bot Telegram: token (verificato con getMe, conservato cifrato), attivazione."""

    permission_required = "core.gestisci_servizi_posta"
    http_method_names = ["post"]

    def post(self, request):
        from apps.comunicazioni import telegram

        from .models import CanaleTelegram

        canale = CanaleTelegram.corrente()
        azione = request.POST.get("azione")
        if azione == "token":
            token = request.POST.get("token", "").strip()
            if not cifratura_disponibile():
                messages.error(request, "Manca la chiave di cifratura (CHIAVE_CIFRATURA).")
                return redirect("core:servizi_posta")
            try:
                nome = telegram.verifica(token)
            except telegram.ErroreTelegram as e:
                messages.error(request, f"Token non accettato da Telegram: {e}.")
                return redirect("core:servizi_posta")
            canale.imposta_token(token)
            canale.nome_bot, canale.ultimo_errore = nome, ""
            canale.save()
            registra(Azione.MODIFICA, canale, descrizione="Bot Telegram", bot=nome)
            messages.success(request, f"Bot @{nome} collegato. Attivarlo per usarlo.")
        elif azione == "verifica" and canale.token_cifrato:
            try:
                nome = telegram.verifica(canale.token())
                messages.success(request, f"Telegram: accesso al bot @{nome} riuscito.")
            except telegram.ErroreTelegram as e:
                messages.error(request, f"Telegram: verifica non riuscita ({e}).")
        elif azione == "rimuovi" and canale.token_cifrato:
            bot = canale.nome_bot
            canale.token_cifrato, canale.nome_bot, canale.attivo, canale.ultimo_errore = (
                "",
                "",
                False,
                "",
            )
            canale.save()
            registra(Azione.ELIMINAZIONE, canale, descrizione="Bot Telegram", bot=bot)
            messages.success(request, f"Bot @{bot} rimosso: Telegram non è più configurato.")
        elif azione in ("attiva", "disattiva") and canale.token_cifrato:
            canale.attivo = azione == "attiva"
            canale.save(update_fields=["attivo"])
            registra(Azione.MODIFICA, canale, descrizione="Bot Telegram", attivo=canale.attivo)
            messages.success(request, f"Telegram {'attivato' if canale.attivo else 'disattivato'}.")
        return redirect("core:servizi_posta")


class PresentazioneView(TemplateView):
    """Pagina pubblica: finalità, documenti pubblici, contatti, accesso (anteprima sempre visibile
    a chi gestisce l'organizzazione)."""

    template_name = "core/pubblici/presentazione.html"

    def get(self, request, *args, **kwargs):
        from django.http import Http404

        org = Organizzazione.corrente()
        if not org.pagina_pubblica and not request.user.has_perm("core.gestisci_organizzazione"):
            raise Http404
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        from . import pubblici

        ctx = super().get_context_data(**kwargs)
        ctx["documenti"] = pubblici.pubblicati()
        return ctx


class DocumentiPubbliciView(TemplateView):
    """Pagina pubblica (senza accesso) con statuto, regolamento e altri documenti pubblicati."""

    template_name = "core/pubblici/elenco.html"

    def get_context_data(self, **kwargs):
        from . import pubblici

        ctx = super().get_context_data(**kwargs)
        ctx["documenti"] = pubblici.pubblicati()
        return ctx


class DocumentoPubblicoView(View):
    """Il PDF di un documento pubblicato: nel browser, o da scaricare con ?scarica=1."""

    def get(self, request, pk, slug=None):
        from django.http import FileResponse, Http404

        from . import pubblici

        doc = pubblici.pubblicati().filter(pk=pk).first()
        if doc is None or not doc.file:
            raise Http404
        try:
            contenuto = doc.file.open("rb")
        except FileNotFoundError:
            raise Http404 from None
        risposta = FileResponse(
            contenuto, as_attachment=request.GET.get("scarica") == "1",
            filename=doc.nome_file or "documento.pdf", content_type="application/pdf",
        )  # fmt: skip
        risposta["X-Content-Type-Options"] = "nosniff"
        risposta["Cache-Control"] = "public, max-age=3600"
        return risposta


class GestioneDocumentiPubbliciView(PermessoMixin, ListView):
    permission_required = "core.gestisci_organizzazione"
    template_name = "core/pubblici/gestione.html"
    context_object_name = "documenti"

    def get_queryset(self):
        from .models import DocumentoPubblico

        return DocumentoPubblico.objects.all()


class _DocumentoPubblicoMixin:
    template_name = "core/pubblici/modulo.html"
    success_url = reverse_lazy("core:documenti_pubblici_gestione")

    def get_form_class(self):
        from .forms import DocumentoPubblicoForm

        return DocumentoPubblicoForm

    def form_valid(self, form):
        from . import pubblici

        try:
            self.object = pubblici.salva(form, self.request.user,
                                         form.cleaned_data.get("nuovo_file"))  # fmt: skip
        except pubblici.FileNonValido as e:
            form.add_error("nuovo_file", e)
            return self.form_invalid(form)
        messages.success(self.request, f"«{self.object}» salvato.")
        return redirect(self.success_url)


class DocumentoPubblicoNuovoView(PermessoMixin, _DocumentoPubblicoMixin, CreateView):
    permission_required = "core.gestisci_organizzazione"


class DocumentoPubblicoModificaView(PermessoMixin, _DocumentoPubblicoMixin, UpdateView):
    permission_required = "core.gestisci_organizzazione"

    def get_queryset(self):
        from .models import DocumentoPubblico

        return DocumentoPubblico.objects.all()


class AspettoView(PermessoMixin, UpdateView):
    permission_required = "core.gestisci_organizzazione"
    form_class = AspettoForm
    template_name = "core/aspetto.html"
    success_url = reverse_lazy("core:aspetto")

    def get_object(self, queryset=None):
        return Organizzazione.corrente()

    def form_valid(self, form):
        from .aspetto import salva_aspetto
        from .immagini import ImmagineNonValida

        try:
            salva_aspetto(
                form,
                self.request.user,
                logo=form.cleaned_data.get("nuovo_logo"),
                togli_logo=form.cleaned_data.get("togli_logo"),
            )
        except ImmagineNonValida as e:
            form.add_error("nuovo_logo", e)
            return self.form_invalid(form)
        messages.success(self.request, "Aspetto dell'interfaccia salvato.")
        return redirect(self.success_url)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.setdefault("form_email", AspettoEmailForm(instance=Organizzazione.corrente()))
        return ctx


class AvvisiView(PermessoMixin, TemplateView):
    """Scelta personale degli avvisi (posta, domande, sicurezza) e collegamento di Telegram.
    Accessibile a chi ha il permesso di almeno un tipo di avviso."""

    permission_required = (
        "protocollo.gestisci_posta",
        "soci.valuta_domanda",
        "accounts.change_utente",
    )
    template_name = "core/avvisi.html"

    def has_permission(self):
        return any(self.request.user.has_perm(p) for p in self.get_permission_required())

    def _tipi(self):
        from . import avvisi

        return [t for t in avvisi.TIPI.values() if self.request.user.has_perm(t.permesso)]

    def get_context_data(self, **kwargs):
        from . import avvisi

        ctx = super().get_context_data(**kwargs)
        u = self.request.user
        canali = avvisi.canali_disponibili()
        righe = []
        for t in self._tipi():
            canale = avvisi.canale_di(u, t.chiave)
            scelte = [("", "Automatico: Telegram, se collegato"), (avvisi.NESSUNO, "Nessuno")]
            if not t.automatico:
                scelte = [("", "Nessuno")]
            righe.append({
                "tipo": t, "scelta": avvisi.scelta(u, t.chiave), "scelte": scelte + canali,
                "canale": dict(avvisi.CANALI_NOMI).get(canale, ""),
                "problema": avvisi.problema(u, canale),
            })  # fmt: skip
        ctx.update(
            righe=righe,
            canali=canali,
            attivi=any(r["canale"] and not r["problema"] for r in righe),
            numero=avvisi.numero_di(u),
            soggetto=u.soggetto,
            link_telegram=self.request.session.pop("link_telegram", ""),
        )
        return ctx

    def post(self, request):
        from apps.comunicazioni import telegram

        from . import avvisi

        u = request.user
        azione = request.POST.get("azione")
        if azione == "salva":
            canali = dict(avvisi.canali_disponibili())
            scelte = {}
            for t in self._tipi():
                valore = request.POST.get(t.chiave, "")
                ammessi = {"", *canali} | ({avvisi.NESSUNO} if t.automatico else set())
                if valore not in ammessi:
                    messages.error(request, f"{t.nome}: canale non disponibile.")
                    return redirect("core:avvisi")
                setattr(u, t.campo, valore)
                scelte[t.chiave] = valore or "automatico" if t.automatico else valore or "nessuno"
            u.save(update_fields=[t.campo for t in self._tipi()])
            if "whatsapp" in scelte.values() and u.soggetto and not u.soggetto.whatsapp_consenso_il:
                from django.utils import timezone

                u.soggetto.whatsapp_consenso_il = timezone.now()  # scelto dalla persona stessa
                u.soggetto.save(update_fields=["whatsapp_consenso_il"])
            registra(Azione.MODIFICA, u, descrizione=f"Avvisi di {u}", **scelte)
            problemi = [f"{t.nome}: {m}" for t in self._tipi()
                        if (m := avvisi.problema(u, avvisi.canale_di(u, t.chiave)))]  # fmt: skip
            if problemi:
                messages.warning(request, "Scelta salvata, ma non partono: " + "; ".join(problemi))
            else:
                messages.success(request, "Scelta salvata.")
        elif azione == "telegram" and u.soggetto is not None:
            request.session["link_telegram"] = telegram.link_invito(u.soggetto)
        elif azione == "prova":
            canali = {avvisi.canale_di(u, t.chiave) for t in self._tipi()} - {""}
            for canale in sorted(canali):
                try:
                    avvisi.invia(
                        u,
                        canale,
                        f"Prova degli avvisi di {Organizzazione.corrente().denominazione} ({u}).",
                    )
                    messages.success(
                        request, f"Avviso di prova inviato su {dict(avvisi.CANALI_NOMI)[canale]}."
                    )
                except avvisi.AvvisoNonInviato as e:
                    messages.error(request, f"Avviso di prova non inviato: {e}.")
        return redirect("core:avvisi")


class AspettoEmailView(PermessoMixin, View):
    """Veste delle email: si salva dalla stessa pagina Aspetto, con un modulo a parte."""

    permission_required = "core.gestisci_organizzazione"

    def post(self, request):
        from .aspetto import salva_aspetto_email

        org = Organizzazione.corrente()
        form = AspettoEmailForm(request.POST, instance=org)
        if not form.is_valid():
            vista = AspettoView(request=request, kwargs={}, object=org)
            ctx = vista.get_context_data(form=AspettoForm(instance=org), form_email=form)
            return render(request, "core/aspetto.html", ctx)
        salva_aspetto_email(form, request.user)
        messages.success(request, "Veste delle email salvata.")
        return redirect(f"{reverse('core:aspetto')}#email")


class AnteprimaEmailView(PermessoMixin, View):
    """Il messaggio di esempio, mostrato in un riquadro della pagina Aspetto: la pagina ha una
    CSP propria (solo stili in linea e il logo del sito, niente script) ed è isolata."""

    permission_required = "core.gestisci_organizzazione"

    @method_decorator(xframe_options_sameorigin)
    def get(self, request):
        from .aspetto import anteprima_email

        risposta = HttpResponse(anteprima_email())
        risposta["Content-Security-Policy"] = (
            "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; "
            "frame-ancestors 'self'; sandbox"
        )
        return risposta


class ProvaEmailView(PermessoMixin, View):
    permission_required = "core.gestisci_organizzazione"

    def post(self, request):
        from .aspetto import ProvaNonInviata, invia_prova

        try:
            indirizzo = invia_prova(request.user)
        except ProvaNonInviata as e:
            messages.error(request, str(e))
        except OSError as e:
            messages.error(request, f"Il server di posta non ha accettato il messaggio: {e}")
        else:
            messages.success(request, f"Messaggio di prova inviato a {indirizzo}.")
        return redirect(f"{reverse('core:aspetto')}#email")


class LogoModuloView(PermessoMixin, View):
    permission_required = "core.gestisci_organizzazione"

    def get(self, request):
        from .immagini import risposta_immagine

        return risposta_immagine(Organizzazione.corrente().modulo_logo)


class RegistroAttivitaView(PermessoMixin, ListView):
    permission_required = "core.view_eventoaudit"
    template_name = "core/registro_attivita.html"
    paginate_by = 50

    def get_queryset(self):
        qs = EventoAudit.objects.select_related("oggetto_tipo")
        if azione := self.request.GET.get("azione"):
            qs = qs.filter(azione=azione)
        if utente := self.request.GET.get("utente"):
            qs = qs.filter(utente_descrizione__icontains=utente)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["azioni"] = EventoAudit.Azione.choices
        return ctx


@never_cache
def salute(request):
    """Controllo per il monitoraggio: 200 se applicazione e database rispondono."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return HttpResponse("ok", content_type="text/plain")


# --- help in linea e crediti ------------------------------------------------------------


class AiutoView(LoginRequiredMixin, TemplateView):
    """Manuale operativo consultabile dall'applicazione (docs/operativo)."""

    template_name = "core/aiuto.html"

    def get_context_data(self, **kwargs):
        from . import aiuto

        ctx = super().get_context_data(**kwargs)
        nome = kwargs.get("pagina", aiuto.INDICE)
        titolo, html, indice = aiuto.pagina(nome)
        ctx.update(pagina=nome, titolo=titolo, html=html, indice=indice, pagine=aiuto.elenco())
        if self.request.user.has_perm("protocollo.view_manualegestione"):
            from apps.protocollo.manuale import ultima_versione

            ctx["manuale_gestione"] = ultima_versione()
        return ctx


class CercaView(LoginRequiredMixin, TemplateView):
    """Ricerca globale nei moduli che l'utente può consultare."""

    template_name = "core/cerca.html"

    def get_context_data(self, **kwargs):
        from . import ricerca

        ctx = super().get_context_data(**kwargs)
        testo = self.request.GET.get("q", "").strip()
        gruppi = ricerca.cerca(self.request.user, testo)
        ctx.update(q=testo, gruppi=gruppi, troppo_corto=ricerca.troppo_corto(testo),
                   totale=sum(g.totale for g in gruppi))  # fmt: skip
        return ctx


class ManualePdfView(LoginRequiredMixin, View):
    """Il manuale operativo completo in PDF, con le immagini."""

    def get(self, request):
        from django.http import FileResponse

        from . import aiuto

        percorso = aiuto.pdf_manuale()
        return FileResponse(percorso.open("rb"), filename="manuale-operativo.pdf",
                            content_type="application/pdf")  # fmt: skip


class InformazioniView(LoginRequiredMixin, TemplateView):
    """Versione, autore, licenza e componenti di terze parti."""

    template_name = "core/informazioni.html"

    def get_context_data(self, **kwargs):
        from django.conf import settings

        from . import aiuto

        ctx = super().get_context_data(**kwargs)
        ctx.update(
            licenze=aiuto.licenze(), novita=aiuto.novita(), repository=settings.APP_REPOSITORY
        )
        return ctx
