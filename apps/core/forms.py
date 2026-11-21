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
    "federazione", "federazione_email", "nazionale_email", "archivio_centrale",
    "codice_amministrazione", "codice_aoo",
]  # fmt: skip
# dati dell'ente che la configurazione guidata non chiede (solo in Sistema → Organizzazione)
CAMPI_NON_GUIDATI = {"federazione_email", "nazionale_email", "archivio_centrale",
                     "codice_amministrazione", "codice_aoo"}  # fmt: skip
CAMPI_MODULO = [
    "modulo_intestazione", "modulo_articoli_statuto", "modulo_dichiarazione", "modulo_piede",
]  # fmt: skip


class OrganizzazioneForm(StileMixin, forms.ModelForm):
    class Meta:
        from .models import Organizzazione

        model = Organizzazione
        fields = [*CAMPI_ENTE, *CAMPI_MODULO, "informativa_privacy", "consensi_impliciti_soci",
                  "consensi_impliciti_rubrica",
                  "iscrizioni_online",
                  "area_soci", "pagina_pubblica", "presentazione",
                  "recapiti_pubblici"]  # fmt: skip
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
        # solo i campi mostrati nel passo: un campo del modulo assente dalla pagina si svuota
        fields = [c for c in CAMPI_ENTE if c not in CAMPI_NON_GUIDATI]


class ServiziPostaForm(StileMixin, forms.ModelForm):
    class Meta:
        from .models import Organizzazione

        model = Organizzazione
        fields = ["invio_email", "ricezione_posta"]


class CasellaForm(StileMixin, forms.ModelForm):
    """Casella IMAP (email o PEC) da leggere; l'uso si abilita in Protocollo → Caselle."""

    nuova_password = forms.CharField(
        label="Password",
        required=False,
        widget=forms.PasswordInput(render_value=False, attrs={"autocomplete": "new-password"}),
        help_text="Lasciare vuoto per mantenere quella salvata. È conservata cifrata.",
    )

    class Meta:
        from apps.protocollo.models import CasellaPosta

        model = CasellaPosta
        fields = [
            "nome", "pec", "server", "porta", "ssl", "utente", "cartella", "cartella_processata",
            "cartella_scartata", "giorni", "servizio_risposta",
        ]  # fmt: skip

    def __init__(self, *args, **kwargs):
        from .models import ServizioInvio

        super().__init__(*args, **kwargs)
        campo = self.fields["servizio_risposta"]
        campo.queryset = ServizioInvio.objects.filter(attivo=True).order_by("tipo", "nome")
        campo.empty_label = "— quello con lo stesso indirizzo —"

    def clean(self):
        dati = super().clean()
        processata = (dati.get("cartella_processata") or "").strip()
        if processata and processata.lower() == (dati.get("cartella") or "").strip().lower():
            self.add_error("cartella_processata", "Deve essere diversa dalla cartella da leggere.")
        scartata = (dati.get("cartella_scartata") or "").strip().lower()
        altre = {(dati.get("cartella") or "").strip().lower(), processata.lower()}
        if scartata and scartata in altre:
            self.add_error(
                "cartella_scartata", "Deve essere diversa da quella da leggere e dei scaricati."
            )
        from .cifratura import cifratura_disponibile

        if not cifratura_disponibile():
            raise forms.ValidationError(
                "Manca la chiave di cifratura (CHIAVE_CIFRATURA): chiedere all'amministratore di "
                "sistema di configurarla prima di salvare una casella."
            )
        if not self.instance.password_cifrata and not dati.get("nuova_password"):
            self.add_error("nuova_password", "Indicare la password della casella.")
        return dati

    def save(self, commit=True):
        if self.cleaned_data.get("nuova_password"):
            self.instance.imposta_password(self.cleaned_data["nuova_password"])
        if self.instance.servizio_risposta is None:
            self.instance.servizio_risposta = self.instance.servizio_stesso_indirizzo()
        return super().save(commit)


class ServizioInvioForm(StileMixin, forms.ModelForm):
    """Server SMTP per email o PEC (la password resta cifrata e non si mostra mai)."""

    nuova_password = forms.CharField(
        label="Password",
        required=False,
        widget=forms.PasswordInput(render_value=False, attrs={"autocomplete": "new-password"}),
        help_text="Lasciare vuoto per mantenere quella salvata. È conservata cifrata.",
    )

    class Meta:
        from .models import ServizioInvio

        model = ServizioInvio
        fields = [
            "nome", "tipo", "indirizzo", "nome_mittente", "server", "porta", "ssl", "utente",
            "generale", "attivo",
        ]  # fmt: skip

    def clean(self):
        from .cifratura import cifratura_disponibile
        from .models import ServizioInvio

        dati = super().clean()
        if not cifratura_disponibile():
            raise forms.ValidationError(
                "Manca la chiave di cifratura (CHIAVE_CIFRATURA): chiedere all'amministratore di "
                "sistema di configurarla prima di salvare un servizio di invio."
            )
        if not self.instance.password_cifrata and not dati.get("nuova_password"):
            self.add_error("nuova_password", "Indicare la password del servizio.")
        if dati.get("generale"):
            if dati.get("tipo") != ServizioInvio.Tipo.EMAIL:
                self.add_error("generale", "Il server generale dev'essere un servizio email.")
            if not dati.get("attivo"):
                self.add_error("generale", "Il server generale dev'essere attivo.")
            altro = ServizioInvio.objects.filter(generale=True).exclude(pk=self.instance.pk)
            if altro.exists():
                self.add_error(
                    "generale",
                    f"Il server generale è già «{altro.first()}»: togliere prima la spunta lì.",
                )
        return dati

    def save(self, commit=True):
        if self.cleaned_data.get("nuova_password"):
            self.instance.imposta_password(self.cleaned_data["nuova_password"])
        return super().save(commit)


class ServizioMessaggiForm(StileMixin, forms.ModelForm):
    """Fornitore di SMS o WhatsApp Business (password o token cifrati, mai mostrati)."""

    nuovo_segreto = forms.CharField(
        label="Password o token",
        required=False,
        widget=forms.PasswordInput(render_value=False, attrs={"autocomplete": "new-password"}),
        help_text="Skebby e Aruba: password; Twilio: Auth Token; WhatsApp: token di accesso "
        "permanente (utente di sistema). Vuoto per mantenere quello salvato. È conservato cifrato.",
    )

    class Meta:
        from .models import ServizioMessaggi

        model = ServizioMessaggi
        fields = [
            "nome", "tipo", "account", "mittente", "tipo_messaggio", "modello", "lingua",
            "url_base", "attivo",
        ]  # fmt: skip

    def clean(self):
        import re

        from .cifratura import cifratura_disponibile

        dati = super().clean()
        if not cifratura_disponibile():
            raise forms.ValidationError("Manca la chiave di cifratura (CHIAVE_CIFRATURA).")
        if not self.instance.segreto_cifrato and not dati.get("nuovo_segreto"):
            self.add_error("nuovo_segreto", "Indicare la password o il token.")
        tipo, mittente = dati.get("tipo"), (dati.get("mittente") or "").strip()
        if tipo == "whatsapp" and not (dati.get("modello") or "").strip():
            self.add_error("modello", "Per WhatsApp serve il nome del modello approvato da Meta.")
        if tipo == "twilio" and not mittente:
            self.add_error("mittente", "Per Twilio serve il numero o il Messaging Service.")
        alfanumerico = tipo in ("skebby", "aruba") and mittente and not mittente.startswith("+")
        if alfanumerico and not re.fullmatch(r"[A-Za-z0-9 ]{1,11}", mittente):
            self.add_error("mittente", "Mittente alfanumerico: al massimo 11 lettere o cifre.")
        return dati

    def save(self, commit=True):
        if self.cleaned_data.get("nuovo_segreto"):
            self.instance.imposta_segreto(self.cleaned_data["nuovo_segreto"])
        return super().save(commit)


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


class AspettoEmailForm(StileMixin, forms.ModelForm):
    """Veste grafica delle email. I colori di testata e accento uguali al colore principale si
    salvano vuoti: restano legati a quello e lo seguono quando cambia."""

    COLORI_LEGATI = ("email_colore_testata", "email_colore_accento")

    class Meta:
        from .models import Organizzazione

        model = Organizzazione
        fields = [
            "email_titolo", "email_sottotitolo", "email_logo", "email_fascia",
            "email_colore_testata", "email_colore_accento", "email_colore_sfondo",
            "email_carattere", "email_firma", "email_informativa",
        ]  # fmt: skip
        widgets = {
            "email_colore_testata": forms.TextInput(
                attrs={"type": "color", "class": "form-control-color"}
            ),
            "email_colore_accento": forms.TextInput(
                attrs={"type": "color", "class": "form-control-color"}
            ),
            "email_colore_sfondo": forms.TextInput(
                attrs={"type": "color", "class": "form-control-color"}
            ),
            "email_fascia": forms.RadioSelect,
            "email_carattere": forms.RadioSelect,
            "email_firma": forms.Textarea(attrs={"rows": 3}),
            "email_informativa": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nome in self.COLORI_LEGATI:
            self.initial[nome] = self.initial.get(nome) or self.instance.colore_primario
        org = self.instance
        self.fields["email_titolo"].widget.attrs["placeholder"] = org.denominazione

    def _colore(self, nome):
        valore = (self.cleaned_data.get(nome) or "").lower()
        return "" if valore == self.instance.colore_primario.lower() else valore

    def clean_email_colore_testata(self):
        return self._colore("email_colore_testata")

    def clean_email_colore_accento(self):
        return self._colore("email_colore_accento")

    def clean_email_colore_sfondo(self):
        return self.cleaned_data["email_colore_sfondo"].lower()
