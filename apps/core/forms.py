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
