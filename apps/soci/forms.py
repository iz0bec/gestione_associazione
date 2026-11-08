# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Moduli del libro soci e della domanda di iscrizione pubblica
# *              (con protezioni anti-spam: campo trappola, tempo minimo, limite per IP).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import time
from datetime import date, timedelta
from decimal import Decimal

from django import forms
from django.core import signing
from django.utils import timezone

from apps.anagrafica.forms import CampiFotoMixin, CampoData
from apps.anagrafica.validatori import dati_da_codice_fiscale
from apps.core.forms import StileMixin

from .models import (
    CartaTessera,
    DomandaIscrizione,
    LottoTessere,
    Sezione,
    Socio,
    Tessera,
    TipologiaSocio,
)
from .sezioni import sezioni_di


def _anni_proposti():
    oggi = date.today().year
    return [(a, str(a)) for a in range(oggi + 1, oggi - 6, -1)]


def _non_futura(valore, campo="La data"):
    if valore and valore > date.today():
        raise forms.ValidationError(f"{campo} non può essere futura.")
    return valore


def prepara_sezione(form, utente, nome="sezione"):
    """Sezioni consentite all'utente; con una sola scelta il campo è nascosto e precompilato."""
    campo = form.fields.get(nome)
    if campo is None:
        return
    qs = sezioni_di(utente) if utente is not None else Sezione.objects.filter(attiva=True)
    campo.queryset = qs
    campo.empty_label = None if qs.count() == 1 else "— scegliere —"
    if qs.count() == 1:
        campo.widget = forms.HiddenInput()
        campo.initial = qs.first().pk
        if form.is_bound:
            form.data = form.data.copy()
            form.data[form.add_prefix(nome)] = qs.first().pk


class TipologiaField(forms.ModelChoiceField):
    def __init__(self, **kwargs):
        super().__init__(queryset=TipologiaSocio.objects.filter(attiva=True), **kwargs)

    def label_from_instance(self, obj):
        from .servizi import quota_per

        quota = quota_per(obj, date.today().year)
        if not quota:
            return f"{obj.nome} (esente)"
        return f"{obj.nome} (quota {quota:.2f} €)".replace(".", ",")


class AmmissioneForm(StileMixin, forms.Form):
    sezione = forms.ModelChoiceField(queryset=Sezione.objects.none(), label="Sezione")
    tipologia = TipologiaField(label="Tipologia di socio")
    matricola = forms.CharField(
        label="Matricola nazionale",
        required=False,
        max_length=30,
        help_text="Numero nel registro nazionale, se già assegnato.",
    )
    data_ammissione = forms.DateField(
        label="Data di ammissione", widget=CampoData, initial=date.today
    )
    delibera = forms.CharField(
        label="Delibera di ammissione",
        required=False,
        max_length=200,
        help_text="Es. «Consiglio direttivo del 12/01/2026, verbale n. 3».",
    )
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    tessera = forms.BooleanField(
        label="Tesseramento dell'anno in corso con la prima tessera disponibile",
        required=False,
        initial=True,
    )

    def __init__(self, *args, utente=None, **kwargs):
        super().__init__(*args, **kwargs)
        prepara_sezione(self, utente)

    def clean_data_ammissione(self):
        return _non_futura(self.cleaned_data["data_ammissione"], "La data di ammissione")


class SocioForm(StileMixin, CampiFotoMixin, forms.ModelForm):
    class Meta:
        model = Socio
        fields = [
            "sezione", "matricola", "tipologia", "data_ammissione", "delibera_ammissione", "note",
        ]  # fmt: skip
        widgets = {"data_ammissione": CampoData, "note": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, utente=None, **kwargs):
        super().__init__(*args, **kwargs)
        prepara_sezione(self, utente)

    def clean_matricola(self):
        matricola = self.cleaned_data["matricola"].strip()
        if matricola and Socio.objects.filter(matricola=matricola).exclude(pk=self.instance.pk):
            raise forms.ValidationError("Matricola già assegnata a un altro socio.")
        return matricola

    def clean_data_ammissione(self):
        return _non_futura(self.cleaned_data["data_ammissione"], "La data di ammissione")


class CessazioneForm(StileMixin, forms.Form):
    data_cessazione = forms.DateField(
        label="Data di cessazione", widget=CampoData, initial=date.today
    )
    causa = forms.ChoiceField(label="Causa", choices=Socio.Cessazione.choices)
    note = forms.CharField(
        label="Note (es. estremi della delibera)", required=False, max_length=255
    )

    def clean_data_cessazione(self):
        return _non_futura(self.cleaned_data["data_cessazione"], "La data di cessazione")


class TesseraForm(StileMixin, forms.Form):
    anno = forms.TypedChoiceField(
        coerce=int, choices=_anni_proposti, initial=lambda: date.today().year
    )
    importo = forms.DecimalField(
        label="Quota (€)", max_digits=8, decimal_places=2, min_value=0, required=False,
        help_text="Vuoto = prezzo del listino dell'anno per la tipologia del socio.",
    )  # fmt: skip
    data_rilascio = forms.DateField(label="Data di rilascio", widget=CampoData, initial=date.today)
    attribuzione = forms.ChoiceField(
        label="Tessera fisica",
        choices=[
            ("prossima", "Prima tessera disponibile"),
            ("numero", "Numero indicato"),
            ("dopo", "Da attribuire in seguito"),
        ],
        initial="prossima",
        widget=forms.RadioSelect,
    )
    numero_tessera = forms.CharField(
        label="Numero della tessera", required=False, max_length=30,
        help_text="Come stampato sulla tessera (con la serie, se presente).",
    )  # fmt: skip
    pagata = forms.BooleanField(label="Quota incassata ora", required=False)
    metodo = forms.ChoiceField(
        label="Metodo di pagamento", choices=Tessera.Metodo.choices, required=False
    )
    riferimento = forms.CharField(label="Riferimento pagamento", required=False, max_length=100)

    def clean(self):
        dati = super().clean()
        if dati.get("attribuzione") == "numero" and not dati.get("numero_tessera"):
            self.add_error("numero_tessera", "Indicare il numero della tessera.")
        return dati

    def carta(self):
        scelta = self.cleaned_data["attribuzione"]
        if scelta == "numero":
            return self.cleaned_data["numero_tessera"]
        return "prossima" if scelta == "prossima" else None


class PagamentoForm(StileMixin, forms.Form):
    pagata_il = forms.DateField(label="Data dell'incasso", widget=CampoData, initial=date.today)
    metodo = forms.ChoiceField(label="Metodo", choices=Tessera.Metodo.choices)
    importo = forms.DecimalField(
        label="Importo (€)", max_digits=8, decimal_places=2, min_value=Decimal("0.01")
    )
    riferimento = forms.CharField(label="Riferimento", required=False, max_length=100)

    def clean_pagata_il(self):
        return _non_futura(self.cleaned_data["pagata_il"], "La data dell'incasso")


class MotivoForm(StileMixin, forms.Form):
    motivo = forms.CharField(label="Motivo", max_length=255)


class RinnovoForm(StileMixin, forms.Form):
    anno = forms.TypedChoiceField(
        coerce=int, choices=_anni_proposti, initial=lambda: date.today().year
    )
    attribuisci = forms.BooleanField(
        label="Attribuisci subito le tessere disponibili (in ordine di numero socio)",
        required=False,
        initial=True,
    )


class LottoForm(StileMixin, forms.ModelForm):
    class Meta:
        model = LottoTessere
        fields = [
            "anno", "sezione", "serie", "numero_da", "numero_a", "cifre", "data_acquisizione",
            "fornitore", "riferimento", "costo_unitario", "note",
        ]  # fmt: skip
        widgets = {"data_acquisizione": CampoData}

    def __init__(self, *args, utente=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["anno"].initial = date.today().year
        prepara_sezione(self, utente)
        costo = self.fields["costo_unitario"]
        costo.required = False
        costo.initial = None
        costo.help_text = "Vuoto = costo d'acquisto del listino dell'anno."

    def clean(self):
        dati = super().clean()
        da, a = dati.get("numero_da"), dati.get("numero_a")
        if da is not None and a is not None and a < da:
            self.add_error("numero_a", "Deve essere maggiore o uguale al numero iniziale.")
        return dati


class StatoCartaForm(StileMixin, forms.Form):
    stato = forms.ChoiceField(
        choices=[c for c in CartaTessera.Stato.choices if c[0] != CartaTessera.Stato.ATTRIBUITA]
    )
    motivo = forms.CharField(required=False, max_length=255)


class AccoglimentoForm(AmmissioneForm):
    pass


class ListinoForm(StileMixin, forms.Form):
    """Costo d'acquisto e un prezzo di distribuzione per ogni tipologia attiva."""

    costo_acquisto = forms.DecimalField(
        label="Costo d'acquisto per tessera (€)",
        max_digits=8,
        decimal_places=2,
        min_value=0,
        help_text="Quanto si paga alla sede centrale per ogni tessera fisica.",
    )
    note = forms.CharField(required=False, max_length=255)

    def __init__(self, *args, listino=None, **kwargs):
        super().__init__(*args, **kwargs)
        attuali = {q.tipologia_id: q.importo for q in listino.quote.all()} if listino else {}
        if listino:
            self.fields["costo_acquisto"].initial = listino.costo_acquisto
            self.fields["note"].initial = listino.note
        self.tipologie = list(TipologiaSocio.objects.filter(attiva=True))
        for t in self.tipologie:
            self.fields[f"quota_{t.pk}"] = forms.DecimalField(
                label=f"{t.nome} (€)",
                max_digits=8,
                decimal_places=2,
                min_value=0,
                initial=attuali.get(t.pk, t.quota_annua),
                help_text="0 = esente",
            )

    def campi_quota(self):
        return [self[f"quota_{t.pk}"] for t in self.tipologie]

    def quote(self):
        return {t: self.cleaned_data[f"quota_{t.pk}"] for t in self.tipologie}


class ImportaForm(StileMixin, forms.Form):
    """Estratto del registro soci nazionale e scelte per i dati che il file non contiene."""

    file = forms.FileField(
        label="File del registro nazionale",
        help_text="Excel (.xlsx) o CSV; la riga delle intestazioni è riconosciuta da sola.",
        widget=forms.FileInput(attrs={"accept": ".xlsx,.csv"}),
    )
    sezione = forms.ModelChoiceField(
        queryset=Sezione.objects.none(),
        label="Sezione",
        required=False,
        help_text="Per le righe senza colonna sezione.",
    )
    tipologia = forms.ModelChoiceField(
        queryset=TipologiaSocio.objects.filter(attiva=True),
        label="Tipologia predefinita",
        help_text="Per le righe senza tipologia o con una tipologia non riconosciuta.",
    )
    crea_sezioni = forms.BooleanField(
        label="Crea le sezioni presenti nel file e non ancora registrate", required=False
    )
    allinea_sezione = forms.BooleanField(
        label="Sposta i soci già presenti nella sezione indicata dal registro", required=False
    )
    tessere = forms.BooleanField(
        label="Registra i tesseramenti con i numeri di tessera del file",
        required=False,
        initial=True,
        help_text="Anche l'anno precedente, se il file ha la colonna «Numero tessera anno …». "
        "Le quote risultano da incassare.",
    )
    crea_tessere = forms.BooleanField(
        label="Aggiungi le tessere fisiche non ancora caricate",
        required=False,
        initial=True,
        help_text="Finiscono nel carico «Registro soci nazionale» dell'anno e della sezione.",
    )
    anno_tessere = forms.TypedChoiceField(
        label="Anno delle tessere",
        coerce=int,
        empty_value=None,
        required=False,
        choices=lambda: [("", "— dalla colonna «Anno sociale» —"), *_anni_proposti()],
    )
    cessazioni = forms.BooleanField(
        label="Registra le cessazioni (data di annullamento dell'iscrizione)",
        required=False,
        initial=True,
    )

    def __init__(self, *args, utente=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sezione"].queryset = sezioni_di(utente)
        self.fields["sezione"].empty_label = "— dalla colonna del file —"
        if self.fields["sezione"].queryset.count() == 1:
            self.fields["sezione"].initial = self.fields["sezione"].queryset.first().pk
        self.fields["tipologia"].initial = TipologiaSocio.objects.filter(attiva=True).first()


class SezioneForm(StileMixin, forms.ModelForm):
    class Meta:
        model = Sezione
        fields = ["codice", "nome", "comune", "provincia", "email", "attiva", "ordine"]
        widgets = {"provincia": forms.TextInput(attrs={"maxlength": 2, "class": "text-uppercase"})}

    def clean_provincia(self):
        return self.cleaned_data["provincia"].strip().upper()

    def clean_attiva(self):
        attiva = self.cleaned_data["attiva"]
        if not attiva and self.instance.pk and self.instance.soci.filter(stato="attivo").exists():
            raise forms.ValidationError("La sezione ha soci attivi: trasferirli prima.")
        return attiva


class TipologiaForm(StileMixin, forms.ModelForm):
    class Meta:
        model = TipologiaSocio
        fields = ["nome", "descrizione", "quota_annua", "attiva", "ordine"]


# --- domanda di iscrizione ---------------------------------------------------------------

CAMPI_DOMANDA = [
    "nome", "cognome", "codice_fiscale", "data_nascita", "luogo_nascita", "email", "telefono",
    "indirizzo", "cap", "comune", "provincia", "sezione", "tipologia", "motivazione",
    "accetta_statuto",
    "consenso_comunicazioni", "consenso_immagini",
]  # fmt: skip


class DomandaForm(StileMixin, forms.ModelForm):
    """Domanda inserita dalla segreteria (es. da modulo cartaceo)."""

    class Meta:
        model = DomandaIscrizione
        fields = CAMPI_DOMANDA
        labels = {
            "consenso_comunicazioni": "Acconsente a ricevere comunicazioni associative",
            "consenso_immagini": "Acconsente alla pubblicazione di foto e video",
        }
        widgets = {
            "data_nascita": CampoData,
            "motivazione": forms.Textarea(attrs={"rows": 3}),
            "codice_fiscale": forms.TextInput(
                attrs={"class": "text-uppercase", "autocomplete": "off"}
            ),
            "provincia": forms.TextInput(attrs={"maxlength": 2, "class": "text-uppercase"}),
        }

    def __init__(self, *args, utente=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tipologia"].queryset = TipologiaSocio.objects.filter(attiva=True)
        self.fields["tipologia"].empty_label = "— da stabilire —"
        self.fields["accetta_statuto"].required = True
        self.fields["sezione"].required = True
        prepara_sezione(self, utente)

    def clean_codice_fiscale(self):
        cf = self.cleaned_data["codice_fiscale"].strip().upper()
        if len(cf) != 16:
            raise forms.ValidationError("Indicare il codice fiscale di 16 caratteri.")
        return cf

    def clean_provincia(self):
        return self.cleaned_data["provincia"].strip().upper()

    def clean(self):
        dati = super().clean()
        da_cf = dati_da_codice_fiscale(dati.get("codice_fiscale"))
        nascita = dati.get("data_nascita")
        if da_cf and nascita and nascita != da_cf["data_nascita"]:
            self.add_error("data_nascita", "Non corrisponde al codice fiscale.")
        if nascita and nascita > date.today() - timedelta(days=365 * 14):
            self.add_error("data_nascita", "Data di nascita non plausibile.")
        return dati


SALE_MODULO = "soci.domanda-pubblica"
TEMPO_MINIMO = 4  # secondi: un umano non compila il modulo più in fretta
TEMPO_MASSIMO = 2 * 60 * 60
LIMITE_PER_IP = 3  # domande per ora dallo stesso indirizzo
LIMITE_GLOBALE = 30  # domande per ora in totale (protezione da invii massivi)


def _adesso():
    return time.time()


class DomandaPubblicaForm(DomandaForm):
    """Modulo pubblico: aggiunge consenso al trattamento e controlli anti-spam."""

    privacy = forms.BooleanField(
        label="Ho letto l'informativa sul trattamento dei dati personali", required=True
    )
    # campo trappola: invisibile alle persone, compilato dai programmi automatici
    sito = forms.CharField(required=False, label="Lasciare vuoto")
    token = forms.CharField(widget=forms.HiddenInput)

    def __init__(self, *args, ip=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.ip = ip
        # nel modulo pubblico scrive il richiedente: prima persona
        self.fields["tipologia"].empty_label = "— scegliere —"
        etichette = {
            "accetta_statuto": "Dichiaro di accettare lo statuto dell'associazione",
            "consenso_comunicazioni": "Acconsento a ricevere comunicazioni associative",
            "consenso_immagini": "Acconsento alla pubblicazione di foto e video",
        }
        for nome, etichetta in etichette.items():
            self.fields[nome].label = etichetta
        self.fields["sito"].widget.attrs.update({"tabindex": "-1", "autocomplete": "off"})
        if not self.is_bound:
            self.initial["token"] = signing.dumps(_adesso(), salt=SALE_MODULO)

    def clean(self):
        if self.cleaned_data.get("sito"):
            raise forms.ValidationError("Invio non accettato.", code="spam")
        try:
            emesso = float(
                signing.loads(self.data.get("token", ""), salt=SALE_MODULO, max_age=TEMPO_MASSIMO)
            )
        except (signing.BadSignature, TypeError, ValueError):
            raise forms.ValidationError(
                "Il modulo è scaduto: ricaricare la pagina e riprovare.", code="token"
            ) from None
        if _adesso() - emesso < TEMPO_MINIMO:
            raise forms.ValidationError("Invio troppo rapido: riprovare.", code="spam")
        un_ora_fa = timezone.now() - timedelta(hours=1)
        recenti = DomandaIscrizione.objects.filter(
            origine=DomandaIscrizione.Origine.PUBBLICA, ricevuta_il__gte=un_ora_fa
        )
        if recenti.count() >= LIMITE_GLOBALE or (
            self.ip and recenti.filter(indirizzo_ip=self.ip).count() >= LIMITE_PER_IP
        ):
            raise forms.ValidationError(
                "Troppe domande inviate di recente: riprovare più tardi.", code="limite"
            )
        return super().clean()
