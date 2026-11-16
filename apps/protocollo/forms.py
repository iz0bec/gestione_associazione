# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Moduli del protocollo: registrazione con corrispondenti dall'anagrafica
# *              o liberi, allegati multipli, dati accessori, caselle di posta, titolario.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import re
from email.utils import parseaddr

from django import forms

from apps.anagrafica.forms import CampoData
from apps.anagrafica.models import Soggetto
from apps.comunicazioni.models import Lista
from apps.core.cifratura import cifratura_disponibile
from apps.core.forms import StileMixin

from .models import (
    CasellaPosta,
    Classificazione,
    Corrispondente,
    ManualeGestione,
    ModelloProtocollo,
    Protocollo,
)


class InputFileMultiplo(forms.ClearableFileInput):
    allow_multiple_selected = True


class CampoFileMultiplo(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", InputFileMultiplo())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        pulisci = super().clean
        if isinstance(data, list | tuple):
            return [pulisci(d, initial) for d in data if d]
        return [pulisci(data, initial)] if data else []


class CampoSegnatura(forms.CharField):
    """Riferimento a un protocollo esistente scritto come 2026-00012 (o 12/2026)."""

    def clean(self, value):
        value = super().clean(value)
        if not value:
            return None
        m = re.fullmatch(r"\s*(\d{4})\s*[-/]\s*0*(\d+)\s*", value) or re.fullmatch(
            r"\s*0*(\d+)\s*/\s*(\d{4})\s*", value
        )
        if not m:
            raise forms.ValidationError("Scrivere il numero come 2026-00012.")
        anno, numero = (m[1], m[2]) if len(m[1]) == 4 else (m[2], m[1])
        protocollo = Protocollo.objects.filter(anno=int(anno), numero=int(numero)).first()
        if protocollo is None:
            raise forms.ValidationError(f"Il protocollo {anno}-{int(numero):05d} non esiste.")
        return protocollo


def leggi_corrispondenti_liberi(testo, ruolo):
    """Una riga per corrispondente: «Nome», «Nome <email>», solo l'indirizzo email oppure
    «Nome; indirizzo postale» (es. «Prefettura; Piazza Pagano 1, 85100 Potenza (PZ)»)."""
    risultato = []
    for riga in (testo or "").splitlines():
        riga = riga.strip()
        if not riga:
            continue
        if ";" in riga and "@" not in riga:
            nome, _, indirizzo = (p.strip() for p in riga.partition(";"))
            risultato.append({"ruolo": ruolo, "descrizione": nome, "indirizzo": indirizzo})
            continue
        nome, indirizzo = parseaddr(riga)
        if "@" in indirizzo and indirizzo in riga:
            risultato.append(
                {"ruolo": ruolo, "descrizione": nome or indirizzo, "indirizzo": indirizzo}
            )
        else:
            risultato.append({"ruolo": ruolo, "descrizione": riga, "indirizzo": ""})
    return risultato


class _SceltaSoggetti(forms.ModelMultipleChoiceField):
    """Soggetti scelti con la ricerca: il template mostra solo quelli selezionati."""

    widget = forms.CheckboxSelectMultiple

    def __init__(self, **kwargs):
        super().__init__(queryset=Soggetto.objects.all(), required=False, **kwargs)


class ProtocolloForm(StileMixin, forms.ModelForm):
    mittenti = _SceltaSoggetti(label="Mittenti dall'anagrafica")
    mittenti_altri = forms.CharField(
        label="Altri mittenti",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Non in anagrafica: uno per riga, es. «Mario Rossi &lt;mario@example.org&gt;» "
        "oppure, per la posta, «Prefettura; Piazza Pagano 1, 85100 Potenza (PZ)».",
    )
    destinatari = _SceltaSoggetti(label="Destinatari dall'anagrafica")
    liste = forms.ModelMultipleChoiceField(
        label="Liste di distribuzione",
        queryset=Lista.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="I componenti delle liste scelte diventano destinatari, una volta sola ciascuno.",
    )
    destinatari_altri = forms.CharField(
        label="Altri destinatari",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Uno per riga, come sopra.",
    )
    in_risposta_a = CampoSegnatura(
        label="In risposta al protocollo", required=False, help_text="Es. 2026-00012."
    )
    allegati = CampoFileMultiplo(
        label="Documenti", required=False, help_text="Il primo file è il documento principale."
    )

    class Meta:
        model = Protocollo
        fields = [
            "direzione", "mezzo", "oggetto", "testo", "data_documento", "riferimento_mittente",
            "data_ricezione", "classificazione", "riservato", "note",
        ]  # fmt: skip
        widgets = {
            "direzione": forms.RadioSelect,
            "oggetto": forms.Textarea(attrs={"rows": 2, "maxlength": 500}),
            "testo": forms.Textarea(attrs={"rows": 6}),
            "data_documento": CampoData,
            "data_ricezione": CampoData,
            "note": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["classificazione"].queryset = Classificazione.objects.filter(attiva=True)
        self.fields["classificazione"].empty_label = "— nessuna —"
        self.fields["direzione"].choices = Protocollo.Direzione.choices  # senza la scelta vuota

    def clean_oggetto(self):
        return " ".join(self.cleaned_data["oggetto"].split())

    def clean_testo(self):
        return self.cleaned_data["testo"].replace("\r\n", "\n").strip()

    def clean(self):
        dati = super().clean()
        direzione = dati.get("direzione")
        self.corrispondenti = []
        mezzo = dati.get("mezzo")
        for ruolo, campo in (
            (Corrispondente.Ruolo.MITTENTE, "mittenti"),
            (Corrispondente.Ruolo.DESTINATARIO, "destinatari"),
        ):
            soggetti = list(dati.get(campo) or [])
            if campo == "destinatari" and direzione != Protocollo.Direzione.ENTRATA:
                soggetti += _componenti(dati.get("liste") or [])
            visti = set()
            for s in soggetti:
                if s.pk in visti:
                    continue
                visti.add(s.pk)
                self.corrispondenti.append(_da_soggetto(s, ruolo, mezzo))
            self.corrispondenti += leggi_corrispondenti_liberi(dati.get(f"{campo}_altri"), ruolo)
        ruoli = {c["ruolo"] for c in self.corrispondenti}
        if direzione == Protocollo.Direzione.ENTRATA and Corrispondente.Ruolo.MITTENTE not in ruoli:
            self.add_error("mittenti_altri", "Indicare almeno un mittente.")
        if (
            direzione == Protocollo.Direzione.USCITA
            and Corrispondente.Ruolo.DESTINATARIO not in ruoli
        ):
            self.add_error("destinatari_altri", "Indicare almeno un destinatario.")
        return dati

    def dati_protocollo(self):
        d = {campo: self.cleaned_data[campo] for campo in self.Meta.fields}
        d["risposta_a"] = self.cleaned_data.get("in_risposta_a")
        return d


def _da_soggetto(soggetto, ruolo, mezzo):
    from .buste import MEZZI_POSTALI
    from .servizi import corrispondente_da_soggetto

    return corrispondente_da_soggetto(
        soggetto, ruolo, pec_preferita=mezzo == Protocollo.Mezzo.PEC, postale=mezzo in MEZZI_POSTALI
    )


def _componenti(liste):
    """Componenti attuali delle liste (persone decedute escluse), in ordine alfabetico."""
    from apps.comunicazioni.servizi import soggetti_lista

    ids = set()
    for lista in liste:
        ids |= set(soggetti_lista(lista).values_list("pk", flat=True))
    return list(Soggetto.objects.filter(pk__in=ids, data_decesso__isnull=True))


class ModificaForm(StileMixin, forms.ModelForm):
    in_risposta_a = CampoSegnatura(label="In risposta al protocollo", required=False)

    class Meta:
        model = Protocollo
        fields = ["classificazione", "riservato", "note"]
        widgets = {"note": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.risposta_a:
            self.initial["in_risposta_a"] = self.instance.risposta_a.segnatura

    def clean_in_risposta_a(self):
        valore = self.cleaned_data["in_risposta_a"]
        if valore and valore.pk == self.instance.pk:
            raise forms.ValidationError("Un protocollo non può rispondere a se stesso.")
        return valore

    def save(self, commit=True):
        self.instance.risposta_a = self.cleaned_data.get("in_risposta_a")
        return super().save(commit)


class AllegatiForm(forms.Form):
    allegati = CampoFileMultiplo(label="Documenti da aggiungere")


class ProtocollaMessaggioForm(StileMixin, forms.Form):
    oggetto = forms.CharField(max_length=500, widget=forms.Textarea(attrs={"rows": 2}))
    classificazione = forms.ModelChoiceField(
        queryset=Classificazione.objects.filter(attiva=True),
        required=False,
        empty_label="— nessuna —",
    )
    riservato = forms.BooleanField(required=False)
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


class CasellaForm(StileMixin, forms.ModelForm):
    nuova_password = forms.CharField(
        label="Password",
        required=False,
        widget=forms.PasswordInput(render_value=False, attrs={"autocomplete": "new-password"}),
        help_text="Lasciare vuoto per mantenere quella salvata. È conservata cifrata.",
    )

    class Meta:
        model = CasellaPosta
        fields = ["nome", "pec", "server", "porta", "ssl", "utente", "cartella", "giorni", "attiva"]

    def clean(self):
        dati = super().clean()
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
        return super().save(commit)


class ClassificazioneForm(StileMixin, forms.ModelForm):
    class Meta:
        model = Classificazione
        fields = ["codice", "descrizione", "attiva"]


class ModelloProtocolloForm(StileMixin, forms.ModelForm):
    class Meta:
        model = ModelloProtocollo
        fields = [
            "nome", "direzione", "mezzo", "classificazione", "oggetto", "testo", "liste",
            "riservato", "ordine", "attivo",
        ]  # fmt: skip
        widgets = {
            "oggetto": forms.Textarea(attrs={"rows": 2, "maxlength": 500}),
            "testo": forms.Textarea(attrs={"rows": 6}),
            "liste": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["classificazione"].queryset = Classificazione.objects.filter(attiva=True)
        self.fields["classificazione"].empty_label = "— nessuna —"
        self.fields["direzione"].choices = Protocollo.Direzione.choices


class ManualeGestioneForm(StileMixin, forms.ModelForm):
    class Meta:
        model = ManualeGestione
        fields = [
            "responsabile", "vicario", "responsabile_conservazione", "conservatore",
            "atto_adozione", "integrazioni",
        ]  # fmt: skip
        widgets = {"integrazioni": forms.Textarea(attrs={"rows": 6})}

    def __init__(self, *args, **kwargs):
        from django.db.models import Q

        super().__init__(*args, **kwargs)
        # chi usa il sistema o ricopre una carica (più chi è già indicato)
        attuali = [getattr(self.instance, f"{c}_id") for c in
                   ("responsabile", "vicario", "responsabile_conservazione")]  # fmt: skip
        persone = (
            Soggetto.objects.filter(tipo="persona")
            .filter(
                Q(utente__isnull=False)
                | Q(cariche__al__isnull=True)
                | Q(pk__in=[a for a in attuali if a])
            )
            .distinct()
            .order_by("cognome", "nome")
        )
        for campo in ("responsabile", "vicario", "responsabile_conservazione"):
            self.fields[campo].queryset = persone
            self.fields[campo].empty_label = "— da indicare —"
        self.fields["responsabile"].help_text = "Persone con un account o una carica in corso."
