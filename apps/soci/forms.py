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


class TrasferimentoForm(StileMixin, forms.Form):
    sezione = forms.ModelChoiceField(label="Nuova sezione", queryset=Sezione.objects.none())
    data = forms.DateField(label="Dal", widget=CampoData, initial=date.today)
    motivo = forms.CharField(required=False, max_length=255,
                             help_text="Es. cambio di residenza, richiesta del socio.")  # fmt: skip
    chiudi_cariche = forms.BooleanField(
        label="Chiudi alla stessa data le cariche negli organi della sezione di provenienza",
        required=False,
    )

    def __init__(self, *args, socio=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = Sezione.objects.filter(attiva=True).order_by("nome")
        self.fields["sezione"].queryset = qs.exclude(pk=socio.sezione_id) if socio else qs


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
        if self.instance.pk and "sezione" in self.fields:
            # dopo l'iscrizione la sezione cambia solo con «Trasferisci di sezione» (con lo storico)
            self.fields["sezione"].disabled = True
            self.fields[
                "sezione"
            ].help_text = "Si cambia con «Trasferisci di sezione» nella scheda."

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


class IncassoMassivoForm(PagamentoForm):
    """Dati comuni dell'incasso massivo; l'importo è quello di ciascuna tessera."""

    tessere = forms.ModelMultipleChoiceField(queryset=Tessera.objects.none())

    def __init__(self, *args, tessere=None, **kwargs):
        super().__init__(*args, **kwargs)
        del self.fields["importo"]
        self.fields["tessere"].queryset = tessere if tessere is not None else Tessera.objects.none()
        self.fields["tessere"].error_messages["required"] = "Spuntare almeno una quota."


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
    abbina = forms.ChoiceField(
        label="Riconosci la sezione del file per",
        choices=[
            ("comune", "Comune della sezione (ogni comune ha una sola sezione)"),
            ("nome", "Nome della sezione"),
            ("codice", "Codice della sezione"),
        ],
        initial="comune",
        required=False,
        widget=forms.RadioSelect,
        help_text="Il valore della colonna «Sezione» del file (es. RIONERO IN VULTURE) viene "
        "confrontato con questo campo delle sezioni registrate.",
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
        help_text="Anche l'anno precedente, se il file ha la colonna «Numero tessera anno …».",
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
    quote = forms.ChoiceField(
        label="Quote dei tesseramenti importati",
        choices=[
            (
                "da_incassare",
                "Da incassare (compaiono tra i morosi finché non si registra l'incasso)",
            ),
            ("pagate", "Già incassate (senza ricevuta e senza registrazione in prima nota)"),
        ],
        initial="da_incassare",
        required=False,
        widget=forms.RadioSelect,
    )
    aggiorna_dati = forms.BooleanField(
        label="Aggiorna anche i dati diversi (scambio fra installazioni)",
        required=False,
        help_text="I dati anagrafici diversi, la matricola e la sospensione dei soci già presenti "
        "prendono il valore del file. Nome, cognome e codice fiscale non cambiano; un socio "
        "cessato non viene riattivato. L'anteprima mostra ogni modifica.",
    )
    valido = forms.BooleanField(
        label="Tieni conto della colonna «Valido» (socio validato: attivo e in regola)",
        required=False,
        help_text="Validato = quota dell'anno sociale incassata; non validato = da incassare; "
        "se la cella è vuota vale la scelta qui sopra.",
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

    def clean(self):
        """Ogni comune ha una sola sezione attiva."""
        from .importazione import comune_normale

        dati = super().clean()
        n = comune_normale(dati.get("comune", ""))
        if n and dati.get("attiva"):
            for altra in Sezione.objects.filter(attiva=True).exclude(pk=self.instance.pk):
                if comune_normale(altra.comune) == n:
                    self.add_error(
                        "comune",
                        f"Il comune ha già una sezione attiva: {altra.codice} {altra.nome}.",
                    )
                    break
        return dati

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
    "cognome", "nome", "luogo_nascita", "data_nascita", "codice_fiscale", "indirizzo", "cap",
    "comune", "provincia", "telefono", "cellulare", "email", "sezione", "tipologia",
    "accetta_statuto", "dichiarazione", "consenso_trattamento", "consenso_particolari",
    "consenso_immagini",
]  # fmt: skip

# testi del modulo di consenso al trattamento dei dati (come nell'Allegato A)
TESTO_TRATTAMENTO = (
    "al trattamento dei miei dati personali, da svolgersi in conformità a quanto indicato "
    "nell'informativa e nel rispetto delle disposizioni del GDPR e del D.Lgs. n. 196/03"
)
TESTO_PARTICOLARI = (
    "al trattamento dei miei dati «particolari», da svolgersi in conformità a quanto indicato "
    "nell'informativa e nel rispetto delle disposizioni del GDPR e del D.Lgs. n. 196/03 e delle "
    "autorizzazioni/indicazioni della Commissione UE e del Garante per la Protezione dei Dati "
    "Personali"
)
TESTO_IMMAGINI = (
    "all'uso della mia immagine per le finalità descritte nell'informativa (pubblicazione sul "
    "sito dell'Associazione, sulla pagina Facebook dell'Associazione o altre similari e affini o "
    "su materiale di promozione delle attività istituzionali dell'Associazione)"
)


def testo_statuto(org):
    articoli = (
        f", in particolare quelli riportati {org.modulo_articoli_statuto} dello Statuto"
        if (org.modulo_articoli_statuto)
        else ""
    )
    return (
        "Avendo preso visione dello Statuto e del Regolamento che regola l'Associazione, "
        f"ne condivido pienamente i contenuti{articoli}"
    )


class DomandaForm(StileMixin, forms.ModelForm):
    """Domanda inserita dalla segreteria (es. dal modulo cartaceo firmato)."""

    dichiarazione = forms.TypedChoiceField(
        choices=[(True, "SI"), (False, "NO")],
        coerce=lambda v: v in (True, "True"),
        widget=forms.RadioSelect,
        required=False,
    )

    class Meta:
        model = DomandaIscrizione
        fields = CAMPI_DOMANDA
        labels = {
            "luogo_nascita": "Nato/a a",
            "data_nascita": "il",
            "indirizzo": "Residente in via",
        }
        widgets = {
            "data_nascita": CampoData,
            "codice_fiscale": forms.TextInput(
                attrs={"class": "text-uppercase", "autocomplete": "off"}
            ),
            "provincia": forms.TextInput(attrs={"maxlength": 2, "class": "text-uppercase"}),
        }

    def __init__(self, *args, utente=None, **kwargs):
        from apps.core.models import Organizzazione

        super().__init__(*args, **kwargs)
        org = Organizzazione.corrente()
        self.fields["tipologia"].queryset = TipologiaSocio.objects.filter(attiva=True)
        self.fields["tipologia"].empty_label = "— da stabilire —"
        self.fields["sezione"].required = True
        self.fields["sezione"].label = "Chiede di essere iscritto/a alla sezione di"
        prepara_sezione(self, utente)
        self.fields["accetta_statuto"].required = True
        self.fields["accetta_statuto"].label = testo_statuto(org)
        self.fields["consenso_trattamento"].required = True
        self.fields["consenso_trattamento"].label = TESTO_TRATTAMENTO
        self.fields["consenso_particolari"].label = TESTO_PARTICOLARI
        self.fields["consenso_immagini"].label = TESTO_IMMAGINI
        if org.modulo_dichiarazione:
            self.fields[
                "dichiarazione"
            ].label = f"Dichiara inoltre di essere {org.modulo_dichiarazione}"
            self.fields["dichiarazione"].required = True
        else:
            del self.fields["dichiarazione"]

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

    def save(self, commit=True):
        domanda = super().save(commit=False)
        # le comunicazioni associative rientrano nelle finalità dell'informativa
        domanda.consenso_comunicazioni = domanda.consenso_trattamento
        if commit:
            domanda.save()
        return domanda


SALE_MODULO = "soci.domanda-pubblica"
TEMPO_MINIMO = 4  # secondi: un umano non compila il modulo più in fretta
TEMPO_MASSIMO = 2 * 60 * 60
LIMITE_PER_IP = 3  # domande per ora dallo stesso indirizzo
LIMITE_GLOBALE = 30  # domande per ora in totale (protezione da invii massivi)


def _adesso():
    return time.time()


class DomandaPubblicaForm(DomandaForm):
    """Modulo pubblico: come quello della segreteria, con i controlli anti-spam."""

    # campo trappola: invisibile alle persone, compilato dai programmi automatici
    sito = forms.CharField(required=False, label="Lasciare vuoto")
    token = forms.CharField(widget=forms.HiddenInput)

    def __init__(self, *args, ip=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.ip = ip
        # il modulo pubblico ricalca quello cartaceo: niente tipologia, email obbligatoria
        del self.fields["tipologia"]
        self.fields["email"].required = True
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
