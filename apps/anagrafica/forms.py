# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Moduli dell'anagrafica
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django import forms

from apps.core.forms import StileMixin

from .models import Categoria, Consenso, Soggetto
from .validatori import dati_da_codice_fiscale


class CampoData(forms.DateInput):
    input_type = "date"

    def __init__(self, attrs=None):
        super().__init__(attrs=attrs, format="%Y-%m-%d")


class CampiFotoMixin(forms.Form):
    """Caricamento e rimozione della foto (il file è ripulito dal servizio)."""

    nuova_foto = forms.ImageField(
        label="Foto",
        required=False,
        help_text="JPEG o PNG; viene ridotta e privata dei dati nascosti (posizione, dispositivo).",
        widget=forms.FileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
    )
    togli_foto = forms.BooleanField(label="Togli la foto attuale", required=False)


class SoggettoForm(StileMixin, CampiFotoMixin, forms.ModelForm):
    class Meta:
        model = Soggetto
        fields = [
            "tipo", "titolo", "nome", "cognome", "sesso", "data_nascita", "luogo_nascita",
            "codice_fiscale", "data_decesso", "denominazione", "partita_iva", "qualifica",
            "email", "pec", "telefono", "cellulare", "indirizzo", "cap", "comune", "provincia",
            "nazione", "categorie", "note",
        ]  # fmt: skip
        widgets = {
            "tipo": forms.RadioSelect,
            "data_nascita": CampoData,
            "data_decesso": CampoData,
            "categorie": forms.CheckboxSelectMultiple,
            "note": forms.Textarea(attrs={"rows": 3}),
            "provincia": forms.TextInput(attrs={"maxlength": 2, "class": "text-uppercase"}),
            "codice_fiscale": forms.TextInput(
                attrs={"class": "text-uppercase", "autocomplete": "off"}
            ),
        }

    def clean_codice_fiscale(self):
        return (self.cleaned_data.get("codice_fiscale") or "").strip().upper() or None

    def clean(self):
        dati = super().clean()
        tipo = dati.get("tipo")
        if tipo == Soggetto.Tipo.PERSONA and not dati.get("cognome"):
            self.add_error("cognome", "Il cognome è obbligatorio per una persona.")
        if tipo == Soggetto.Tipo.ENTE and not dati.get("denominazione"):
            self.add_error("denominazione", "La denominazione è obbligatoria per un ente.")

        cf = dati.get("codice_fiscale")
        da_cf = dati_da_codice_fiscale(cf) if tipo == Soggetto.Tipo.PERSONA and cf else None
        if da_cf:
            # completa i dati mancanti, segnala quelli in contrasto
            for campo in ("sesso", "data_nascita", "luogo_nascita"):
                if not dati.get(campo):
                    dati[campo] = da_cf[campo]
            if dati.get("sesso") != da_cf["sesso"]:
                self.add_error("sesso", "Non corrisponde al codice fiscale.")
            if dati.get("data_nascita") and dati["data_nascita"] != da_cf["data_nascita"]:
                self.add_error("data_nascita", "Non corrisponde al codice fiscale.")
        nascita, decesso = dati.get("data_nascita"), dati.get("data_decesso")
        if nascita and decesso and decesso < nascita:
            self.add_error("data_decesso", "Precedente alla data di nascita.")
        return dati


class ConsensoForm(StileMixin, forms.ModelForm):
    class Meta:
        model = Consenso
        fields = ["finalita", "prestato", "data", "modalita"]
        widgets = {"data": CampoData}


class ImportaVCardForm(StileMixin, forms.Form):
    file = forms.FileField(
        label="File della rubrica (.vcf)",
        help_text="Esportato dal telefono, da Google Contatti, Outlook o Thunderbird; può "
        "contenere molti contatti.",
        widget=forms.FileInput(attrs={"accept": ".vcf,text/vcard,text/x-vcard"}),
    )
    categoria = forms.ModelChoiceField(
        queryset=Categoria.objects.all(),
        required=False,
        help_text="Facoltativa: assegnata a tutti i contatti importati (es. «Autorità»).",
    )

    def clean_file(self):
        f = self.cleaned_data["file"]
        if f.size > 10 * 1024 * 1024:
            raise forms.ValidationError("Il file supera 10 MB.")
        return f


class ConservazioneForm(StileMixin, forms.ModelForm):
    class Meta:
        from apps.core.models import Organizzazione

        model = Organizzazione
        fields = ["conservazione_anni", "anonimizzazione_automatica"]
