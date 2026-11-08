# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Coerenza fra ruoli, permessi e funzioni: ogni pagina è protetta, ogni voce
# *              di menu visibile a un ruolo si apre, chi modifica può anche consultare.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import re

import pytest
from django.contrib.auth.mixins import AccessMixin
from django.contrib.auth.models import Permission
from django.urls import URLPattern, URLResolver, get_resolver

from apps.accounts.ruoli import RUOLI

# pagine raggiungibili senza accesso, per scelta
PUBBLICHE = {
    "salute", "aspetto_css", "logo", "stato_ripristino", "bene_pubblico", "bene_pubblico_foto",
    "iscrizione", "iscrizione_inviata", "feed_pubblico", "documenti_pubblici", "documento_pubblico",
    "presentazione", "verifica_tessera", "verifica_tessera_codice",
}  # fmt: skip

# chi ha il primo permesso deve avere anche il secondo (la funzione lo usa)
IMPLICAZIONI = [
    ("soci.incassa_quota", "tesoreria.add_movimento"),  # l'incasso va in prima nota
    ("organi.convoca_riunione", "comunicazioni.add_invio"),  # invio delle convocazioni
    ("documenti.stampa_documento", "anagrafica.view_soggetto"),  # scelta dei destinatari
    ("comunicazioni.add_invio", "anagrafica.view_soggetto"),
    ("soci.add_socio", "anagrafica.view_soggetto"),
    ("anagrafica.importa_soggetti", "anagrafica.add_soggetto"),
    ("anagrafica.importa_soggetti", "anagrafica.change_soggetto"),
    ("protocollo.add_protocollo", "anagrafica.view_soggetto"),
]


def _viste(patterns=None, prefisso=""):
    for p in patterns if patterns is not None else get_resolver().url_patterns:
        if isinstance(p, URLResolver):
            ns = f"{p.namespace}:" if p.namespace else ""
            yield from _viste(p.url_patterns, prefisso + ns)
        elif isinstance(p, URLPattern):
            yield prefisso + (p.name or ""), p.callback


def _nostre():
    for nome, callback in _viste():
        if callback.__module__.startswith("apps."):
            yield nome, callback


def test_ogni_pagina_e_protetta():
    scoperte = []
    for nome, callback in _nostre():
        classe = getattr(callback, "view_class", None)
        if nome.split(":")[-1] in PUBBLICHE:
            continue
        if classe is None or not issubclass(classe, AccessMixin):
            scoperte.append(nome)
    assert not scoperte, f"Pagine senza controllo di accesso: {scoperte}"


@pytest.mark.django_db
def test_i_permessi_richiesti_esistono():
    esistenti = {
        f"{a}.{c}" for a, c in Permission.objects.values_list("content_type__app_label", "codename")
    }
    mancanti = []
    for nome, callback in _nostre():
        richiesti = getattr(getattr(callback, "view_class", None), "permission_required", None)
        if not richiesti:
            continue
        for p in [richiesti] if isinstance(richiesti, str) else richiesti:
            if p not in esistenti:
                mancanti.append(f"{nome}: {p}")
    assert not mancanti, mancanti


@pytest.mark.parametrize("ruolo", sorted(RUOLI))
def test_chi_modifica_puo_consultare(ruolo):
    permessi = set(RUOLI[ruolo])
    tutti = {p for perms in RUOLI.values() for p in perms}
    errori = []
    for p in permessi:
        app, codice = p.split(".")
        for azione in ("add_", "change_"):
            if codice.startswith(azione):
                vista = f"{app}.view_{codice.removeprefix(azione)}"
                if vista in tutti and vista not in permessi:
                    errori.append(f"{p} senza {vista}")
    for se, allora in IMPLICAZIONI:
        if se in permessi and allora not in permessi:
            errori.append(f"{se} senza {allora}")
    assert not errori, f"{ruolo}: {errori}"


@pytest.mark.django_db
@pytest.mark.parametrize("ruolo", sorted(RUOLI))
def test_le_voci_di_menu_si_aprono(ruolo, client_ruolo, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    client = client_ruolo(ruolo)
    pagina = client.get("/").content.decode()
    menu = pagina[pagina.index('aria-label="Menu principale"') : pagina.index("</aside>")]
    link = sorted(set(re.findall(r'href="(/[^"#]*)"', menu)) - {"/amministrazione-tecnica/"})
    assert len(link) >= 3, link
    negati = [url for url in link if client.get(url).status_code in (403, 404, 500)]
    assert not negati, f"{ruolo}: voci di menu che non si aprono {negati}"


@pytest.mark.django_db
class TestOperazioniFraModuli:
    def test_solo_chi_puo_protocollare_protocolla(self, crea_utente):
        from apps.protocollo import servizi as protocollo

        tesoriere = crea_utente("t", ruoli=["Tesoriere"])
        with pytest.raises(protocollo.OperazioneNonValida):
            protocollo.registra_protocollo(
                {"direzione": "interno", "oggetto": "Prova"},
                [{"ruolo": "mittente", "descrizione": "Noi"}],
                tesoriere,
            )
        addetto = crea_utente("a", ruoli=["Addetto protocollo"])
        p = protocollo.registra_protocollo(
            {"direzione": "interno", "oggetto": "Prova"},
            [{"ruolo": "mittente", "descrizione": "Noi"}],
            addetto,
        )
        assert p.numero == 1

    def test_invio_protocollato_solo_con_permesso(self, crea_utente):
        from apps.anagrafica.models import Soggetto
        from apps.comunicazioni import servizi as comunicazioni

        s = Soggetto.objects.create(tipo="persona", cognome="Rossi", email="r@example.org")
        tesoriere = crea_utente("t", ruoli=["Tesoriere"])
        with pytest.raises(comunicazioni.OperazioneNonValida):
            comunicazioni.crea_invio(tesoriere, oggetto="O", corpo="C", finalita="istituzionale",
                                     soggetti=[s], protocolla=True)  # fmt: skip
        assert comunicazioni.crea_invio(tesoriere, oggetto="O", corpo="C",
                                        finalita="istituzionale", soggetti=[s])  # fmt: skip

    def test_ricevuta_di_un_altra_sezione(self, client_ruolo):
        from apps.anagrafica.models import Soggetto
        from apps.soci import servizi as soci
        from apps.soci.models import Sezione, TipologiaSocio

        client = client_ruolo("Tesoriere")
        nord = Sezione.objects.create(codice="N", nome="Nord", comune="Nordville")
        sud = Sezione.objects.create(codice="S", nome="Sud", comune="Sudville")
        client.utente.sezioni.add(nord)
        s = Soggetto.objects.create(tipo="persona", cognome="Rossi", email="r@example.org")
        socio = soci.ammetti_socio(s, TipologiaSocio.objects.get(nome="Ordinario"),
                                   client.utente, sezione=sud)  # fmt: skip
        tessera = soci.rilascia_tessera(socio, 2026, client.utente)
        r = client.post(f"/comunicazioni/da/tessera/{tessera.pk}/")
        assert r.status_code == 403
