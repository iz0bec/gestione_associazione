# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Moduli delle comunicazioni: nuovo invio, modelli, liste, ricorrenze,
# *              onomastici e auguri automatici.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django import forms

from apps.anagrafica.models import Categoria, Soggetto
from apps.core.forms import StileMixin
from apps.organi.forms import CampoDataOra
from apps.protocollo.forms import CampoFileMultiplo

from .anniversari import normalizza_nome
from .models import Automazione, Finalita, Lista, Modello, Onomastico, Ricorrenza
from .servizi import SEGNAPOSTO, leggi_indirizzi, segnaposto_sconosciuti

AIUTO_SEGNAPOSTO = "Segnaposto: " + ", ".join("{{ " + k + " }}" for k in SEGNAPOSTO)


def _controlla_segnaposto(form, *campi):
    for campo in campi:
        if sconosciuti := segnaposto_sconosciuti(form.cleaned_data.get(campo) or ""):
            form.add_error(campo, "Segnaposto sconosciuti: " + ", ".join(sconosciuti))


class _SceltaSoggetti(forms.ModelMultipleChoiceField):
    widget = forms.CheckboxSelectMultiple

    def __init__(self, **kwargs):
        super().__init__(queryset=Soggetto.objects.all(), required=False, **kwargs)


class InvioForm(StileMixin, forms.Form):
    modello = forms.ModelChoiceField(
        queryset=Modello.objects.filter(attivo=True), required=False, widget=forms.HiddenInput
    )
    oggetto = forms.CharField(max_length=200)
    corpo = forms.CharField(
        label="Testo", widget=forms.Textarea(attrs={"rows": 10}), help_text=AIUTO_SEGNAPOSTO
    )
    finalita = forms.ChoiceField(
        label="Finalità", choices=Finalita.choices, initial=Finalita.COMUNICAZIONI
    )
    liste = forms.ModelMultipleChoiceField(
        queryset=Lista.objects.all(), required=False, widget=forms.CheckboxSelectMultiple
    )
    soggetti = _SceltaSoggetti(label="Persone ed enti dall'anagrafica")
    indirizzi = forms.CharField(
        label="Altri indirizzi",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Uno per riga: «Nome &lt;email&gt;» o solo l'email.",
    )
    allegati = CampoFileMultiplo(required=False)
    protocolla = forms.BooleanField(
        label="Protocolla in uscita al termine dell'invio", required=False
    )
    programmato_il = forms.DateTimeField(
        label="Invia non prima di", required=False, widget=CampoDataOra, help_text="Vuoto = subito."
    )

    def clean(self):
        dati = super().clean()
        _controlla_segnaposto(self, "oggetto", "corpo")
        self.indirizzi_validi, errati = leggi_indirizzi(dati.get("indirizzi"))
        if errati:
            self.add_error("indirizzi", "Indirizzi non validi: " + "; ".join(errati))
        if not (dati.get("liste") or dati.get("soggetti") or self.indirizzi_validi):
            raise forms.ValidationError(
                "Indicare almeno un destinatario (lista, anagrafica o indirizzo)."
            )
        return dati


class ModelloForm(StileMixin, forms.ModelForm):
    class Meta:
        model = Modello
        fields = ["nome", "uso", "oggetto", "corpo", "attivo"]
        widgets = {"corpo": forms.Textarea(attrs={"rows": 10})}
        help_texts = {"corpo": AIUTO_SEGNAPOSTO}

    def clean(self):
        dati = super().clean()
        _controlla_segnaposto(self, "oggetto", "corpo")
        return dati


class ListaForm(StileMixin, forms.ModelForm):
    soggetti = _SceltaSoggetti(label="Persone ed enti")

    class Meta:
        model = Lista
        fields = [
            "nome",
            "descrizione",
            "categorie",
            "soci_attivi",
            "soci_in_regola",
            "organo",
            "soggetti",
        ]
        widgets = {"categorie": forms.CheckboxSelectMultiple}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["categorie"].queryset = Categoria.objects.all()
        self.fields["organo"].empty_label = "— nessuno —"


class RicorrenzaForm(StileMixin, forms.ModelForm):
    class Meta:
        model = Ricorrenza
        fields = [
            "nome", "giorno", "mese", "anno_inizio", "descrizione", "lista", "modello",
            "invio_automatico", "attiva",
        ]  # fmt: skip
        widgets = {"descrizione": forms.Textarea(attrs={"rows": 2})}

    def clean(self):
        dati = super().clean()
        if dati.get("invio_automatico") and not dati.get("lista"):
            self.add_error("lista", "Per l'invio automatico serve una lista di destinatari.")
        return dati


class OnomasticoForm(StileMixin, forms.ModelForm):
    class Meta:
        model = Onomastico
        fields = ["nome", "giorno", "mese", "santo"]

    def clean_nome(self):
        return normalizza_nome(self.cleaned_data["nome"])


class AutomazioneForm(StileMixin, forms.ModelForm):
    class Meta:
        model = Automazione
        fields = ["attiva", "modello", "destinatari", "ora", "anni"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["modello"].queryset = Modello.objects.filter(
            uso=self.instance.tipo, attivo=True
        )
        self.fields["modello"].empty_label = "— il primo modello attivo di questo tipo —"
        if self.instance.tipo != Automazione.Tipo.ANZIANITA:
            del self.fields["anni"]
