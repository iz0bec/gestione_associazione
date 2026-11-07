# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Moduli del patrimonio: bene, valutazione, prestito o uscita, restituzione,
# *              passaggio di consegne.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from datetime import date

from django import forms

from apps.anagrafica.forms import CampoData
from apps.core.forms import StileMixin

from .models import Bene, CategoriaBene, PassaggioConsegne, Uscita, Valutazione


class BeneForm(StileMixin, forms.ModelForm):
    file_foto = forms.ImageField(
        label="Foto",
        required=False,
        help_text="JPEG o PNG: viene ridimensionata e privata dei dati di posizione.",
    )
    togli_foto = forms.BooleanField(label="Togli la foto attuale", required=False)

    class Meta:
        model = Bene
        fields = [
            "nome", "categoria", "descrizione", "quantita", "ubicazione", "conservazione",
            "acquisizione", "data_acquisizione", "provenienza_testo", "documento",
            "valore_acquisizione", "codice_precedente", "note", "pubblico", "descrizione_pubblica",
            "foto_pubblica",
        ]  # fmt: skip
        widgets = {
            "data_acquisizione": CampoData,
            "descrizione": forms.Textarea(attrs={"rows": 3}),
            "note": forms.Textarea(attrs={"rows": 2}),
            "descrizione_pubblica": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["categoria"].queryset = CategoriaBene.objects.all()
        if self.instance.pk:
            del self.fields["valore_acquisizione"]  # il valore cambia con le valutazioni


class ValutazioneForm(StileMixin, forms.ModelForm):
    class Meta:
        model = Valutazione
        fields = ["data", "valore", "metodo", "note"]
        widgets = {"data": CampoData}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["data"].initial = date.today()


class UscitaForm(StileMixin, forms.ModelForm):
    class Meta:
        model = Uscita
        fields = [
            "tipo",
            "data",
            "controparte_testo",
            "motivo",
            "condizioni",
            "restituzione_prevista",
            "importo",
        ]
        widgets = {
            "data": CampoData,
            "restituzione_prevista": CampoData,
            "condizioni": forms.Textarea(attrs={"rows": 2}),
            "tipo": forms.RadioSelect,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["data"].initial = date.today()
        self.fields["tipo"].choices = Uscita.Tipo.choices
        self.fields["tipo"].initial = Uscita.Tipo.PRESTITO


class RestituzioneForm(StileMixin, forms.Form):
    data = forms.DateField(label="Restituito il", widget=CampoData, initial=date.today)
    rientro = forms.ChoiceField(label="Condizioni", choices=Uscita.Rientro.choices)
    note = forms.CharField(required=False, max_length=255)


class PassaggioForm(StileMixin, forms.ModelForm):
    protocolla = forms.BooleanField(
        label="Protocolla il verbale di consegna", required=False, initial=True
    )

    class Meta:
        model = PassaggioConsegne
        fields = [
            "data",
            "consegnante",
            "consegnante_ruolo",
            "ricevente",
            "ricevente_ruolo",
            "note",
        ]
        widgets = {"data": CampoData, "note": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["data"].initial = date.today()


class CategoriaForm(StileMixin, forms.ModelForm):
    class Meta:
        model = CategoriaBene
        fields = ["nome", "ordine"]
