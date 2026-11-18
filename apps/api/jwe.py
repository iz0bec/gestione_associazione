# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Cifratura dei dati personali per il destinatario (ADR-030 §5): JWE compatto
# *              (RFC 7516) con la sola combinazione ammessa, alg ECDH-ES+A256KW e enc A256GCM su
# *              chiavi X25519 (RFC 8037). Concat KDF secondo RFC 7518 §4.6, avvolgimento della
# *              chiave AES secondo RFC 3394. Nessuna dipendenza oltre `cryptography`.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import hashlib
import json
import os
import struct

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.keywrap import InvalidUnwrap, aes_key_unwrap, aes_key_wrap

from .firma import b64url, b64url_decodifica

ALG = "ECDH-ES+A256KW"
ENC = "A256GCM"
TIPO = "application/jose"
DIMENSIONE_MASSIMA = 2 * 1024 * 1024


class ErroreJwe(ValueError):
    pass


def _lunghezza(dati: bytes) -> bytes:
    return struct.pack(">I", len(dati)) + dati


def concat_kdf(z: bytes, algoritmo: str, bit: int, apu: bytes = b"", apv: bytes = b"") -> bytes:
    """Concat KDF (NIST SP 800-56A) come in RFC 7518 §4.6.2, con SHA-256."""
    altre = (
        _lunghezza(algoritmo.encode()) + _lunghezza(apu) + _lunghezza(apv) + struct.pack(">I", bit)
    )
    uscita = b""
    giro = 1
    while len(uscita) * 8 < bit:
        uscita += hashlib.sha256(struct.pack(">I", giro) + z + altre).digest()
        giro += 1
    return uscita[: bit // 8]


def _pubblica_x25519(x_b64url: str) -> X25519PublicKey:
    try:
        grezza = b64url_decodifica(x_b64url)
        if len(grezza) != 32:
            raise ValueError
        return X25519PublicKey.from_public_bytes(grezza)
    except ValueError as e:
        raise ErroreJwe("Chiave X25519 non valida.") from e


def cifra(dati, destinatario_jwk: dict, *, cty="application/json") -> str:
    """JWE compatto per la chiave X25519 del destinatario (`destinatario_jwk`, use=enc)."""
    if destinatario_jwk.get("crv") != "X25519" or destinatario_jwk.get("use", "enc") != "enc":
        raise ErroreJwe("Serve la chiave di cifratura X25519 del destinatario.")
    contenuto = dati if isinstance(dati, bytes) else json.dumps(dati, ensure_ascii=False).encode()
    effimera = X25519PrivateKey.generate()
    z = effimera.exchange(_pubblica_x25519(destinatario_jwk["x"]))
    kek = concat_kdf(z, ALG, 256)
    cek = AESGCM.generate_key(256)
    epk = effimera.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    intestazione = {
        "alg": ALG,
        "enc": ENC,
        "cty": cty,
        "kid": destinatario_jwk.get("kid", ""),
        "epk": {"kty": "OKP", "crv": "X25519", "x": b64url(epk)},
    }
    protetta = b64url(json.dumps(intestazione, separators=(",", ":")).encode())
    iv = os.urandom(12)
    cifrato = AESGCM(cek).encrypt(iv, contenuto, protetta.encode("ascii"))
    testo, tag = cifrato[:-16], cifrato[-16:]
    return ".".join(
        [protetta, b64url(aes_key_wrap(kek, cek)), b64url(iv), b64url(testo), b64url(tag)]
    )


def intestazione(jwe: str) -> dict:
    parti = jwe.strip().split(".") if isinstance(jwe, str) else []
    if len(parti) != 5:
        raise ErroreJwe("JWE compatto non valido (servono 5 parti).")
    try:
        return json.loads(b64url_decodifica(parti[0]))
    except ValueError as e:
        raise ErroreJwe("Intestazione del JWE non valida.") from e


def decifra(jwe: str, chiave_per_kid) -> bytes:
    """Contenuto in chiaro. `chiave_per_kid(kid)` restituisce la X25519PrivateKey o None."""
    if len(jwe) > DIMENSIONE_MASSIMA:
        raise ErroreJwe("JWE troppo grande.")
    testa = intestazione(jwe)
    protetta, chiave_avvolta, iv, testo, tag = jwe.strip().split(".")
    if testa.get("alg") != ALG or testa.get("enc") != ENC:
        raise ErroreJwe(f"Algoritmi ammessi solo {ALG} / {ENC}.")
    if set(testa) - {"alg", "enc", "cty", "kid", "epk", "apu", "apv", "typ"} or testa.get("zip"):
        raise ErroreJwe("Parametri dell'intestazione non ammessi.")
    epk = testa.get("epk") or {}
    if epk.get("kty") != "OKP" or epk.get("crv") != "X25519":
        raise ErroreJwe("Chiave effimera non valida.")
    privata = chiave_per_kid(testa.get("kid"))
    if privata is None:
        raise ErroreJwe("Chiave di cifratura sconosciuta (kid).")
    try:
        apu = b64url_decodifica(testa.get("apu", ""))
        apv = b64url_decodifica(testa.get("apv", ""))
        z = privata.exchange(_pubblica_x25519(epk.get("x", "")))
        if z == b"\x00" * 32:
            raise ErroreJwe("Chiave effimera non valida.")
        cek = aes_key_unwrap(concat_kdf(z, ALG, 256, apu, apv), b64url_decodifica(chiave_avvolta))
        return AESGCM(cek).decrypt(
            b64url_decodifica(iv),
            b64url_decodifica(testo) + b64url_decodifica(tag),
            protetta.encode("ascii"),
        )
    except (InvalidUnwrap, InvalidTag, ValueError) as e:
        if isinstance(e, ErroreJwe):
            raise
        raise ErroreJwe("Decifratura non riuscita.") from e


def decifra_json(jwe: str, chiave_per_kid):
    try:
        return json.loads(decifra(jwe, chiave_per_kid))
    except UnicodeDecodeError as e:
        raise ErroreJwe("Contenuto cifrato non JSON.") from e
    except json.JSONDecodeError as e:
        raise ErroreJwe("Contenuto cifrato non JSON.") from e
