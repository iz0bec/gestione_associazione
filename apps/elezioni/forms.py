# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Moduli del rinnovo degli organi: avvio, assemblea, esiti, passaggio di consegne,
# *              profili elettorali.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django import forms

from apps.core.forms import StileMixin

from .models import Decadenza, ProfiloElettorale, Rinnovo

DATA = {"type": "date"}
ORA = {"type": "time"}
MOMENTO = {"type": "datetime-local"}


class NuovoRinnovoForm(StileMixin, forms.Form):
    profilo = forms.ModelChoiceField(
        queryset=ProfiloElettorale.objects.filter(attivo=True), label="Profilo elettorale"
    )
    sezione = forms.ModelChoiceField(
        queryset=None, required=False, label="Sezione",
        empty_label="— organi dell'ente (federazione o associazione) —",
    )  # fmt: skip
    quadriennio = forms.CharField(
        label="Mandato", required=False, max_length=20,
        help_text="Es. 2027-2031. Vuoto: calcolato dalla scadenza dei mandati in corso.",
    )  # fmt: skip

    def __init__(self, *args, sezioni=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sezione"].queryset = sezioni
        if sezioni is not None and sezioni.count() <= 1:
            self.fields["sezione"].required = False


class AssembleaForm(StileMixin, forms.ModelForm):
    class Meta:
        model = Rinnovo
        fields = [
            "quadriennio", "data_assemblea", "seconda_convocazione", "luogo", "seggio",
            "apertura_seggio", "chiusura_seggio", "termine_liste", "ordine_del_giorno",
        ]  # fmt: skip
        widgets = {
            "data_assemblea": forms.DateTimeInput(attrs=MOMENTO, format="%Y-%m-%dT%H:%M"),
            "seconda_convocazione": forms.DateTimeInput(attrs=MOMENTO, format="%Y-%m-%dT%H:%M"),
            "apertura_seggio": forms.TimeInput(attrs=ORA, format="%H:%M"),
            "chiusura_seggio": forms.TimeInput(attrs=ORA, format="%H:%M"),
            "termine_liste": forms.DateInput(attrs=DATA, format="%Y-%m-%d"),
            "ordine_del_giorno": forms.Textarea(attrs={"rows": 6}),
        }
        help_texts = {
            "termine_liste": "Vuoto: calcolato dal profilo (giorni prima dell'assemblea).",
            "ordine_del_giorno": "Un punto per riga. Vuoto: quello proposto dal programma.",
        }


class EsitiForm(StileMixin, forms.ModelForm):
    class Meta:
        model = Rinnovo
        fields = [
            "presidente_assemblea", "segretario_assemblea", "commissione_presidente",
            "commissione_segretario", "commissione_componenti", "votato_il", "voto_aperto",
            "voto_chiuso", "scrutinio_ore", "presenti", "deleghe", "schede_votate",
            "schede_bianche", "schede_nulle", "non_partecipanti", "note_votazione",
        ]  # fmt: skip
        widgets = {
            "votato_il": forms.DateInput(attrs=DATA, format="%Y-%m-%d"),
            "voto_aperto": forms.TimeInput(attrs=ORA, format="%H:%M"),
            "voto_chiuso": forms.TimeInput(attrs=ORA, format="%H:%M"),
            "scrutinio_ore": forms.TimeInput(attrs=ORA, format="%H:%M"),
            "commissione_componenti": forms.Textarea(attrs={"rows": 3}),
            "non_partecipanti": forms.Textarea(attrs={"rows": 2}),
            "note_votazione": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["votato_il"].required = True
        if not self.instance.federazione:
            del self.fields["non_partecipanti"]


class ConsegneForm(StileMixin, forms.Form):
    giorno = forms.DateField(label="Giorno", widget=forms.DateInput(attrs=DATA))
    ora = forms.TimeField(label="Ora", required=False, widget=forms.TimeInput(attrs=ORA))
    sede = forms.CharField(label="Presso la sede", max_length=200, required=False)
    consegnante = forms.CharField(label="Consegna (presidente uscente)", max_length=150)
    ricevente = forms.CharField(label="Riceve (nuovo presidente)", max_length=150)
    testimone_1 = forms.CharField(label="Primo testimone", max_length=200, required=False)
    testimone_2 = forms.CharField(label="Secondo testimone", max_length=200, required=False)
    bilancio_al = forms.DateField(label="Bilancio alla data del", required=False,
                                  widget=forms.DateInput(attrs=DATA))  # fmt: skip
    saldo = forms.CharField(label="Saldo (€)", max_length=30, required=False)
    libretti_postali = forms.IntegerField(label="Libretti postali", required=False, min_value=0)
    libretti_bancari = forms.IntegerField(label="Libretti o conti bancari", required=False,
                                          min_value=0)  # fmt: skip
    liquidita = forms.CharField(label="Liquidità (€)", max_length=30, required=False)
    documenti = forms.CharField(
        label="Documenti consegnati", required=False, widget=forms.Textarea(attrs={"rows": 4}),
        help_text="Libro verbali, bandiera, registro protocollo, contabilità, libro iscritti, "
        "contratti di comodato… uno per riga, con gli estremi.",
    )  # fmt: skip
    materiale = forms.CharField(
        label="Materiale consegnato", required=False, widget=forms.Textarea(attrs={"rows": 4}),
        help_text="L'inventario dei beni si consegna anche con Patrimonio → Passaggio di consegne.",
    )  # fmt: skip
    utenze_regolari = forms.BooleanField(
        label="Il presidente uscente dichiara regolari utenze, tasse e imposte", required=False
    )

    def dati(self):
        d = dict(self.cleaned_data)
        for chiave in ("giorno", "bilancio_al"):
            d[f"{chiave}_testo"] = d[chiave].strftime("%d/%m/%Y") if d.get(chiave) else ""
        for chiave in ("giorno", "bilancio_al"):
            d[chiave] = d[chiave].isoformat() if d.get(chiave) else ""
        d["ora"] = d["ora"].strftime("%H:%M") if d.get("ora") else ""
        return d


class ProfiloForm(StileMixin, forms.ModelForm):
    class Meta:
        model = ProfiloElettorale
        fields = [
            f.name for f in ProfiloElettorale._meta.get_fields() if f.concrete and not f.primary_key
        ]


class DecadenzaForm(StileMixin, forms.Form):
    sezione = forms.ModelChoiceField(
        queryset=None, required=False, label="Sezione",
        empty_label="— organi dell'ente (federazione) —",
    )  # fmt: skip
    motivo = forms.ChoiceField(choices=Decadenza.Motivo.choices)
    giorno = forms.DateField(label="Dal giorno", widget=forms.DateInput(attrs=DATA))
    disposto_da = forms.CharField(
        label="Disposto da", max_length=150, required=False,
        help_text="Es. Consiglio direttivo provinciale (sezioni), Giunta esecutiva nazionale "
        "(federazione).",
    )  # fmt: skip
    atto = forms.CharField(label="Provvedimento", max_length=200, required=False,
                           help_text="Es. delibera n. 3 del 12/03/2027.")  # fmt: skip
    altri = forms.BooleanField(
        label="Decadono anche gli altri organi elettivi (es. garanti)", required=False,
        help_text="Il consiglio direttivo e l'organo di controllo (sindaci) decadono sempre.",
    )  # fmt: skip
    termine = forms.DateField(
        label="Nuovo congresso entro", required=False, widget=forms.DateInput(attrs=DATA),
        help_text="Vuoto: dodici mesi dalla decadenza (prorogabili).",
    )  # fmt: skip
    profilo = forms.ModelChoiceField(
        queryset=ProfiloElettorale.objects.filter(attivo=True), required=False,
        label="Profilo elettorale", empty_label="— quello del livello (sezione o federazione) —",
    )  # fmt: skip
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, sezioni=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sezione"].queryset = sezioni

    def tipi(self):
        """Tipi di organo che decadono oltre al consiglio e ai sindaci."""
        from apps.organi.models import Organo

        return [Organo.Tipo.ALTRO] if self.cleaned_data["altri"] else []
