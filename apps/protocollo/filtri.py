# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Filtri del registro di protocollo
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import re

import django_filters
from django import forms
from django.db.models import Q

from apps.anagrafica.forms import CampoData

from .models import Classificazione, Protocollo


class ProtocolloFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(method="filtra_testo", label="Cerca")
    direzione = django_filters.ChoiceFilter(
        choices=Protocollo.Direzione.choices, empty_label="Tutte le direzioni"
    )
    anno = django_filters.NumberFilter(label="Anno")
    classificazione = django_filters.ModelChoiceFilter(
        queryset=Classificazione.objects.all(), empty_label="Ogni classificazione"
    )
    dal = django_filters.DateFilter(
        field_name="registrato_il", lookup_expr="date__gte", label="Dal", widget=CampoData
    )
    al = django_filters.DateFilter(
        field_name="registrato_il", lookup_expr="date__lte", label="Al", widget=CampoData
    )
    stato = django_filters.ChoiceFilter(
        choices=[("validi", "Validi"), ("annullati", "Annullati")],
        method="filtra_stato",
        empty_label="Tutti gli stati",
    )

    class Meta:
        model = Protocollo
        fields = ["q", "direzione", "anno", "classificazione", "dal", "al", "stato"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.form.fields.values():
            classe = "form-select" if isinstance(campo.widget, forms.Select) else "form-control"
            campo.widget.attrs["class"] = classe
        self.form.fields["q"].widget.attrs.update(
            {"placeholder": "Numero, oggetto, mittente, destinatario...", "type": "search"}
        )
        self.form.fields["anno"].widget.attrs.update({"placeholder": "Anno", "min": 1900})

    def filtra_testo(self, queryset, name, value):
        m = re.fullmatch(r"\s*(?:(\d{4})\s*-\s*)?0*(\d{1,7})\s*", value)
        if m:
            numero = Q(numero=int(m[2]))
            if m[1]:
                numero &= Q(anno=int(m[1]))
            # un numero cerca il protocollo, ma anche i testi che lo contengono
            return queryset.filter(numero | Q(oggetto__icontains=value.strip())).distinct()
        for parola in value.split():
            queryset = queryset.filter(
                Q(oggetto__icontains=parola)
                | Q(corrispondenti__descrizione__icontains=parola)
                | Q(corrispondenti__indirizzo__icontains=parola)
                | Q(riferimento_mittente__icontains=parola)
                | Q(note__icontains=parola)
            )
        return queryset.distinct()

    def filtra_stato(self, queryset, name, value):
        return queryset.filter(annullato=(value == "annullati"))
