# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Moduli di Sistema → Collegamenti API: nuovo invito, uso di un invito ricevuto,
# *              modifica di una controparte (ambiti, indirizzi, verifica TLS, limiti).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import ipaddress
import re

from django import forms

from apps.collegamenti.trasporto import Destinazione, ErroreTrasporto, controlla
from apps.core.forms import StileMixin

from . import servizi
from .models import AMBITI, ClienteApi

AIUTO_DATI_PERSONALI = (
    "Obbligatorio se un'integrazione esterna riceve i dati dei soci: chi la gestisce tratta dati "
    "personali per conto dell'associazione (serve un accordo ai sensi dell'art. 28 GDPR)."
)
_SPKI = re.compile(r"[A-Za-z0-9+/]{43}=")


def _ambiti_campo(**extra):
    return forms.MultipleChoiceField(
        choices=list(AMBITI.items()), widget=forms.CheckboxSelectMultiple, required=False, **extra
    )


def _aiuto(campo):
    return ClienteApi._meta.get_field(campo).help_text


def _righe(testo):
    return [r.strip() for r in (testo or "").splitlines() if r.strip()]


def pulisci_spki(testo):
    impronte = _righe(testo)
    for impronta in impronte:
        if not _SPKI.fullmatch(impronta):
            raise forms.ValidationError(
                f"«{impronta}» non è un'impronta SPKI SHA-256 in base64 (44 caratteri)."
            )
    return impronte


class _IndirizziMixin:
    """Controlli comuni sugli indirizzi (le stesse regole del trasporto)."""

    def _controlla_indirizzi(self, dati):
        interno, pubblico = dati.get("indirizzo_interno"), dati.get("indirizzo_pubblico")
        if not interno and not pubblico:
            raise forms.ValidationError("Indicare almeno un indirizzo.")
        if pubblico:
            try:
                controlla(Destinazione(url=pubblico))
                if not pubblico.startswith("https://"):
                    raise ErroreTrasporto("L'indirizzo pubblico deve essere https.")
            except ErroreTrasporto as e:
                self.add_error("indirizzo_pubblico", str(e))
        if interno:
            dest = Destinazione(
                url=interno,
                verifica=dati.get("verifica_tls") or "pubblica",
                ca_pem=dati.get("ca_pem") or "",
                spki=dati.get("tls_spki") or [],
                privati_ammessi=bool(dati.get("rete_interna")),
                http_ammesso=bool(dati.get("http_in_chiaro")),
            )
            try:
                controlla(dest)
            except ErroreTrasporto as e:
                self.add_error("indirizzo_interno", str(e))
            if interno.startswith("https://"):
                if dest.verifica == "impronta" and not dest.spki:
                    self.add_error(
                        "tls_spki", "Con la verifica per impronta serve almeno un'impronta."
                    )
                if dest.verifica == "ca_interna" and "BEGIN CERTIFICATE" not in dest.ca_pem:
                    self.add_error("ca_pem", "Incollare il certificato della CA in formato PEM.")


class InvitoForm(StileMixin, forms.Form):
    nome = forms.CharField(
        max_length=150, help_text="Come la riconoscerete, es. «Sezione di Avigliano»."
    )
    tipo = forms.ChoiceField(choices=ClienteApi.Tipo.choices)
    ambiti = _ambiti_campo(help_text="Cosa potrà fare la controparte. Si cambia anche dopo.")
    dati_personali = forms.BooleanField(
        label="Confermo il trattamento dei dati personali", required=False,
        help_text=AIUTO_DATI_PERSONALI,
    )  # fmt: skip
    note = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), required=False)

    def clean(self):
        dati = super().clean()
        try:
            dati["ambiti"] = servizi.controlla_ambiti(
                dati.get("tipo"), dati.get("ambiti") or [],
                dati_personali_confermati=dati.get("dati_personali"),
            )  # fmt: skip
        except servizi.OperazioneNonValida as e:
            self.add_error("dati_personali", str(e))
        return dati


class UsaInvitoForm(StileMixin, _IndirizziMixin, forms.Form):
    nome = forms.CharField(max_length=150, help_text="Come la riconoscerete, es. «Federazione».")
    codice = forms.CharField(
        label="Codice d'invito", max_length=100,
        help_text="Ricevuto dall'amministratore dell'altra installazione (vale 24 ore, una volta).",
    )  # fmt: skip
    indirizzo_pubblico = forms.URLField(
        required=False, assume_scheme="https", help_text=_aiuto("indirizzo_pubblico")
    )
    indirizzo_interno = forms.URLField(
        required=False, assume_scheme="https", help_text=_aiuto("indirizzo_interno")
    )
    rete_interna = forms.BooleanField(required=False, help_text=_aiuto("rete_interna"))
    verifica_tls = forms.ChoiceField(
        label="Verifica del certificato (indirizzo interno)", choices=ClienteApi.VerificaTls.choices
    )
    ca_pem = forms.CharField(
        label="Certificato della CA interna (PEM)", required=False,
        widget=forms.Textarea(attrs={"rows": 4, "class": "font-monospace"}),
    )  # fmt: skip
    tls_spki = forms.CharField(
        label="Impronte SPKI ammesse", required=False,
        widget=forms.Textarea(attrs={"rows": 2, "class": "font-monospace"}),
        help_text="Una per riga: l'installatore la stampa alla fine "
        "(«Impronta SPKI del certificato»).",
    )  # fmt: skip
    http_in_chiaro = forms.BooleanField(
        label="Consenti http in chiaro", required=False, help_text=_aiuto("http_in_chiaro")
    )
    ambiti = _ambiti_campo(help_text="Cosa potrà fare l'altra installazione presso di noi.")

    def clean_tls_spki(self):
        return pulisci_spki(self.cleaned_data.get("tls_spki"))

    def clean(self):
        dati = super().clean()
        self._controlla_indirizzi(dati)
        return dati


class ControparteForm(StileMixin, _IndirizziMixin, forms.ModelForm):
    ambiti = _ambiti_campo()
    notifiche_flussi = forms.MultipleChoiceField(
        label="Flussi notificati", required=False, widget=forms.CheckboxSelectMultiple,
        choices=[("eventi", "Eventi"), ("sezioni", "Sezioni")],
        help_text="A ogni cambiamento si invia un avviso firmato all'indirizzo delle notifiche "
        "(solo per i flussi di cui la controparte ha l'ambito di lettura).",
    )  # fmt: skip
    tls_spki = forms.CharField(
        label="Impronte SPKI ammesse", required=False,
        widget=forms.Textarea(attrs={"rows": 2, "class": "font-monospace"}),
        help_text="Una per riga (verifica del certificato per impronta).",
    )  # fmt: skip
    dati_personali = forms.BooleanField(label="Confermo il trattamento dei dati personali",
                                        required=False, help_text=AIUTO_DATI_PERSONALI)  # fmt: skip

    class Meta:
        model = ClienteApi
        fields = ["nome", "ruolo", "sezione", "ambiti", "ip_ammessi", "scade_il",
                  "indirizzo_pubblico",
                  "indirizzo_interno", "rete_interna", "verifica_tls", "ca_pem", "tls_spki",
                  "http_in_chiaro", "indirizzo_notifiche", "notifiche_flussi", "note"]  # fmt: skip
        widgets = {
            "ip_ammessi": forms.Textarea(attrs={"rows": 2, "class": "font-monospace"}),
            "ca_pem": forms.Textarea(attrs={"rows": 4, "class": "font-monospace"}),
            "note": forms.Textarea(attrs={"rows": 2}),
            "scade_il": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["ruolo"].required = False
        self.initial["tls_spki"] = "\n".join(self.instance.tls_spki or [])
        self.initial["dati_personali"] = bool(
            set(self.instance.ambiti or []) & servizi.AMBITI_DATI_PERSONALI
        )

    def clean_tls_spki(self):
        return pulisci_spki(self.cleaned_data.get("tls_spki"))

    def clean_indirizzo_notifiche(self):
        url = self.cleaned_data.get("indirizzo_notifiche")
        if url:
            interna = bool(self.data.get("rete_interna"))
            try:
                http = bool(self.data.get("http_in_chiaro"))
                dest = Destinazione(
                    url=url.split("?")[0], privati_ammessi=interna, http_ammesso=http
                )
                controlla(dest)
            except ErroreTrasporto as e:
                raise forms.ValidationError(str(e)) from e
        return url

    def clean_ruolo(self):
        return self.cleaned_data.get("ruolo") or ClienteApi.Ruolo.PARI

    def clean_sezione(self):
        sezione = self.cleaned_data.get("sezione")
        if self.cleaned_data.get("ruolo") == ClienteApi.Ruolo.SEZIONE:
            if sezione is None:
                raise forms.ValidationError("Indicare quale delle nostre sezioni è.")
            altre = ClienteApi.objects.filter(sezione=sezione).exclude(
                stato=ClienteApi.Stato.REVOCATA).exclude(pk=self.instance.pk)  # fmt: skip
            if altre.exists():
                raise forms.ValidationError(f"La sezione è già collegata a «{altre.first()}».")
            return sezione
        return None

    def clean_ip_ammessi(self):
        righe = _righe(self.cleaned_data.get("ip_ammessi"))
        for riga in righe:
            try:
                ipaddress.ip_network(riga, strict=False)
            except ValueError as e:
                raise forms.ValidationError(f"«{riga}» non è un indirizzo IP o una rete.") from e
        return "\n".join(righe)

    def clean(self):
        dati = super().clean()
        if (
            self.instance.indirizzo_interno
            or self.instance.indirizzo_pubblico
            or (dati.get("indirizzo_interno") or dati.get("indirizzo_pubblico"))
        ):
            self._controlla_indirizzi(dati)
        try:
            dati["ambiti"] = servizi.controlla_ambiti(
                self.instance.tipo, dati.get("ambiti") or [],
                dati_personali_confermati=dati.get("dati_personali"),
            )  # fmt: skip
        except servizi.OperazioneNonValida as e:
            self.add_error("dati_personali", str(e))
        return dati
