# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Rendering dei moduli con lo stile dell'interfaccia (Tabler/Bootstrap)
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django import forms
from django.forms.renderers import TemplatesSetting


class RendererModuli(TemplatesSetting):
    """Tutti i moduli usano templates/moduli/*.html (etichetta, campo, aiuto, errori)."""

    form_template_name = "moduli/modulo.html"
    field_template_name = "moduli/campo.html"


class StileMixin:
    """Classe CSS sulle singole opzioni di radio e checkbox multiple.

    Il resto dello stile lo applica il filtro `con_stile` (templatetags/interfaccia.py).
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            if isinstance(campo.widget, forms.CheckboxSelectMultiple | forms.RadioSelect):
                campo.widget.attrs.setdefault("class", "form-check-input")


# --- organizzazione e aspetto ------------------------------------------------------------

CAMPI_ENTE = [
    "denominazione", "denominazione_breve", "codice_fiscale", "partita_iva", "iscrizione_runts",
    "indirizzo", "cap", "comune", "provincia", "telefono", "email", "pec", "sito_web",
    "federazione",
]  # fmt: skip
CAMPI_MODULO = [
    "modulo_intestazione", "modulo_articoli_statuto", "modulo_dichiarazione", "modulo_piede",
]  # fmt: skip


class OrganizzazioneForm(StileMixin, forms.ModelForm):
    class Meta:
        from .models import Organizzazione

        model = Organizzazione
        fields = [*CAMPI_ENTE, *CAMPI_MODULO, "informativa_privacy", "iscrizioni_online",
                  "pagina_pubblica", "presentazione"]  # fmt: skip
        widgets = {
            "informativa_privacy": forms.Textarea(attrs={"rows": 10}),
            "modulo_intestazione": forms.Textarea(attrs={"rows": 3}),
            "modulo_piede": forms.Textarea(attrs={"rows": 3}),
            "provincia": forms.TextInput(attrs={"maxlength": 2, "class": "text-uppercase"}),
        }

    def clean_provincia(self):
        return self.cleaned_data["provincia"].strip().upper()

    def clean_codice_fiscale(self):
        return self.cleaned_data["codice_fiscale"].strip().upper()


class OrganizzazioneCompletaForm(OrganizzazioneForm):
    """Pagina Organizzazione: anche il logo del modulo di adesione."""

    nuovo_logo_modulo = forms.ImageField(
        label="Logo del modulo",
        required=False,
        help_text="Es. il logo della presidenza nazionale; senza, si usa il logo dell'ente.",
        widget=forms.FileInput(attrs={"accept": "image/png,image/jpeg,image/webp"}),
    )
    togli_logo_modulo = forms.BooleanField(label="Togli il logo del modulo", required=False)


class EnteForm(OrganizzazioneForm):
    """Solo i dati dell'ente (primo passo della configurazione iniziale)."""

    class Meta(OrganizzazioneForm.Meta):
        fields = CAMPI_ENTE


class ServiziPostaForm(StileMixin, forms.ModelForm):
    class Meta:
        from .models import Organizzazione

        model = Organizzazione
        fields = ["invio_email", "ricezione_posta"]


class DocumentoPubblicoForm(StileMixin, forms.ModelForm):
    nuovo_file = forms.FileField(
        label="File PDF",
        required=False,
        help_text="Per un documento già caricato, solo se va sostituito.",
        widget=forms.FileInput(attrs={"accept": "application/pdf,.pdf"}),
    )

    class Meta:
        from .models import DocumentoPubblico

        model = DocumentoPubblico
        fields = ["titolo", "descrizione", "ordine", "pubblicato"]


class AspettoForm(StileMixin, forms.ModelForm):
    nuovo_logo = forms.ImageField(
        label="Logo",
        required=False,
        help_text="PNG o JPEG, meglio quadrato e con sfondo trasparente; ridotto a 512 pixel.",
        widget=forms.FileInput(attrs={"accept": "image/png,image/jpeg,image/webp"}),
    )
    togli_logo = forms.BooleanField(label="Togli il logo attuale", required=False)

    class Meta:
        from .models import Organizzazione

        model = Organizzazione
        fields = ["colore_primario", "stile_menu"]
        widgets = {
            "colore_primario": forms.TextInput(
                attrs={"type": "color", "class": "form-control-color"}
            ),
            "stile_menu": forms.RadioSelect,
        }

    def clean_colore_primario(self):
        return self.cleaned_data["colore_primario"].lower()
