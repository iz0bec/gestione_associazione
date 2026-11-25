# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Moduli degli eventi e delle adesioni (anche il modulo pubblico con i
# *              controlli anti-spam)
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import time
from datetime import timedelta

from django import forms
from django.core import signing
from django.utils import timezone

from apps.core.forms import StileMixin

from .models import Adesione, Evento

SALE = "eventi.adesione"
TEMPO_MINIMO = 3  # secondi fra apertura e invio del modulo pubblico
TEMPO_MASSIMO = 2 * 3600
LIMITE_PER_IP = 5  # adesioni pubbliche per ora dallo stesso indirizzo


class CampoDataOra(forms.DateTimeInput):
    input_type = "datetime-local"

    def format_value(self, value):
        if hasattr(value, "strftime"):
            return timezone.localtime(value).strftime("%Y-%m-%dT%H:%M")
        return value


class EventoForm(StileMixin, forms.ModelForm):
    class Meta:
        model = Evento
        fields = [
            "titolo", "tipo", "inizio", "fine", "luogo", "descrizione", "quota", "posti",
            "accompagnatori", "adesioni_aperte", "chiusura_adesioni", "pubblico", "sito",
            "condiviso", "annullato",
        ]  # fmt: skip
        widgets = {
            "inizio": CampoDataOra, "fine": CampoDataOra, "chiusura_adesioni": CampoDataOra,
            "descrizione": forms.Textarea(attrs={"rows": 4}),
        }  # fmt: skip

    def clean(self):
        dati = super().clean()
        inizio, fine = dati.get("inizio"), dati.get("fine")
        if inizio and fine and fine < inizio:
            self.add_error("fine", "La fine viene prima dell'inizio.")
        return dati


class AdesioneForm(StileMixin, forms.Form):
    cognome = forms.CharField(max_length=100, label="Cognome (o denominazione)")
    nome = forms.CharField(max_length=100, required=False)
    email = forms.EmailField(required=False)
    telefono = forms.CharField(max_length=30, required=False)
    accompagnatori = forms.IntegerField(min_value=0, initial=0, required=False)
    note = forms.CharField(max_length=255, required=False, help_text="Es. esigenze alimentari.")

    def __init__(self, *args, evento=None, **kwargs):
        super().__init__(*args, **kwargs)
        if evento is not None:
            if evento.accompagnatori:
                self.fields["accompagnatori"].max_value = evento.accompagnatori
                self.fields["accompagnatori"].help_text = f"Al massimo {evento.accompagnatori}."
            else:
                del self.fields["accompagnatori"]


def _adesso():
    return time.time()


class AdesionePubblicaForm(AdesioneForm):
    sito = forms.CharField(required=False, label="Lasciare vuoto")  # trappola per i programmi
    token = forms.CharField(widget=forms.HiddenInput)

    def __init__(self, *args, ip=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.ip = ip
        self.fields["nome"].required = True
        self.fields["email"].required = True
        self.fields["sito"].widget.attrs.update({"tabindex": "-1", "autocomplete": "off"})
        if not self.is_bound:
            self.initial["token"] = signing.dumps(_adesso(), salt=SALE)

    def clean(self):
        if self.cleaned_data.get("sito"):
            raise forms.ValidationError("Invio non accettato.", code="spam")
        try:
            emesso = float(signing.loads(self.data.get("token", ""), salt=SALE,
                                         max_age=TEMPO_MASSIMO))  # fmt: skip
        except (signing.BadSignature, TypeError, ValueError):
            raise forms.ValidationError(
                "Il modulo è scaduto: ricaricare la pagina e riprovare.", code="token"
            ) from None
        if _adesso() - emesso < TEMPO_MINIMO:
            raise forms.ValidationError("Invio troppo rapido: riprovare.", code="spam")
        un_ora_fa = timezone.now() - timedelta(hours=1)
        if (
            self.ip
            and Adesione.objects.filter(
                origine=Adesione.Origine.PUBBLICO, indirizzo_ip=self.ip, creata_il__gte=un_ora_fa
            ).count()
            >= LIMITE_PER_IP
        ):
            raise forms.ValidationError("Troppe adesioni inviate di recente: riprovare più tardi.")
        return super().clean()


class IscrizioneCondivisoForm(StileMixin, forms.Form):
    """Iscrizione di uno o più soci a un evento di un'installazione collegata."""

    soggetti = forms.ModelMultipleChoiceField(
        label="Soci da iscrivere", queryset=None,
        help_text="Soci attivi di questa installazione, non ancora iscritti.",
    )  # fmt: skip
    accompagnatori = forms.IntegerField(label="Accompagnatori per socio", min_value=0,
                                        required=False, initial=0)  # fmt: skip
    note = forms.CharField(label="Note", max_length=255, required=False)

    def __init__(self, *args, evento, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.anagrafica.models import Soggetto

        iscritti = (
            evento.adesioni_valide().exclude(soggetto=None).values_list("soggetto", flat=True)
        )
        self.fields["soggetti"].queryset = (
            Soggetto.objects.filter(socio__stato="attivo").exclude(pk__in=iscritti)
            .order_by("cognome", "nome")
        )  # fmt: skip
        massimo = (evento.dati or {}).get("accompagnatori_max")
        if massimo is not None:
            self.fields["accompagnatori"].max_value = int(massimo)
            self.fields["accompagnatori"].widget.attrs["max"] = int(massimo)
            self.fields["accompagnatori"].help_text = f"Al massimo {massimo}."
