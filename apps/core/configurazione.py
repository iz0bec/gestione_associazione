# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Configurazione iniziale guidata (wizard): dati dell'ente, aspetto, sezioni,
# *              tesseramento (listino), tesoreria (esercizio e saldi), riepilogo. Ogni passo
# *              salva subito; si può ripetere in seguito per rivedere le impostazioni.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import re
from datetime import date
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View

from .audit import Azione, registra
from .forms import AspettoForm, EnteForm, StileMixin
from .models import Organizzazione
from .views import PermessoMixin

PASSI = [
    ("ente", "Dati dell'ente", "building"),
    ("aspetto", "Logo e colori", "palette"),
    ("sezioni", "Sezioni", "map-pin"),
    ("tesseramento", "Tesseramento", "id-badge-2"),
    ("tesoreria", "Tesoreria", "cash"),
    ("riepilogo", "Riepilogo", "checklist"),
]
CHIAVI = [p[0] for p in PASSI]


def da_configurare(utente):
    """Vero se l'ente non è ancora configurato e l'utente può farlo."""
    return (
        utente.has_perm("core.gestisci_organizzazione")
        and not Organizzazione.corrente().configurata
    )


# --- moduli dei passi --------------------------------------------------------------------


class SezioniForm(StileMixin, forms.Form):
    struttura = forms.ChoiceField(
        label="Come è organizzata l'associazione?",
        choices=[
            ("singola", "Un'unica associazione (o una sola sezione)"),
            ("federazione", "Una federazione con più sezioni territoriali"),
        ],
        widget=forms.RadioSelect,
    )
    codice = forms.CharField(
        label="Codice della sezione", max_length=20, required=False,
        help_text="Come nel registro nazionale, se esiste (es. 085).",
    )  # fmt: skip
    nome = forms.CharField(label="Nome della sezione", max_length=150, required=False)
    elenco = forms.CharField(
        label="Sezioni della federazione",
        required=False,
        widget=forms.Textarea(
            attrs={"rows": 6, "placeholder": "085; Sezione di Avigliano; Avigliano; PZ"}
        ),
        help_text="Una per riga: codice; nome; comune; provincia (comune e provincia facoltativi). "
        "Le sezioni si possono aggiungere anche in seguito o con l'importazione dei soci.",
    )

    def clean(self):
        d = super().clean()
        if d.get("struttura") == "singola" and not (d.get("codice") and d.get("nome")):
            raise ValidationError("Indicare codice e nome della sezione.")
        if d.get("struttura") == "federazione":
            d["righe"] = []
            for n, riga in enumerate((d.get("elenco") or "").splitlines(), start=1):
                if not riga.strip():
                    continue
                parti = [p.strip() for p in riga.split(";")]
                if len(parti) < 2 or not parti[0] or not parti[1]:
                    raise ValidationError(
                        f"Riga {n}: servono almeno codice e nome separati da «;»."
                    )
                parti += ["", ""]
                # «Avigliano, PZ» scritto con la virgola: comune e provincia insieme
                if not parti[3] and (m := re.fullmatch(r"(.+?),\s*([A-Za-z]{2})", parti[2])):
                    parti[2], parti[3] = m.group(1).strip(), m.group(2)
                provincia = parti[3].upper()[:2]
                d["righe"].append((parti[0][:20], parti[1][:150], parti[2][:100], provincia))
            if not d["righe"]:
                raise ValidationError("Indicare almeno una sezione.")
            from apps.soci.importazione import comune_normale

            comuni = [comune_normale(r[2]) for r in d["righe"] if r[2]]
            doppi = sorted({c for c in comuni if comuni.count(c) > 1})
            if doppi:
                raise ValidationError(
                    f"Ogni comune può avere una sola sezione: ripetuto {', '.join(doppi)}."
                )
        return d


class TesseramentoForm(StileMixin, forms.Form):
    anno = forms.TypedChoiceField(label="Anno del tesseramento", coerce=int, choices=())

    def __init__(self, *args, **kwargs):
        from apps.soci.forms import ListinoForm

        super().__init__(*args, **kwargs)
        oggi = date.today().year
        self.fields["anno"].choices = [(a, str(a)) for a in (oggi, oggi + 1)]
        anno = int(self.data.get("anno") or self.initial.get("anno") or oggi)
        from apps.soci.servizi import listino

        self.listino_form = ListinoForm(*args, listino=listino(anno), **kwargs)
        self.fields.update(self.listino_form.fields)
        self.tipologie = self.listino_form.tipologie

    def campi_quota(self):
        return [self[f"quota_{t.pk}"] for t in self.tipologie]

    def quote(self):
        return {t: self.cleaned_data[f"quota_{t.pk}"] for t in self.tipologie}


class TesoreriaForm(StileMixin, forms.Form):
    anno = forms.TypedChoiceField(label="Primo esercizio da gestire", coerce=int, choices=())

    def __init__(self, *args, **kwargs):
        from apps.tesoreria.models import Conto

        super().__init__(*args, **kwargs)
        oggi = date.today().year
        self.fields["anno"].choices = [(a, str(a)) for a in (oggi - 1, oggi, oggi + 1)]
        self.fields["anno"].initial = oggi
        self.conti = list(Conto.objects.filter(attivo=True))
        for c in self.conti:
            self.fields[f"iban_{c.pk}"] = forms.CharField(
                label=f"IBAN di «{c.nome}»", max_length=34, required=False, initial=c.iban
            )
            self.fields[f"saldo_{c.pk}"] = forms.DecimalField(
                label=f"Saldo di «{c.nome}» all'inizio dell'esercizio (€)",
                max_digits=12, decimal_places=2, initial=Decimal("0"),
            )  # fmt: skip
            if c.e_cassa:
                del self.fields[f"iban_{c.pk}"]

    def righe_conti(self):
        return [(c, self[f"saldo_{c.pk}"], self[f"iban_{c.pk}"] if not c.e_cassa else None)
                for c in self.conti]  # fmt: skip


# --- salvataggio dei passi ---------------------------------------------------------------


@transaction.atomic
def _salva_sezioni(d, utente):
    from apps.soci.models import Sezione

    if d["struttura"] == "singola":
        s = Sezione.predefinita()
        s.codice, s.nome = d["codice"], d["nome"]
        org = Organizzazione.corrente()
        s.comune, s.provincia = s.comune or org.comune, s.provincia or org.provincia
        s.save()
        registra(Azione.MODIFICA, s, utente=utente, configurazione="sezione unica")
        return
    predefinita = Sezione.predefinita()
    for i, (codice, nome, comune, provincia) in enumerate(d["righe"]):
        s = Sezione.objects.filter(codice=codice).first()
        if s is None and i == 0 and not predefinita.soci.exists():
            s = predefinita  # la sezione creata in automatico diventa la prima dell'elenco
        if s is None:
            s = Sezione(codice=codice)
        s.codice, s.nome, s.ordine = codice, nome, i
        s.comune, s.provincia = comune or s.comune, provincia or s.provincia
        s.save()
    registra(Azione.MODIFICA, utente=utente, descrizione="Sezioni della federazione",
             sezioni=len(d["righe"]))  # fmt: skip


def _salva_tesoreria(form, utente):
    from apps.tesoreria import servizi as tesoreria
    from apps.tesoreria.models import Esercizio

    anno = form.cleaned_data["anno"]
    with transaction.atomic():
        esercizio = Esercizio.objects.filter(anno=anno).first() or tesoreria.apri_esercizio(
            anno, utente
        )
        for c in form.conti:
            iban = form.cleaned_data.get(f"iban_{c.pk}", c.iban).replace(" ", "").upper()
            if iban != c.iban:
                c.iban = iban
                c.save(update_fields=["iban"])
        if tesoreria.saldi_iniziali_modificabili(esercizio):
            tesoreria.imposta_saldi_iniziali(
                esercizio, {c: form.cleaned_data[f"saldo_{c.pk}"] for c in form.conti}, utente
            )
    return esercizio


# --- vista -------------------------------------------------------------------------------


class ConfigurazioneView(PermessoMixin, View):
    permission_required = "core.gestisci_organizzazione"

    def dispatch(self, request, *args, passo="ente", **kwargs):
        if passo not in CHIAVI:
            raise Http404
        self.passo = passo
        return super().dispatch(request, *args, **kwargs)

    def _successivo(self):
        return reverse("configurazione", args=[CHIAVI[CHIAVI.index(self.passo) + 1]])

    def _form(self, data=None, files=None):
        org = Organizzazione.corrente()
        if self.passo == "ente":
            return EnteForm(data, instance=org)
        if self.passo == "aspetto":
            return AspettoForm(data, files, instance=org)
        if self.passo == "sezioni":
            from apps.soci.models import Sezione

            sezioni = list(Sezione.objects.all())
            iniziale = {
                "struttura": "federazione" if len(sezioni) > 1 else "singola",
                "codice": sezioni[0].codice if sezioni else "",
                "nome": sezioni[0].nome if sezioni else org.nome_breve,
                "elenco": "\n".join(
                    "; ".join(x for x in (s.codice, s.nome, s.comune, s.provincia) if x)
                    for s in sezioni
                ),
            }
            if len(sezioni) == 1 and sezioni[0].nome == "Sezione principale":
                iniziale["nome"] = org.nome_breve
            return SezioniForm(data, initial=iniziale)
        if self.passo == "tesseramento":
            return TesseramentoForm(data, initial={"anno": date.today().year})
        if self.passo == "tesoreria":
            return TesoreriaForm(data)
        return None

    def _contesto(self, form):
        indice = CHIAVI.index(self.passo)
        ctx = {
            "passi": PASSI, "passo": self.passo, "indice": indice, "form": form,
            "titolo_passo": PASSI[indice][1],
            "precedente": reverse("configurazione", args=[CHIAVI[indice - 1]]) if indice else None,
        }  # fmt: skip
        if self.passo == "riepilogo":
            ctx.update(_riepilogo())
        return ctx

    def get(self, request):
        return render(request, "core/configurazione.html", self._contesto(self._form()))

    def post(self, request):
        if self.passo == "riepilogo":
            org = Organizzazione.corrente()
            org.configurata = True
            org.save(update_fields=["configurata", "modificato_il"])
            registra(Azione.MODIFICA, org, descrizione="Configurazione iniziale completata")
            messages.success(request, "Configurazione completata. Buon lavoro!")
            return redirect("core:cruscotto")
        if request.POST.get("salta"):
            return redirect(self._successivo())
        form = self._form(request.POST, request.FILES)
        if not form.is_valid():
            return render(request, "core/configurazione.html", self._contesto(form))
        try:
            self._salva(form, request.user)
        except ValidationError as e:
            form.add_error(None, e)
            return render(request, "core/configurazione.html", self._contesto(form))
        return redirect(self._successivo())

    def _salva(self, form, utente):
        if self.passo == "ente":
            from .audit import campi_modificati

            dettagli = campi_modificati(form)
            form.save()
            if dettagli.get("campi"):
                registra(Azione.MODIFICA, form.instance, utente=utente, **dettagli)
        elif self.passo == "aspetto":
            from .aspetto import salva_aspetto

            salva_aspetto(form, utente, logo=form.cleaned_data.get("nuovo_logo"),
                          togli_logo=form.cleaned_data.get("togli_logo"))  # fmt: skip
        elif self.passo == "sezioni":
            _salva_sezioni(form.cleaned_data, utente)
        elif self.passo == "tesseramento":
            from apps.soci.servizi import salva_listino

            d = form.cleaned_data
            salva_listino(
                d["anno"], utente, costo_acquisto=d["costo_acquisto"], quote=form.quote(),
                note=d["note"],
            )  # fmt: skip
        elif self.passo == "tesoreria":
            _salva_tesoreria(form, utente)


def _riepilogo():
    from django.conf import settings

    from apps.soci.models import ListinoTessere, Sezione
    from apps.tesoreria.models import Esercizio

    org = Organizzazione.corrente()
    listino = ListinoTessere.objects.prefetch_related("quote__tipologia").first()
    esercizio = Esercizio.objects.order_by("-anno").prefetch_related("saldi__conto").first()
    return {
        "org": org,
        "sezioni": Sezione.objects.filter(attiva=True),
        "listino": listino,
        "esercizio": esercizio,
        "email_configurata": settings.MAILERS["default"]["BACKEND"].endswith("smtp.EmailBackend"),
        "url_pubblico": settings.URL_PUBBLICO,
    }
