# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test del trasporto verso le controparti con un vero server HTTPS locale:
# *              verifica per impronta SPKI, CA interna e CA di sistema, redirect non seguiti,
# *              http solo come eccezione in rete interna, indirizzi privati (SSRF).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import base64
import hashlib
import ipaddress
import ssl
import threading
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from apps.collegamenti.trasporto import Destinazione, ErroreTrasporto, controlla, privato, richiesta


def _certificato(cartella, nome):
    chiave = ec.generate_private_key(ec.SECP256R1())
    soggetto = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, nome)])
    adesso = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(soggetto)
        .issuer_name(soggetto)
        .public_key(chiave.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(adesso - timedelta(minutes=5))
        .not_valid_after(adesso + timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]),
            critical=False,
        )
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(chiave, hashes.SHA256())
    )
    pem = cert.public_bytes(serialization.Encoding.PEM)
    (cartella / f"{nome}.crt").write_bytes(pem)
    (cartella / f"{nome}.key").write_bytes(
        chiave.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )  # fmt: skip
    )
    spki = cert.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return pem.decode(), base64.b64encode(hashlib.sha256(spki).digest()).decode()


class _Gestore(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "https://example.org/")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        corpo = f"ok {self.headers.get('Host')}".encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def log_message(self, *args):
        pass


class _Server(ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        pass  # strette di mano rifiutate di proposito dai test


def _server(tls_contesto=None):
    server = _Server(("127.0.0.1", 0), _Gestore)
    if tls_contesto:
        server.socket = tls_contesto.wrap_socket(server.socket, server_side=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


@pytest.fixture(scope="module")
def https(tmp_path_factory):
    cartella = tmp_path_factory.mktemp("tls")
    pem, spki = _certificato(cartella, "server")
    contesto = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    contesto.load_cert_chain(cartella / "server.crt", cartella / "server.key")
    server = _server(contesto)
    altra_ca, _ = _certificato(cartella, "altra")
    yield {"url": f"https://127.0.0.1:{server.server_port}", "pem": pem, "spki": spki,
           "altra_ca": altra_ca}  # fmt: skip
    server.shutdown()


@pytest.fixture(scope="module")
def http():
    server = _server()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def _interna(url, **extra):
    return Destinazione(url=url, privati_ammessi=True, **extra)


def test_impronta(https):
    r = richiesta(_interna(https["url"], verifica="impronta", spki=[https["spki"]]), "GET", "/x")
    assert r.stato == 200 and r.corpo.startswith(b"ok 127.0.0.1:")
    with pytest.raises(ErroreTrasporto, match="Impronta del certificato inattesa"):
        richiesta(_interna(https["url"], verifica="impronta", spki=["A" * 43 + "="]), "GET", "/")


def test_ca_interna(https):
    r = richiesta(_interna(https["url"], verifica="ca_interna", ca_pem=https["pem"]), "GET", "/")
    assert r.stato == 200
    with pytest.raises(ErroreTrasporto, match="Certificato non valido"):
        richiesta(
            _interna(https["url"], verifica="ca_interna", ca_pem=https["altra_ca"]), "GET", "/"
        )


def test_ca_di_sistema_rifiuta_l_autofirmato(https):
    with pytest.raises(ErroreTrasporto, match="Certificato non valido"):
        richiesta(_interna(https["url"]), "GET", "/")


def test_redirect_non_seguiti(https):
    dest = _interna(https["url"], verifica="impronta", spki=[https["spki"]])
    assert richiesta(dest, "GET", "/redirect").stato == 302


def test_indirizzi_privati_solo_in_rete_interna(https):
    with pytest.raises(ErroreTrasporto, match="indirizzo privato"):
        richiesta(Destinazione(url=https["url"]), "GET", "/")


def test_http_solo_come_eccezione(http):
    with pytest.raises(ErroreTrasporto, match="http in chiaro non abilitato"):
        richiesta(_interna(http), "GET", "/")
    assert richiesta(_interna(http, http_ammesso=True), "GET", "/").stato == 200


@pytest.mark.parametrize(
    "dest",
    [
        Destinazione(url="http://example.org", privati_ammessi=True, http_ammesso=True),
        Destinazione(url="https://utente:segreto@example.org"),
        Destinazione(url="https://example.org/?a=1"),
        Destinazione(url="ftp://example.org"),
        Destinazione(url="https://example.org", verifica="impronta", spki=["x"]),
    ],
)
def test_regole_degli_indirizzi(dest):
    with pytest.raises(ErroreTrasporto):
        controlla(dest)


def test_indirizzi_privati():
    for ip in ("10.0.0.1", "192.168.0.34", "127.0.0.1", "::1", "fd00::1", "169.254.1.1",
               "::ffff:192.168.0.1", "0.0.0.0"):  # noqa: S104  # fmt: skip
        assert privato(ipaddress.ip_address(ip)), ip
    for ip in ("130.25.177.151", "2a00:1450::1", "::ffff:8.8.8.8"):
        assert not privato(ipaddress.ip_address(ip)), ip
