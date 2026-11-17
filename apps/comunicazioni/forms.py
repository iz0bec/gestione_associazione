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
from .models import (
    Automazione,
    Finalita,
    Lista,
    Modello,
    Onomastico,
    PromemoriaRinnovo,
    Ricorrenza,
)
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
        label="Testo",
        required=False,
        widget=forms.Textarea(attrs={"rows": 10}),
        help_text=AIUTO_SEGNAPOSTO,
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
    da = forms.ChoiceField(
        label="Spedisci da",
        required=False,
        help_text="Con un servizio PEC chi ha la PEC in anagrafica la riceve per PEC (con le "
        "ricevute di consegna), gli altri per email dal server generale.",
    )
    telegram = forms.BooleanField(
        label="Anche su Telegram",
        required=False,
        help_text="A chi ha collegato Telegram; chi non ha l'email la riceve solo lì.",
    )
    email = forms.BooleanField(
        label="Per email",
        required=False,
        initial=True,
        help_text="Togliendo la spunta la comunicazione parte solo per SMS, WhatsApp o Telegram "
        "(il testo lungo serve solo per Telegram).",
    )
    sms = forms.BooleanField(
        label="Anche per SMS", required=False, help_text="Al cellulare dell'anagrafica."
    )
    whatsapp = forms.BooleanField(
        label="Anche su WhatsApp",
        required=False,
        help_text="Al cellulare di chi ha dato il consenso a ricevere messaggi su WhatsApp.",
    )
    testo_breve = forms.CharField(
        label="Testo breve (SMS e WhatsApp)",
        required=False,
        max_length=300,
        widget=forms.Textarea(attrs={"rows": 2, "maxlength": 300}),
        help_text="Con i segnaposto, es. «{{ saluto }} {{ nome }}, assemblea il 12/12 ore 18: "
        "dettagli per email». Vuoto: l'oggetto. Si aggiunge il nome dell'associazione.",
    )

    def __init__(self, *args, **kwargs):
        from apps.core import invio
        from apps.core.models import CanaleTelegram

        super().__init__(*args, **kwargs)
        self.servizi = list(invio.servizi_attivi())
        scelte = [(str(s.pk), f"{s.nome} - {s.indirizzo}{' (PEC)' if s.pec else ''}")
                  for s in self.servizi]  # fmt: skip
        if not any(s.generale for s in self.servizi):
            scelte.insert(0, ("", "Server di invio generale (email)"))
        self.fields["da"].choices = scelte
        generale = next((s for s in self.servizi if s.generale), None)
        self.fields["da"].initial = str(generale.pk) if generale else ""
        self.telegram_pronto = CanaleTelegram.corrente().pronto
        if not self.telegram_pronto:
            del self.fields["telegram"]
        from apps.core.models import ServizioMessaggi

        for canale in ("sms", "whatsapp"):
            if ServizioMessaggi.attivo_per(canale) is None:
                del self.fields[canale]
        if "sms" not in self.fields and "whatsapp" not in self.fields:
            del self.fields["testo_breve"]
        if not ({"sms", "whatsapp", "telegram"} & set(self.fields)):
            del self.fields["email"]  # nessun altro canale: sempre per email

    def per_email(self):
        return self.cleaned_data.get("email", True) if "email" in self.fields else True

    def servizio(self):
        valore = self.cleaned_data.get("da") or ""
        servizio = next((s for s in self.servizi if str(s.pk) == valore), None)
        return None if servizio is not None and servizio.generale else servizio

    def clean(self):
        dati = super().clean()
        _controlla_segnaposto(self, "oggetto", "corpo")
        if "testo_breve" in self.fields:
            _controlla_segnaposto(self, "testo_breve")
        email = dati.get("email", True) if "email" in self.fields else True
        altri = [c for c in ("sms", "whatsapp", "telegram") if dati.get(c)]
        if not email and not altri:
            self.add_error("email", "Scegliere almeno un canale (email, SMS, WhatsApp o Telegram).")
        if (email or dati.get("telegram")) and not (dati.get("corpo") or "").strip():
            self.add_error("corpo", "Il testo è obbligatorio per l'email e per Telegram.")
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
            "sezioni",
            "organo",
            "soggetti",
        ]
        widgets = {
            "categorie": forms.CheckboxSelectMultiple,
            "sezioni": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, utente=None, **kwargs):
        from apps.soci import sezioni

        super().__init__(*args, **kwargs)
        self.fields["categorie"].queryset = Categoria.objects.all()
        self.fields["organo"].empty_label = "— nessuno —"
        self.utente = utente
        self.sezioni_utente = sezioni.id_sezioni(utente) if utente else None
        scelte = sezioni.sezioni_di(utente) if utente else sezioni.Sezione.objects.all()
        gia = set(self.instance.sezioni.values_list("pk", flat=True)) if self.instance.pk else set()
        self.fields["sezioni"].queryset = sezioni.Sezione.objects.filter(
            pk__in={*scelte.values_list("pk", flat=True), *gia}
        )
        if not sezioni.multisezione() and not gia:
            del self.fields["sezioni"]

    def clean(self):
        dati = super().clean()
        consentite = self.sezioni_utente
        if consentite is None or "sezioni" not in self.fields:
            return dati
        scelte = {s.pk for s in dati.get("sezioni") or []}
        gia = set(self.instance.sezioni.values_list("pk", flat=True)) if self.instance.pk else set()
        if scelte - consentite - gia:
            self.add_error("sezioni", "Si possono scegliere solo le proprie sezioni.")
        if (dati.get("soci_attivi") or dati.get("soci_in_regola")) and not scelte:
            self.add_error("sezioni", "Indicare le sezioni dei soci da includere.")
        return dati


class ImportaListaForm(StileMixin, forms.Form):
    file = forms.FileField(
        label="File Excel della lista (.xlsx)",
        help_text="Esportato da una lista con «Esporta in Excel» e modificato fuori linea.",
        widget=forms.FileInput(attrs={"accept": ".xlsx"}),
    )
    crea_schede = forms.BooleanField(
        label="Crea in anagrafica le persone non trovate",
        required=False,
        help_text="Con i soli dati del file (tipo, cognome o denominazione, nome, codice fiscale, "
        "email). Senza spunta sono solo segnalate.",
    )

    def __init__(self, *args, puo_creare_schede=False, **kwargs):
        super().__init__(*args, **kwargs)
        if not puo_creare_schede:
            del self.fields["crea_schede"]

    def clean_file(self):
        f = self.cleaned_data["file"]
        if f.size > 5 * 1024 * 1024:
            raise forms.ValidationError("Il file supera 5 MB.")
        return f


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


class PromemoriaRinnovoForm(StileMixin, forms.ModelForm):
    class Meta:
        model = PromemoriaRinnovo
        fields = ["attivo", "modello", "date_invio", "ora"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["modello"].queryset = Modello.objects.filter(uso="rinnovo", attivo=True)
        self.fields["modello"].empty_label = "— il primo modello attivo di questo tipo —"

    def clean_date_invio(self):
        valore = self.cleaned_data["date_invio"]
        prova = PromemoriaRinnovo(date_invio=valore)
        if not prova.date_scelte():
            raise forms.ValidationError(
                "Indicare almeno una data nella forma giorno/mese, es. 15/01."
            )
        return ", ".join(
            f"{g:02d}/{m:02d}" for g, m in sorted(prova.date_scelte(), key=lambda d: (d[1], d[0]))
        )
