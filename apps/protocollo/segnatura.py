# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Segnatura di protocollo secondo le Linee guida AgID sul documento informatico,
# *              Allegato 6 (schema 3.0.0): Segnatura.xml con le impronte dei documenti, firmata
# *              XAdES baseline B con il sigillo dell'ente; copia PDF con il timbro della
# *              segnatura (l'originale protocollato non si modifica mai).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import base64
import io
import re
from datetime import UTC, datetime, timedelta

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from django.db import transaction
from django.utils import timezone
from lxml import etree

from apps.core.audit import Azione, registra
from apps.core.cifratura import cifra, cifratura_disponibile, decifra
from apps.core.models import Organizzazione

from .models import Allegato, Corrispondente, Protocollo, SigilloSegnatura

NS = "http://www.agid.gov.it/protocollo/"
VERSIONE = "3.0.0"
CODICE_REGISTRO = "PROTOCOLLO"
NOME_FILE = "Segnatura.xml"
TIPO = "application/xml"
# C14N 1.0 inclusiva: la più diffusa fra i verificatori XAdES
C14N = "http://www.w3.org/TR/2001/REC-xml-c14n-20010315"
ANNI_CERTIFICATO = 10
_RE_CF = re.compile(
    r"[A-Z]{6}[0-9LMNPQRSTUV]{2}[ABCDEHLMPRST][0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{3}[A-Z]"
)
_RE_PIVA = re.compile(r"[0-9]{11}")


class OperazioneNonValida(Exception):
    pass


# --- sigillo ------------------------------------------------------------------------------------


def _nome(certificato_name):
    try:
        return certificato_name.rfc4514_string()[:300]
    except ValueError:
        return str(certificato_name)[:300]


def _salva(chiave, certificato, catena=(), *, qualificato=False, generato=False, utente=None):
    pem = certificato.public_bytes(serialization.Encoding.PEM).decode()
    chiave_pem = chiave.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    return SigilloSegnatura.objects.create(
        certificato=pem,
        catena="".join(c.public_bytes(serialization.Encoding.PEM).decode() for c in catena),
        chiave_cifrata=cifra(chiave_pem),
        titolare=_nome(certificato.subject),
        emittente=_nome(certificato.issuer),
        valido_dal=certificato.not_valid_before_utc,
        valido_al=certificato.not_valid_after_utc,
        qualificato=qualificato,
        generato=generato,
        caricato_da=utente,
    )


def genera_sigillo(utente=None):
    """Certificato autoemesso dell'installazione (non qualificato), RSA 3072, 10 anni."""
    org = Organizzazione.corrente()
    chiave = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    attributi = [
        x509.NameAttribute(NameOID.COMMON_NAME, (org.denominazione or "Associazione")[:64]),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, (org.denominazione or "Associazione")[:64]),
        x509.NameAttribute(NameOID.COUNTRY_NAME, "IT"),
    ]
    if org.codice_fiscale:
        attributi.append(x509.NameAttribute(NameOID.ORGANIZATION_IDENTIFIER,
                                            f"VATIT-{org.codice_fiscale}"[:64]))  # fmt: skip
    nome = x509.Name(attributi)
    adesso = datetime.now(UTC)
    certificato = (
        x509.CertificateBuilder()
        .subject_name(nome)
        .issuer_name(nome)
        .public_key(chiave.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(adesso - timedelta(minutes=5))
        .not_valid_after(adesso + timedelta(days=365 * ANNI_CERTIFICATO))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=True,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )  # fmt: skip
        .sign(chiave, hashes.SHA256())
    )
    sigillo = _salva(chiave, certificato, generato=True, utente=utente)
    registra(Azione.CREAZIONE, sigillo, utente=utente,
             descrizione="Sigillo della segnatura generato", titolare=sigillo.titolare,
             valido_al=sigillo.valido_al.isoformat())  # fmt: skip
    return sigillo


def carica_sigillo(dati, password, *, qualificato, utente):
    """Sigillo da un file PKCS#12 (.p12/.pfx) con chiave e certificato."""
    try:
        chiave, certificato, catena = pkcs12.load_key_and_certificates(
            dati, (password or "").encode() or None
        )
    except ValueError as e:
        raise OperazioneNonValida("File non leggibile o password errata.") from e
    if chiave is None or certificato is None:
        raise OperazioneNonValida("Il file deve contenere la chiave privata e il certificato.")
    if not isinstance(chiave, rsa.RSAPrivateKey | ec.EllipticCurvePrivateKey):
        raise OperazioneNonValida("Sono ammesse solo chiavi RSA o a curve ellittiche.")
    adesso = datetime.now(UTC)
    if not certificato.not_valid_before_utc <= adesso <= certificato.not_valid_after_utc:
        raise OperazioneNonValida("Il certificato non è valido oggi (scaduto o non ancora valido).")
    try:
        uso = certificato.extensions.get_extension_for_class(x509.KeyUsage).value
        if not (uso.digital_signature or uso.content_commitment):
            raise OperazioneNonValida("Il certificato non è abilitato alla firma.")
    except x509.ExtensionNotFound:
        pass
    sigillo = _salva(chiave, certificato, catena or (), qualificato=qualificato, utente=utente)
    registra(Azione.CREAZIONE, sigillo, utente=utente,
             descrizione="Sigillo della segnatura caricato", titolare=sigillo.titolare,
             emittente=sigillo.emittente, qualificato=qualificato,
             valido_al=sigillo.valido_al.isoformat())  # fmt: skip
    return sigillo


def sigillo_attivo(*, crea=True):
    """L'ultimo sigillo valido; se manca (o è scaduto) se ne genera uno, con `crea`."""
    sigillo = SigilloSegnatura.objects.filter(valido_al__gt=timezone.now()).first()
    if sigillo is None and crea:
        sigillo = genera_sigillo()
    return sigillo


def _materiale(sigillo):
    chiave = serialization.load_pem_private_key(decifra(sigillo.chiave_cifrata).encode(), None)
    certificati = [x509.load_pem_x509_certificate(sigillo.certificato.encode())]
    if sigillo.catena:
        certificati += x509.load_pem_x509_certificates(sigillo.catena.encode())
    return chiave, certificati


# --- composizione -------------------------------------------------------------------------------


def _el(padre, nome, testo=None, **attributi):
    qualificati = {f"{{{NS}}}{k}": v for k, v in attributi.items()}
    e = etree.SubElement(padre, f"{{{NS}}}{nome}", qualificati)
    if testo is not None:
        e.text = str(testo)
    return e


def _contatti(padre, nome_elemento, *indirizzi):
    indirizzi = [i for i in indirizzi if i]
    if indirizzi:
        contatti = _el(padre, nome_elemento)
        for i in dict.fromkeys(indirizzi):  # senza doppioni, nell'ordine
            _el(contatti, "IndirizzoTelematico", i, tipo="smtp")


def _ente(padre, denominazione, codice="", indirizzi=()):
    pg = _el(padre, "PersonaGiuridica")
    _el(pg, "Denominazione", denominazione or "—")
    codice = (codice or "").strip()
    if _RE_PIVA.fullmatch(codice):
        _el(pg, "PIVAoCF", codice)
    _contatti(pg, "ContattiPersonaGiuridica", *indirizzi)


def _mittente_ente(padre, org):
    _ente(padre, org.denominazione, org.codice_fiscale or org.partita_iva, (org.pec, org.email))


def _corrispondente(padre, c: Corrispondente, indirizzo=""):
    s = c.soggetto if c else None
    indirizzi = (indirizzo, c.indirizzo if c else "", s.pec if s else "", s.email if s else "")
    indirizzi = [i for i in indirizzi if i and "@" in i]
    if s is not None and s.tipo == s.Tipo.PERSONA and s.nome and s.cognome:
        pf = _el(padre, "PersonaFisica")
        _el(pf, "Nome", s.nome)
        _el(pf, "Cognome", s.cognome)
        if s.codice_fiscale and _RE_CF.fullmatch(s.codice_fiscale.upper()):
            _el(pf, "CodiceFiscale", s.codice_fiscale.upper())
        _contatti(pf, "Contatti", *indirizzi)
    elif s is not None:
        _ente(padre, s.denominazione or c.descrizione, s.codice_fiscale or s.partita_iva or "",
              indirizzi)  # fmt: skip
    else:
        _ente(padre, c.descrizione if c else "", "", indirizzi)


def _documento(padre, nome_elemento, a: Allegato):
    d = _el(padre, nome_elemento, nomeFile=a.nome, mimeType=a.tipo or "application/octet-stream")
    _el(d, "Impronta", base64.b64encode(bytes.fromhex(a.impronta)).decode(), algoritmo="SHA-256")


def componi(protocollo: Protocollo, *, allegati=None, destinatari=None):
    """Albero XML (non firmato). `destinatari`: lista di (corrispondente o None, nome, indirizzo);
    senza, i destinatari del protocollo (l'ente, per un protocollo in entrata)."""
    org = Organizzazione.corrente()
    if not org.codice_amministrazione_segnatura:
        raise OperazioneNonValida(
            "Indicare in Sistema → Organizzazione il codice fiscale dell'ente o il codice IPA."
        )
    allegati = list(protocollo.allegati.all() if allegati is None else allegati)
    if not allegati:
        raise OperazioneNonValida("La segnatura richiede almeno un documento.")
    allegati.sort(key=lambda a: (not a.principale, a.pk))
    registrato = timezone.localtime(protocollo.registrato_il)

    radice = etree.Element(f"{{{NS}}}SegnaturaInformatica", nsmap={"prot": NS})
    radice.set(f"{{{NS}}}versione", VERSIONE)
    radice.set(f"{{{NS}}}lang", "it")
    intestazione = _el(radice, "Intestazione")
    ident = _el(intestazione, "Identificatore")
    _el(ident, "CodiceAmministrazione", org.codice_amministrazione_segnatura,
        descrizione=org.denominazione)  # fmt: skip
    _el(ident, "CodiceAOO", org.codice_aoo_segnatura, descrizione=org.denominazione)
    _el(ident, "CodiceRegistro", CODICE_REGISTRO)
    _el(ident, "NumeroRegistrazione", f"{protocollo.numero:07d}")
    _el(ident, "DataRegistrazione", registrato.date().isoformat())
    _el(ident, "OraRegistrazione", registrato.strftime("%H:%M:%S"))
    _el(intestazione, "Oggetto", protocollo.oggetto)
    classifica = _el(intestazione, "Classifica")
    voce = protocollo.classificazione
    _el(classifica, "Denominazione", voce.descrizione if voce else "Non classificato")
    _el(classifica, "CodiceFlat", voce.codice if voce else "")
    if protocollo.riservato:
        _el(intestazione, "Riservato", "true")

    descrizione = _el(radice, "Descrizione")
    entrata = protocollo.direzione == Protocollo.Direzione.ENTRATA
    mittente = _el(descrizione, "Mittente")
    if entrata and protocollo.mittenti:
        _corrispondente(mittente, protocollo.mittenti[0])
    else:
        _mittente_ente(mittente, org)
    if destinatari is None:
        destinatari = [] if entrata else [(c, c.descrizione, "") for c in protocollo.destinatari]
    if not destinatari:  # in entrata, o interno senza destinatari: l'ente stesso
        _mittente_ente(_el(descrizione, "Destinatario", confermaRicezione="false"), org)
    for c, nome, indirizzo in destinatari:
        d = _el(descrizione, "Destinatario", confermaRicezione="false")
        if c is None:
            _ente(d, nome, "", (indirizzo,))
        else:
            _corrispondente(d, c, indirizzo)
    _documento(descrizione, "DocumentoPrimario", allegati[0])
    for a in allegati[1:]:
        _documento(descrizione, "Allegato", a)
    return radice


def firma(radice, sigillo=None) -> bytes:
    from signxml.xades import XAdESSigner

    sigillo = sigillo or sigillo_attivo()
    chiave, certificati = _materiale(sigillo)
    algoritmo = "rsa-sha256" if isinstance(chiave, rsa.RSAPrivateKey) else "ecdsa-sha256"
    firmatario = XAdESSigner(signature_algorithm=algoritmo, digest_algorithm="sha256",
                             c14n_algorithm=C14N)  # fmt: skip
    firmato = firmatario.sign(radice, key=chiave, cert=certificati)
    return etree.tostring(firmato, xml_declaration=True, encoding="UTF-8")


def genera(protocollo, *, allegati=None, destinatari=None) -> bytes:
    """Segnatura.xml firmata. Solleva OperazioneNonValida se non si può comporre."""
    if not cifratura_disponibile():
        raise OperazioneNonValida("Manca la chiave di cifratura (CHIAVE_CIFRATURA).")
    with transaction.atomic():
        return firma(componi(protocollo, allegati=allegati, destinatari=destinatari))


def verifica(xml: bytes, certificato_pem: str):
    """Controlla la firma con il certificato indicato e restituisce l'albero verificato."""
    from signxml.xades import XAdESVerifier

    esiti = XAdESVerifier().verify(xml, x509_cert=certificato_pem, expect_references=3)
    return esiti[0].signed_xml


def nome_file(protocollo):
    return f"Segnatura_{protocollo.anno}-{protocollo.numero:07d}.xml"


# --- timbro sulla copia PDF ---------------------------------------------------------------------


def righe_timbro(protocollo, org=None):
    org = org or Organizzazione.corrente()
    registrato = timezone.localtime(protocollo.registrato_il)
    voce = protocollo.classificazione
    return [
        org.denominazione,
        f"Cod. amm. {org.codice_amministrazione_segnatura or '—'} · "
        f"Cod. AOO {org.codice_aoo_segnatura} · Registro {CODICE_REGISTRO}",
        f"Prot. n. {protocollo.numero:07d} del {registrato:%d/%m/%Y} ore {registrato:%H:%M}",
        f"{protocollo.get_direzione_display()}" + (f" · classifica {voce.codice}" if voce else ""),
    ]


def copia_con_timbro(allegato: Allegato) -> bytes:
    """Copia del PDF con il timbro della segnatura in alto a destra della prima pagina."""
    from pypdf import PdfReader, PdfWriter
    from pypdf.errors import PdfReadError

    from apps.core.pdf import genera_pdf

    if allegato.tipo != "application/pdf":
        raise OperazioneNonValida("Il timbro si appone solo ai documenti PDF.")
    try:
        with allegato.file.open("rb") as f:
            lettore = PdfReader(io.BytesIO(f.read()))
        if lettore.is_encrypted:
            raise OperazioneNonValida("PDF protetto da password: il timbro non si può apporre.")
        scrittore = PdfWriter(clone_from=lettore)
    except (PdfReadError, ValueError, OSError) as e:
        raise OperazioneNonValida("Il PDF non è leggibile.") from e
    pagina = scrittore.pages[0]
    if pagina.rotation:
        pagina.transfer_rotation_to_content()
    box = pagina.cropbox
    larghezza, altezza = float(box.width), float(box.height)
    timbro = genera_pdf(
        "protocollo/pdf/timbro.html",
        {"righe": righe_timbro(allegato.protocollo), "larghezza": larghezza, "altezza": altezza},
    )
    sovrapposta = PdfReader(io.BytesIO(timbro)).pages[0]
    pagina.merge_translated_page(sovrapposta, float(box.left), float(box.bottom))
    oggetto = f"Copia con segnatura - Prot. n. {allegato.protocollo.segnatura}"
    scrittore.add_metadata({"/Subject": oggetto})
    uscita = io.BytesIO()
    scrittore.write(uscita)
    return uscita.getvalue()
