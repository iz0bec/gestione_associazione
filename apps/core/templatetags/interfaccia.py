# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Filtri di template: stile dei campi dei moduli (vale anche per i moduli di allauth)
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django import forms, template

register = template.Library()


@register.filter
def presentazione(campo):
    """'casella' (checkbox singola), 'scelte' (radio/checkbox multiple) o 'campo'."""
    widget = campo.field.widget
    if isinstance(widget, forms.CheckboxInput):
        return "casella"
    if isinstance(widget, forms.CheckboxSelectMultiple | forms.RadioSelect):
        return "scelte"
    return "campo"


@register.filter
def con_stile(campo):
    """Il widget del campo con le classi Tabler/Bootstrap e gli attributi di accessibilità."""
    widget = campo.field.widget
    tipo = presentazione(campo)
    if tipo != "campo":
        classe = "form-check-input"
    elif isinstance(widget, forms.Select | forms.SelectMultiple):
        classe = "form-select"
    else:
        classe = "form-control"
    classi = widget.attrs.get("class", "").split()
    if classe not in classi:
        classi.append(classe)
    attrs = {}
    if campo.errors:
        classi.append("is-invalid")
        attrs["aria-invalid"] = "true"
    if campo.help_text:
        attrs["aria-describedby"] = f"{campo.auto_id}_helptext"
    attrs["class"] = " ".join(classi)
    return campo.as_widget(attrs=attrs)
