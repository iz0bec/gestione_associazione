# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Moduli della gestione utenti
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django import forms
from django.contrib.auth.models import Group

from apps.anagrafica.models import Soggetto
from apps.core.forms import StileMixin

from .models import Utente


class UtenteForm(StileMixin, forms.ModelForm):
    groups = forms.ModelMultipleChoiceField(
        label="Ruoli",
        queryset=Group.objects.order_by("name"),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="I permessi si sommano. Senza ruoli l'utente vede solo il cruscotto.",
    )
    crea_scheda = forms.BooleanField(
        label="Crea la scheda in anagrafica con nome, cognome, email e telefono dell'utente",
        required=False,
        help_text="Se la persona non è ancora in anagrafica.",
    )

    class Meta:
        model = Utente
        fields = [
            "username", "first_name", "last_name", "email", "telefono", "soggetto", "groups",
            "sezioni", "puo_cambiare_password", "deve_cambiare_password",
        ]  # fmt: skip
        labels = {"username": "Nome utente", "first_name": "Nome", "last_name": "Cognome"}
        widgets = {"sezioni": forms.CheckboxSelectMultiple}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].help_text = "Si può usare anche per accedere."
        self.fields["username"].help_text = "Lettere, cifre e @ . + - _ (senza spazi)."
        soggetti = Soggetto.objects.filter(tipo=Soggetto.Tipo.PERSONA).filter(utente__isnull=True)
        if self.instance.soggetto_id:
            soggetti = soggetti | Soggetto.objects.filter(pk=self.instance.soggetto_id)
        self.fields["soggetto"].queryset = soggetti.order_by("cognome", "nome")
        self.fields["soggetto"].empty_label = "scegliere la persona"
        self.fields["soggetto"].label = "Scheda in anagrafica"
        self.fields["soggetto"].help_text = (
            "Ogni utente corrisponde a una persona dell'anagrafica (se è un socio, il collegamento "
            "vale anche per il libro soci)."
        )
        if self.instance.soggetto_id:
            del self.fields["crea_scheda"]
        if not self.instance.pk:  # alla creazione la password temporanea va sempre cambiata
            del self.fields["deve_cambiare_password"]
            del self.fields["puo_cambiare_password"]
        from apps.soci.models import Sezione

        sezioni = Sezione.objects.all()
        if sezioni.count() <= 1:
            del self.fields["sezioni"]  # associazione singola: niente scelta
        else:
            self.fields["sezioni"].queryset = sezioni.order_by("nome")

    def clean(self):
        dati = super().clean()
        crea = dati.get("crea_scheda")
        if dati.get("soggetto") and crea:
            self.add_error(
                "crea_scheda", "Scegliere una scheda esistente oppure crearne una nuova."
            )
        elif not dati.get("soggetto") and not crea:
            self.add_error("soggetto", "Scegliere la scheda in anagrafica o spuntare la creazione.")
        elif crea and not (dati.get("last_name") or "").strip():
            self.add_error("last_name", "Il cognome serve per creare la scheda in anagrafica.")
        if dati.get("puo_cambiare_password") is False and dati.get("deve_cambiare_password"):
            self.add_error(
                "deve_cambiare_password",
                "Non si può obbligare al cambio chi non può cambiare la propria password.",
            )
        return dati

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if Utente.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Email già usata da un altro utente.")
        return email


class RuoliMfaForm(StileMixin, forms.Form):
    ruoli = forms.ModelMultipleChoiceField(
        label="Ruoli con secondo fattore obbligatorio",
        queryset=Group.objects.order_by("name"),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )


class ImpostaPasswordForm(StileMixin, forms.Form):
    password1 = forms.CharField(
        label="Nuova password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    password2 = forms.CharField(
        label="Ripeti la password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    obbligo_cambio = forms.BooleanField(
        label="Deve cambiarla al primo accesso",
        required=False,
        help_text="Solo se l'utente può cambiare la propria password.",
    )

    def __init__(self, *args, utente=None, **kwargs):
        self.utente = utente
        super().__init__(*args, **kwargs)
        if utente is not None and not utente.puo_cambiare_password:
            del self.fields["obbligo_cambio"]

    def clean(self):
        from django.contrib.auth.password_validation import validate_password

        d = super().clean()
        p1, p2 = d.get("password1"), d.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Le due password non coincidono.")
        elif p1:
            try:
                validate_password(p1, self.utente)
            except forms.ValidationError as e:
                self.add_error("password1", e)
        return d
