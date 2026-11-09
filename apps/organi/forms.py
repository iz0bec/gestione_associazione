# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Moduli degli organi sociali: regole dell'organo, cariche, riunioni con
# *              ordine del giorno, verbale e delibere.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from datetime import date

from django import forms

from apps.anagrafica.forms import CampoData
from apps.anagrafica.models import Soggetto
from apps.core.forms import StileMixin

from .models import (
    Carica,
    Delibera,
    ModelloConvocazione,
    Organo,
    RappresentanteLegale,
    Riunione,
    Verbale,
)


class CampoDataOra(forms.DateTimeInput):
    input_type = "datetime-local"

    def __init__(self, attrs=None):
        super().__init__(attrs=attrs, format="%Y-%m-%dT%H:%M")


class OrganoForm(StileMixin, forms.ModelForm):
    class Meta:
        model = Organo
        fields = [
            "nome", "sezione", "sigla", "tipo", "quorum_prima", "quorum_seconda", "max_deleghe",
            "solo_soci_in_regola", "ordine", "attivo",
        ]  # fmt: skip

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sezione"].empty_label = "— dell'associazione (federazione) —"

    def validate_unique(self):
        super().validate_unique()
        # stesso nome con maiuscole diverse nella stessa sezione
        nome, sezione = self.cleaned_data.get("nome"), self.cleaned_data.get("sezione")
        doppio = Organo.objects.filter(nome__iexact=nome or "", sezione=sezione).exclude(
            pk=self.instance.pk
        )
        if nome and doppio.exists():
            self.add_error("nome", "Esiste già un organo con questo nome per la stessa sezione.")


class CaricaForm(StileMixin, forms.Form):
    soggetto = forms.ModelChoiceField(
        label="Persona",
        queryset=Soggetto.objects.attivi().filter(
            tipo=Soggetto.Tipo.PERSONA, data_decesso__isnull=True
        ),
        help_text="Persone attive dell'anagrafica.",
    )
    ruolo = forms.ChoiceField(choices=Carica.Ruolo.choices)
    dal = forms.DateField(widget=CampoData, initial=date.today)
    atto = forms.CharField(label="Atto di nomina", required=False, max_length=200)
    note = forms.CharField(required=False, max_length=255)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["soggetto"].queryset = self.fields["soggetto"].queryset.order_by(
            "cognome", "nome"
        )


class FineCaricaForm(StileMixin, forms.Form):
    al = forms.DateField(
        label="Data di cessazione",
        widget=CampoData,
        initial=date.today,
        help_text="Da questo giorno la persona non è più in carica.",
    )
    motivo = forms.CharField(required=False, max_length=200)


class ModificaCaricaForm(StileMixin, forms.Form):
    dal = forms.DateField(label="Inizio", widget=CampoData)
    al = forms.DateField(
        label="Data di cessazione",
        widget=CampoData,
        required=False,
        help_text="Vuota = ancora in carica. Da questo giorno la persona non è più in carica.",
    )
    atto = forms.CharField(label="Atto di nomina", required=False, max_length=200)
    note = forms.CharField(required=False, max_length=255)

    @classmethod
    def per(cls, carica, data=None):
        iniziali = {"dal": carica.dal, "al": carica.al, "atto": carica.nomina, "note": carica.note}
        return cls(data, initial=iniziali, prefix=f"carica{carica.pk}")


class RappresentanteForm(StileMixin, forms.Form):
    """Nuova nomina del rappresentante legale (associazione o sezione)."""

    sezione = forms.ModelChoiceField(
        label="Ente rappresentato",
        queryset=None,
        required=False,
        empty_label="— l'associazione (federazione) —",
    )
    tutta_la_struttura = forms.BooleanField(
        label="Vale per tutta la struttura",
        required=False,
        help_text="Solo per l'associazione: rappresenta anche le sezioni senza un proprio "
        "rappresentante legale (es. il presidente nazionale per tutte le sezioni).",
    )
    soggetto = forms.ModelChoiceField(
        label="Persona",
        queryset=Soggetto.objects.attivi().filter(
            tipo=Soggetto.Tipo.PERSONA, data_decesso__isnull=True
        ),
        help_text="Anche esterna all'associazione: va prima inserita in Anagrafica.",
    )
    qualifica = forms.CharField(
        max_length=100,
        initial=RappresentanteLegale.QUALIFICA_PREDEFINITA,
        help_text="Come compare sopra la firma, es. «Il Presidente nazionale».",
    )
    dal = forms.DateField(widget=CampoData, initial=date.today)
    atto = forms.CharField(
        label="Atto di nomina", required=False, max_length=200, help_text="Es. statuto, procura."
    )
    note = forms.CharField(required=False, max_length=255)

    def __init__(self, *args, **kwargs):
        from apps.soci.models import Sezione

        super().__init__(*args, **kwargs)
        self.fields["sezione"].queryset = Sezione.objects.filter(attiva=True)
        self.fields["soggetto"].queryset = self.fields["soggetto"].queryset.order_by(
            "cognome", "nome"
        )

    def clean(self):
        dati = super().clean()
        if dati.get("sezione") and dati.get("tutta_la_struttura"):
            self.add_error(
                "tutta_la_struttura", "Vale solo per il rappresentante dell'associazione."
            )
        return dati


class ModificaRappresentanteForm(StileMixin, forms.Form):
    qualifica = forms.CharField(max_length=100)
    dal = forms.DateField(label="Inizio", widget=CampoData)
    al = forms.DateField(
        label="Data di cessazione",
        widget=CampoData,
        required=False,
        help_text="Vuota = in carica. Da questo giorno non rappresenta più l'ente.",
    )
    tutta_la_struttura = forms.BooleanField(label="Vale per tutta la struttura", required=False)
    atto = forms.CharField(label="Atto di nomina", required=False, max_length=200)
    note = forms.CharField(required=False, max_length=255)

    @classmethod
    def per(cls, nomina, data=None):
        iniziali = {
            "qualifica": nomina.qualifica, "dal": nomina.dal, "al": nomina.al,
            "tutta_la_struttura": nomina.tutta_la_struttura, "atto": nomina.nomina,
            "note": nomina.note,
        }  # fmt: skip
        form = cls(data, initial=iniziali, prefix=f"rapp{nomina.pk}")
        if nomina.sezione_id:
            del form.fields["tutta_la_struttura"]
        return form


class ModelloConvocazioneForm(StileMixin, forms.ModelForm):
    class Meta:
        model = ModelloConvocazione
        fields = ["nome", "tipo_organo", "straordinaria", "premessa", "punti", "ordine", "attivo"]
        widgets = {
            "premessa": forms.Textarea(attrs={"rows": 4}),
            "punti": forms.Textarea(attrs={"rows": 8}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tipo_organo"].choices = [("", "— qualsiasi organo —"),
                                              *Organo.Tipo.choices]  # fmt: skip


class RiunioneForm(StileMixin, forms.ModelForm):
    punti = forms.CharField(
        label="Ordine del giorno",
        widget=forms.Textarea(attrs={"rows": 6}),
        help_text="Un punto per riga, nell'ordine di discussione.",
    )

    class Meta:
        model = Riunione
        fields = [
            "organo", "straordinaria", "prima_convocazione", "luogo", "seconda_convocazione",
            "luogo_seconda", "modalita", "collegamento", "data_convocazione", "premessa",
        ]  # fmt: skip
        widgets = {
            "prima_convocazione": CampoDataOra,
            "seconda_convocazione": CampoDataOra,
            "data_convocazione": CampoData,
            "premessa": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["organo"].queryset = Organo.objects.filter(attivo=True)
        if self.instance.pk:
            self.fields["organo"].disabled = True
            self.initial["punti"] = "\n".join(p.titolo for p in self.instance.punti.all())

    def clean(self):
        dati = super().clean()
        prima, seconda = dati.get("prima_convocazione"), dati.get("seconda_convocazione")
        if prima and seconda and seconda <= prima:
            self.add_error(
                "seconda_convocazione", "Deve essere successiva alla prima convocazione."
            )
        if dati.get("modalita") in ("mista", "remoto") and not dati.get("collegamento"):
            self.add_error("collegamento", "Indicare come collegarsi.")
        return dati

    def titoli_punti(self):
        return self.cleaned_data["punti"].splitlines()


class VerbaleForm(StileMixin, forms.ModelForm):
    class Meta:
        model = Verbale
        fields = [
            "convocazione", "inizio", "fine", "luogo", "presidente", "segretario", "apertura",
            "altri_presenti", "varie",
        ]  # fmt: skip
        widgets = {
            "convocazione": forms.RadioSelect,
            "inizio": CampoDataOra,
            "fine": CampoDataOra,
            "apertura": forms.Textarea(attrs={"rows": 3}),
            "altri_presenti": forms.Textarea(attrs={"rows": 2}),
            "varie": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        dati = super().clean()
        if dati.get("inizio") and dati.get("fine") and dati["fine"] <= dati["inizio"]:
            self.add_error("fine", "Deve essere successiva all'apertura.")
        return dati


class DeliberaForm(StileMixin, forms.ModelForm):
    class Meta:
        model = Delibera
        fields = [
            "punto", "oggetto", "testo", "votazione", "unanimita", "favorevoli", "contrari",
            "astenuti", "esito",
        ]  # fmt: skip
        widgets = {"testo": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, riunione, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["punto"].queryset = riunione.punti.all()
        self.fields["punto"].empty_label = "— nessun punto (varie) —"

    def clean(self):
        dati = super().clean()
        if dati.get("unanimita") and (dati.get("contrari") or 0) > 0:
            self.add_error("contrari", "Con l'unanimità non ci sono contrari.")
        if (
            dati.get("esito") == Delibera.Esito.APPROVATA
            and not dati.get("unanimita")
            and dati.get("votazione") != Delibera.Votazione.ACCLAMAZIONE
            and (dati.get("favorevoli") or 0) <= (dati.get("contrari") or 0)
        ):
            self.add_error("esito", "I favorevoli non superano i contrari.")
        return dati
