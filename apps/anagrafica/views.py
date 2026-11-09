# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Viste dell'anagrafica: elenco con ricerca istantanea (HTMX),
# *              scheda, inserimento, modifica, archiviazione, consensi, esportazione CSV e
# *              vCard, importazione da rubrica.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import base64
import io
from datetime import date

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils.text import slugify
from django.views import View
from django.views.generic import CreateView, DetailView, FormView, TemplateView, UpdateView
from django_filters.views import FilterView

from apps.core.immagini import ImmagineNonValida, risposta_immagine
from apps.core.models import EventoAudit
from apps.core.views import PermessoMixin

from . import codice_fiscale, servizi, vcard
from .filtri import SoggettoFilter
from .forms import ConsensoForm, ImportaVCardForm, SoggettoForm
from .models import Soggetto


class ElencoView(PermessoMixin, FilterView):
    permission_required = "anagrafica.view_soggetto"
    filterset_class = SoggettoFilter
    paginate_by = 25
    template_name = "anagrafica/elenco.html"

    def get_queryset(self):
        return Soggetto.objects.prefetch_related("categorie")

    def get_template_names(self):
        # richiesta HTMX dalla ricerca: solo la tabella
        if self.request.htmx and not self.request.htmx.boosted:
            return ["anagrafica/elenco.html#tabella"]
        return [self.template_name]


class DettaglioView(PermessoMixin, DetailView):
    permission_required = "anagrafica.view_soggetto"
    model = Soggetto
    template_name = "anagrafica/dettaglio.html"
    context_object_name = "soggetto"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["consensi"] = self.object.consensi.all()
        ctx["form_consenso"] = ConsensoForm()
        ctx["socio"] = getattr(self.object, "socio", None)
        from apps.organi.models import cariche_di

        ctx["cariche"] = cariche_di(self.object) if self.object.is_persona else []
        if self.object.is_persona and not self.object.anonimizzato_il:
            esame = codice_fiscale.esamina(self.object)
            if esame.stato != "mancante" or ctx["socio"]:
                ctx["esame_cf"] = esame
        if self.request.user.has_perm("comunicazioni.view_invio"):
            ctx["comunicazioni"] = self.object.comunicazioni.select_related("invio").order_by(
                "-invio__creato_il"
            )[:10]
        if self.request.user.has_perm("protocollo.view_protocollo"):
            from apps.protocollo.models import Protocollo

            ctx["protocolli"] = (
                Protocollo.objects.visibili_a(self.request.user)
                .filter(corrispondenti__soggetto=self.object)
                .distinct()[:10]
            )
        if self.request.user.has_perm("anagrafica.anonimizza_soggetto"):
            from . import gdpr

            ctx["impedimenti_gdpr"] = gdpr.impedimenti(self.object)
            ctx["parola_gdpr"] = gdpr.PAROLA_CONFERMA
        if self.request.user.has_perm("core.view_eventoaudit"):
            ctx["storia"] = EventoAudit.objects.filter(
                oggetto_tipo=ContentType.objects.get_for_model(Soggetto),
                oggetto_id=str(self.object.pk),
            )[:20]
        return ctx


class _SalvaMixin:
    model = Soggetto
    form_class = SoggettoForm
    template_name = "anagrafica/modulo.html"
    context_object_name = "soggetto"

    def form_valid(self, form):
        try:
            self.object = servizi.salva_soggetto(
                form,
                self.request.user,
                foto=form.cleaned_data.get("nuova_foto"),
                togli_foto=form.cleaned_data.get("togli_foto"),
            )
        except ImmagineNonValida as e:
            form.add_error("nuova_foto", e)
            return self.form_invalid(form)
        messages.success(self.request, f"«{self.object}» salvato.")
        return redirect(self.object)


class CreaView(PermessoMixin, _SalvaMixin, CreateView):
    permission_required = "anagrafica.add_soggetto"

    def get_initial(self):
        iniziali = super().get_initial()
        if tipo := self.request.GET.get("tipo"):
            iniziali["tipo"] = tipo
        return iniziali


class ModificaView(PermessoMixin, _SalvaMixin, UpdateView):
    permission_required = "anagrafica.change_soggetto"

    def get_queryset(self):
        return Soggetto.objects.filter(anonimizzato_il__isnull=True)  # le anonimizzate no


class FotoView(LoginRequiredMixin, View):
    """Foto del soggetto: per chi vede l'anagrafica o, se è un socio, il libro soci."""

    def get(self, request, pk):
        soggetto = get_object_or_404(Soggetto, pk=pk)
        utente = request.user
        if not (
            utente.has_perm("anagrafica.view_soggetto")
            or (utente.has_perm("soci.view_socio") and hasattr(soggetto, "socio"))
        ):
            raise PermissionDenied
        return risposta_immagine(soggetto.foto)


class ArchiviaView(PermessoMixin, View):
    permission_required = "anagrafica.archivia_soggetto"
    http_method_names = ["post"]

    def post(self, request, pk):
        soggetto = get_object_or_404(Soggetto, pk=pk)
        archivia = request.POST.get("azione") == "archivia"
        servizi.imposta_archiviato(soggetto, archivia, request.user)
        messages.success(request, f"«{soggetto}» {'archiviato' if archivia else 'ripristinato'}.")
        return redirect(soggetto)


class ConsensoView(PermessoMixin, View):
    permission_required = "anagrafica.add_consenso"
    http_method_names = ["post"]

    def post(self, request, pk):
        soggetto = get_object_or_404(Soggetto, pk=pk)
        form = ConsensoForm(request.POST)
        if form.is_valid():
            consenso = form.save(commit=False)
            consenso.soggetto = soggetto
            consenso.save()
            from apps.core.audit import Azione, registra

            registra(Azione.MODIFICA, soggetto, consenso=str(consenso))
            messages.success(request, "Consenso registrato.")
        else:
            messages.error(request, "Consenso non registrato: controllare i dati.")
        return redirect(soggetto)


class EsportaView(PermessoMixin, View):
    permission_required = "anagrafica.esporta_soggetti"

    def get(self, request):
        filtro = SoggettoFilter(request.GET, queryset=Soggetto.objects.all())
        buffer = io.StringIO()
        servizi.esporta_csv(filtro.qs, buffer, request.user)
        risposta = HttpResponse("﻿" + buffer.getvalue(), content_type="text/csv; charset=utf-8")
        risposta["Content-Disposition"] = (
            f'attachment; filename="anagrafica_{date.today():%Y%m%d}.csv"'
        )
        return risposta


def _risposta_vcf(testo, nome):
    risposta = HttpResponse(testo, content_type="text/vcard; charset=utf-8")
    risposta["Content-Disposition"] = f'attachment; filename="{nome}"'
    return risposta


class EsportaVCardView(PermessoMixin, View):
    """Le schede dell'elenco filtrato in un file .vcf da aprire con la rubrica."""

    permission_required = "anagrafica.esporta_soggetti"

    def get(self, request):
        filtro = SoggettoFilter(request.GET, queryset=Soggetto.objects.all())
        testo, _n = vcard.esporta(filtro.qs, request.user)
        return _risposta_vcf(testo, f"rubrica_{date.today():%Y%m%d}.vcf")


class VCardSoggettoView(PermessoMixin, View):
    permission_required = "anagrafica.esporta_soggetti"

    def get(self, request, pk):
        soggetto = get_object_or_404(Soggetto, pk=pk)
        testo, _n = vcard.esporta(Soggetto.objects.filter(pk=pk), request.user,
                                  descrizione=f"vCard di {soggetto}")  # fmt: skip
        return _risposta_vcf(testo, f"{slugify(soggetto.nome_completo) or soggetto.pk}.vcf")


class ImportaVCardView(PermessoMixin, FormView):
    """Caricamento del file, anteprima (nulla viene salvato) e conferma."""

    permission_required = "anagrafica.importa_soggetti"
    form_class = ImportaVCardForm
    template_name = "anagrafica/importa_vcard.html"
    CHIAVE = "importa_vcard"

    def _rapporto(self, righe, **extra):
        return self.render_to_response(self.get_context_data(
            righe=righe, conteggi=vcard.riepilogo(righe), **extra
        ))  # fmt: skip

    def form_valid(self, form):
        contenuto = form.cleaned_data["file"].read()
        try:
            contatti = vcard.leggi(contenuto)
        except vcard.FileNonValido as e:
            form.add_error("file", e)
            return self.form_invalid(form)
        categoria = form.cleaned_data["categoria"]
        self.request.session[self.CHIAVE] = {
            "contenuto": base64.b64encode(contenuto).decode("ascii"),
            "nome": form.cleaned_data["file"].name,
            "categoria": categoria.pk if categoria else None,
        }
        righe = vcard.importa(contatti, self.request.user, categoria=categoria)
        return self._rapporto(righe, anteprima=True, nome_file=form.cleaned_data["file"].name,
                              categoria=categoria)  # fmt: skip

    def post(self, request, *args, **kwargs):
        if request.POST.get("azione") != "esegui":
            return super().post(request, *args, **kwargs)
        dati = request.session.pop(self.CHIAVE, None)
        if not dati:
            messages.error(request, "Anteprima scaduta: caricare di nuovo il file.")
            return redirect("anagrafica:importa_vcard")
        from .models import Categoria

        categoria = Categoria.objects.filter(pk=dati["categoria"]).first()
        contatti = vcard.leggi(base64.b64decode(dati["contenuto"]))
        righe = vcard.importa(contatti, request.user, categoria=categoria, esegui=True)
        c = vcard.riepilogo(righe)
        messages.success(request, f"Importazione completata: {c['nuovo']} schede nuove, "
                                  f"{c['aggiornato']} completate.")  # fmt: skip
        return self._rapporto(righe, eseguita=True, nome_file=dati["nome"], categoria=categoria)


class DatiPersonaliView(PermessoMixin, View):
    """Tutti i dati della persona in un archivio ZIP (JSON + riepilogo PDF + foto)."""

    permission_required = "anagrafica.esporta_dati_personali"

    def get(self, request, pk):
        from . import gdpr

        soggetto = get_object_or_404(Soggetto, pk=pk)
        risposta = HttpResponse(
            gdpr.esporta(soggetto, request.user), content_type="application/zip"
        )
        nome = slugify(soggetto.nome_completo) or str(soggetto.pk)
        risposta["Content-Disposition"] = f'attachment; filename="dati-personali-{nome}.zip"'
        risposta["Content-Security-Policy"] = "default-src 'none'; sandbox"
        return risposta


class AnonimizzaView(PermessoMixin, View):
    permission_required = "anagrafica.anonimizza_soggetto"
    http_method_names = ["post"]

    def post(self, request, pk):
        from . import gdpr

        soggetto = get_object_or_404(Soggetto, pk=pk)
        try:
            gdpr.anonimizza(soggetto, request.user, motivo=request.POST.get("motivo", ""),
                            conferma=request.POST.get("conferma", ""))  # fmt: skip
        except gdpr.OperazioneNonValida as e:
            messages.error(request, " ".join(e.messages))
        else:
            messages.success(request, "Dati personali cancellati: la scheda è anonimizzata.")
        return redirect(soggetto)


class ConservazioneView(PermessoMixin, View):
    """Termini di conservazione: impostazioni e persone oltre il termine, da anonimizzare."""

    permission_required = "anagrafica.anonimizza_soggetto"
    template_name = "anagrafica/conservazione.html"

    def _pagina(self, request, form):
        from django.shortcuts import render

        from apps.core.models import Organizzazione

        from . import gdpr

        return render(request, self.template_name, {
            "form": form, "scaduti": gdpr.scaduti(), "parola": gdpr.PAROLA_CONFERMA,
            "organizzazione_conservazione": Organizzazione.corrente(),
        })  # fmt: skip

    def get(self, request):
        from apps.core.models import Organizzazione

        from .forms import ConservazioneForm

        return self._pagina(request, ConservazioneForm(instance=Organizzazione.corrente()))

    def post(self, request):
        from apps.core.audit import Azione, campi_modificati, registra
        from apps.core.models import Organizzazione

        from . import gdpr
        from .forms import ConservazioneForm

        if request.POST.get("azione") == "anonimizza":
            if request.POST.get("conferma", "").strip().upper() != gdpr.PAROLA_CONFERMA:
                messages.error(request, f"Per confermare scrivere {gdpr.PAROLA_CONFERMA}.")
                return redirect("anagrafica:conservazione")
            ids = [i for i in request.POST.getlist("soggetti") if i.isdigit()]
            scelti = list(Soggetto.objects.filter(pk__in=ids))
            if not scelti:
                messages.warning(request, "Nessuna persona selezionata.")
                return redirect("anagrafica:conservazione")
            fatti, saltati = gdpr.anonimizza_scaduti(request.user, scelti)
            testo = f"{fatti} persone anonimizzate."
            if saltati:
                testo += f" {saltati} saltate (non più oltre il termine o con impedimenti)."
            messages.success(request, testo)
            return redirect("anagrafica:conservazione")
        form = ConservazioneForm(request.POST, instance=Organizzazione.corrente())
        if not form.is_valid():
            return self._pagina(request, form)
        dettagli = campi_modificati(form)
        org = form.save()
        if dettagli.get("campi"):
            registra(Azione.MODIFICA, org, descrizione="Conservazione dei dati", **dettagli)
        messages.success(request, "Termini di conservazione salvati.")
        return redirect("anagrafica:conservazione")


# --- codice fiscale assistito ------------------------------------------------------------


class CalcolaCodiceFiscaleView(PermessoMixin, View):
    """Calcolo del codice fiscale per il pulsante «Calcola» dei moduli (risposta JSON).

    Con un codice già scritto nel modulo segnala anche le differenze con i dati.
    """

    http_method_names = ["post"]
    PERMESSI = (
        "anagrafica.add_soggetto",
        "anagrafica.change_soggetto",
        "soci.add_domandaiscrizione",
    )

    def has_permission(self):
        return any(self.request.user.has_perm(p) for p in self.PERMESSI)

    def post(self, request):
        dati = {
            campo: request.POST.get(campo, "").strip()
            for campo in ("cognome", "nome", "sesso", "data_nascita", "luogo_nascita")
        }
        calcolo = codice_fiscale.calcola(**dati)
        attuale = request.POST.get("codice_fiscale", "").strip().upper()
        avvisi = []
        if attuale and calcolo.codice and attuale != calcolo.codice:
            avvisi = codice_fiscale.anomalie(attuale, **dati)
        return JsonResponse({
            "codice": calcolo.codice,
            "errore": calcolo.errore,
            "candidati": [luogo.etichetta for luogo in calcolo.candidati],
            "avvisi": avvisi,
        })  # fmt: skip


class CodiciFiscaliView(PermessoMixin, TemplateView):
    """Persone con il codice fiscale mancante, non valido o non corrispondente ai dati,
    con la correzione calcolata da applicare (una per volta, con conferma)."""

    permission_required = "anagrafica.view_soggetto"
    template_name = "anagrafica/codici_fiscali.html"
    STATI = {
        "non_valido": "Non validi",
        "incoerente": "Non corrispondenti",
        "mancante": "Mancanti (soci)",
    }

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        persone = (
            Soggetto.objects.attivi()
            .filter(tipo=Soggetto.Tipo.PERSONA, anonimizzato_il__isnull=True)
            .order_by("cognome", "nome")
        )
        esami = [(p, codice_fiscale.esamina(p)) for p in persone.select_related("socio")]
        # un codice mancante si segnala solo per i soci (per un contatto della rubrica è normale)
        da_sistemare = [
            (p, e) for p, e in esami
            if e.da_sistemare and (e.stato != "mancante" or hasattr(p, "socio"))
        ]  # fmt: skip
        stato = self.request.GET.get("stato", "")
        if stato not in self.STATI:
            stato = "non_valido" if any(e.stato == "non_valido" for _, e in da_sistemare) else ""
        ctx.update(
            stato=stato,
            stati=[
                (chiave, etichetta, sum(1 for _, e in da_sistemare if e.stato == chiave))
                for chiave, etichetta in self.STATI.items()
            ],
            righe=[(p, e) for p, e in da_sistemare if not stato or e.stato == stato],
            totale=len(esami),
            puo_correggere=self.request.user.has_perm("anagrafica.change_soggetto"),
        )
        return ctx

    def post(self, request):
        if not request.user.has_perm("anagrafica.change_soggetto"):
            raise PermissionDenied
        soggetto = get_object_or_404(Soggetto, pk=request.POST.get("soggetto"))
        try:
            codice_fiscale.correggi(soggetto, request.POST.get("codice", ""), request.user)
        except codice_fiscale.OperazioneNonValida as e:
            messages.error(request, f"{soggetto.nome_completo}: {e}")
        else:
            messages.success(request, f"Codice fiscale di {soggetto.nome_completo} aggiornato.")
        return redirect(f"{request.path}?stato={request.POST.get('stato', '')}")
