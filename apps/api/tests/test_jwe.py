# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test della cifratura JWE con i vettori ufficiali: Concat KDF (RFC 7518 App. C),
# *              accordo X25519 (RFC 8037 A.6), AES Key Wrap (RFC 3394 §4.6); andata e ritorno,
# *              alterazioni e parametri non ammessi.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import json

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.keywrap import aes_key_wrap

from apps.api import jwe
from apps.api.firma import b64url, b64url_decodifica


def test_concat_kdf_rfc7518_appendice_c():
    z = bytes([158, 86, 217, 29, 129, 113, 53, 211, 114, 131, 66, 131, 191, 132, 38, 156, 251,
               49, 110, 163, 218, 128, 106, 72, 246, 218, 167, 121, 140, 254, 144, 196])  # fmt: skip
    chiave = jwe.concat_kdf(z, "A128GCM", 128, b"Alice", b"Bob")
    assert list(chiave) == [86, 170, 141, 234, 248, 35, 109, 32, 92, 34, 40, 205, 113, 167, 16, 26]
    assert b64url(chiave) == "VqqN6vgjbSBcIijNcacQGg"


def test_x25519_rfc8037_a6():
    effimera = X25519PrivateKey.from_private_bytes(bytes.fromhex(
        "77076d0a7318a57d3c16c17251b26645df4c2f87ebc0992ab177fba51db92c2a"))  # fmt: skip
    destinatario = X25519PublicKey.from_public_bytes(b64url_decodifica(
        "3p7bfXt9wbTTW2HC7OQ1Nz-DQ8hbeGdNrfx-FG-IK08"))  # fmt: skip
    pubblica = effimera.public_key().public_bytes(serialization.Encoding.Raw,
                                                  serialization.PublicFormat.Raw)  # fmt: skip
    assert b64url(pubblica) == "hSDwCYkwp1R0i33ctD73Wg2_Og0mOBr066SpjqqbTmo"
    assert effimera.exchange(destinatario).hex() == (
        "4a5d9d5ba4ce2de1728e3bf480350f25e07e21c947d19e3376f09b3c1e161742"
    )


def test_aes_key_wrap_rfc3394():
    kek = bytes.fromhex("000102030405060708090A0B0C0D0E0F101112131415161718191A1B1C1D1E1F")
    dati = bytes.fromhex("00112233445566778899AABBCCDDEEFF000102030405060708090A0B0C0D0E0F")
    assert aes_key_wrap(kek, dati).hex().upper() == (
        "28C9F404C4B810F4CBCCB35CFB87F8263F5786E2D80ED326CBC7F0E71A99F43BFB988B9B7A02DD21"
    )


def _coppia():
    privata = X25519PrivateKey.generate()
    x = b64url(privata.public_key().public_bytes(serialization.Encoding.Raw,
                                                 serialization.PublicFormat.Raw))  # fmt: skip
    return privata, {"kty": "OKP", "crv": "X25519", "x": x, "kid": "k1", "use": "enc"}


def test_andata_e_ritorno():
    privata, jwk = _coppia()
    testo = jwe.cifra({"cognome": "Rossi", "note": "è così"}, jwk)
    assert testo.count(".") == 4
    testa = jwe.intestazione(testo)
    assert (testa["alg"], testa["enc"], testa["kid"]) == ("ECDH-ES+A256KW", "A256GCM", "k1")
    assert jwe.decifra_json(testo, lambda kid: privata if kid == "k1" else None) == {
        "cognome": "Rossi", "note": "è così"}  # fmt: skip
    # due cifrature dello stesso contenuto sono diverse (chiave effimera e IV nuovi)
    assert jwe.cifra({"a": 1}, jwk) != jwe.cifra({"a": 1}, jwk)


def test_alterazioni_e_chiavi_sbagliate():
    privata, jwk = _coppia()
    testo = jwe.cifra({"a": 1}, jwk)
    protetta, chiave, iv, cifrato, tag = testo.split(".")
    altra, _ = _coppia()
    chiavi = lambda kid: privata  # noqa: E731
    falso_tag = b64url(bytes(16))
    for alterato in (
        ".".join([protetta, chiave, iv, cifrato, falso_tag]),
        ".".join([protetta, chiave, iv, b64url(b"x" + b64url_decodifica(cifrato)[1:]), tag]),
    ):
        with pytest.raises(jwe.ErroreJwe, match="Decifratura"):
            jwe.decifra(alterato, chiavi)
    with pytest.raises(jwe.ErroreJwe):
        jwe.decifra(testo, lambda kid: altra)
    with pytest.raises(jwe.ErroreJwe, match="sconosciuta"):
        jwe.decifra(testo, lambda kid: None)
    testa = jwe.intestazione(testo)
    for modifica in ({"alg": "RSA-OAEP"}, {"enc": "A128CBC-HS256"}, {"zip": "DEF"}):
        nuova = b64url(json.dumps(testa | modifica).encode())
        with pytest.raises(jwe.ErroreJwe):
            jwe.decifra(".".join([nuova, chiave, iv, cifrato, tag]), chiavi)
    # intestazione cambiata = dati autenticati diversi: rifiutata anche con algoritmi validi
    nuova = b64url(json.dumps(testa | {"cty": "text/plain"}).encode())
    with pytest.raises(jwe.ErroreJwe, match="Decifratura"):
        jwe.decifra(".".join([nuova, chiave, iv, cifrato, tag]), chiavi)
    with pytest.raises(jwe.ErroreJwe, match="5 parti"):
        jwe.decifra("a.b.c", chiavi)
