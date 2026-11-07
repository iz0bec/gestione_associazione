# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Moduli della tesoreria: movimenti di prima nota, conti, sottovoci,
# *              esercizi, saldi iniziali e preventivo.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from datetime import date
from decimal import Decimal

from django import forms

from apps.anagrafica.forms import CampoData
from apps.core.forms import StileMixin

from .models import Conto, Movimento, Voce


class SceltaVoce(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return str(obj)


class MovimentoForm(StileMixin, forms.ModelForm):
    voce = SceltaVoce(queryset=Voce.objects.none(), required=False, label="Voce del rendiconto")
    file = forms.FileField(
        label="Giustificativo",
        required=False,
        help_text="Fattura, ricevuta, scontrino (PDF o immagine).",
    )

    class Meta:
        model = Movimento
        fields = [
            "tipo", "data", "importo", "conto", "conto_destinazione", "voce", "descrizione",
            "controparte_testo", "documento",
        ]  # fmt: skip
        widgets = {"tipo": forms.RadioSelect, "data": CampoData}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tipo"].choices = Movimento.Tipo.choices
        self.fields["conto"].queryset = Conto.objects.filter(attivo=True)
        self.fields["conto_destinazione"].queryset = Conto.objects.filter(attivo=True)
        self.fields["conto_destinazione"].required = False
        self.fields["voce"].queryset = (
            Voce.objects.filter(attiva=True)
            .select_related("padre")
            .order_by("tipo", "sezione", "numero", "padre_id", "descrizione")
        )
        self.fields["data"].initial = date.today()
        self.fields["importo"].widget.attrs.update({"min": "0.01", "step": "0.01"})

    def clean(self):
        dati = super().clean()
        tipo, voce = dati.get("tipo"), dati.get("voce")
        if tipo in ("entrata", "uscita"):
            dati["conto_destinazione"] = None
            if voce is None:
                self.add_error("voce", "Scegliere la voce del rendiconto.")
            elif voce.tipo != tipo:
                self.add_error("voce", f"È una voce di {voce.get_tipo_display().lower()}.")
        elif tipo == "giroconto":
            dati["voce"] = None
            dest = dati.get("conto_destinazione")
            if dest is None or dest == dati.get("conto"):
                self.add_error(
                    "conto_destinazione", "Scegliere un conto diverso da quello di partenza."
                )
        return dati

    def dati(self):
        return {c: self.cleaned_data.get(c) for c in self.Meta.fields}


class MotivoForm(forms.Form):
    motivo = forms.CharField(max_length=255)


class ContoForm(StileMixin, forms.ModelForm):
    class Meta:
        model = Conto
        fields = [
            "nome",
            "tipo",
            "iban",
            "per_contanti",
            "per_pagamenti_elettronici",
            "attivo",
            "ordine",
        ]

    def clean_iban(self):
        return self.cleaned_data["iban"].replace(" ", "").upper()

    def clean(self):
        dati = super().clean()
        for campo in ("per_contanti", "per_pagamenti_elettronici"):
            if (
                dati.get(campo)
                and Conto.objects.filter(**{campo: True}).exclude(pk=self.instance.pk).exists()
            ):
                self.add_error(campo, "Già impostato su un altro conto.")
        return dati


class SottovoceForm(StileMixin, forms.ModelForm):
    class Meta:
        model = Voce
        fields = ["padre", "descrizione", "attiva"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["padre"].queryset = Voce.objects.filter(padre__isnull=True)
        self.fields["padre"].required = True
        self.fields["padre"].label_from_instance = lambda v: (
            f"{v.get_tipo_display()} · {v.etichetta}"
        )

    def save(self, commit=True):
        v = self.instance
        v.tipo, v.sezione, v.numero = v.padre.tipo, v.padre.sezione, v.padre.numero
        if not v.codice:
            base = f"{v.padre.codice}."
            n = Voce.objects.filter(codice__startswith=base).count() + 1
            while Voce.objects.filter(codice=f"{base}{n}").exists():
                n += 1
            v.codice = f"{base}{n}"
        return super().save(commit)


class ImportoField(forms.DecimalField):
    def __init__(self, **kwargs):
        super().__init__(max_digits=12, decimal_places=2, required=False, **kwargs)
        self.widget.attrs.update({"step": "0.01", "class": "form-control form-control-sm text-end"})

    def clean(self, value):
        return super().clean(value) or Decimal("0.00")
