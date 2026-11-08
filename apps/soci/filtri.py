# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Filtri dell'elenco soci (ricerca, stato, tipologia, situazione quota)
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from datetime import date

import django_filters
from django import forms
from django.db.models import Q

from .models import Sezione, Socio, TipologiaSocio
from .sezioni import sezioni_di


class SocioFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(method="filtra_testo", label="Cerca")
    stato = django_filters.ChoiceFilter(
        choices=[*Socio.Stato.choices, ("tutti", "Tutti gli stati")],
        method="filtra_stato",
        empty_label=None,
    )
    tipologia = django_filters.ModelChoiceFilter(
        queryset=TipologiaSocio.objects.all(), empty_label="Ogni tipologia"
    )
    sezione = django_filters.ModelChoiceFilter(
        queryset=Sezione.objects.all(), empty_label="Ogni sezione"
    )
    quota = django_filters.ChoiceFilter(
        choices=[("in_regola", "Quota: in regola"), ("morosi", "Quota: non in regola")],
        method="filtra_quota",
        empty_label="Quota: tutti",
    )
    anno = django_filters.NumberFilter(method="nessun_filtro", label="Anno")

    class Meta:
        model = Socio
        fields = ["q", "stato", "sezione", "tipologia", "quota", "anno"]

    def __init__(self, data=None, *args, **kwargs):
        data = data.copy() if data is not None else {}
        data.setdefault("stato", Socio.Stato.ATTIVO)
        if not data.get("anno"):
            data["anno"] = date.today().year
        super().__init__(data, *args, **kwargs)
        utente = getattr(self.request, "user", None)
        self.filters["sezione"].queryset = sezioni_di(utente) if utente else Sezione.objects.all()
        for campo in self.form.fields.values():
            classe = "form-select" if isinstance(campo.widget, forms.Select) else "form-control"
            campo.widget.attrs["class"] = classe
        self.form.fields["q"].widget.attrs.update(
            {"placeholder": "Cognome, nome, numero, codice fiscale...", "type": "search"}
        )
        self.form.fields["anno"].widget.attrs.update({"min": 1900, "max": 2100})

    @property
    def anno_riferimento(self):
        try:
            return int(self.form.cleaned_data.get("anno") or date.today().year)
        except (AttributeError, TypeError, ValueError):
            return date.today().year

    def filtra_testo(self, queryset, name, value):
        for parola in value.split():
            condizione = (
                Q(soggetto__cognome__icontains=parola)
                | Q(soggetto__nome__icontains=parola)
                | Q(soggetto__codice_fiscale__iexact=parola)
                | Q(soggetto__comune__icontains=parola)
                | Q(matricola__iexact=parola)
            )
            if parola.isdigit():
                condizione |= Q(numero=int(parola))
            queryset = queryset.filter(condizione)
        return queryset

    def filtra_stato(self, queryset, name, value):
        return queryset if value == "tutti" else queryset.filter(stato=value)

    def filtra_quota(self, queryset, name, value):
        if value == "in_regola":
            return queryset.in_regola(self.anno_riferimento)
        if value == "morosi":
            return queryset.morosi(self.anno_riferimento)
        return queryset

    def nessun_filtro(self, queryset, name, value):
        return queryset  # usato da filtra_quota e per mostrare la tessera dell'anno
