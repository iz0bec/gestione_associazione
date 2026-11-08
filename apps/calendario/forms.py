# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Modulo degli appuntamenti e delle scadenze
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django import forms

from apps.anagrafica.forms import CampoData
from apps.core.forms import StileMixin

from .models import Appuntamento


class CampoOra(forms.TimeInput):
    input_type = "time"

    def __init__(self, attrs=None):
        super().__init__(attrs=attrs, format="%H:%M")


class AppuntamentoForm(StileMixin, forms.ModelForm):
    class Meta:
        model = Appuntamento
        fields = ["titolo", "tipo", "giorno", "ora", "fine_giorno", "ora_fine", "luogo",
                  "descrizione", "annuale"]  # fmt: skip
        widgets = {
            "giorno": CampoData(),
            "fine_giorno": CampoData(),
            "ora": CampoOra(),
            "ora_fine": CampoOra(),
            "descrizione": forms.Textarea(attrs={"rows": 4}),
            "tipo": forms.RadioSelect,
        }

    def clean(self):
        d = super().clean()
        giorno, fine = d.get("giorno"), d.get("fine_giorno")
        ora, ora_fine = d.get("ora"), d.get("ora_fine")
        if ora_fine and not ora:
            self.add_error("ora_fine", "Indicare anche l'ora di inizio.")
        if giorno and fine and fine < giorno:
            self.add_error("fine_giorno", "La fine è prima dell'inizio.")
        if ora and ora_fine and (not fine or fine == giorno) and ora_fine < ora:
            self.add_error("ora_fine", "L'ora di fine è prima di quella di inizio.")
        if d.get("annuale") and fine and fine != giorno:
            self.add_error("annuale", "Gli impegni di più giorni non si ripetono ogni anno.")
        return d
