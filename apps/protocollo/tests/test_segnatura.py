# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test della segnatura di protocollo AgID (Allegato 6): composizione, firma
# *              XAdES-B verificabile, impronte, sigillo caricato o generato, spedizione con
# *              Segnatura.xml, copia PDF con il timbro (originale invariato), viste.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import base64
import hashlib
import io
import os
from datetime import UTC, datetime, timedelta

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from lxml import etree

from apps.anagrafica.models import Soggetto
from apps.core.cifratura import nuova_chiave
from apps.core.models import Organizzazione
from apps.protocollo import segnatura, servizi, spedizioni
from apps.protocollo.models import Classificazione, SigilloSegnatura

pytestmark = pytest.mark.django_db
NS = {"prot": segnatura.NS, "ds": "http://www.w3.org/2000/09/xmldsig#"}


def _pdf():
    from apps.core.pdf import genera_pdf

    return genera_pdf("protocollo/pdf/timbro.html", {"righe": ["Documento di prova"],
                                                     "larghezza": 595, "altezza": 842})  # fmt: skip


@pytest.fixture(autouse=True)
def ambiente(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    settings.CHIAVE_CIFRATURA = nuova_chiave()
    settings.MAILERS = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}
    Organizzazione.objects.update_or_create(
        pk=1, defaults={"denominazione": "ANCR Sezione di Prova", "codice_fiscale": "96012340765",
                        "pec": "sezione@pec.example.it"},
    )  # fmt: skip


@pytest.fixture
def utente(crea_utente):
    return crea_utente("addetto", ruoli=["Addetto protocollo"])


@pytest.fixture
def protocollo(utente):
    comune = Soggetto.objects.create(tipo="ente", denominazione="Comune di Avigliano",
                                     pec="protocollo@pec.comune.example.it")  # fmt: skip
    rossi = Soggetto.objects.create(nome="Mario", cognome="Rossi", email="mario@example.org",
                                    codice_fiscale="RSSMRA50C15A519V")  # fmt: skip
    voce = Classificazione.objects.create(codice="1.2", descrizione="Corrispondenza")
    corr = [servizi.corrispondente_da_soggetto(s, "destinatario") for s in (comune, rossi)]
    p = servizi.registra_protocollo({"direzione": "uscita", "mezzo": "pec", "oggetto": "Invito",
                                     "classificazione": voce}, corr, utente)  # fmt: skip
    servizi.aggiungi_allegato(p, SimpleUploadedFile("lettera.pdf", _pdf()), utente, principale=True)
    servizi.aggiungi_allegato(p, SimpleUploadedFile("elenco.txt", b"allegato"), utente)
    return p


def test_composizione_e_firma_verificabile(protocollo):
    xml = segnatura.genera(protocollo)
    sigillo = SigilloSegnatura.objects.get()
    assert sigillo.generato and not sigillo.qualificato
    albero = etree.fromstring(xml)
    segnatura.verifica(xml, sigillo.certificato)  # firma XAdES valida
    t = lambda percorso: albero.findtext(percorso, namespaces=NS)  # noqa: E731
    ident = "prot:Intestazione/prot:Identificatore/"
    assert t(ident + "prot:CodiceAmministrazione") == "96012340765"
    assert t(ident + "prot:CodiceAOO") == "AOO" and t(ident + "prot:CodiceRegistro") == "PROTOCOLLO"
    assert t(ident + "prot:NumeroRegistrazione") == f"{protocollo.numero:07d}"
    assert t("prot:Intestazione/prot:Classifica/prot:CodiceFlat") == "1.2"
    assert albero.get(f"{{{segnatura.NS}}}versione") == "3.0.0"
    assert t("prot:Descrizione/prot:Mittente/prot:PersonaGiuridica/prot:Denominazione") == (
        "ANCR Sezione di Prova"
    )
    persona = albero.find("prot:Descrizione/prot:Destinatario/prot:PersonaFisica", NS)
    assert persona.findtext("prot:CodiceFiscale", namespaces=NS) == "RSSMRA50C15A519V"
    primario = albero.find("prot:Descrizione/prot:DocumentoPrimario", NS)
    principale = protocollo.allegati.get(principale=True)
    assert primario.get(f"{{{segnatura.NS}}}nomeFile") == "lettera.pdf"
    attesa = base64.b64encode(bytes.fromhex(principale.impronta)).decode()
    assert primario.findtext("prot:Impronta", namespaces=NS) == attesa
    assert len(albero.findall("prot:Descrizione/prot:Allegato", NS)) == 1
    assert albero.find("ds:Signature", NS) is not None and albero[-1].tag.endswith("Signature")


def test_firma_alterata_non_verifica(protocollo):
    from signxml.exceptions import InvalidSignature

    xml = segnatura.genera(protocollo).replace(b">Invito<", b">Altro<")
    with pytest.raises(InvalidSignature):
        segnatura.verifica(xml, SigilloSegnatura.objects.get().certificato)


def test_codici_ipa_e_niente_valori_inventati(protocollo):
    Organizzazione.objects.update(codice_amministrazione="ancr_pz", codice_aoo="A1B2C3D")
    albero = etree.fromstring(segnatura.genera(protocollo))
    assert albero.findtext(".//prot:CodiceAmministrazione", namespaces=NS) == "ancr_pz"
    assert albero.findtext(".//prot:CodiceAOO", namespaces=NS) == "A1B2C3D"
    Organizzazione.objects.update(codice_amministrazione="", codice_fiscale="")
    with pytest.raises(segnatura.OperazioneNonValida, match="codice fiscale"):
        segnatura.genera(protocollo)


def test_serve_un_documento(utente):
    p = servizi.registra_protocollo({"direzione": "uscita", "mezzo": "email", "oggetto": "X"},
                                    [{"ruolo": "destinatario", "descrizione": "A"}], utente)  # fmt: skip
    with pytest.raises(segnatura.OperazioneNonValida, match="almeno un documento"):
        segnatura.genera(p)


def test_spedizione_porta_la_segnatura(protocollo, utente):
    destinatari = [(r["corrispondente"], r["nome"], r["indirizzo"])
                   for r in spedizioni.indirizzi_proposti(protocollo)]  # fmt: skip
    s = spedizioni.prepara_spedizione(protocollo, utente, servizio=None, destinatari=destinatari,
                                      testo="Si trasmette.", allegati=protocollo.allegati.all(),
                                      email_ordinaria=True)  # fmt: skip
    assert s.segnatura.startswith("<?xml")
    spedizioni.spedisci(s)
    nomi = [a[0] for a in mail.outbox[0].attachments]
    assert nomi[-1] == "Segnatura.xml" and "lettera.pdf" in nomi
    assert mail.outbox[0].attachments[-1][1] == s.segnatura.encode()


def _p12(qualificato_scaduto=False):
    chiave = ec.generate_private_key(ec.SECP256R1())
    nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Sigillo ente")])
    adesso = datetime.now(UTC)
    inizio = adesso - timedelta(days=30)
    fine = adesso - timedelta(days=1) if qualificato_scaduto else adesso + timedelta(days=365)
    cert = (x509.CertificateBuilder().subject_name(nome).issuer_name(nome)
            .public_key(chiave.public_key()).serial_number(1).not_valid_before(inizio)
            .not_valid_after(fine).sign(chiave, hashes.SHA256()))  # fmt: skip
    cifratura = serialization.BestAvailableEncryption(b"segreta")
    return pkcs12.serialize_key_and_certificates(b"s", chiave, cert, None, cifratura)


def test_sigillo_caricato_si_usa(protocollo, crea_utente):
    admin = crea_utente("admin", ruoli=["Amministratore di sistema"])
    with pytest.raises(segnatura.OperazioneNonValida, match="password"):
        segnatura.carica_sigillo(_p12(), "sbagliata", qualificato=True, utente=admin)
    with pytest.raises(segnatura.OperazioneNonValida, match="non è valido"):
        segnatura.carica_sigillo(_p12(True), "segreta", qualificato=True, utente=admin)
    s = segnatura.carica_sigillo(_p12(), "segreta", qualificato=True, utente=admin)
    assert segnatura.sigillo_attivo() == s and "segreta" not in s.chiave_cifrata
    xml = segnatura.genera(protocollo)
    segnatura.verifica(xml, s.certificato)
    assert b"ecdsa-sha256" in xml


def test_copia_con_timbro_lascia_l_originale(protocollo):
    from pypdf import PdfReader

    a = protocollo.allegati.get(principale=True)
    with a.file.open("rb") as f:
        prima = hashlib.sha256(f.read()).hexdigest()
    copia = segnatura.copia_con_timbro(a)
    testo = PdfReader(io.BytesIO(copia)).pages[0].extract_text()
    assert f"Prot. n. {protocollo.numero:07d}" in testo and "96012340765" in testo
    with a.file.open("rb") as f:
        assert hashlib.sha256(f.read()).hexdigest() == prima == a.impronta
    with pytest.raises(segnatura.OperazioneNonValida, match="PDF"):
        segnatura.copia_con_timbro(protocollo.allegati.get(principale=False))


def test_viste(client_ruolo, crea_utente, protocollo):
    admin = client_ruolo("Amministratore di sistema")
    r = admin.get(reverse("protocollo:segnatura_xml", args=[protocollo.pk]))
    assert r.status_code == 200 and r["Content-Type"] == "application/xml"
    assert b"SegnaturaInformatica" in b"".join(r.streaming_content)
    a = protocollo.allegati.get(principale=True)
    r = admin.get(reverse("protocollo:copia_timbro", args=[a.pk]))
    assert r.status_code == 200 and b"".join(r.streaming_content).startswith(b"%PDF")
    pagina = admin.get(reverse("protocollo:sigillo")).content.decode()
    assert "96012340765" in pagina and "non qualificato" in pagina
    r = admin.post(reverse("protocollo:sigillo"), {"file": SimpleUploadedFile("s.p12", _p12()),
                                                  "password": "segreta", "qualificato": "on"},
                   follow=True)  # fmt: skip
    assert "Sigillo caricato" in r.content.decode() and segnatura.sigillo_attivo().qualificato
    admin.force_login(crea_utente("tesoriere", ruoli=["Tesoriere"]))
    assert admin.get(reverse("protocollo:sigillo")).status_code == 403


@pytest.mark.skipif(not os.environ.get("SEGNATURA_XSD"), reason="schema AgID non indicato")
@pytest.mark.parametrize("direzione", ["uscita", "entrata"])
def test_conforme_allo_schema_agid(protocollo, direzione):
    """Con SEGNATURA_XSD=…/segnatura_protocollo.xsd (github.com/AgID/protocollo-comunicazione-aoo,
    senza licenza: non si include nel repository)."""
    from apps.protocollo.models import Protocollo

    Protocollo.objects.filter(pk=protocollo.pk).update(direzione=direzione, riservato=True)
    protocollo.refresh_from_db()
    if direzione == "entrata":
        protocollo.corrispondenti.update(ruolo="mittente")
    schema = etree.XMLSchema(etree.parse(os.environ["SEGNATURA_XSD"]))
    documento = etree.fromstring(segnatura.genera(protocollo))
    assert schema.validate(documento), schema.error_log
