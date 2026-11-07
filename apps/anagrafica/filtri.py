# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Filtri dell'elenco anagrafica
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import django_filters
from django import forms

from .models import Categoria, Soggetto


class SoggettoFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(method="filtra_testo", label="Cerca")
    tipo = django_filters.ChoiceFilter(choices=Soggetto.Tipo.choices, empty_label="Tutti i tipi")
    categoria = django_filters.ModelChoiceFilter(
        field_name="categorie", queryset=Categoria.objects.all(), empty_label="Tutte le categorie"
    )
    stato = django_filters.ChoiceFilter(
        choices=[("attivi", "Attivi"), ("archiviati", "Archiviati"), ("tutti", "Tutti")],
        method="filtra_stato",
        empty_label=None,
        initial="attivi",
    )

    class Meta:
        model = Soggetto
        fields = ["q", "tipo", "categoria", "stato"]

    def __init__(self, data=None, *args, **kwargs):
        data = data.copy() if data is not None else {}
        data.setdefault("stato", "attivi")
        super().__init__(data, *args, **kwargs)
        for campo in self.form.fields.values():
            classe = "form-select" if isinstance(campo.widget, forms.Select) else "form-control"
            campo.widget.attrs["class"] = classe
        self.form.fields["q"].widget.attrs.update(
            {"placeholder": "Nome, cognome, ente, email, comune, CF...", "type": "search"}
        )

    def filtra_testo(self, queryset, name, value):
        return queryset.ricerca(value) if value else queryset

    def filtra_stato(self, queryset, name, value):
        if value == "archiviati":
            return queryset.filter(attivo=False)
        if value == "tutti":
            return queryset
        return queryset.filter(attivo=True)
