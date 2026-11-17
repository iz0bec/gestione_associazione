# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Moduli della chat interna: nuova conversazione, aggiunta di persone a un gruppo
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django import forms

from . import servizi


class _Persone(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        return obj.get_full_name() or obj.get_username()


class NuovaConversazioneForm(forms.Form):
    persone = _Persone(
        queryset=None,
        widget=forms.CheckboxSelectMultiple,
        help_text="Una sola persona senza nome del gruppo: conversazione a due.",
    )
    titolo = forms.CharField(
        label="Nome del gruppo", max_length=120, required=False,
        help_text="Serve solo se scegli più persone (es. «Consiglio direttivo»).",
    )  # fmt: skip

    def __init__(self, *args, utente, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["persone"].queryset = servizi.utenti_chat(escluso=utente)

    def clean(self):
        dati = super().clean()
        persone = dati.get("persone") or []
        if len(persone) > 1 and not (dati.get("titolo") or "").strip():
            self.add_error("titolo", "Con più persone dai un nome al gruppo.")
        return dati


class AggiungiForm(forms.Form):
    persone = _Persone(queryset=None, widget=forms.CheckboxSelectMultiple)

    def __init__(self, *args, utente, conversazione, **kwargs):
        super().__init__(*args, **kwargs)
        presenti = [p.utente_id for p in conversazione.presenti()]
        self.fields["persone"].queryset = servizi.utenti_chat(escluso=utente).exclude(
            pk__in=presenti
        )
