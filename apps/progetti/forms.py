# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Moduli del modulo Progetti (P1): idee, valutazioni, priorità, progetti, stato,
# *              gruppo di lavoro, scadenze, commenti, allegati, finalità e criteri.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django import forms
from django.contrib.auth import get_user_model

from apps.anagrafica.forms import CampoData
from apps.anagrafica.models import Soggetto
from apps.core.forms import StileMixin

from .models import (
    Attivita,
    Bando,
    CriterioValutazione,
    FinalitaStatutaria,
    FonteBandi,
    FonteFinanziamento,
    Idea,
    Indicatore,
    LimiteCategoria,
    Obiettivo,
    ParolaChiave,
    Partner,
    Progetto,
    Requisito,
    VoceCosto,
)


def _delibere():
    from apps.organi.models import Delibera

    return Delibera.objects.select_related("verbale__riunione__organo").order_by("-pk")[:200]


class _ConFinalita:
    def _finalita(self):
        self.fields["finalita"].queryset = FinalitaStatutaria.objects.filter(attiva=True)
        self.fields["finalita"].widget = forms.CheckboxSelectMultiple()
        self.fields["finalita"].widget.choices = self.fields["finalita"].choices
        if not self.fields["finalita"].queryset.exists():
            self.fields[
                "finalita"
            ].help_text = (
                "Nessuna finalità statutaria inserita: si aggiungono in Progetti → Finalità."
            )


class IdeaForm(StileMixin, _ConFinalita, forms.ModelForm):
    class Meta:
        model = Idea
        fields = [
            "titolo",
            "descrizione",
            "bisogno",
            "destinatari",
            "finalita",
            "costo_stimato",
            "fonte",
            "fonte_soggetto",
            "fonte_testo",
        ]
        widgets = {
            "descrizione": forms.Textarea(attrs={"rows": 4}),
            "bisogno": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._finalita()
        self.fields["fonte_soggetto"].queryset = Soggetto.objects.attivi().order_by(
            "cognome", "nome", "denominazione"
        )
        self.fields["fonte_soggetto"].required = False

    def clean(self):
        dati = super().clean()
        if dati.get("fonte") == Idea.Fonte.ESTERNA and not (
            dati.get("fonte_soggetto") or (dati.get("fonte_testo") or "").strip()
        ):
            self.add_error("fonte_testo", "Per una sollecitazione esterna indicare da chi arriva.")
        return dati


class PrioritaForm(StileMixin, forms.Form):
    priorita = forms.ChoiceField(
        label="Priorità", required=False, choices=[("", "— nessuna —"), *Idea.Priorita.choices]
    )
    delibera = forms.ModelChoiceField(
        label="Delibera",
        required=False,
        queryset=None,
        help_text="La delibera del consiglio che fissa la priorità.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["delibera"].queryset = _delibere()


class ProgettoForm(StileMixin, _ConFinalita, forms.ModelForm):
    class Meta:
        model = Progetto
        fields = [
            "titolo",
            "sintesi",
            "finalita",
            "responsabile",
            "inizio_previsto",
            "fine_prevista",
        ]
        widgets = {
            "sintesi": forms.Textarea(attrs={"rows": 4}),
            "inizio_previsto": CampoData,
            "fine_prevista": CampoData,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._finalita()
        self.fields["responsabile"].queryset = (
            get_user_model()
            .objects.filter(is_active=True)
            .order_by("first_name", "last_name", "username")
        )

    def clean(self):
        dati = super().clean()
        inizio, fine = dati.get("inizio_previsto"), dati.get("fine_prevista")
        if inizio and fine and fine < inizio:
            self.add_error("fine_prevista", "La fine non può precedere l'inizio.")
        return dati


class AvvioForm(forms.Form):
    """Delibera facoltativa che avvia la progettazione (da un'idea o da zero)."""

    delibera = forms.ModelChoiceField(label="Delibera di avvio", required=False, queryset=None)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["delibera"].queryset = _delibere()


class StatoForm(StileMixin, forms.Form):
    stato = forms.ChoiceField(label="Nuovo stato")
    motivo = forms.CharField(label="Motivo", max_length=255, required=False)
    delibera = forms.ModelChoiceField(label="Delibera", required=False, queryset=None)

    def __init__(self, *args, progetto, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["stato"].choices = progetto.stati_successivi
        self.fields["delibera"].queryset = _delibere()


class MembroForm(StileMixin, forms.Form):
    utente = forms.ModelChoiceField(label="Utente del gestionale", required=False, queryset=None)
    soggetto = forms.ModelChoiceField(
        label="Oppure persona dell'anagrafica", required=False, queryset=None
    )
    ruolo = forms.CharField(max_length=100)
    volontario = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["utente"].queryset = (
            get_user_model()
            .objects.filter(is_active=True)
            .order_by("first_name", "last_name", "username")
        )
        self.fields["soggetto"].queryset = Soggetto.objects.attivi().order_by(
            "cognome", "nome", "denominazione"
        )


class ScadenzaForm(StileMixin, forms.Form):
    titolo = forms.CharField(max_length=200)
    data = forms.DateField(widget=CampoData)


class AllegatoForm(StileMixin, forms.Form):
    file = forms.FileField()
    descrizione = forms.CharField(max_length=255, required=False)


class FinalitaForm(StileMixin, forms.ModelForm):
    class Meta:
        model = FinalitaStatutaria
        fields = ["codice", "titolo", "testo", "ordine", "attiva"]
        widgets = {"testo": forms.Textarea(attrs={"rows": 3})}


class CriterioForm(StileMixin, forms.ModelForm):
    class Meta:
        model = CriterioValutazione
        fields = ["nome", "descrizione", "peso", "ordine", "attivo"]


# --- bandi (P2) ----------------------------------------------------------------------------------


class BandoForm(StileMixin, _ConFinalita, forms.ModelForm):
    class Meta:
        model = Bando
        fields = [
            "titolo",
            "finanziatore",
            "finanziatore_testo",
            "link",
            "descrizione",
            "finalita",
            "importo_massimo",
            "cofinanziamento",
            "spese_generali_massime",
            "natura_massima",
            "apertura",
            "scadenza",
            "esito_previsto",
        ]
        widgets = {
            "descrizione": forms.Textarea(attrs={"rows": 4}),
            "apertura": CampoData,
            "scadenza": CampoData,
            "esito_previsto": CampoData,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._finalita()
        self.fields["finanziatore"].queryset = Soggetto.objects.attivi().order_by(
            "denominazione", "cognome", "nome"
        )

    def clean(self):
        dati = super().clean()
        apertura, scadenza = dati.get("apertura"), dati.get("scadenza")
        if apertura and scadenza and scadenza < apertura:
            self.add_error("scadenza", "La scadenza non può precedere l'apertura.")
        return dati


class RequisitoForm(StileMixin, forms.Form):
    verifica = forms.ChoiceField(label="Verifica", required=False)
    parametro = forms.CharField(
        max_length=100,
        required=False,
        help_text="Per le verifiche che lo chiedono: numero, sigle, comuni.",
    )
    descrizione = forms.CharField(
        max_length=255, required=False, help_text="Vuota: il nome della verifica."
    )

    def __init__(self, *args, **kwargs):
        from .requisiti import SCELTE

        super().__init__(*args, **kwargs)
        self.fields["verifica"].choices = SCELTE


class CandidaForm(StileMixin, forms.Form):
    """Dal progetto: il bando a cui candidarlo. Dal bando: il progetto da candidare."""

    bando = forms.ModelChoiceField(queryset=None, required=False)
    progetto = forms.ModelChoiceField(queryset=None, required=False)
    delibera = forms.ModelChoiceField(label="Delibera", required=False, queryset=None)

    def __init__(self, *args, progetto=None, bando=None, **kwargs):
        from django.utils import timezone

        super().__init__(*args, **kwargs)
        oggi = timezone.localdate()
        self.fields["delibera"].queryset = _delibere()
        if progetto is not None:
            del self.fields["progetto"]
            self.fields["bando"].required = True
            self.fields["bando"].queryset = (
                Bando.objects.exclude(stato=Bando.Stato.SCARTATO)
                .exclude(scadenza__lt=oggi)
                .order_by("scadenza")
            )
        if bando is not None:
            del self.fields["bando"]
            self.fields["progetto"].required = True
            self.fields["progetto"].queryset = Progetto.objects.filter(
                stato=Progetto.Stato.PROGETTAZIONE
            )


ESITI = [("", "Automatico (dai dati del gestionale)"), *Requisito.Esito.choices]


# --- raccolta dei bandi (P3) ---------------------------------------------------------------------


class FonteForm(StileMixin, forms.ModelForm):
    class Meta:
        model = FonteBandi
        fields = ["nome", "tipo", "indirizzo", "parole_chiave", "tutte", "attiva"]

    def clean_indirizzo(self):
        indirizzo = self.cleaned_data["indirizzo"]
        if not indirizzo.startswith("https://"):
            raise forms.ValidationError("Serve un indirizzo https://.")
        return indirizzo


class ParolaForm(StileMixin, forms.ModelForm):
    class Meta:
        model = ParolaChiave
        fields = ["parola", "esclusa"]

    def clean_parola(self):
        return " ".join(self.cleaned_data["parola"].split()).lower()


# --- progettazione (P4) --------------------------------------------------------------------------


class QuadroForm(StileMixin, forms.ModelForm):
    class Meta:
        model = Progetto
        fields = ["obiettivo_generale", "destinatari", "territorio"]
        widgets = {
            "obiettivo_generale": forms.Textarea(attrs={"rows": 3}),
            "destinatari": forms.Textarea(attrs={"rows": 2}),
        }


class ObiettivoForm(StileMixin, forms.ModelForm):
    class Meta:
        model = Obiettivo
        fields = ["testo", "risultati"]
        widgets = {"risultati": forms.Textarea(attrs={"rows": 2})}


class _DelProgetto:
    """Limita le scelte collegate (obiettivi, attività) al progetto."""

    def _limita(self, progetto, *campi):
        for campo in campi:
            modello = self.fields[campo].queryset.model
            self.fields[campo].queryset = modello.objects.filter(progetto=progetto)


class IndicatoreForm(StileMixin, _DelProgetto, forms.ModelForm):
    class Meta:
        model = Indicatore
        fields = ["obiettivo", "descrizione", "unita", "valore_iniziale", "valore_atteso",
                  "fonte_verifica"]  # fmt: skip

    def __init__(self, *args, progetto, **kwargs):
        super().__init__(*args, **kwargs)
        self._limita(progetto, "obiettivo")


class AttivitaForm(StileMixin, _DelProgetto, forms.ModelForm):
    class Meta:
        model = Attivita
        fields = ["titolo", "descrizione", "obiettivo", "responsabile", "inizio", "fine", "dopo"]
        widgets = {"descrizione": forms.Textarea(attrs={"rows": 2}), "inizio": CampoData,
                   "fine": CampoData}  # fmt: skip

    def __init__(self, *args, progetto, **kwargs):
        super().__init__(*args, **kwargs)
        self._limita(progetto, "obiettivo", "dopo")
        if self.instance.pk:
            self.fields["dopo"].queryset = self.fields["dopo"].queryset.exclude(pk=self.instance.pk)
        self.fields["responsabile"].queryset = (
            get_user_model().objects.filter(is_active=True)
            .order_by("first_name", "last_name", "username")
        )  # fmt: skip

    def clean(self):
        dati = super().clean()
        inizio, fine, dopo = dati.get("inizio"), dati.get("fine"), dati.get("dopo")
        if inizio and fine and fine < inizio:
            self.add_error("fine", "La fine non può precedere l'inizio.")
        if dopo and inizio and inizio <= dopo.fine:
            self.add_error(
                "inizio", f"Deve iniziare dopo il {dopo.fine:%d/%m/%Y} (fine di «{dopo}»)."
            )
        return dati


class PartnerForm(StileMixin, forms.ModelForm):
    class Meta:
        model = Partner
        fields = ["soggetto", "ruolo", "contributo", "cofinanziamento", "lettera_ricevuta"]
        widgets = {"contributo": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["soggetto"].queryset = Soggetto.objects.attivi().order_by(
            "denominazione", "cognome", "nome"
        )


class VoceForm(StileMixin, forms.ModelForm):
    class Meta:
        model = VoceCosto
        fields = ["categoria", "descrizione", "quantita", "unita", "costo_unitario"]

    def clean(self):
        dati = super().clean()
        for campo in ("quantita", "costo_unitario"):
            if dati.get(campo) is not None and dati[campo] < 0:
                self.add_error(campo, "Non può essere negativo.")
        return dati


class FinanziamentoForm(StileMixin, forms.ModelForm):
    class Meta:
        model = FonteFinanziamento
        fields = ["tipo", "descrizione", "importo"]

    def clean_importo(self):
        importo = self.cleaned_data["importo"]
        if importo <= 0:
            raise forms.ValidationError("Indicare un importo positivo.")
        return importo


class SpeseGeneraliForm(StileMixin, forms.ModelForm):
    class Meta:
        model = Progetto
        fields = ["spese_generali"]


class LimiteForm(StileMixin, forms.ModelForm):
    class Meta:
        model = LimiteCategoria
        fields = ["categoria", "percentuale_massima"]
