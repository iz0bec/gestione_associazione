# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Moduli dei modelli di stampa e della stampa
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django import forms

from apps.anagrafica.models import Categoria, Soggetto
from apps.comunicazioni.models import Lista
from apps.core.forms import StileMixin
from apps.protocollo.models import Protocollo

from . import servizi
from .models import ModelloStampa


class ModelloForm(StileMixin, forms.ModelForm):
    nuovo_stemma = forms.ImageField(
        label="Stemma o logo aggiuntivo",
        required=False,
        help_text="Solo per l'attestato solenne: a destra del logo dell'ente (es. stemma della "
        "presidenza nazionale o del Comune). Senza, si usa il logo del modulo di adesione.",
        widget=forms.FileInput(attrs={"accept": "image/png,image/jpeg,image/webp"}),
    )
    togli_stemma = forms.BooleanField(label="Togli lo stemma", required=False)

    class Meta:
        model = ModelloStampa
        fields = ["nome", "tipo", "titolo", "corpo", "firma_ruolo", "firma_nome", "firma_legale",
                  "seconda_firma", "attivo"]  # fmt: skip
        widgets = {"corpo": forms.Textarea(attrs={"rows": 14}), "tipo": forms.RadioSelect}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.stemma:
            del self.fields["togli_stemma"]

    def clean(self):
        dati = super().clean()
        ignoti = servizi.segnaposto_sconosciuti(dati.get("titolo"), dati.get("corpo"))
        if ignoti:
            raise forms.ValidationError(
                "Segnaposto sconosciuti: " + ", ".join("{{ " + s + " }}" for s in ignoti)
            )
        return dati


class StampaForm(StileMixin, forms.Form):
    DESTINAZIONI = [
        ("soggetto", "Una persona o un ente"),
        ("lista", "Una lista di distribuzione"),
        ("categoria", "Una categoria dell'anagrafica"),
        ("nessuno", "Nessun destinatario (documento unico)"),
    ]
    MEZZI = [
        (Protocollo.Mezzo.POSTA, "Posta ordinaria"),
        (Protocollo.Mezzo.RACCOMANDATA, "Raccomandata"),
        (Protocollo.Mezzo.MANO, "Consegna a mano"),
    ]

    modello = forms.ModelChoiceField(queryset=ModelloStampa.objects.filter(attivo=True))
    destinazione = forms.ChoiceField(choices=DESTINAZIONI, widget=forms.RadioSelect,
                                     initial="soggetto")  # fmt: skip
    soggetto = forms.ModelChoiceField(
        label="Destinatario", queryset=Soggetto.objects.none(), required=False
    )
    lista = forms.ModelChoiceField(queryset=Lista.objects.all(), required=False)
    categoria = forms.ModelChoiceField(queryset=Categoria.objects.all(), required=False)
    protocolla = forms.BooleanField(
        label="Registra a protocollo in uscita",
        required=False,
        help_text="Il numero di protocollo viene stampato sul documento e il PDF allegato.",
    )
    mezzo = forms.ChoiceField(label="Mezzo di spedizione", choices=MEZZI, required=False)

    def __init__(self, *args, soggetto=None, **kwargs):
        super().__init__(*args, **kwargs)
        attivi = Soggetto.objects.filter(attivo=True, data_decesso__isnull=True)
        if soggetto is not None:  # dalla scheda in anagrafica: solo quella persona
            self.fields["soggetto"].queryset = Soggetto.objects.filter(pk=soggetto.pk)
            self.fields["soggetto"].initial = soggetto.pk
        else:
            self.fields["soggetto"].queryset = attivi.order_by("cognome", "nome", "denominazione")

    def clean(self):
        dati = super().clean()
        destinazione = dati.get("destinazione")
        if destinazione in ("soggetto", "lista", "categoria") and not dati.get(destinazione):
            self.add_error(destinazione, "Scegliere il destinatario.")
        return dati

    def destinatari(self):
        from apps.comunicazioni.servizi import soggetti_lista

        d = self.cleaned_data
        if d["destinazione"] == "soggetto":
            qs = [d["soggetto"]]
        elif d["destinazione"] == "lista":
            qs = soggetti_lista(d["lista"]).order_by("cognome", "nome", "denominazione")
        elif d["destinazione"] == "categoria":
            qs = d["categoria"].soggetti.order_by("cognome", "nome", "denominazione")
        else:
            qs = []
        return servizi.destinatari_validi(qs)
