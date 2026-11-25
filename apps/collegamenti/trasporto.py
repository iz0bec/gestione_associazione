# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Trasporto HTTP verso le controparti (ADR-030 §6): HTTPS con verifica del
# *              certificato mai disattivabile (CA di sistema, CA interna o impronta SPKI),
# *              http in chiaro solo su indirizzi privati e se abilitato, niente redirect,
# *              risoluzione del nome a ogni chiamata e controllo dell'indirizzo (contro SSRF e
# *              DNS rebinding), limiti di tempo e di dimensione.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import base64
import hashlib
import http.client
import ipaddress
import socket
import ssl
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from cryptography import x509
from cryptography.hazmat.primitives import serialization

TEMPO_MASSIMO = 15
DIMENSIONE_MASSIMA = 5 * 1024 * 1024


class ErroreTrasporto(Exception):
    pass


@dataclass
class Destinazione:
    """Un indirizzo di una controparte con le sue regole di verifica."""

    url: str  # base, es. https://gestionale.example.org (senza /api/v1)
    verifica: str = "pubblica"  # pubblica | ca_interna | impronta
    ca_pem: str = ""
    spki: list = field(default_factory=list)
    privati_ammessi: bool = False  # controparte in rete interna
    http_ammesso: bool = False

    @property
    def descrizione(self):
        return f"{self.url} ({self.verifica})"


@dataclass
class Risposta:
    stato: int
    intestazioni: dict  # nomi in minuscolo
    corpo: bytes
    destinazione: Destinazione


def privato(ip) -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_unspecified
        or ip.is_multicast
        or (ip.version == 6 and ip.ipv4_mapped is not None and privato(ip.ipv4_mapped))
    )


def impronta_spki_der(der: bytes) -> str:
    certificato = x509.load_der_x509_certificate(der)
    spki = certificato.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return base64.b64encode(hashlib.sha256(spki).digest()).decode()


def _risolvi(host, porta, dest: Destinazione):
    try:
        letterale = ipaddress.ip_address(host.strip("[]"))
        indirizzi = [letterale]
    except ValueError:
        try:
            info = socket.getaddrinfo(host, porta, type=socket.SOCK_STREAM)
        except socket.gaierror as e:
            raise ErroreTrasporto(f"Nome non risolto: {host}.") from e
        indirizzi = list(dict.fromkeys(ipaddress.ip_address(i[4][0]) for i in info))
    if not indirizzi:
        raise ErroreTrasporto(f"Nome non risolto: {host}.")
    for ip in indirizzi:
        if privato(ip) and not dest.privati_ammessi:
            raise ErroreTrasporto(
                f"{host} corrisponde a un indirizzo privato ({ip}): ammesso solo per le "
                "controparti segnate «rete interna»."
            )
    return indirizzi


def _contesto(dest: Destinazione):
    if dest.verifica == "impronta":
        if not dest.spki:
            raise ErroreTrasporto("Modalità «impronta» senza impronte SPKI registrate.")
        contesto = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        contesto.check_hostname = False
        contesto.verify_mode = ssl.CERT_NONE  # sostituita dal confronto dell'impronta, sotto
    elif dest.verifica == "ca_interna":
        if not dest.ca_pem.strip():
            raise ErroreTrasporto("Modalità «CA interna» senza il certificato della CA.")
        try:
            contesto = ssl.create_default_context(cadata=dest.ca_pem)
        except ssl.SSLError as e:
            raise ErroreTrasporto("Certificato della CA interna non valido.") from e
    elif dest.verifica == "pubblica":
        contesto = ssl.create_default_context()
    else:
        raise ErroreTrasporto(f"Modalità di verifica sconosciuta: {dest.verifica}.")
    contesto.minimum_version = ssl.TLSVersion.TLSv1_2
    return contesto


def controlla(dest: Destinazione):
    """Regole statiche dell'indirizzo (prima di qualsiasi connessione)."""
    parti = urlsplit(dest.url)
    if parti.scheme not in ("https", "http") or not parti.hostname:
        raise ErroreTrasporto(f"Indirizzo non valido: {dest.url}.")
    if parti.username or parti.password or parti.query or parti.fragment:
        raise ErroreTrasporto("L'indirizzo non deve contenere credenziali, query o frammenti.")
    if parti.scheme == "http":
        if not (dest.http_ammesso and dest.privati_ammessi):
            raise ErroreTrasporto(
                "http in chiaro non abilitato: serve HTTPS (o il consenso esplicito per la rete "
                "interna)."
            )
        try:
            if not privato(ipaddress.ip_address(parti.hostname)):
                raise ErroreTrasporto("http in chiaro solo verso indirizzi IP privati.")
        except ValueError as e:
            raise ErroreTrasporto("http in chiaro solo verso indirizzi IP privati.") from e
    elif dest.verifica != "pubblica" and not dest.privati_ammessi:
        raise ErroreTrasporto("CA interna e impronta valgono solo per la rete interna.")
    return parti


def richiesta(dest: Destinazione, metodo, percorso, intestazioni=None, corpo=b"") -> Risposta:
    """Una richiesta HTTP verso `dest.url` + `percorso` (che deve iniziare con /)."""
    parti = controlla(dest)
    https = parti.scheme == "https"
    porta = parti.port or (443 if https else 80)
    host = parti.hostname
    indirizzi = _risolvi(host, porta, dest)
    errore = None
    for ip in indirizzi:
        try:
            sock = socket.create_connection((str(ip), porta), timeout=TEMPO_MASSIMO)
        except OSError as e:
            errore = e
            continue
        try:
            if https:
                sock = _contesto(dest).wrap_socket(sock, server_hostname=host)
                if dest.verifica == "impronta":
                    impronta = impronta_spki_der(sock.getpeercert(binary_form=True))
                    if impronta not in dest.spki:
                        raise ErroreTrasporto(
                            f"Impronta del certificato inattesa ({impronta}): "
                            "connessione rifiutata."
                        )
            return _scambia(sock, dest, parti, porta, metodo, percorso, intestazioni or {}, corpo)
        except ssl.SSLCertVerificationError as e:
            sock.close()
            raise ErroreTrasporto(f"Certificato non valido per {host}: {e.verify_message}.") from e
        except (ssl.SSLError, OSError, http.client.HTTPException) as e:
            sock.close()
            errore = e
        except ErroreTrasporto:
            sock.close()
            raise
    raise ErroreTrasporto(f"Connessione non riuscita a {host}:{porta}: {errore}.")


def _scambia(sock, dest, parti, porta, metodo, percorso, intestazioni, corpo):
    predefinita = 443 if parti.scheme == "https" else 80
    connessione = http.client.HTTPConnection(parti.hostname, porta, timeout=TEMPO_MASSIMO)
    connessione.sock = sock
    base = parti.path.rstrip("/")
    try:
        connessione.putrequest(metodo, base + percorso, skip_host=True, skip_accept_encoding=True)
        host = parti.hostname if ":" not in parti.hostname else f"[{parti.hostname}]"
        connessione.putheader("Host", host if porta == predefinita else f"{host}:{porta}")
        predefinite = {"User-Agent": "GestioneAssociazione-API/1", "Accept": "application/json"}
        for nome, valore in (predefinite | intestazioni).items():
            connessione.putheader(nome, valore)
        connessione.putheader("Content-Length", str(len(corpo)))
        connessione.endheaders(corpo or None)
        risposta = connessione.getresponse()
        dati = risposta.read(DIMENSIONE_MASSIMA + 1)
        if len(dati) > DIMENSIONE_MASSIMA:
            raise ErroreTrasporto("Risposta troppo grande.")
        return Risposta(
            stato=risposta.status,
            intestazioni={k.lower(): v for k, v in risposta.getheaders()},
            corpo=dati,
            destinazione=dest,
        )
    finally:
        connessione.close()
